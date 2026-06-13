import json
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from phase1.amazon_scraper import discover_amazon_products

load_dotenv()

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config.yaml"
BACKLOG_PATH = ROOT / "backlog.json"
PRODUCTS_DIR = ROOT / "products"


def run(config_path=CONFIG_PATH, backlog_path=BACKLOG_PATH, products_dir=PRODUCTS_DIR):
    with open(config_path) as f:
        config = yaml.safe_load(f)

    backlog = load_backlog(backlog_path)
    limit = config["research"]["products_per_niche_per_run"]
    min_score = config["research"]["min_affiliate_score"]
    new_count = 0

    for niche in config["niches"]:
        print(f"\nResearching niche: {niche['label']}")
        products = discover_amazon_products(niche, limit=limit)

        for product in products:
            if is_already_queued(product["product_id"], backlog):
                print(f"  Skip (already queued): {product['product_id']}")
                continue

            if product["scoring"]["total_score"] < min_score:
                print(f"  Skip (score {product['scoring']['total_score']} < {min_score}): {product['product_id']}")
                continue

            write_product(product, products_dir=str(products_dir))
            backlog.append({
                "product_id": product["product_id"],
                "niche_id": product["niche_id"],
                "title": product["product"]["title"],
                "analysis_path": f"products/{product['product_id']}.json",
                "total_score": product["scoring"]["total_score"],
                "status": "queued",
                "queued_at": product["discovered_at"],
                "published_at": None,
            })
            new_count += 1
            print(f"  Queued (score {product['scoring']['total_score']}): {product['product_id']}")

    save_backlog(backlog, backlog_path)
    print(f"\nPhase 1 complete. {new_count} new products queued. Backlog total: {len(backlog)}")


def write_product(product: dict, products_dir: str = str(PRODUCTS_DIR)) -> str:
    os.makedirs(products_dir, exist_ok=True)
    path = os.path.join(products_dir, f"{product['product_id']}.json")
    with open(path, "w") as f:
        json.dump(product, f, indent=2)
    return path


def load_backlog(backlog_path=BACKLOG_PATH) -> list:
    if not os.path.exists(backlog_path):
        return []
    with open(backlog_path) as f:
        return json.load(f)


def save_backlog(backlog: list, backlog_path=BACKLOG_PATH):
    with open(backlog_path, "w") as f:
        json.dump(backlog, f, indent=2)


def is_already_queued(product_id: str, backlog: list) -> bool:
    return any(entry["product_id"] == product_id for entry in backlog)


if __name__ == "__main__":
    run()
