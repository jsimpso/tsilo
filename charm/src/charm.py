#!/usr/bin/env python3
"""Tsilo charm - lifecycle hooks, PostgreSQL relation, S3 relation."""

import logging
import secrets

import ops

logger = logging.getLogger(__name__)


class TsiloCharm(ops.CharmBase):
    """Juju charm for the Tsilo private Terraform module registry."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade)
        self.framework.observe(self.on.tsilo_pebble_ready, self._on_pebble_ready)

        # Database relation events
        self.framework.observe(self.on.postgresql_relation_joined, self._on_db_relation_joined)
        self.framework.observe(self.on.postgresql_relation_changed, self._on_db_relation_changed)
        self.framework.observe(self.on.postgresql_relation_broken, self._on_db_relation_broken)

        # S3 relation events
        self.framework.observe(self.on.s3_credentials_relation_joined, self._on_s3_relation_joined)
        self.framework.observe(self.on.s3_credentials_relation_changed, self._on_s3_relation_changed)
        self.framework.observe(self.on.s3_credentials_relation_broken, self._on_s3_relation_broken)

    # ── Lifecycle hooks ──────────────────────────────────────────────────

    def _on_install(self, event: ops.InstallEvent) -> None:
        """Handle install event - generate secret key if not set."""
        logger.info("Installing Tsilo charm")
        if not self._stored_secret_key:
            self._peer_data["secret_key"] = secrets.token_hex(32)
            self._peer_data["csrf_secret_key"] = secrets.token_hex(32)
        self.unit.status = ops.WaitingStatus("Waiting for relations")

    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        """Handle config changes - update environment variables and restart."""
        logger.info("Configuration changed, updating pebble layer")
        self._update_pebble_layer()

    def _on_upgrade(self, event: ops.UpgradeCharmEvent) -> None:
        """Handle charm upgrade - reapply pebble layer."""
        logger.info("Upgrading Tsilo charm")
        self._update_pebble_layer()

    def _on_pebble_ready(self, event: ops.PebbleReadyEvent) -> None:
        """Handle pebble ready - configure the workload."""
        logger.info("Pebble ready, configuring workload")
        self._update_pebble_layer()

    # ── Database relation ────────────────────────────────────────────────

    def _on_db_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Handle PostgreSQL relation joined."""
        logger.info("PostgreSQL relation joined")
        self.unit.status = ops.WaitingStatus("Waiting for database credentials")

    def _on_db_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Handle PostgreSQL relation data changed - extract connection string."""
        db_data = event.relation.data.get(event.app, {})
        endpoints = db_data.get("endpoints", "")
        username = db_data.get("username", "")
        password = db_data.get("password", "")
        database = db_data.get("database", "tsilo")

        if not all([endpoints, username, password]):
            logger.info("Waiting for complete database credentials")
            return

        host_port = endpoints.split(",")[0]
        host = host_port.split(":")[0]
        port = host_port.split(":")[1] if ":" in host_port else "5432"

        db_url = f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"
        self._peer_data["database_url"] = db_url

        logger.info("Database connection configured", extra={"host": host, "port": port})
        self._update_pebble_layer()

    def _on_db_relation_broken(self, event: ops.RelationBrokenEvent) -> None:
        """Handle PostgreSQL relation removed."""
        logger.warning("PostgreSQL relation broken")
        self._peer_data.pop("database_url", None)
        self.unit.status = ops.BlockedStatus("Database relation required")
        self._update_pebble_layer()

    # ── S3 relation ──────────────────────────────────────────────────────

    def _on_s3_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Handle S3 relation joined."""
        logger.info("S3 relation joined")

    def _on_s3_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Handle S3 relation data changed - extract credentials."""
        s3_data = event.relation.data.get(event.app, {})
        access_key = s3_data.get("access-key", "")
        secret_key = s3_data.get("secret-key", "")
        bucket = s3_data.get("bucket", "")
        endpoint = s3_data.get("endpoint", "")
        region = s3_data.get("region", "us-east-1")

        if not all([access_key, secret_key, bucket]):
            logger.info("Waiting for complete S3 credentials")
            return

        self._peer_data["s3_access_key_id"] = access_key
        self._peer_data["s3_secret_access_key"] = secret_key
        self._peer_data["s3_bucket"] = bucket
        self._peer_data["s3_region"] = region
        if endpoint:
            self._peer_data["s3_endpoint_url"] = endpoint

        logger.info("S3 storage configured", extra={"bucket": bucket})
        self._update_pebble_layer()

    def _on_s3_relation_broken(self, event: ops.RelationBrokenEvent) -> None:
        """Handle S3 relation removed."""
        logger.warning("S3 relation broken")
        for key in ("s3_access_key_id", "s3_secret_access_key", "s3_bucket", "s3_endpoint_url", "s3_region"):
            self._peer_data.pop(key, None)
        self.unit.status = ops.BlockedStatus("S3 relation required")
        self._update_pebble_layer()

    # ── Pebble layer management ──────────────────────────────────────────

    def _build_environment(self) -> dict[str, str]:
        """Build environment variables from config and relation data."""
        config = self.config
        env = {
            "APP_ENV": "production",
            "LOG_LEVEL": str(config.get("log-level", "INFO")),
            "PYTHONPATH": "/app/src",
        }

        # Config-driven settings
        if config.get("app-base-url"):
            env["APP_BASE_URL"] = str(config["app-base-url"])
        if config.get("oidc-issuer"):
            env["OIDC_ISSUER"] = str(config["oidc-issuer"])
        if config.get("oidc-client-id"):
            env["OIDC_CLIENT_ID"] = str(config["oidc-client-id"])
        if config.get("oidc-client-secret"):
            env["OIDC_CLIENT_SECRET"] = str(config["oidc-client-secret"])
        if config.get("app-base-url"):
            env["OIDC_REDIRECT_URI"] = f"{config['app-base-url']}/auth/callback"

        # Relation-driven settings
        if self._peer_data.get("database_url"):
            env["DATABASE_URL"] = self._peer_data["database_url"]
        if self._peer_data.get("s3_access_key_id"):
            env["S3_ACCESS_KEY_ID"] = self._peer_data["s3_access_key_id"]
        if self._peer_data.get("s3_secret_access_key"):
            env["S3_SECRET_ACCESS_KEY"] = self._peer_data["s3_secret_access_key"]
        if self._peer_data.get("s3_bucket"):
            env["S3_BUCKET"] = self._peer_data["s3_bucket"]
        if self._peer_data.get("s3_endpoint_url"):
            env["S3_ENDPOINT_URL"] = self._peer_data["s3_endpoint_url"]
        if self._peer_data.get("s3_region"):
            env["S3_REGION"] = self._peer_data["s3_region"]

        # Security keys
        if self._stored_secret_key:
            env["SECRET_KEY"] = self._stored_secret_key
        if self._peer_data.get("csrf_secret_key"):
            env["CSRF_SECRET_KEY"] = self._peer_data["csrf_secret_key"]

        return env

    def _update_pebble_layer(self) -> None:
        """Update the pebble layer with current configuration."""
        container = self.unit.get_container("tsilo")
        if not container.can_connect():
            logger.info("Pebble not ready yet")
            return

        env = self._build_environment()

        # Check required relations
        if "DATABASE_URL" not in env:
            self.unit.status = ops.WaitingStatus("Waiting for PostgreSQL relation")
            return
        if "S3_BUCKET" not in env:
            self.unit.status = ops.WaitingStatus("Waiting for S3 relation")
            return

        layer = {
            "summary": "Tsilo service layer",
            "services": {
                "tsilo": {
                    "override": "replace",
                    "command": "/bin/python3 -m uvicorn tsilo.main:app --host 0.0.0.0 --port 8000",
                    "startup": "enabled",
                    "environment": env,
                }
            },
        }

        container.add_layer("tsilo", layer, combine=True)
        container.replan()

        self.unit.status = ops.ActiveStatus("Running")
        logger.info("Pebble layer updated, service running")

    # ── Helpers ───────────────────────────────────────────────────────────

    @property
    def _peer_data(self) -> dict:
        """Access peer relation data for storing shared state."""
        relation = self.model.get_relation("peer")
        if relation is None:
            return {}
        return relation.data[self.app]

    @property
    def _stored_secret_key(self) -> str | None:
        """Get stored secret key from peer data."""
        return self._peer_data.get("secret_key")


if __name__ == "__main__":
    ops.main(TsiloCharm)
