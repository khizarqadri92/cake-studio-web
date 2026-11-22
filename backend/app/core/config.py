from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Either set DATABASE_URL, or leave it empty and set the POSTGRES_* parts (passwords with @ / : etc. are encoded for you).
    database_url: str = ""
    postgres_user: str = "cakestudio"
    postgres_password: str = ""
    postgres_db: str = "cakestudio"
    postgres_host: str = "db"
    postgres_port: int = 5432
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    public_base_url: str = "http://localhost:5173"
    media_dir: str = "/srv/media"
    max_upload_mb: int = 10
    storage_backend: str = "local"  # "local" (media volume) or "s3" (any S3-compatible service)
    s3_endpoint: str = ""  # e.g. https://s3.eu-west-1.amazonaws.com or https://<account>.r2.cloudflarestorage.com
    s3_bucket: str = ""
    s3_region: str = "us-east-1"  # R2 uses "auto"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_public_base_url: str = ""  # public/CDN URL that serves the bucket, e.g. https://cdn.example.com
    dev_log_email_links: bool = False  # DEV ONLY: log verification/reset links when e-mail is not configured
    trust_proxy_headers: bool = False  # set true only behind a proxy that overwrites X-Forwarded-For
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    cors_origins: str = "http://localhost:5173"
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = ""

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        from sqlalchemy.engine import URL

        return URL.create("postgresql+psycopg2", username=self.postgres_user, password=self.postgres_password,
                          host=self.postgres_host, port=self.postgres_port, database=self.postgres_db).render_as_string(hide_password=False)

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
