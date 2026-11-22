"""Validation for each website_settings group. Unknown groups are rejected."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class General(_Base):
    site_name: str = Field("Cake Studio", max_length=100)
    tagline: str = Field("Freshly Baked. Beautifully Crafted.", max_length=200)
    logo_url: str | None = None
    favicon_url: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    address: str | None = None
    google_maps_embed_url: str | None = None
    business_hours: list[dict] = []  # [{"day": "Mon", "open": "09:00", "close": "18:00", "closed": false}]
    currency_code: str = Field("USD", min_length=3, max_length=3)
    currency_symbol: str = Field("$", max_length=5)
    tax_enabled: bool = False
    tax_rate_percent: float = Field(0, ge=0, le=100)
    tax_inclusive: bool = True

    @field_validator("google_maps_embed_url")
    @classmethod
    def _maps_embed(cls, v):
        """Accept either the embed URL or the whole <iframe ...> snippet Google gives you; store just the URL."""
        if not v or not v.strip():
            return None
        v = v.strip()
        m = re.search(r'src\s*=\s*["\']([^"\']+)["\']', v, re.I) if "<" in v else None
        url = (m.group(1) if m else v).replace("&amp;", "&").strip()
        if not re.match(r"^https://(www\.)?google\.com/maps/|^https://maps\.google\.com/", url, re.I) or len(url) > 2000:
            raise ValueError("Paste the embed code from Google Maps > Share > Embed a map (it starts with <iframe src=\"https://www.google.com/maps/embed...\")")
        return url


class Theme(_Base):
    primary_color: str = "#8B5A3C"  # chocolate
    secondary_color: str = "#F4C2C2"  # soft pink
    background_color: str = "#FFF8F0"  # cream
    surface_color: str = "#FFFFFF"
    text_color: str = "#3E2723"
    heading_font: str = Field("Playfair Display", max_length=60)
    body_font: str = Field("Inter", max_length=60)
    button_style: Literal["rounded", "pill", "square"] = "pill"
    header_layout: Literal["centered", "left", "split"] = "centered"
    footer_layout: Literal["simple", "columns"] = "columns"

    @field_validator("primary_color", "secondary_color", "background_color", "surface_color", "text_color")
    @classmethod
    def _hex(cls, v: str) -> str:
        if not HEX.match(v):
            raise ValueError("must be a #RRGGBB hex colour")
        return v

    @field_validator("heading_font", "body_font")
    @classmethod
    def _font(cls, v: str) -> str:  # these end up in CSS / font URLs: keep them boring
        if not re.match(r"^[A-Za-z0-9 ]+$", v):
            raise ValueError("font names may contain only letters, digits and spaces")
        return v


class Social(_Base):
    facebook: str | None = None
    instagram: str | None = None
    tiktok: str | None = None
    youtube: str | None = None
    whatsapp: str | None = None

    @field_validator("*")
    @classmethod
    def _http(cls, v):
        if v and not re.match(r"^(https?://|\+?\d[\d\s-]{5,})", v):
            raise ValueError("must be an http(s) URL (or a phone number for WhatsApp)")
        return v


class Seo(_Base):
    meta_title: str | None = Field(None, max_length=70)
    meta_description: str | None = Field(None, max_length=200)
    keywords: list[str] = []
    og_image_url: str | None = None
    robots_txt: str = "User-agent: *\nAllow: /\n"


class Checkout(_Base):
    delivery_fee: float = Field(0, ge=0, le=100000)
    free_delivery_over: float | None = Field(None, ge=0)
    min_prep_hours: int = Field(24, ge=0, le=720)  # store-wide floor; products may need longer
    max_days_ahead: int = Field(60, ge=1, le=365)
    timezone: str = "UTC"  # IANA name; slot times and "today" are evaluated in this zone
    pickup_address_note: str = Field("", max_length=300)
    custom_cake_min_days: int = Field(3, ge=0, le=60)  # notice needed for custom cake requests

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("unknown IANA timezone, e.g. Asia/Karachi")
        return v


class Notifications(_Base):
    email_enabled: bool = False
    whatsapp_enabled: bool = False
    admin_email: str | None = None
    notify_statuses: list[str] = ["confirmed", "ready_for_pickup", "out_for_delivery", "delivered", "cancelled"]


class Inventory(_Base):
    # When recipe ingredients are taken from stock: on one order status, or never (manual stock control only).
    deduct_on: Literal["never", "confirmed", "in_preparation"] = "in_preparation"


GROUPS: dict[str, type[_Base]] = {"general": General, "theme": Theme, "social": Social, "seo": Seo, "checkout": Checkout, "notifications": Notifications, "inventory": Inventory}
# Groups exposed to the public storefront (all of the above; nothing secret lives in these).
PRIVATE_GROUPS = {"notifications", "inventory"}  # staff-only (contains admin contact); never sent to the storefront
PUBLIC_GROUPS = tuple(g for g in GROUPS if g not in PRIVATE_GROUPS)  # provider secrets live in env vars only


def validate_group(group: str, value: dict) -> dict:
    model = GROUPS.get(group)
    if model is None:
        raise KeyError(group)
    return model(**value).model_dump()


def defaults(group: str) -> dict:
    return GROUPS[group]().model_dump()
