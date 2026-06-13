import math


def score_product(product: dict, min_price: float, max_price: float) -> dict:
    affiliate_score = _score_affiliate(product)
    popularity_score = _score_popularity(product)
    visual_score = _score_visual(product)
    price = product["price_usd"]
    price_score = _score_price(price, min_price, max_price)
    out_of_range = price < min_price or price > max_price

    total = round(
        (affiliate_score * 0.35)
        + (popularity_score * 0.35)
        + (visual_score * 0.15)
        + (price_score * 0.15),
        1,
    )

    # Hard cap for out-of-range prices — we can't reasonably promote them
    if out_of_range:
        total = min(total, 3.9)

    return {
        "affiliate_score": affiliate_score,
        "popularity_score": popularity_score,
        "visual_score": visual_score,
        "price_score": price_score,
        "total_score": total,
    }


def _score_affiliate(product: dict) -> float:
    commission = product.get("commission_pct", 0)
    price = product.get("price_usd", 0)
    estimated_commission = price * (commission / 100)

    if estimated_commission >= 10:
        return 10.0
    elif estimated_commission >= 5:
        return 8.0
    elif estimated_commission >= 2:
        return 6.0
    elif estimated_commission >= 1:
        return 4.0
    return 2.0


def _score_popularity(product: dict) -> float:
    review_count = product.get("review_count", 0)
    rating = product.get("rating", 0)
    bsr = product.get("best_seller_rank", 999999)

    review_score = min(10, math.log10(max(review_count, 1)) * 2.5)
    rating_score = max(0, (rating - 3.0) * 5)
    bsr_score = max(0, 10 - math.log10(max(bsr, 1)) * 1.5)

    return round((review_score + rating_score + bsr_score) / 3, 1)


def _score_visual(product: dict) -> float:
    return 8.0 if product.get("has_good_images") else 4.0


def _score_price(price: float, min_price: float, max_price: float) -> float:
    if price < min_price or price > max_price:
        return 2.0
    sweet_spot = (min_price + max_price) / 2
    distance = abs(price - sweet_spot) / sweet_spot
    return round(max(4.0, 10.0 - distance * 6), 1)
