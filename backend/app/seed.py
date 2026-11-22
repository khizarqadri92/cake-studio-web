"""Idempotent seed: permissions, the six roles, and an initial Super Admin."""
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import session_factory
from app.models import DeliverySlot, PaymentMethod, HomepageSection, NavigationMenu, Page, Permission, Role, User

log = logging.getLogger("seed")

RESOURCES = {
    "dashboard": ["read"],
    "settings": ["read", "write"],
    "cms": ["read", "write"],
    "products": ["read", "write"],
    "categories": ["read", "write"],
    "orders": ["read", "write"],
    "payments": ["read", "write"],
    "customers": ["read", "write"],
    "inventory": ["read", "write"],
    "coupons": ["read", "write"],
    "reports": ["read"],
    "users": ["read", "write"],
    "roles": ["read", "write"],
    "audit": ["read"],
}
ALL = [f"{r}.{a}" for r, acts in RESOURCES.items() for a in acts]

ROLE_DEFAULTS: dict[str, list[str]] = {
    "Super Admin": [],  # bypasses checks in code
    "Admin": list(ALL),
    "Order Manager": ["dashboard.read", "orders.read", "orders.write", "payments.read", "payments.write",
                      "customers.read", "reports.read"],
    "Production Staff": ["orders.read", "products.read", "inventory.read"],
    "Inventory Manager": ["inventory.read", "inventory.write", "products.read", "reports.read"],
    "Customer Support": ["orders.read", "customers.read", "customers.write"],
}


HOME_SECTIONS = [
    ("hero", "Freshly Baked. Beautifully Crafted.", {"description": "Celebration cakes, pastries and more, made to order.", "cta_label": "Shop Now", "cta_url": "/shop", "image_url": None}),
    ("categories", "Shop by Category", {}),
    ("featured_products", "Featured Cakes", {"limit": 8}),
    ("best_sellers", "Best Sellers", {"limit": 8}),
    ("new_arrivals", "New Arrivals", {"limit": 8}),
    ("promotions", "Special Offers", {}),
    ("custom_cake", "Dream up a custom cake", {"description": "Tell us your idea and we will quote it.", "cta_label": "Request a Quote", "cta_url": "/custom-cake"}),
    ("about", "About Cake Studio", {"description": ""}),
    ("testimonials", "What Our Customers Say", {}),
    ("social_gallery", "Follow Us", {"images": []}),
    ("newsletter", "Stay in the loop", {"description": "Get offers and new flavours in your inbox."}),
    ("contact", "Visit or Contact Us", {}),
]
STATIC_PAGES = [("about", "About Us"), ("privacy-policy", "Privacy Policy"), ("terms-and-conditions", "Terms and Conditions"),
                ("return-and-refund-policy", "Return and Refund Policy"), ("delivery-policy", "Delivery Policy")]
NAV = [("header", "Home", "/"), ("header", "Shop", "/shop"), ("header", "Custom Cakes", "/custom-cake"),
       ("header", "About", "/p/about"), ("header", "Contact", "/contact"),
       ("footer", "Track Order", "/track"), ("footer", "Privacy Policy", "/p/privacy-policy"), ("footer", "Terms", "/p/terms-and-conditions"),
       ("footer", "Delivery Policy", "/p/delivery-policy"), ("footer", "Refunds", "/p/return-and-refund-policy")]


def seed_cms(db) -> None:
    """Only fills empty tables, so admin edits are never overwritten."""
    if db.scalar(select(HomepageSection.id).limit(1)) is None:
        for i, (k, t, c) in enumerate(HOME_SECTIONS):
            db.add(HomepageSection(key=k, title=t, content=c, sort_order=i))
    if db.scalar(select(NavigationMenu.id).limit(1)) is None:
        for i, (loc, label, url) in enumerate(NAV):
            db.add(NavigationMenu(location=loc, label=label, url=url, sort_order=i))
    if db.scalar(select(Page.id).limit(1)) is None:
        for slug, title in STATIC_PAGES:
            db.add(Page(slug=slug, title=title, body_html=f"<p>Edit this {title.lower()} page in the admin panel.</p>"))


def seed_commerce(db) -> None:
    from datetime import time

    if db.scalar(select(PaymentMethod.id).limit(1)) is None:
        for i, (code, name, applies, active) in enumerate([
                ("cod", "Cash on delivery", "delivery", True), ("pay_on_pickup", "Pay on pickup", "pickup", True),
                ("bank_transfer", "Bank transfer", "both", False), ("online", "Online payment", "both", False)]):
            db.add(PaymentMethod(code=code, name=name, applies_to=applies, is_active=active, sort_order=i))
    if db.scalar(select(DeliverySlot.id).limit(1)) is None:
        for a, b in [(10, 13), (13, 16), (16, 19)]:
            db.add(DeliverySlot(start_time=time(a), end_time=time(b), max_orders=5))


def run() -> None:
    s = get_settings()
    db = session_factory()
    try:
        existing = {p.code: p for p in db.scalars(select(Permission))}
        for code in ALL:
            if code not in existing:
                existing[code] = Permission(code=code, description=code.replace(".", " "))
                db.add(existing[code])
        db.flush()

        for name, codes in ROLE_DEFAULTS.items():
            role = db.scalar(select(Role).where(Role.name == name))
            if role is None:  # never overwrite permissions an admin has since edited
                role = Role(name=name, is_system=True, permissions=[existing[c] for c in codes])
                db.add(role)
        db.flush()

        seed_cms(db)
        seed_commerce(db)

        if db.scalar(select(User.id).limit(1)) is None:
            if not s.seed_admin_password:
                raise SystemExit("SEED_ADMIN_PASSWORD must be set to create the first admin")
            admin = User(
                email=s.seed_admin_email.lower(),
                full_name="Super Admin",
                password_hash=hash_password(s.seed_admin_password),
                roles=[db.scalar(select(Role).where(Role.name == "Super Admin"))],
            )
            db.add(admin)
            log.info("Created initial super admin %s", admin.email)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
