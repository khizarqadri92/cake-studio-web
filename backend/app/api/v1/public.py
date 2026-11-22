from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import rate_limit
from app.services.sanitize import sanitize_html
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Banner, HomepageSection, NavigationMenu, Page, Testimonial, WebsiteSetting
from app.services.settings_schema import PUBLIC_GROUPS, defaults

router = APIRouter(prefix="/public", tags=["public"])


def _cache(resp: Response) -> None:
    resp.headers["Cache-Control"] = "public, max-age=30"


@router.get("/settings")
def public_settings(response: Response, db: Session = Depends(get_db)):
    _cache(response)
    rows = {r.group: r.value for r in db.scalars(select(WebsiteSetting))}
    return {g: {**defaults(g), **rows.get(g, {})} for g in PUBLIC_GROUPS}


@router.get("/navigation")
def public_navigation(response: Response, db: Session = Depends(get_db)):
    _cache(response)
    items = db.scalars(
        select(NavigationMenu).where(NavigationMenu.is_active.is_(True)).order_by(NavigationMenu.sort_order)
    ).all()
    out: dict[str, list[dict]] = {"header": [], "footer": []}
    by_id: dict[int, dict] = {}
    for i in items:
        node = {"id": i.id, "label": i.label, "url": i.url, "new_tab": i.open_in_new_tab, "children": []}
        by_id[i.id] = node
        if i.parent_id is None:
            out.setdefault(i.location, []).append(node)
    for i in items:
        if i.parent_id in by_id:
            by_id[i.parent_id]["children"].append(by_id[i.id])
    return out


@router.get("/homepage")
def public_homepage(response: Response, db: Session = Depends(get_db)):
    """Visible sections in admin-defined order, plus active banners and testimonials."""
    _cache(response)
    sections = db.scalars(
        select(HomepageSection).where(HomepageSection.is_visible.is_(True)).order_by(HomepageSection.sort_order)
    ).all()
    banners = db.scalars(select(Banner).where(Banner.is_active.is_(True)).order_by(Banner.sort_order)).all()
    testimonials = db.scalars(
        select(Testimonial).where(Testimonial.is_active.is_(True)).order_by(Testimonial.sort_order)
    ).all()
    return {
        "sections": [{"key": s.key, "title": s.title, "content": s.content} for s in sections],
        "banners": [
            {"id": b.id, "title": b.title, "subtitle": b.subtitle, "image_url": b.image_url,
             "link_url": b.link_url, "placement": b.placement}
            for b in banners
        ],
        "testimonials": [
            {"id": t.id, "name": t.customer_name, "quote": t.quote, "rating": t.rating, "photo_url": t.photo_url}
            for t in testimonials
        ],
    }


@router.get("/pages/{slug}")
def public_page(slug: str, response: Response, db: Session = Depends(get_db)):
    _cache(response)
    page = db.scalar(select(Page).where(Page.slug == slug, Page.deleted_at.is_(None), Page.is_published.is_(True)))
    if page is None:
        raise HTTPException(404, "Page not found")
    return {"slug": page.slug, "title": page.title, "body_html": sanitize_html(page.body_html),  # also cleaned on output, in case rows were edited outside the API
            "meta_title": page.meta_title, "meta_description": page.meta_description}


@router.get("/robots.txt", response_class=Response)
def robots(db: Session = Depends(get_db)):
    row = db.scalar(select(WebsiteSetting).where(WebsiteSetting.group == "seo"))
    text = (row.value.get("robots_txt") if row else None) or defaults("seo")["robots_txt"]
    return Response(text, media_type="text/plain")


@router.get("/sitemap.xml", response_class=Response)
def sitemap(db: Session = Depends(get_db)):
    from xml.sax.saxutils import escape

    slugs = db.scalars(select(Page.slug).where(Page.deleted_at.is_(None), Page.is_published.is_(True))).all()
    base = get_settings().public_base_url.rstrip("/")
    urls = ["/", "/shop", "/custom-cake", "/contact", *[f"/p/{s}" for s in slugs]]
    body = "".join(f"<url><loc>{escape(base + u)}</loc></url>" for u in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'
    return Response(xml, media_type="application/xml")


# ---------- newsletter & contact form ----------
from pydantic import BaseModel, EmailStr, Field  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.models import ContactMessage, NewsletterSubscriber  # noqa: E402


class NewsletterIn(BaseModel):
    email: EmailStr


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str | None = Field(None, max_length=40)
    message: str = Field(min_length=5, max_length=3000)


@router.post("/newsletter", status_code=202, dependencies=[Depends(rate_limit("newsletter", 5, 60))])
def subscribe(data: NewsletterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(NewsletterSubscriber.id).where(NewsletterSubscriber.email == email)) is None:
        db.add(NewsletterSubscriber(email=email))
        try:
            db.commit()
        except IntegrityError:  # concurrent duplicate: treat as success
            db.rollback()
    return {"ok": True}  # same response whether or not already subscribed


@router.post("/contact", status_code=201, dependencies=[Depends(rate_limit("contact", 5, 60))])
def contact(data: ContactIn, db: Session = Depends(get_db)):
    db.add(ContactMessage(name=data.name.strip(), email=data.email.lower(), phone=data.phone, message=data.message.strip()))
    db.commit()
    return {"ok": True}
