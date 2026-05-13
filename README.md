# Tsilo — Private Terraform Module Registry

A private Terraform module registry that implements the [Terraform Module Registry Protocol](https://developer.hashicorp.com/terraform/internals/module-registry-protocol), enabling teams to host, version, and discover internal infrastructure modules.

## Features

- **Terraform CLI Compatible** — Works with `terraform init`, `terraform login`, and version constraints (`~> 1.0`)
- **Web UI** — Browse, search, and view module documentation with inputs/outputs tables, README rendering, and usage examples
- **Namespace-Based Access Control** — Multi-tenant isolation via OIDC groups mapped to namespace permissions (read/write)
- **Module Upload & Versioning** — Upload `.tar.gz` packages with automatic extraction of `variables.tf`, `outputs.tf`, and `README.md`
- **CI/CD Authentication** — API tokens for pipelines; `terraform login` via OAuth 2.0 + PKCE
- **Usage Metrics** — Download tracking per version, deprecation flagging (90+ days inactive), Prometheus `/metrics` endpoint
- **12-Factor Design** — Stateless processes, environment-variable configuration, structured JSON logging, health checks

## Architecture

```text
┌──────────────┐       ┌──────────────────────────────────┐
│ Terraform CLI│──────►│          Tsilo (FastAPI)          │
└──────────────┘       │                                   │
┌──────────────┐       │  ┌─────────┐  ┌───────────────┐  │
│  Web Browser │──────►│  │ API     │  │ Static Files  │  │
└──────────────┘       │  │ Routers │  │ (HTML/CSS/JS) │  │
                       │  └────┬────┘  └───────────────┘  │
                       │       │                           │
                       │  ┌────▼────┐                      │
                       │  │Services │                      │
                       │  └──┬───┬──┘                      │
                       └─────┼───┼─────────────────────────┘
                             │   │
                    ┌────────┘   └────────┐
                    ▼                     ▼
             ┌────────────┐       ┌──────────────┐
             │ PostgreSQL │       │ S3 / MinIO   │
             │ (metadata) │       │ (packages)   │
             └────────────┘       └──────────────┘
```

### Key Components

| Layer | Directory | Purpose |
|-------|-----------|---------|
| API Routers | `src/tsilo/api/` | FastAPI endpoints (registry protocol, web UI API, auth, metrics) |
| Services | `src/tsilo/services/` | Business logic (modules, versions, permissions, storage, auth, OAuth) |
| Models | `src/tsilo/models/` | SQLAlchemy ORM (8 tables: Namespace, Module, ModuleVersion, User, APIToken, etc.) |
| Schemas | `src/tsilo/schemas/` | Pydantic request/response validation |
| Middleware | `src/tsilo/middleware/` | Auth, rate limiting, structured logging |
| Frontend | `src/tsilo/static/` | Vanilla HTML/CSS/JS pages |
| Migrations | `src/alembic/` | Alembic database migrations |

## Quickstart

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- S3-compatible storage (MinIO for local dev)
- An OIDC provider (or mock for development)

### Setup

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/your-org/tsilo.git
cd tsilo
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Configure
cp .env.example .env   # Edit with your database/S3/OIDC settings

# Run migrations
alembic upgrade head

# Start dev server
uvicorn tsilo.main:app --reload --host 0.0.0.0 --port 8000
```

### Using with Terraform

```hcl
# In your Terraform configuration
module "vpc" {
  source  = "tsilo.example.com/networking/vpc/aws"
  version = "~> 1.0"
}
```

```bash
# Authenticate Terraform CLI
terraform login tsilo.example.com

# Initialize and download modules
terraform init
```

## Configuration

All configuration is via environment variables (12-factor). Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://tsilo:tsilo@localhost:5432/tsilo` |
| `S3_BUCKET` | Module storage bucket | `tsilo-modules` |
| `S3_ENDPOINT_URL` | S3 endpoint (for MinIO) | *(none — uses AWS)* |
| `S3_ACCESS_KEY_ID` | S3 access key | `minioadmin` |
| `S3_SECRET_ACCESS_KEY` | S3 secret key | `minioadmin` |
| `OIDC_ISSUER` | OIDC provider URL | `https://your-oidc-provider.com` |
| `OIDC_CLIENT_ID` | OIDC client ID | `tsilo-dev` |
| `OIDC_CLIENT_SECRET` | OIDC client secret | *(empty)* |
| `SECRET_KEY` | Session signing key | `change-me-in-production` |
| `ADMIN_GROUP` | OIDC group for admin access | `tsilo-admins` |
| `APP_ENV` | Environment (`development`/`production`) | `development` |
| `LOG_LEVEL` | Logging level | `INFO` |

## API Endpoints

### Terraform Registry Protocol

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/.well-known/terraform.json` | Service discovery |
| `GET` | `/v1/modules/:ns/:name/:system/versions` | List versions |
| `GET` | `/v1/modules/:ns/:name/:system/:version/download` | Download module |
| `POST` | `/v1/modules/:ns/:name/:system/:version` | Upload module |

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/auth/login` | OIDC login redirect |
| `GET` | `/auth/callback` | OIDC callback |
| `POST` | `/auth/logout` | Logout |
| `GET` | `/oauth/authorization` | OAuth authorization (Terraform login) |
| `POST` | `/oauth/token` | OAuth token exchange |

### Web UI API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/modules` | List/search modules |
| `GET` | `/api/modules/:ns/:name/:provider` | Module detail |
| `GET` | `/api/namespaces` | List namespaces |
| `POST` | `/api/namespaces` | Create namespace (admin) |
| `GET/POST/DELETE` | `/api/tokens` | API token management |

### Observability

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/api/metrics/overview` | System metrics (admin) |

## Development

```bash
# Run tests
pytest

# Run linter
ruff check src/ tests/

# Run formatter
black src/ tests/

# Run type checker
mypy src/
```

## Deployment

Tsilo is packaged as an Ubuntu Rock (OCI image) and deployed via Juju charm:

```bash
# Build OCI image
rockcraft pack

# Build charm
charmcraft pack

# Deploy with Juju
juju deploy ./tsilo_amd64.charm --resource oci-image=tsilo:latest
juju relate tsilo postgresql
juju relate tsilo s3-integrator
```

## Project Structure

```text
├── src/
│   ├── tsilo/           # Application source
│   │   ├── api/         # FastAPI routers
│   │   ├── middleware/   # Auth, logging, rate limiting
│   │   ├── models/      # SQLAlchemy models
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # Business logic
│   │   ├── static/      # Frontend (HTML/CSS/JS)
│   │   └── templates/   # Jinja2 templates
│   └── alembic/         # Database migrations
├── tests/
│   ├── contract/        # Terraform protocol contract tests
│   ├── integration/     # Multi-component integration tests
│   └── unit/            # Unit tests
├── charm/               # Juju charm source
├── rockcraft.yaml       # OCI image definition
├── charmcraft.yaml      # Charm packaging
└── pyproject.toml       # Python project config
```

## License

[Apache-2.0](LICENSE)
