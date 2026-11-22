"""Allowlist HTML sanitizer for admin-authored CMS pages (stdlib only).

Anything not explicitly allowed is dropped; script/style content is removed entirely.
"""
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "h1", "h2", "h3", "h4", "ul", "ol", "li",
    "blockquote", "a", "img", "hr", "table", "thead", "tbody", "tr", "th", "td", "span", "div",
}
ALLOWED_ATTRS = {"a": {"href", "title", "target", "rel"}, "img": {"src", "alt", "title"}}
VOID = {"br", "hr", "img"}
DROP_CONTENT = {"script", "style", "iframe", "object", "embed", "noscript", "template"}
SAFE_SCHEMES = {"http", "https", "mailto", "tel", ""}


def _safe_url(value: str) -> bool:
    v = "".join(value.split()).lower()  # strip whitespace tricks like "java\nscript:"
    if v.startswith("//"):
        return True
    return urlparse(v).scheme in SAFE_SCHEMES


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT:
            self._skip += 1
            return
        if self._skip or tag not in ALLOWED_TAGS:
            return
        parts = []
        for name, val in attrs:
            if name not in ALLOWED_ATTRS.get(tag, set()) or val is None:
                continue
            if name in {"href", "src"} and not _safe_url(val):
                continue
            parts.append(f' {name}="{escape(val, quote=True)}"')
        if tag == "a" and any(" href=" in p for p in parts):
            parts.append(' rel="noopener noreferrer"')
        self.out.append(f"<{tag}{''.join(parts)}>")

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip or tag not in ALLOWED_TAGS or tag in VOID:
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self._skip:
            self.out.append(escape(data, quote=False))


def sanitize_html(html: str) -> str:
    s = _Sanitizer()
    s.feed(html)
    s.close()
    return "".join(s.out)
