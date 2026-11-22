"""Recipe / bill-of-materials maths (pure)."""
from collections import defaultdict
from decimal import Decimal

# line: (product_id, variant_id | None, quantity)
# recipe: (product_id, variant_id | None, item_id, qty_per_unit)


def requirements(lines: list[tuple[int, int | None, int]], recipes: list[tuple[int, int | None, int, Decimal]]) -> dict[int, Decimal]:
    """Ingredient totals needed for the order lines. A variant-specific recipe (e.g. '2 kg') replaces the
    product-level recipe for that variant; otherwise the product-level recipe (variant_id None) is used."""
    by_variant: dict[tuple[int, int | None], list[tuple[int, Decimal]]] = defaultdict(list)
    for pid, vid, item, per in recipes:
        by_variant[(pid, vid)].append((item, per))
    need: dict[int, Decimal] = defaultdict(Decimal)
    for pid, vid, qty in lines:
        recipe = by_variant.get((pid, vid)) or by_variant.get((pid, None)) or []
        for item, per in recipe:
            need[item] += per * qty
    return dict(need)


def shortages(need: dict[int, Decimal], stock: dict[int, Decimal]) -> dict[int, Decimal]:
    """Item -> amount missing (only items that would go below zero)."""
    return {i: n - stock.get(i, Decimal(0)) for i, n in need.items() if stock.get(i, Decimal(0)) < n}
