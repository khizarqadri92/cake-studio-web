import re
import unicodedata


def slugify(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t or "item"


def unique_slug(base: str, exists) -> str:
    """`exists(slug) -> bool`. Appends -2, -3... until free."""
    slug, n = base, 2
    while exists(slug):
        slug = f"{base}-{n}"
        n += 1
    return slug
