"""
Daily automation runner.
Called by Windows Task Scheduler at each post time (e.g. 09:00 and 18:00).
Generates one carousel and posts it to TikTok, enforcing daily limits.

Usage:
    python run_pipeline.py [niche_id]
    python run_pipeline.py womens-fashion
"""

import json
import logging
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
POSTS_LOG = LOGS_DIR / "posts.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "pipeline.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def main():
    niche_id = sys.argv[1] if len(sys.argv) > 1 else None
    config = _load_config()

    # ── daily limit check ────────────────────────────────────────────────
    posts_today = _count_today_posts()
    daily_limit = config["posting"]["new_account_daily_limit"]
    if posts_today >= daily_limit:
        log.info(f"Daily limit reached ({posts_today}/{daily_limit}). Nothing to do.")
        return

    log.info(f"=== Pipeline run: post {posts_today + 1} of {daily_limit} today ===")

    # ── wait for ComfyUI to be ready ─────────────────────────────────────
    if not _wait_for_comfyui():
        log.error("ComfyUI not reachable at localhost:8188. Is it running?")
        sys.exit(1)

    # ── generate carousel ─────────────────────────────────────────────────
    log.info("Generating carousel...")
    from pipeline.orchestrator import run_one
    metadata = run_one(niche_id=niche_id)
    if not metadata:
        log.warning("Backlog is empty — no queued products. Add products first.")
        return

    run_id = metadata["run_id"]
    metadata_path = str(ROOT / "output" / run_id / "metadata.json")
    log.info(f"Carousel ready: output/{run_id}/")

    # ── post to TikTok ───────────────────────────────────────────────────
    log.info("Posting to TikTok...")
    from pipeline.publisher import post_carousel
    result = post_carousel(metadata_path)

    # ── mark published in backlog ────────────────────────────────────────
    from pipeline.backlog_manager import update_status
    update_status(metadata["product_id"], "published", run_id=run_id)

    # ── record to posts log ──────────────────────────────────────────────
    _record_post(run_id, metadata["account_id"], result.get("publish_id"))

    log.info(f"=== Done. run_id={run_id}  publish_id={result.get('publish_id')} ===")


def _wait_for_comfyui(host: str = "localhost:8188", retries: int = 6, delay: int = 10) -> bool:
    import urllib.request
    for i in range(retries):
        try:
            urllib.request.urlopen(f"http://{host}/system_stats", timeout=5)
            return True
        except Exception:
            if i < retries - 1:
                log.info(f"  ComfyUI not ready, retrying in {delay}s... ({i+1}/{retries})")
                time.sleep(delay)
    return False


def _count_today_posts() -> int:
    if not POSTS_LOG.exists():
        return 0
    with open(POSTS_LOG) as f:
        posts = json.load(f)
    today = date.today().isoformat()
    return sum(1 for p in posts if p["date"] == today)


def _record_post(run_id: str, account_id: str, publish_id: str = None):
    posts = []
    if POSTS_LOG.exists():
        with open(POSTS_LOG) as f:
            posts = json.load(f)
    posts.append({
        "date": date.today().isoformat(),
        "run_id": run_id,
        "account_id": account_id,
        "publish_id": publish_id,
        "posted_at": datetime.now(timezone.utc).isoformat(),
    })
    with open(POSTS_LOG, "w") as f:
        json.dump(posts, f, indent=2)


def _load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    main()
