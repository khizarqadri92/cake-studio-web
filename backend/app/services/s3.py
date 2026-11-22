"""S3-compatible object storage (AWS S3, Cloudflare R2, MinIO, DigitalOcean Spaces, ...) with no SDK
dependency: AWS Signature V4 is implemented with the standard library. `sign_v4` is pure and unit-tested."""
import hashlib
import hmac
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import quote

from app.services.storage import MAX_BYTES_DEFAULT, UploadError, sniff_image

CONTENT_TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def sign_v4(*, method: str, path: str, query: str, headers: dict[str, str], payload_hash: str, region: str,
            service: str, access_key: str, secret_key: str, amz_date: str) -> str:
    """Return the value of the Authorization header. `headers` must already contain every header to sign
    (lower-case names), including host and x-amz-date."""
    date = amz_date[:8]
    names = sorted(headers)
    canonical_headers = "".join(f"{n}:{' '.join(headers[n].split())}\n" for n in names)
    signed = ";".join(names)
    canonical = "\n".join([method, path, query, canonical_headers, signed, payload_hash])
    scope = f"{date}/{region}/{service}/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _hmac(_hmac(_hmac(_hmac(("AWS4" + secret_key).encode(), date), region), service), "aws4_request")
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    return f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={signed}, Signature={sig}"


class S3Storage:
    def __init__(self, *, endpoint: str, bucket: str, region: str, access_key: str, secret_key: str, public_base_url: str,
                 max_bytes: int = MAX_BYTES_DEFAULT, prefix: str = "uploads"):
        self.endpoint = endpoint.rstrip("/")
        self.bucket, self.region, self.access_key, self.secret_key = bucket, region, access_key, secret_key
        self.public_base = public_base_url.rstrip("/")
        self.max_bytes, self.prefix = max_bytes, prefix.strip("/")

    def save(self, data: bytes) -> str:
        if not data:
            raise UploadError("Empty file")
        if len(data) > self.max_bytes:
            raise UploadError(f"File too large (max {self.max_bytes // (1024 * 1024)} MB)")
        ext = sniff_image(data)  # content decides the type, never the client's filename/Content-Type
        key = f"{self.prefix}/{secrets.token_hex(16)}.{ext}"
        # path-style addressing (endpoint/bucket/key) works on every S3-compatible service
        host = self.endpoint.split("://", 1)[1]
        path = "/" + quote(f"{self.bucket}/{key}", safe="/")
        payload_hash = hashlib.sha256(data).hexdigest()
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date,
                   "content-type": CONTENT_TYPES[ext], "cache-control": "public, max-age=31536000, immutable"}
        auth = sign_v4(method="PUT", path=path, query="", headers=headers, payload_hash=payload_hash, region=self.region,
                       service="s3", access_key=self.access_key, secret_key=self.secret_key, amz_date=amz_date)
        req = urllib.request.Request(self.endpoint + path, data=data, method="PUT", headers={**{k: v for k, v in headers.items() if k != "host"}, "Authorization": auth})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status not in (200, 201):
                    raise UploadError("Image storage rejected the upload")
        except urllib.error.URLError as e:
            raise UploadError("Image storage is unavailable, please try again") from e
        return f"{self.public_base}/{key}"
