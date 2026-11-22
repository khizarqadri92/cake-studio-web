from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class WebsiteSetting(Base, TimestampMixin):
    """One row per settings group (general, theme, social, seo, ...). Value is a JSON object."""

    __tablename__ = "website_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    group: Mapped[str] = mapped_column(String(50), unique=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)


class HomepageSection(Base, TimestampMixin):
    __tablename__ = "homepage_sections"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True)  # hero, featured_products, ...
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)


class NavigationMenu(Base, TimestampMixin):
    __tablename__ = "navigation_menus"
    __table_args__ = (Index("ix_nav_location_order", "location", "sort_order"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    location: Mapped[str] = mapped_column(String(20))  # header | footer
    label: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(500))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("navigation_menus.id", ondelete="CASCADE"))
    open_in_new_tab: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Page(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "pages"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    body_html: Mapped[str] = mapped_column(Text, default="")  # sanitized on write
    meta_title: Mapped[str | None] = mapped_column(String(200))
    meta_description: Mapped[str | None] = mapped_column(String(300))
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)


class Banner(Base, TimestampMixin):
    __tablename__ = "banners"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    subtitle: Mapped[str] = mapped_column(String(300), default="")
    image_url: Mapped[str | None] = mapped_column(String(500))
    link_url: Mapped[str | None] = mapped_column(String(500))
    placement: Mapped[str] = mapped_column(String(30), default="home_promo")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Testimonial(Base, TimestampMixin):
    __tablename__ = "testimonials"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(120))
    quote: Mapped[str] = mapped_column(Text)
    rating: Mapped[int] = mapped_column(Integer, default=5)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class NewsletterSubscriber(Base, TimestampMixin):
    __tablename__ = "newsletter_subscribers"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ContactMessage(Base, TimestampMixin):
    __tablename__ = "contact_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
