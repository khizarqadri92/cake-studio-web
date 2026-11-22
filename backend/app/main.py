import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import account, auth, auth_customer, cart_checkout, catalog_admin, catalog_public, cms_admin, commerce_admin, custom_cakes, customers_admin, inventory_admin, orders_admin, orders_public, public, reports_admin, reviews, roles, users_admin
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("cakestudio")


def create_app() -> FastAPI:
    app = FastAPI(title="Cake Studio API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_list,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return resp

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error on %s", request.url.path)
        return JSONResponse({"error": {"code": "internal_error", "message": "Internal server error"}}, status_code=500)

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(roles.router, prefix="/api/v1")
    app.include_router(users_admin.router, prefix="/api/v1")
    app.include_router(reviews.public, prefix="/api/v1")
    app.include_router(reviews.admin, prefix="/api/v1")
    app.include_router(auth_customer.router, prefix="/api/v1")
    app.include_router(account.router, prefix="/api/v1")
    app.include_router(cms_admin.router, prefix="/api/v1")
    app.include_router(public.router, prefix="/api/v1")
    app.include_router(catalog_admin.router, prefix="/api/v1")
    app.include_router(catalog_public.router, prefix="/api/v1")
    app.include_router(cart_checkout.router, prefix="/api/v1")
    app.include_router(orders_admin.router, prefix="/api/v1")
    app.include_router(orders_public.router, prefix="/api/v1")
    app.include_router(inventory_admin.router, prefix="/api/v1")
    app.include_router(reports_admin.router, prefix="/api/v1")
    app.include_router(customers_admin.router, prefix="/api/v1")
    app.include_router(custom_cakes.public, prefix="/api/v1")
    app.include_router(custom_cakes.admin, prefix="/api/v1")
    app.include_router(commerce_admin.router, prefix="/api/v1")

    import os

    from fastapi.staticfiles import StaticFiles

    os.makedirs(get_settings().media_dir, exist_ok=True)
    app.mount("/media", StaticFiles(directory=get_settings().media_dir), name="media")

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
