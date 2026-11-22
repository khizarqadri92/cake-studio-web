import pytest
from pydantic import ValidationError

from app.services.sanitize import sanitize_html
from app.services.settings_schema import defaults, validate_group


def test_script_and_handlers_removed():
    out = sanitize_html('<p onclick="x()">Hi</p><script>alert(1)</script><img src=x onerror=alert(1)>')
    assert "script" not in out and "alert" not in out and "onclick" not in out and "onerror" not in out
    assert "<p>Hi</p>" in out


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "JaVa\nScRiPt:alert(1)", "data:text/html,<b>", "vbscript:x"])
def test_dangerous_urls_dropped(bad):
    out = sanitize_html(f'<a href="{bad}">x</a>')
    assert "href" not in out


def test_safe_link_gets_rel_and_formatting_kept():
    out = sanitize_html('<h2>T</h2><a href="https://example.com">l</a><strong>b</strong>')
    assert 'rel="noopener noreferrer"' in out and "<h2>T</h2>" in out and "<strong>b</strong>" in out


def test_text_is_escaped_and_unknown_tags_unwrapped():
    out = sanitize_html("<custom>a &lt;b&gt;</custom>")
    assert out == "a &lt;b&gt;"


def test_iframe_content_dropped():
    assert sanitize_html("<iframe src='//evil'>inner</iframe>ok") == "ok"


def test_theme_defaults_are_valid_and_palette_matches_brief():
    t = defaults("theme")
    assert t["background_color"] == "#FFF8F0"


def test_theme_rejects_bad_color_and_font():
    with pytest.raises(ValidationError):
        validate_group("theme", {"primary_color": "red"})
    with pytest.raises(ValidationError):
        validate_group("theme", {"heading_font": "Arial;}body{display:none"})


def test_unknown_field_and_group_rejected():
    with pytest.raises(ValidationError):
        validate_group("general", {"nope": 1})
    with pytest.raises(KeyError):
        validate_group("payments", {})


def test_social_requires_http():
    assert validate_group("social", {"instagram": "https://instagram.com/x"})["instagram"]
    with pytest.raises(ValidationError):
        validate_group("social", {"facebook": "javascript:alert(1)"})
