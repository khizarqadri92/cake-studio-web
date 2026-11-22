"""Image storage. Validates by magic bytes (never trusts client filename/Content-Type) and stores
under a random name. `LocalStorage` is the default; an S3/Cloudinary provider implements the same
`save(data) -> url` interface."""
import secrets
from pathlib import Path
from typing import Protocol

MAX_BYTES_DEFAULT = 5 * 1024 * 1024


class UploadError(ValueError):
    pass


def sniff_image(data: bytes) -> str:
    """Return a safe extension for png/jpg/webp/gif, else raise."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    raise UploadError("Unsupported image type (allowed: PNG, JPEG, WebP, GIF)")


class Storage(Protocol):
    def save(self, data: bytes) -> str: ...


class LocalStorage:
    def __init__(self, root: str, url_prefix: str = "/media", max_bytes: int = MAX_BYTES_DEFAULT):
        self.root = Path(root)
        self.url_prefix = url_prefix.rstrip("/")
        self.max_bytes = max_bytes

    def save(self, data: bytes) -> str:
        if not data:
            raise UploadError("Empty file")
        if len(data) > self.max_bytes:
            raise UploadError(f"File too large (max {self.max_bytes // (1024 * 1024)} MB)")
        ext = sniff_image(data)
        self.root.mkdir(parents=True, exist_ok=True)
        name = f"{secrets.token_hex(16)}.{ext}"
        (self.root / name).write_bytes(data)
        return f"{self.url_prefix}/{name}"


def get_storage():
    """Storage chosen by STORAGE_BACKEND. Imported lazily to avoid a circular import with s3.py."""
    from app.core.config import get_settings

    c = get_settings()
    max_bytes = c.max_upload_mb * 1024 * 1024
    if c.storage_backend == "s3":
        from app.services.s3 import S3Storage

        if not (c.s3_endpoint.startswith("https://") and c.s3_bucket and c.s3_access_key and c.s3_secret_key and c.s3_public_base_url.startswith("https://")):
            raise RuntimeError("STORAGE_BACKEND=s3 needs an https S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY and https S3_PUBLIC_BASE_URL")
        return S3Storage(endpoint=c.s3_endpoint, bucket=c.s3_bucket, region=c.s3_region, access_key=c.s3_access_key,
                         secret_key=c.s3_secret_key, public_base_url=c.s3_public_base_url, max_bytes=max_bytes)
    return LocalStorage(c.media_dir, "/media", max_bytes)
