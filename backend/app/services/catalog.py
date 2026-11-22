"""Bridges DB models <-> pricing engine specs."""
from decimal import Decimal

from app.models import Product
from app.services.pricing import Addon, Choice, Group, ProductSpec, Variant


def to_spec(p: Product) -> ProductSpec:
    return ProductSpec(
        id=p.id,
        product_type=p.product_type,
        base_price=Decimal(p.base_price),
        sale_price=None if p.sale_price is None else Decimal(p.sale_price),
        is_available=p.is_available and p.deleted_at is None,
        track_stock=p.track_stock,
        stock_qty=p.stock_qty,
        allows_message=p.allows_message,
        message_max_length=p.message_max_length,
        variants=tuple(
            Variant(v.id, Decimal(v.price), None if v.sale_price is None else Decimal(v.sale_price), v.stock_qty, v.is_active)
            for v in p.variants
        ),
        groups=tuple(
            Group(g.id, g.name, g.is_required,
                  tuple(Choice(c.id, Decimal(c.price_delta), c.is_active) for c in g.choices))
            for g in p.option_groups
        ),
        addons=tuple(Addon(a.id, Decimal(a.price), a.is_active) for a in p.addons),
    )
