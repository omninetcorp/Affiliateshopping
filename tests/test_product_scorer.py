import sys
sys.path.insert(0, '..')
from phase1.product_scorer import score_product


def test_high_score_product():
    product = {
        "price_usd": 45.0,
        "commission_pct": 10.0,
        "rating": 4.5,
        "review_count": 3000,
        "best_seller_rank": 50,
        "has_good_images": True,
    }
    result = score_product(product, min_price=15, max_price=120)
    assert result["total_score"] >= 7.0
    assert "affiliate_score" in result
    assert "popularity_score" in result
    assert "visual_score" in result


def test_low_score_cheap_product():
    product = {
        "price_usd": 5.0,
        "commission_pct": 3.0,
        "rating": 3.2,
        "review_count": 12,
        "best_seller_rank": 50000,
        "has_good_images": False,
    }
    result = score_product(product, min_price=15, max_price=120)
    assert result["total_score"] < 5.0


def test_score_outside_price_range():
    product = {
        "price_usd": 500.0,
        "commission_pct": 8.0,
        "rating": 4.8,
        "review_count": 5000,
        "best_seller_rank": 10,
        "has_good_images": True,
    }
    result = score_product(product, min_price=15, max_price=120)
    assert result["total_score"] < 4.0
