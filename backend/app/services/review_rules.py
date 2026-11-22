"""Product review rules (pure, unit-tested). Reviews come from real, delivered orders only."""
from dataclasses import dataclass

STATUSES = ("pending", "approved", "rejected")
MAX_COMMENT = 1500


class ReviewError(ValueError):
    pass


@dataclass(frozen=True)
class Eligibility:
    order_status: str
    product_ids: frozenset[int]


def check_new_review(*, rating: int, comment: str, product_id: int, order: Eligibility, already_reviewed: bool) -> str:
    """Return the cleaned comment, or raise ReviewError with a customer-friendly message."""
    if not 1 <= rating <= 5:
        raise ReviewError("Rating must be between 1 and 5")
    comment = " ".join((comment or "").split())  # collapse whitespace/newlines
    if len(comment) > MAX_COMMENT:
        raise ReviewError(f"Please keep your review under {MAX_COMMENT} characters")
    if order.order_status != "delivered":
        raise ReviewError("You can review a product once your order has been delivered")
    if product_id not in order.product_ids:
        raise ReviewError("That product isn't part of this order")
    if already_reviewed:
        raise ReviewError("You've already reviewed this product for this order")
    return comment


def summarize(ratings: list[int]) -> dict:
    n = len(ratings)
    return {"count": n, "average": round(sum(ratings) / n, 1) if n else None,
            "distribution": {str(s): sum(1 for r in ratings if r == s) for s in (5, 4, 3, 2, 1)}}
