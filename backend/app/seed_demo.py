"""Optional, idempotent demo data: catalogue with images, banners, testimonials, homepage content,
coupons, suppliers/inventory/recipes, customers, delivered orders and approved reviews.

Run:  docker compose exec backend python -m app.seed_demo
Everything is ordinary data - edit or delete it from the admin. Images are illustrations shipped in
app/demo_assets and copied into the media folder; replace them with real photos from Admin.
"""
import logging
import shutil
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import session_factory
from app.models import (
    Banner, Coupon, Customer, Flavour, HomepageSection, InventoryItem, InventoryTransaction, OptionChoice,
    OptionGroup, Order, OrderItem, OrderStatusHistory, Page, Payment, Product, ProductAddon, ProductCategory,
    ProductImage, ProductRecipe, ProductVariant, Review, Supplier, Testimonial,
)
from app.models.commerce import DeliverySlot
from app.models.cms import WebsiteSetting
from app.services import shop

log = logging.getLogger("seed_demo")
ASSETS = Path(__file__).parent / "demo_assets"


def media(name: str) -> str:
    """Copy a bundled image into the media dir under a stable name; return its public URL."""
    root = Path(get_settings().media_dir)
    root.mkdir(parents=True, exist_ok=True)
    dst = root / f"demo-{name}"
    if not dst.exists():
        shutil.copyfile(ASSETS / name, dst)
    return f"/media/demo-{name}"


def slugify(s: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in s)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


CATEGORIES = [("Birthday Cakes", "choc-cake.jpg", "Cakes to make every birthday sweeter."),
              ("Wedding Cakes", "wedding.jpg", "Elegant tiered cakes for your big day."),
              ("Cupcakes", "cupcakes.jpg", "Single-serve treats, boxed and ready to share."),
              ("Pastries", "croissant.jpg", "Fresh-baked every morning.")]
FLAVOURS = ["Chocolate", "Vanilla", "Red Velvet", "Strawberry", "Butterscotch"]
ADDONS = [("Candles", "150"), ("Greeting card", "200")]

# name, category, type, base, description, variants, flavour options, images, flags
PRODUCTS = [
    ("Classic Chocolate Cake", "Birthday Cakes", "variable", "0", "Rich, moist chocolate sponge layered with dark chocolate ganache and topped with cherries.",
     [("1 lb", "1800"), ("2 lb", "3400"), ("3 lb", "4900")], True, ["choc-cake.jpg"], dict(is_featured=True, is_bestseller=True, allows_message=True, sales_count=48)),
    ("Red Velvet Cake", "Birthday Cakes", "variable", "0", "Velvety red sponge with silky cream cheese frosting and fresh berries.",
     [("1 lb", "2000"), ("2 lb", "3800")], True, ["red-velvet.jpg"], dict(is_featured=True, is_bestseller=True, allows_message=True, sales_count=36)),
    ("Strawberry Dream Cake", "Birthday Cakes", "variable", "0", "Light vanilla sponge, strawberry cream and a pink berry drip.",
     [("1 lb", "1900"), ("2 lb", "3600")], True, ["strawberry.jpg"], dict(is_featured=True, allows_message=True, sales_count=22)),
    ("Butterscotch Crunch Cake", "Birthday Cakes", "variable", "0", "Caramelised butterscotch sponge with crunchy praline.",
     [("1 lb", "1700"), ("2 lb", "3200")], False, ["butterscotch.jpg"], dict(allows_message=True, sales_count=15)),
    ("Funfetti Celebration Cake", "Birthday Cakes", "variable", "0", "Vanilla funfetti layers with sprinkles and candles - pure party.",
     [("1 lb", "1600"), ("2 lb", "3000")], True, ["birthday.jpg"], dict(is_bestseller=True, allows_message=True, sales_count=30)),
    ("Three-Tier Wedding Cake", "Wedding Cakes", "simple", "25000", "Elegant four-layer cake with sugar flowers, made to order. Serves 60.",
     [], False, ["wedding.jpg"], dict(is_featured=True, prep_time_hours=72, sales_count=6)),
    ("Cupcake Box (6)", "Cupcakes", "simple", "1500", "Six assorted frosted cupcakes with buttercream swirls.",
     [], True, ["cupcakes.jpg"], dict(is_bestseller=True, sales_count=60)),
    ("Almond Croissant", "Pastries", "simple", "350", "Buttery, flaky croissant filled with almond cream.",
     [], False, ["croissant.jpg"], dict(prep_time_hours=4, sales_count=80)),
]

BANNERS = [("Birthday Special", "Flat 10% off on celebration cakes - use code SWEET10", "banner-offer.jpg", "/shop"),
           ("Wedding Season", "Book your wedding cake 2 weeks ahead", "banner-wedding.jpg", "/custom-cake")]
TESTIMONIALS = [("Ayesha K.", "The chocolate cake was the best we've ever had. Delivered right on time!", 5),
                ("Bilal R.", "Ordered a custom cake for my daughter's birthday - it looked exactly like the picture.", 5),
                ("Sana M.", "Fresh, beautiful and not too sweet. Our go-to bakery now.", 5),
                ("Usman T.", "Great wedding cake and very friendly team.", 4)]
SUPPLIERS = [("Golden Mills Flour", "Hamid Ali", "+923001234567"), ("Dairy Fresh Co.", "Farah Noor", "+923011234567")]
# name, kind, unit, stock, low, cost, supplier idx
INVENTORY = [("Flour", "ingredient", "kg", "50", "10", "120", 0), ("Sugar", "ingredient", "kg", "30", "8", "140", 0),
             ("Butter", "ingredient", "kg", "12", "4", "1400", 1), ("Cocoa powder", "ingredient", "kg", "5", "2", "1800", 0),
             ("Eggs", "ingredient", "pcs", "180", "60", "30", 1), ("Cake boxes", "packaging", "pcs", "80", "30", "90", None)]
CUSTOMERS = [("Ayesha Khan", "+923001111111", "ayesha@example.com", "House 12, Street 4, DHA", "Karachi"),
             ("Bilal Raza", "+923002222222", "bilal@example.com", "Flat 5, Gulshan Block 3", "Karachi"),
             ("Sana Malik", "+923003333333", "sana@example.com", "House 7, F-8/2", "Islamabad")]
REVIEWS = [("Classic Chocolate Cake", 5, "Rich and moist. Everyone asked where it was from!"),
           ("Red Velvet Cake", 5, "Perfect frosting, looked stunning."),
           ("Cupcake Box (6)", 4, "Lovely cupcakes, arrived fresh."),
           ("Strawberry Dream Cake", 5, "Light and fruity - highly recommend.")]


def seed_catalogue(db):
    cats = {}
    for i, (n, img, desc) in enumerate(CATEGORIES):
        c = db.scalar(select(ProductCategory).where(ProductCategory.slug == slugify(n)))
        if not c:
            c = ProductCategory(name=n, slug=slugify(n), description=desc, image_url=media(img), sort_order=i)
            db.add(c)
        elif not c.image_url:
            c.image_url = media(img)
        cats[n] = c
    fl = {}
    for i, n in enumerate(FLAVOURS):
        f = db.scalar(select(Flavour).where(Flavour.name == n)) or Flavour(name=n, sort_order=i)
        db.add(f)
        fl[n] = f
    db.flush()
    prods = {}
    for name, cat, ptype, base, desc, variants, with_flavour, imgs, flags in PRODUCTS:
        p = db.scalar(select(Product).where(Product.slug == slugify(name)))
        if p:
            prods[name] = p
            continue
        p = Product(name=name, slug=slugify(name), category_id=cats[cat].id, product_type=ptype, base_price=D(base),
                    description=desc, **flags)
        db.add(p)
        db.flush()
        prods[name] = p
        for i, im in enumerate(imgs):
            db.add(ProductImage(product_id=p.id, url=media(im), alt=name, sort_order=i))
        for i, (vn, vp) in enumerate(variants):
            db.add(ProductVariant(product_id=p.id, name=vn, price=D(vp), sort_order=i))
        if with_flavour:
            g = OptionGroup(product_id=p.id, name="Flavour", is_required=True)
            db.add(g)
            db.flush()
            for i, f in enumerate(FLAVOURS[:4]):
                db.add(OptionChoice(group_id=g.id, label=f, flavour_id=fl[f].id, sort_order=i))
        for i, (an, ap) in enumerate(ADDONS):
            db.add(ProductAddon(product_id=p.id, name=an, price=D(ap), sort_order=i))
    db.flush()
    return prods


PAGE_BODIES = {
    "delivery-policy": "<h2>Delivery</h2><p>We deliver within the city every day between 10:00 and 19:00. Choose your delivery date and time slot at checkout.</p><h2>Delivery fee</h2><p>A flat delivery fee is shown at checkout. Pickup from our shop is free.</p><h2>Lead time</h2><p>Most cakes need 24 hours notice; wedding and custom cakes need more. The exact time is shown on each product.</p>",
    "return-and-refund-policy": "<h2>Refunds</h2><p>Because our products are fresh and made to order, we cannot accept returns. If something is wrong with your order, contact us within 24 hours with a photo and we will make it right with a replacement or refund.</p><h2>Cancellations</h2><p>Orders can be cancelled free of charge until we start baking. Contact us as soon as possible.</p>",
    "privacy-policy": "<h2>What we collect</h2><p>Your name, phone number, email and delivery address - only to fulfil your orders and contact you about them.</p><h2>How we use it</h2><p>We never sell your data. It is shared only with the delivery and payment steps needed to complete your order.</p><h2>Your rights</h2><p>You can ask us to view or delete your data at any time via the Contact page.</p>",
    "terms-and-conditions": "<h2>Orders</h2><p>An order is confirmed once we accept it. Prices and availability may change without notice.</p><h2>Allergens</h2><p>Our products may contain milk, eggs, gluten, nuts and soy. Please tell us about any allergies when you order.</p><h2>Changes</h2><p>We may update these terms from time to time.</p>",
}


def seed_contact_details(db):
    hours = [{"day": d, "open": "09:00", "close": "20:00", "closed": False} for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")]
    hours.append({"day": "Sun", "open": "11:00", "close": "18:00", "closed": False})
    demo = {"email": "hello@cakestudio.example", "phone": "+92 300 1234567", "whatsapp": "+923001234567",
            "address": "Shop 4, Bakery Lane, DHA Phase 6, Karachi", "business_hours": hours}
    row = db.scalar(select(WebsiteSetting).where(WebsiteSetting.group == "general"))
    if row is None:
        db.add(WebsiteSetting(group="general", value=demo))
    else:  # only fill what the admin hasn't set
        row.value = {**demo, **{k: v for k, v in row.value.items() if v not in (None, "", [])}}


def seed_cms(db):
    seed_contact_details(db)
    if db.scalar(select(Banner.id).limit(1)) is None:
        for i, (t, s, img, link) in enumerate(BANNERS):
            db.add(Banner(title=t, subtitle=s, image_url=media(img), link_url=link, sort_order=i))
    if db.scalar(select(Testimonial.id).limit(1)) is None:
        for i, (n, q, r) in enumerate(TESTIMONIALS):
            db.add(Testimonial(customer_name=n, quote=q, rating=r, sort_order=i))
    secs = {s.key: s for s in db.scalars(select(HomepageSection))}
    if "hero" in secs and not secs["hero"].content.get("image_url"):
        secs["hero"].content = {**secs["hero"].content, "image_url": media("hero.jpg")}
    if "about" in secs and not secs["about"].content.get("description"):
        secs["about"].content = {"description": "Cake Studio is a family bakery. We bake every cake to order using real butter, "
                                 "fresh cream and quality chocolate - no shortcuts.", "image_url": media("about.jpg")}
    if "social_gallery" in secs and not secs["social_gallery"].content.get("images"):
        secs["social_gallery"].content = {"images": [media(f"gallery{i}.jpg") for i in range(1, 5)]}
    for slug, body in PAGE_BODIES.items():
        pg = db.scalar(select(Page).where(Page.slug == slug))
        if pg and "Edit this" in pg.body_html:
            pg.body_html = body
    about = db.scalar(select(Page).where(Page.slug == "about"))
    if about and ("Edit this" in about.body_html or about.body_html.startswith("<h2>Our story</h2>")):
        about.body_html = ("<h2>Cakes that taste as good as they look</h2><p>Cake Studio started in a home kitchen with one goal: "
                           "cakes that taste as good as they look. Today we bake celebration, wedding and custom cakes fresh to order.</p>"
                           "<p>Every cake is made with real butter, fresh cream and quality chocolate - no shortcuts, no preservatives.</p>"
                           "<p>Whether it is a birthday, an anniversary or a wedding, we would love to be part of your celebration.</p>")


def seed_coupons(db):
    if db.scalar(select(Coupon.id).limit(1)) is None:
        now = datetime.now(timezone.utc)
        db.add(Coupon(code="SWEET10", kind="percent", value=D("10"), max_discount=D("1000"), min_order=D("1500"),
                      expires_at=now + timedelta(days=365)))
        db.add(Coupon(code="WELCOME200", kind="fixed", value=D("200"), min_order=D("1000"), first_order_only=True,
                      expires_at=now + timedelta(days=365)))


def seed_inventory(db, prods):
    if db.scalar(select(InventoryItem.id).limit(1)) is not None:
        return
    sup = []
    for n, c, p in SUPPLIERS:
        s = Supplier(name=n, contact_name=c, phone=p)
        db.add(s)
        sup.append(s)
    db.flush()
    items = {}
    now = datetime.now(timezone.utc)
    for n, kind, unit, stock, low, cost, si in INVENTORY:
        it = InventoryItem(name=n, kind=kind, unit=unit, stock_qty=D(stock), low_stock_threshold=D(low),
                           cost_per_unit=D(cost), supplier_id=sup[si].id if si is not None else None)
        db.add(it)
        db.flush()
        db.add(InventoryTransaction(item_id=it.id, kind="purchase", qty_change=D(stock), balance_after=D(stock),
                                    reference="demo", note="Opening stock", created_at=now))
        items[n] = it
    # recipe per unit for the chocolate cake (default recipe)
    p = prods["Classic Chocolate Cake"]
    for n, q in [("Flour", "0.25"), ("Sugar", "0.2"), ("Butter", "0.15"), ("Cocoa powder", "0.08"), ("Eggs", "3")]:
        db.add(ProductRecipe(product_id=p.id, variant_id=None, item_id=items[n].id, qty_per_unit=D(q)))


def seed_orders(db, prods):
    if db.scalar(select(Order.id).limit(1)) is not None:
        return
    slot = db.scalar(select(DeliverySlot).order_by(DeliverySlot.id))
    now = datetime.now(timezone.utc)
    today = now.date()
    plan = [(0, "Classic Chocolate Cake", "2 lb", "3400", 1, 12), (1, "Red Velvet Cake", "1 lb", "2000", 1, 9),
            (2, "Cupcake Box (6)", None, "1500", 2, 6), (0, "Strawberry Dream Cake", "1 lb", "1900", 1, 4),
            (1, "Almond Croissant", None, "350", 4, 2)]
    custs, orders = [], {}
    for n, ph, em, addr, city in CUSTOMERS:
        c = db.scalar(select(Customer).where(Customer.phone == ph)) or Customer(full_name=n, phone=ph, email=em)
        db.add(c)
        custs.append((c, addr, city))
    db.flush()
    for ci, pname, vname, price, qty, days_ago in plan:
        c, addr, city = custs[ci]
        p = prods[pname]
        day = today - timedelta(days=days_ago)
        total = D(price) * qty
        fee = D("200")
        created = now - timedelta(days=days_ago + 2)
        o = Order(order_number=shop.new_order_number(db, day), status="delivered", customer_id=c.id, customer_name=c.full_name,
                  customer_phone=c.phone, customer_email=c.email, fulfillment="delivery", address_line=addr, city=city,
                  delivery_date=day, slot_id=slot.id if slot else None,
                  slot_label=f"{slot.start_time:%H:%M}-{slot.end_time:%H:%M}" if slot else "10:00-13:00",
                  subtotal=total, delivery_fee=fee, total=total + fee, payment_method_code="cod", payment_status="paid",
                  ingredients_deducted=True, created_at=created, updated_at=created)
        o.items = [OrderItem(product_id=p.id, product_name=pname, variant_name=vname, options=[], addons=[], unit_price=D(price),
                             quantity=qty, line_total=total, category_id=p.category_id)]
        o.history = [OrderStatusHistory(from_status=None, to_status="pending_confirmation", created_at=created, note="Order placed"),
                     OrderStatusHistory(from_status="pending_confirmation", to_status="delivered", created_at=created + timedelta(days=2), note="Demo order")]
        o.payments = [Payment(method_code="cod", amount=total + fee, status="verified", reference="demo")]
        db.add(o)
        db.flush()
        orders[pname] = o
    for pname, rating, comment in REVIEWS:
        o = orders.get(pname)
        if o:
            db.add(Review(product_id=prods[pname].id, order_id=o.id, reviewer_name=o.customer_name.split()[0], rating=rating,
                          comment=comment, status="approved"))


def run() -> None:
    with session_factory() as db:
        prods = seed_catalogue(db)
        seed_cms(db)
        seed_coupons(db)
        seed_inventory(db, prods)
        seed_orders(db, prods)
        db.commit()
        log.info("demo data ready")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
