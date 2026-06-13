import os
import urllib.parse
from datetime import datetime, timezone

from phase1.product_scorer import score_product


def discover_amazon_products(niche_config: dict, limit: int = 20) -> list:
    try:
        from paapi5_python_sdk.api.default_api import DefaultApi
        from paapi5_python_sdk.models.search_items_request import SearchItemsRequest
        from paapi5_python_sdk.models.partner_type import PartnerType
        from paapi5_python_sdk.rest import ApiException
    except ImportError:
        print("paapi5-python-sdk not installed. Run: pip install paapi5-python-sdk")
        return []

    api = _build_client(DefaultApi)
    results = []

    for keyword in niche_config.get("amazon_keywords", []):
        if len(results) >= limit:
            break
        try:
            items = _search(api, keyword, niche_config["amazon_category"], limit, SearchItemsRequest, PartnerType)
            for item in items:
                product = _parse_item(item, niche_config)
                if product:
                    results.append(product)
                if len(results) >= limit:
                    break
        except ApiException as e:
            print(f"Amazon API error for '{keyword}': {e}")
            continue

    return results[:limit]


def _build_client(DefaultApi):
    return DefaultApi(
        access_key=os.environ["AMAZON_ACCESS_KEY"],
        secret_key=os.environ["AMAZON_SECRET_KEY"],
        host="webservices.amazon.com",
        region=os.environ.get("AMAZON_REGION", "us-east-1"),
    )


def _search(api, keyword, category, limit, SearchItemsRequest, PartnerType):
    request = SearchItemsRequest(
        partner_tag=os.environ["AMAZON_PARTNER_TAG"],
        partner_type=PartnerType.ASSOCIATES,
        keywords=keyword,
        search_index=category,
        item_count=min(limit, 10),
        resources=[
            "Images.Primary.Large",
            "Images.Variants.Large",
            "ItemInfo.Title",
            "ItemInfo.ByLineInfo",
            "Offers.Listings.Price",
            "CustomerReviews.Count",
            "CustomerReviews.StarRating",
            "BrowseNodeInfo.BrowseNodes.SalesRank",
        ],
    )
    response = api.search_items(request)
    return response.search_result.items if response.search_result else []


def _parse_item(item, niche_config: dict) -> dict | None:
    try:
        title = item.item_info.title.display_value
        asin = item.asin
        price = item.offers.listings[0].price.amount if item.offers and item.offers.listings else None
        if not price:
            return None

        primary_image = item.images.primary.large.url if item.images and item.images.primary else None
        variant_images = []
        if item.images and item.images.variants:
            variant_images = [v.large.url for v in item.images.variants[:4]]

        review_count = 0
        rating = 0.0
        if item.customer_reviews:
            review_count = item.customer_reviews.count or 0
            rating = float(item.customer_reviews.star_rating.value or 0)

        bsr = 999999
        if item.browse_node_info and item.browse_node_info.browse_nodes:
            for node in item.browse_node_info.browse_nodes:
                if node.sales_rank:
                    bsr = min(bsr, node.sales_rank)

        partner_tag = os.environ["AMAZON_PARTNER_TAG"]
        affiliate_url = f"https://www.amazon.com/dp/{asin}?tag={partner_tag}"

        scoring = score_product(
            {
                "price_usd": float(price),
                "commission_pct": 8.0,
                "rating": rating,
                "review_count": review_count,
                "best_seller_rank": bsr,
                "has_good_images": primary_image is not None,
            },
            min_price=niche_config.get("price_min", 10),
            max_price=niche_config.get("price_max", 200),
        )

        return {
            "product_id": f"{niche_config['id']}-{asin.lower()}",
            "niche_id": niche_config["id"],
            "source": "amazon",
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "status": "queued",
            "product": {
                "title": title,
                "asin": asin,
                "url": f"https://www.amazon.com/dp/{asin}",
                "price_usd": float(price),
                "image_urls": ([primary_image] + variant_images) if primary_image else [],
                "primary_image_url": primary_image,
                "rating": rating,
                "review_count": review_count,
                "best_seller_rank": bsr,
                "category": niche_config.get("amazon_category", ""),
            },
            "affiliate": {
                "program": "amazon-associates",
                "partner_tag": partner_tag,
                "affiliate_url": affiliate_url,
                "commission_pct": 8.0,
                "estimated_commission_usd": round(float(price) * 0.08, 2),
            },
            "scoring": scoring,
            "slide_plan": {
                "template_id": niche_config.get("template_id"),
                "format": "single-product",
                "product_description": title.lower()[:120],
            },
        }
    except Exception as e:
        print(f"Failed to parse item {getattr(item, 'asin', '?')}: {e}")
        return None
