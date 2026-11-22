from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import Banner, HomepageSection, NavigationMenu, Page, Testimonial, User, WebsiteSetting
from app.services import audit
from app.services.sanitize import sanitize_html
from app.services.settings_schema import GROUPS, defaults, validate_group

router = APIRouter(prefix="/admin", tags=["cms-admin"])
read = require_permission("cms.read")
write = require_permission("cms.write")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ReorderIn(BaseModel):
    ids: list[int]  # new order, first = top


def _reorder(db: Session, model, ids: list[int], **scope) -> None:
    q = select(model).where(model.id.in_(ids))
    for k, v in scope.items():
        q = q.where(getattr(model, k) == v)
    rows = {r.id: r for r in db.scalars(q)}
    if set(rows) != set(ids) or len(ids) != len(set(ids)):
        raise HTTPException(422, "ids must be unique and all exist")
    for pos, i in enumerate(ids):
        rows[i].sort_order = pos


def _get(db: Session, model, id_: int):
    obj = db.get(model, id_)
    if obj is None or getattr(obj, "deleted_at", None) is not None:
        raise HTTPException(404, "Not found")
    return obj


# ---------- settings ----------
@router.get("/settings/{group}")
def get_settings_group(group: str, db: Session = Depends(get_db), _: User = Depends(require_permission("settings.read"))):
    if group not in GROUPS:
        raise HTTPException(404, "Unknown settings group")
    row = db.scalar(select(WebsiteSetting).where(WebsiteSetting.group == group))
    return {**defaults(group), **(row.value if row else {})}


@router.put("/settings/{group}")
def put_settings_group(
    group: str,
    body: dict,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("settings.write")),
):
    if group not in GROUPS:
        raise HTTPException(404, "Unknown settings group")
    try:
        clean = validate_group(group, body)
    except Exception as e:  # pydantic ValidationError -> 422 with details
        errors = getattr(e, "errors", None)
        raise HTTPException(422, errors(include_url=False, include_context=False) if errors else str(e))
    row = db.scalar(select(WebsiteSetting).where(WebsiteSetting.group == group))
    before = row.value if row else None
    if row is None:
        db.add(WebsiteSetting(group=group, value=clean))
    else:
        row.value = clean
    audit.record(db, actor, "settings.update", "website_settings", group, {"before": before, "after": clean})
    db.commit()
    return clean


# ---------- homepage sections ----------
class SectionIn(BaseModel):
    title: str = Field("", max_length=200)
    content: dict = {}
    is_visible: bool = True


class SectionOut(ORM):
    id: int
    key: str
    title: str
    content: dict
    is_visible: bool
    sort_order: int


@router.get("/homepage/sections", response_model=list[SectionOut])
def list_sections(db: Session = Depends(get_db), _: User = Depends(read)):
    return list(db.scalars(select(HomepageSection).order_by(HomepageSection.sort_order)))


@router.put("/homepage/sections/reorder", response_model=list[SectionOut])
def reorder_sections(data: ReorderIn, db: Session = Depends(get_db), actor: User = Depends(write)):
    _reorder(db, HomepageSection, data.ids)
    audit.record(db, actor, "homepage.reorder", "homepage_sections", None, {"ids": data.ids})
    db.commit()
    return list_sections(db, actor)


@router.put("/homepage/sections/{section_id}", response_model=SectionOut)
def update_section(section_id: int, data: SectionIn, db: Session = Depends(get_db), actor: User = Depends(write)):
    s = _get(db, HomepageSection, section_id)
    s.title, s.content, s.is_visible = data.title, data.content, data.is_visible
    audit.record(db, actor, "homepage.update", "homepage_sections", s.id)
    db.commit()
    return s


# ---------- navigation ----------
class NavIn(BaseModel):
    location: str = Field(pattern="^(header|footer)$")
    label: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=500, pattern=r"^(/|https?://|mailto:|tel:)")
    parent_id: int | None = None
    open_in_new_tab: bool = False
    is_active: bool = True


class NavOut(ORM, NavIn):
    id: int
    sort_order: int


@router.get("/navigation", response_model=list[NavOut])
def list_nav(location: str | None = None, db: Session = Depends(get_db), _: User = Depends(read)):
    q = select(NavigationMenu).order_by(NavigationMenu.location, NavigationMenu.sort_order)
    if location:
        q = q.where(NavigationMenu.location == location)
    return list(db.scalars(q))


@router.post("/navigation", response_model=NavOut, status_code=201)
def create_nav(data: NavIn, db: Session = Depends(get_db), actor: User = Depends(write)):
    if data.parent_id is not None:
        parent = db.get(NavigationMenu, data.parent_id)
        if not parent or parent.location != data.location or parent.parent_id is not None:
            raise HTTPException(422, "parent must be a top-level item in the same menu")
    last = db.scalar(select(NavigationMenu.sort_order).where(NavigationMenu.location == data.location)
                     .order_by(NavigationMenu.sort_order.desc()).limit(1))
    item = NavigationMenu(**data.model_dump(), sort_order=(last or 0) + 1)
    db.add(item)
    db.flush()
    audit.record(db, actor, "navigation.create", "navigation_menus", item.id)
    db.commit()
    return item


@router.put("/navigation/reorder", response_model=list[NavOut])
def reorder_nav(data: ReorderIn, location: str, db: Session = Depends(get_db), actor: User = Depends(write)):
    _reorder(db, NavigationMenu, data.ids, location=location)
    audit.record(db, actor, "navigation.reorder", "navigation_menus", None, {"ids": data.ids})
    db.commit()
    return list_nav(location, db, actor)


@router.put("/navigation/{item_id}", response_model=NavOut)
def update_nav(item_id: int, data: NavIn, db: Session = Depends(get_db), actor: User = Depends(write)):
    item = _get(db, NavigationMenu, item_id)
    if data.parent_id == item.id:
        raise HTTPException(422, "item cannot be its own parent")
    for k, v in data.model_dump().items():
        setattr(item, k, v)
    audit.record(db, actor, "navigation.update", "navigation_menus", item.id)
    db.commit()
    return item


@router.delete("/navigation/{item_id}", status_code=204)
def delete_nav(item_id: int, db: Session = Depends(get_db), actor: User = Depends(write)):
    db.delete(_get(db, NavigationMenu, item_id))
    audit.record(db, actor, "navigation.delete", "navigation_menus", item_id)
    db.commit()


# ---------- pages ----------
class PageIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    title: str = Field(min_length=1, max_length=200)
    body_html: str = ""
    meta_title: str | None = Field(None, max_length=200)
    meta_description: str | None = Field(None, max_length=300)
    is_published: bool = True


class PageOut(ORM, PageIn):
    id: int


@router.get("/pages", response_model=list[PageOut])
def list_pages(db: Session = Depends(get_db), _: User = Depends(read)):
    return list(db.scalars(select(Page).where(Page.deleted_at.is_(None)).order_by(Page.title)))


@router.post("/pages", response_model=PageOut, status_code=201)
def create_page(data: PageIn, db: Session = Depends(get_db), actor: User = Depends(write)):
    if db.scalar(select(Page.id).where(Page.slug == data.slug)):
        raise HTTPException(409, "Slug already in use")
    page = Page(**{**data.model_dump(), "body_html": sanitize_html(data.body_html)})
    db.add(page)
    db.flush()
    audit.record(db, actor, "page.create", "pages", page.id)
    db.commit()
    return page


@router.put("/pages/{page_id}", response_model=PageOut)
def update_page(page_id: int, data: PageIn, db: Session = Depends(get_db), actor: User = Depends(write)):
    page = _get(db, Page, page_id)
    clash = db.scalar(select(Page.id).where(Page.slug == data.slug, Page.id != page_id))
    if clash:
        raise HTTPException(409, "Slug already in use")
    for k, v in {**data.model_dump(), "body_html": sanitize_html(data.body_html)}.items():
        setattr(page, k, v)
    audit.record(db, actor, "page.update", "pages", page.id)
    db.commit()
    return page


@router.delete("/pages/{page_id}", status_code=204)
def delete_page(page_id: int, db: Session = Depends(get_db), actor: User = Depends(write)):
    from datetime import datetime, timezone

    page = _get(db, Page, page_id)
    page.deleted_at = datetime.now(timezone.utc)
    page.slug = f"{page.slug}--deleted-{page.id}"  # free the slug for reuse
    audit.record(db, actor, "page.delete", "pages", page.id)
    db.commit()


# ---------- banners & testimonials (simple ordered lists) ----------
class BannerIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    subtitle: str = Field("", max_length=300)
    image_url: str | None = None
    link_url: str | None = None
    placement: str = "home_promo"
    is_active: bool = True


class BannerOut(ORM, BannerIn):
    id: int
    sort_order: int


class TestimonialIn(BaseModel):
    customer_name: str = Field(min_length=1, max_length=120)
    quote: str = Field(min_length=1, max_length=1000)
    rating: int = Field(5, ge=1, le=5)
    photo_url: str | None = None
    is_active: bool = True


class TestimonialOut(ORM, TestimonialIn):
    id: int
    sort_order: int


def _crud(path: str, model, In, Out, entity: str):
    @router.get(path, response_model=list[Out], name=f"list_{entity}")
    def _list(db: Session = Depends(get_db), _: User = Depends(read)):
        return list(db.scalars(select(model).order_by(model.sort_order, model.id)))

    @router.post(path, response_model=Out, status_code=201, name=f"create_{entity}")
    def _create(data: In, db: Session = Depends(get_db), actor: User = Depends(write)):
        obj = model(**data.model_dump())
        db.add(obj)
        db.flush()
        audit.record(db, actor, f"{entity}.create", path.strip("/"), obj.id)
        db.commit()
        return obj

    @router.put(f"{path}/reorder", response_model=list[Out], name=f"reorder_{entity}")
    def _reorder_route(data: ReorderIn, db: Session = Depends(get_db), actor: User = Depends(write)):
        _reorder(db, model, data.ids)
        audit.record(db, actor, f"{entity}.reorder", path.strip("/"), None, {"ids": data.ids})
        db.commit()
        return list(db.scalars(select(model).order_by(model.sort_order, model.id)))

    @router.put(f"{path}/{{item_id}}", response_model=Out, name=f"update_{entity}")
    def _update(item_id: int, data: In, db: Session = Depends(get_db), actor: User = Depends(write)):
        obj = _get(db, model, item_id)
        for k, v in data.model_dump().items():
            setattr(obj, k, v)
        audit.record(db, actor, f"{entity}.update", path.strip("/"), obj.id)
        db.commit()
        return obj

    @router.delete(f"{path}/{{item_id}}", status_code=204, name=f"delete_{entity}")
    def _delete(item_id: int, db: Session = Depends(get_db), actor: User = Depends(write)):
        db.delete(_get(db, model, item_id))
        audit.record(db, actor, f"{entity}.delete", path.strip("/"), item_id)
        db.commit()


_crud("/banners", Banner, BannerIn, BannerOut, "banner")
_crud("/testimonials", Testimonial, TestimonialIn, TestimonialOut, "testimonial")
