# Deployment guide

## 1. Local (Docker Desktop)
```
cp .env.example .env        # set POSTGRES_PASSWORD, JWT_SECRET, SEED_ADMIN_*
docker compose up --build
docker compose exec backend python -m app.seed_demo   # sample products, images, orders, reviews
```
Shop: http://localhost:8080 · Admin: http://localhost:8080/admin/login
Reset everything: `docker compose down -v`.

## 2. Production checklist
**Server**: any Linux VPS (2 GB RAM is enough) with Docker + Compose.

**.env must change**
| Variable | Value |
|---|---|
| `POSTGRES_PASSWORD` | long random (letters/digits avoid quoting issues) |
| `JWT_SECRET` | `openssl rand -hex 48` |
| `SEED_ADMIN_PASSWORD` | strong; change it again in the admin after first login |
| `PUBLIC_BASE_URL`, `CORS_ORIGINS` | `https://your-domain` |
| `DEV_LOG_EMAIL_LINKS` | `false` |
| `SMTP_*` | real mail account so password-reset / order emails send |
| `STORAGE_BACKEND` + `S3_*` | optional; use S3-compatible storage so images survive server rebuilds |

**HTTPS**: put a TLS terminator in front of the `frontend` container (port 8080). Easiest: Caddy on the host:
```
your-domain.com {
    reverse_proxy localhost:8080
}
```
Caddy obtains and renews certificates automatically. Keep `TRUST_PROXY_HEADERS=true` (already set in compose) so rate limiting sees real client IPs; the nginx in the stack overwrites `X-Forwarded-For`.

**Firewall**: expose only 80/443. Do not publish Postgres (it is not published by default).

## 3. Backups
Database (daily cron):
```
docker compose exec -T db pg_dump -U $POSTGRES_USER $POSTGRES_DB | gzip > backup-$(date +%F).sql.gz
```
Restore: `gunzip -c backup.sql.gz | docker compose exec -T db psql -U $POSTGRES_USER $POSTGRES_DB`.
Images (local storage): back up the `media` volume, or use S3 storage. Copy backups off the server.

## 4. Updating
```
git pull    # or copy new files
docker compose up -d --build
```
Migrations run automatically on backend start. Take a DB backup first.

## 5. Monitoring
- `GET /api/v1/health` (used by Docker healthchecks)
- `docker compose logs -f backend worker`
- Failed email/WhatsApp sends are retried with backoff; see Admin → Notifications.

## 6. Not included yet
Online payment gateway (deferred). Cash on delivery / pay on pickup are active; bank transfer can be enabled in Admin → Payment methods.
