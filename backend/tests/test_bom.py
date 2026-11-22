from decimal import Decimal as D

from app.services.bom import requirements, shortages

RECIPES = [(1, None, 10, D("0.5")), (1, None, 11, D("3")),  # product 1 base: 0.5 kg flour, 3 eggs
           (1, 7, 10, D("1.2")),                              # variant 7 (2 kg): 1.2 kg flour, no eggs listed
           (2, None, 10, D("0.1"))]


def test_product_level_and_variant_override():
    need = requirements([(1, None, 2), (1, 8, 1), (1, 7, 1), (2, None, 5), (3, None, 4)], RECIPES)
    # (1,None,2): flour 1.0 eggs 6 ; (1,8,1): falls back to product recipe: flour .5 eggs 3 ;
    # (1,7,1): variant recipe only: flour 1.2 ; (2,None,5): flour .5 ; product 3 has no recipe
    assert need == {10: D("3.2"), 11: D("9")}


def test_no_recipe_no_requirements():
    assert requirements([(9, None, 3)], RECIPES) == {}


def test_shortages():
    assert shortages({10: D("3"), 11: D("2")}, {10: D("2.5"), 11: D("2")}) == {10: D("0.5")}
    assert shortages({12: D("1")}, {}) == {12: D("1")}
