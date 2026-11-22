# Cake Studio

Bakery storefront + admin CMS (React/Vite/Tailwind, FastAPI, PostgreSQL, Docker).

## Run locally
```
cp .env.example .env      # set secrets; leave DATABASE_URL empty
docker compose up --build
docker compose exec backend python -m app.seed_demo   # optional sample catalogue
```
- Shop: http://localhost:8080
- Admin: http://localhost:8080/admin/login (SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD from .env)
- API docs: http://localhost:8000/docs

Docs: `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/DEPLOYMENT.md`.
Tests: `cd backend && pytest` (integration tests need `TEST_DATABASE_URL`).
