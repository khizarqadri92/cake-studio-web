from decimal import Decimal as D

import pytest

from app.services.pricing import (Addon, Choice, Group, PricingError, ProductSpec, Selection, Variant,
                                  from_price, price_line)
from app.services.storage import LocalStorage, UploadError, sniff_image
from app.services.text import slugify, unique_slug

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


def cake(**kw):
    base = dict(
        id=1, product_type="variable", base_price=D("20"),
        variants=(Variant(1, D("20")), Variant(2, D("35"), sale_price=D("30")), Variant(3, D("50"), is_active=False)),
        groups=(
            Group(10, "Flavour", True, (Choice(100, D("0")), Choice(101, D("5")), Choice(102, D("9"), is_active=False))),
            Group(11, "Egg", False, (Choice(110, D("0")), Choice(111, D("2.50")))),
        ),
        addons=(Addon(200, D("3")), Addon(201, D("4.25")), Addon(202, D("1"), is_active=False)),
        allows_message=True, message_max_length=10,
    )
    base.update(kw)
    return ProductSpec(**base)


def test_variant_sale_price_options_and_addons_sum():
    r = price_line(cake(), Selection(variant_id=2, choice_ids=[101, 111], addon_ids=[200, 201], quantity=2))
    assert r.unit_base == D("30.00")  # sale price wins
    assert r.options_total == D("7.50") and r.addons_total == D("7.25")
    assert r.unit_price == D("44.75") and r.line_total == D("89.50")


def test_simple_product_uses_sale_price():
    p = ProductSpec(id=2, product_type="simple", base_price=D("10"), sale_price=D("8.5"))
    assert price_line(p, Selection()).unit_price == D("8.50")


def test_variable_requires_active_variant():
    with pytest.raises(PricingError):
        price_line(cake(), Selection(choice_ids=[100]))
    with pytest.raises(PricingError):
        price_line(cake(), Selection(variant_id=3, choice_ids=[100]))


def test_required_group_and_single_choice_enforced():
    with pytest.raises(PricingError, match="Flavour"):
        price_line(cake(), Selection(variant_id=1))
    with pytest.raises(PricingError, match="Only one"):
        price_line(cake(), Selection(variant_id=1, choice_ids=[100, 101]))


def test_inactive_unknown_options_and_addons_rejected():
    for sel in (Selection(variant_id=1, choice_ids=[102]), Selection(variant_id=1, choice_ids=[999]),
                Selection(variant_id=1, choice_ids=[100], addon_ids=[202]),
                Selection(variant_id=1, choice_ids=[100], addon_ids=[200, 200])):
        with pytest.raises(PricingError):
            price_line(cake(), sel)


def test_message_rules():
    ok = price_line(cake(), Selection(variant_id=1, choice_ids=[100], message="  Happy Bday "))
    assert ok.message == "Happy Bday"
    with pytest.raises(PricingError):
        price_line(cake(), Selection(variant_id=1, choice_ids=[100], message="x" * 11))
    with pytest.raises(PricingError):
        price_line(cake(allows_message=False), Selection(variant_id=1, choice_ids=[100], message="hi"))


def test_stock_and_availability():
    spec = cake(track_stock=True, variants=(Variant(1, D("20"), stock_qty=2),))
    with pytest.raises(PricingError, match="stock"):
        price_line(spec, Selection(variant_id=1, choice_ids=[100], quantity=3))
    with pytest.raises(PricingError):
        price_line(cake(is_available=False), Selection(variant_id=1, choice_ids=[100]))
    with pytest.raises(PricingError):
        price_line(cake(), Selection(variant_id=1, choice_ids=[100], quantity=0))


def test_rounding_half_up():
    p = ProductSpec(id=3, product_type="simple", base_price=D("0.005"))
    assert price_line(p, Selection()).unit_price == D("0.01")


def test_from_price_uses_cheapest_active_variant():
    assert from_price(cake()) == D("20.00")


def test_sniff_and_storage(tmp_path):
    assert sniff_image(PNG) == "png"
    assert sniff_image(b"\xff\xd8\xff\xe0" + b"0" * 8) == "jpg"
    for bad in (b"<svg onload=alert(1)>", b"<?php echo 1;", b"MZ\x90\x00"):
        with pytest.raises(UploadError):
            sniff_image(bad)
    st = LocalStorage(str(tmp_path), max_bytes=100)
    url = st.save(PNG)
    assert url.startswith("/media/") and url.endswith(".png")
    assert (tmp_path / url.split("/")[-1]).read_bytes() == PNG
    with pytest.raises(UploadError):
        st.save(PNG + b"0" * 200)
    with pytest.raises(UploadError):
        st.save(b"")


def test_slugs():
    assert slugify("Choco-Lava Cake!! Ünï") == "choco-lava-cake-uni"
    assert slugify("###") == "item"
    taken = {"cake", "cake-2"}
    assert unique_slug("cake", lambda s: s in taken) == "cake-3"
