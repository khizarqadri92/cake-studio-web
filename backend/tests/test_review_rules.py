import pytest

from app.services.review_rules import Eligibility, ReviewError, check_new_review, summarize

OK = Eligibility("delivered", frozenset({1, 2}))


def go(**kw):
    base = dict(rating=5, comment="Lovely", product_id=1, order=OK, already_reviewed=False)
    return check_new_review(**{**base, **kw})


def test_valid_review_is_cleaned():
    assert go(comment="  great\n\n cake  ") == "great cake"


@pytest.mark.parametrize("kw", [dict(rating=0), dict(rating=6), dict(order=Eligibility("confirmed", frozenset({1}))), dict(product_id=9), dict(already_reviewed=True), dict(comment="x" * 1501)])
def test_invalid_reviews_rejected(kw):
    with pytest.raises(ReviewError):
        go(**kw)


def test_summary():
    s = summarize([5, 5, 4, 1])
    assert s["count"] == 4 and s["average"] == 3.8 and s["distribution"]["5"] == 2
    assert summarize([]) == {"count": 0, "average": None, "distribution": {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}}
