"""S3 storage service for module package upload and download."""

import boto3
from botocore.config import Config as BotoConfig

from tsilo.config import get_settings


class StorageService:
    """Manages module package storage in S3-compatible object storage."""

    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.s3_bucket
        self._client = boto3.client(
            "s3",
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            config=BotoConfig(signature_version="s3v4"),
        )

    def _build_key(self, namespace: str, name: str, provider: str, version: str) -> str:
        """Build S3 object key for a module package."""
        return f"{namespace}/{name}/{provider}/{version}/module.tar.gz"

    def upload_module(
        self,
        namespace: str,
        name: str,
        provider: str,
        version: str,
        file_data: bytes,
        checksum_sha256: str,
    ) -> str:
        """Upload a module package to S3.

        Returns the S3 object key.
        """
        key = self._build_key(namespace, name, provider, version)
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=file_data,
            ContentType="application/gzip",
            ChecksumSHA256=checksum_sha256,
            ServerSideEncryption="AES256",
        )
        return f"s3://{self._bucket}/{key}"

    def generate_download_url(
        self,
        namespace: str,
        name: str,
        provider: str,
        version: str,
        expires_in: int = 300,
    ) -> str:
        """Generate a pre-signed download URL for a module package.

        Args:
            expires_in: URL expiration time in seconds (default 5 minutes).

        Returns:
            Pre-signed URL for downloading the module package.
        """
        key = self._build_key(namespace, name, provider, version)
        url: str = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url

    def check_connectivity(self) -> bool:
        """Check if S3 storage is accessible."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return True
        except Exception:
            return False
