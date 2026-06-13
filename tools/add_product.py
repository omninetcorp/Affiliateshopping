"""
Add products to the backlog from a CSV file or a single URL.

BATCH MODE (recommended):
    python tools/add_product.py --csv tools/products.csv

SINGLE MODE:
    python tools/add_product.py --url "https://www.amazon.com/dp/B07XYZ1234" --niche womens-fashion

CSV FORMAT (tools/products.csv):
    url,niche_id
    https://www.amazon.com/dp/B07XYZ1234,womens-fashion
    https://www.amazon.com/dp/B08ABC5678,womens-fashion
    https://www.amazon.com/dp/B09DEF9012,kitchen-gadgets

The script auto-scrapes title, price, image, and rating from each Amazon page.
Just provide the URL and niche — nothing else needed.

Niche IDs:
    womens-fashion
    kitchen-gadgets
    beauty-tools
"""

import csv
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config.yaml"
BACKLOG_PATH = ROOT / "backlog.json"
PRODUCTS_DIR = ROOT / "products"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def run_csv(csv_path: str):
    if not os.path.exists(csv_path):
        print(f"ERROR: CSV file not found: {csv_path}")
        sys.exit(1)

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Found {len(rows)} products to process\n")
    success, skipped, failed = 0, 0, 0

    for i, row in enumerate(rows):
        url = row.get("url", "").strip()
        niche_id = row.get("niche_id", "").strip()

        if not url or not niche_id:
            print(f"[{i+1}/{len(rows)}] SKIP — missing url or niche_id")
            skipped += 1
            continue

        print(f"[{i+1}/{len(rows)}] {url}")
        try:
            result = _process_url(url, niche_id)
            if result == "exists":
                print(f"  Already in backlog — skipped")
                skipped += 1
            else:
                print(f"  Added: {result}")
                success += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1

        # Polite delay between Amazon requests
        if i < len(rows) - 1:
            time.sleep(2)

    print(f"\nDone. Added: {success} | Skipped: {skipped} | Failed: {failed}")
    if success > 0:
        print(f"\nGenerate carousels with:")
        print(f"  python pipeline/orchestrator.py")


def run_single(url: str, niche_id: str):
    try:
        result = _process_url(url, niche_id)
        if result == "exists":
            print("Already in backlog.")
        else:
            print(f"\nAdded: {result}")
            niche_id_out = niche_id
            print(f"\nGenerate carousel with:")
            print(f"  python pipeline/orchestrator.py {niche_id_out}")
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


def _process_url(url: str, niche_id: str) -> str:
    config = _load_config()
    niche = _find_niche(config, niche_id)
    if not niche:
        raise ValueError(f"Unknown niche '{niche_id}'. Valid: {[n['id'] for n in config['niches']]}")

    asin = _extract_asin(url)
    if not asin:
        raise ValueError(f"Could not extract ASIN from URL: {url}")

    product_id = f"{niche_id}-{asin.lower()}"

    backlog = _load_backlog()
    if any(e["product_id"] == product_id for e in backlog):
        return "exists"

    print(f"  Scraping Amazon page...")
    data = _scrape_amazon(asin)

    partner_tag = os.environ.get("AMAZON_PARTNER_TAG", "findwomenswea-20")
    affiliate_url = f"https://www.amazon.com/dp/{asin}?tag={partner_tag}"
    commission_pct = niche.get("commission_target_pct", 8.0)
    price = data["price"]

    product = {
        "product_id": product_id,
        "niche_id": niche_id,
        "source": "manual-csv",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "status": "queued",
        "product": {
            "title": data["title"],
            "asin": asin,
            "url": f"https://www.amazon.com/dp/{asin}",
            "price_usd": price,
            "image_urls": [data["image_url"]] if data["image_url"] else [],
            "primary_image_url": data["image_url"],
            "rating": data["rating"],
            "review_count": data["review_count"],
            "best_seller_rank": 999,
            "category": niche.get("amazon_category", ""),
        },
        "affiliate": {
            "program": "amazon-associates",
            "partner_tag": partner_tag,
            "affiliate_url": affiliate_url,
            "commission_pct": commission_pct,
            "estimated_commission_usd": round(price * (commission_pct / 100), 2),
        },
        "scoring": {
            "affiliate_score": 7.0,
            "popularity_score": 7.0,
            "visual_score": 8.0 if data["image_url"] else 4.0,
            "price_score": 8.0,
            "total_score": 7.5,
            "score_reason": "Manual CSV import",
        },
        "slide_plan": {
            "template_id": niche.get("template_id"),
            "format": "single-product",
            "product_description": data["title"].lower()[:120],
        },
    }

    os.makedirs(PRODUCTS_DIR, exist_ok=True)
    product_path = PRODUCTS_DIR / f"{product_id}.json"
    with open(product_path, "w") as f:
        json.dump(product, f, indent=2)

    backlog.append({
        "product_id": product_id,
        "niche_id": niche_id,
        "title": data["title"],
        "analysis_path": f"products/{product_id}.json",
        "total_score": 7.5,
        "status": "queued",
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "published_at": None,
    })
    _save_backlog(backlog)

    return product_id


def _scrape_amazon(asin: str) -> dict:
    url = f"https://www.amazon.com/dp/{asin}"
    req = urllib.request.Request(url, headers=HEADERS)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch Amazon page: {e}")

    if "Enter the characters you see below" in html or "Type the characters" in html:
        raise RuntimeError("Amazon returned a CAPTCHA — try again later or add product manually")

    title = _extract_title(html)
    price = _extract_price(html)
    image_url = _extract_image(html)
    rating = _extract_rating(html)
    review_count = _extract_review_count(html)

    print(f"  Title:   {title[:60]}...")
    print(f"  Price:   ${price}")
    print(f"  Rating:  {rating} ({review_count} reviews)")
    print(f"  Image:   {'found' if image_url else 'not found'}")

    return {
        "title": title,
        "price": price,
        "image_url": image_url,
        "rating": rating,
        "review_count": review_count,
    }


def _extract_title(html: str) -> str:
    match = re.search(r'id="productTitle"[^>]*>\s*([^<]+)', html)
    if match:
        return match.group(1).strip()
    match = re.search(r'"title"\s*:\s*"([^"]{10,})"', html)
    return match.group(1).strip() if match else "Unknown Product"


def _extract_price(html: str) -> float:
    patterns = [
        r'class="a-price-whole">([0-9,]+)<',
        r'"price"\s*:\s*"?\$?([0-9]+\.[0-9]{2})',
        r'priceAmount["\s:]+([0-9]+\.[0-9]{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                continue
    return 0.0


def _extract_image(html: str) -> str:
    # Try landing image JSON first
    match = re.search(r'"large"\s*:\s*"(https://m\.media-amazon\.com/images/I/[^"]+)"', html)
    if match:
        return match.group(1)
    # Try og:image meta tag
    match = re.search(r'property="og:image"\s+content="([^"]+)"', html)
    if match:
        return match.group(1)
    # Try data-old-hires attribute
    match = re.search(r'data-old-hires="(https://[^"]+)"', html)
    return match.group(1) if match else ""


def _extract_rating(html: str) -> float:
    match = re.search(r'"ratingScore"\s*:\s*"?([0-9.]+)"?', html)
    if match:
        return float(match.group(1))
    match = re.search(r'([0-9.]+) out of 5 stars', html)
    return float(match.group(1)) if match else 0.0


def _extract_review_count(html: str) -> int:
    match = re.search(r'"totalReviewCount"\s*:\s*([0-9]+)', html)
    if match:
        return int(match.group(1))
    match = re.search(r'([0-9,]+)\s+ratings', html)
    if match:
        return int(match.group(1).replace(",", ""))
    return 0


def _extract_asin(url: str) -> str | None:
    match = re.search(r"/dp/([A-Z0-9]{10})", url)
    if match:
        return match.group(1)
    match = re.search(r"[?&]asin=([A-Z0-9]{10})", url)
    return match.group(1) if match else None


def _load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _find_niche(config: dict, niche_id: str) -> dict | None:
    for niche in config["niches"]:
        if niche["id"] == niche_id:
            return niche
    return None


def _load_backlog() -> list:
    if not BACKLOG_PATH.exists():
        return []
    with open(BACKLOG_PATH) as f:
        return json.load(f)


def _save_backlog(backlog: list):
    with open(BACKLOG_PATH, "w") as f:
        json.dump(backlog, f, indent=2)


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--csv" in args:
        idx = args.index("--csv")
        csv_path = args[idx + 1] if idx + 1 < len(args) else "tools/products.csv"
        run_csv(csv_path)

    elif "--url" in args and "--niche" in args:
        url = args[args.index("--url") + 1]
        niche = args[args.index("--niche") + 1]
        run_single(url, niche)

    else:
        print(__doc__)
        sys.exit(1)
