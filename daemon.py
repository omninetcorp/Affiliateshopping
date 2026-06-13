"""
TikTok Affiliate Daemon
Runs continuously in a terminal. Generates carousels on schedule,
pauses for your approval, then posts to TikTok.

Usage:
    "C:\\Users\\james\\ComfyUI\\venv\\Scripts\\python.exe" daemon.py
    "C:\\Users\\james\\ComfyUI\\venv\\Scripts\\python.exe" daemon.py womens-fashion

Press Ctrl+C to stop cleanly.
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
LOGS_DIR = ROOT / "logs"
POSTS_LOG = LOGS_DIR / "posts.json"
LOGS_DIR.mkdir(exist_ok=True)

# ── logging: file + console ───────────────────────────────────────────────────
log = logging.getLogger("daemon")
log.setLevel(logging.INFO)
fmt = logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S")
fh = logging.FileHandler(LOGS_DIR / "daemon.log", encoding="utf-8")
fh.setFormatter(fmt)
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(fmt)
log.addHandler(fh)
log.addHandler(sh)


def main():
    niche_id = sys.argv[1] if len(sys.argv) > 1 else None
    config = _load_config()
    post_times = config["posting"]["post_times"]          # e.g. ["09:00","18:00","20:00"]
    daily_limit = config["posting"]["new_account_daily_limit"]  # 2 or 3

    _banner(post_times, daily_limit)

    while True:
        try:
            now = datetime.now()
            next_dt = _next_post_time(now, post_times)
            _sleep_until(next_dt)

            posts_today = _count_today_posts()
            if posts_today >= daily_limit:
                log.info(f"Daily limit reached ({posts_today}/{daily_limit}). Sleeping until tomorrow.")
                _sleep_until(_tomorrow_first_post(post_times))
                continue

            _run_post(niche_id, posts_today, daily_limit)

        except KeyboardInterrupt:
            print("\n\nStopped. Goodbye.")
            sys.exit(0)
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            log.info("Retrying in 5 minutes...")
            time.sleep(300)


def _run_post(niche_id, posts_today, daily_limit):
    log.info(f"━━━ Starting post {posts_today + 1} of {daily_limit} ━━━")

    # ── check ComfyUI ─────────────────────────────────────────────────────────
    if not _wait_for_comfyui():
        log.error("ComfyUI not reachable at localhost:8188 — start it and retry.")
        log.info("Start ComfyUI: C:\\Users\\james\\ComfyUI\\start.bat")
        _prompt_continue()
        return

    # ── generate carousel ─────────────────────────────────────────────────────
    log.info("Generating carousel (this takes a few minutes)...")
    from pipeline.orchestrator import run_one
    metadata = run_one(niche_id=niche_id)

    if not metadata:
        log.warning("Backlog is empty — add more products with: python tools/add_product.py --csv tools/products.csv")
        return

    run_id = metadata["run_id"]
    slides_dir = ROOT / "output" / run_id / "tiktok"
    affiliate_url = metadata.get("affiliate_url", "")
    caption = metadata.get("title", "")

    # ── show review info ──────────────────────────────────────────────────────
    print()
    print("─" * 60)
    print(f"  READY TO REVIEW: output/{run_id}/tiktok/")
    print(f"  Product : {caption[:70]}")
    print(f"  Link    : {affiliate_url}")
    print("─" * 60)

    # Open folder in Explorer for visual review
    subprocess.Popen(f'explorer "{slides_dir}"')
    print("  (Slides folder opened in Explorer)")
    print()

    # ── approval prompt ───────────────────────────────────────────────────────
    while True:
        answer = input("  Post to TikTok? [y]es / [n]o / [r]etry generate : ").strip().lower()
        if answer in ("y", "yes"):
            _do_post(metadata)
            break
        elif answer in ("n", "no", "skip", "s"):
            log.info("Skipped by user.")
            # Keep status as ready_to_post so it can be posted later
            break
        elif answer in ("r", "retry"):
            log.info("Regenerating...")
            from pipeline.backlog_manager import update_status
            update_status(metadata["product_id"], "queued")
            _run_post(niche_id, posts_today, daily_limit)
            return
        else:
            print("  Please type y, n, or r.")


def _do_post(metadata):
    run_id = metadata["run_id"]
    metadata_path = str(ROOT / "output" / run_id / "metadata.json")

    log.info("Posting to TikTok...")
    from pipeline.publisher import post_carousel
    result = post_carousel(metadata_path)

    from pipeline.backlog_manager import update_status
    update_status(metadata["product_id"], "published", run_id=run_id)

    _record_post(run_id, metadata["account_id"], result.get("publish_id"))
    log.info(f"Posted! publish_id={result.get('publish_id')}")
    print()


def _sleep_until(target: datetime):
    """Sleep in 1-minute ticks, printing a countdown."""
    while True:
        now = datetime.now()
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        print(f"\r  Next post at {target.strftime('%H:%M')} — {mins:02d}:{secs:02d} remaining   ", end="", flush=True)
        time.sleep(min(30, remaining))
    print()


def _next_post_time(now: datetime, post_times: list) -> datetime:
    """Return the next scheduled datetime after now."""
    today = now.date()
    for t in sorted(post_times):
        h, m = map(int, t.split(":"))
        candidate = datetime(today.year, today.month, today.day, h, m)
        if candidate > now + timedelta(seconds=30):
            return candidate
    # All times passed today — use first time tomorrow
    h, m = map(int, sorted(post_times)[0].split(":"))
    tomorrow = today + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, h, m)


def _tomorrow_first_post(post_times: list) -> datetime:
    from datetime import date, timedelta
    tomorrow = date.today() + timedelta(days=1)
    h, m = map(int, sorted(post_times)[0].split(":"))
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, h, m)


def _wait_for_comfyui(host: str = "localhost:8188", retries: int = 3, delay: int = 5) -> bool:
    import urllib.request
    for i in range(retries):
        try:
            urllib.request.urlopen(f"http://{host}/system_stats", timeout=5)
            return True
        except Exception:
            if i < retries - 1:
                time.sleep(delay)
    return False


def _prompt_continue():
    input("  Press Enter when ComfyUI is ready to retry, or Ctrl+C to stop: ")


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
        "posted_at": datetime.now().isoformat(),
    })
    with open(POSTS_LOG, "w") as f:
        json.dump(posts, f, indent=2)


def _load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def _banner(post_times, daily_limit):
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║      TikTok Affiliate Pipeline Daemon        ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║  Post times : {', '.join(post_times):<30} ║")
    print(f"║  Daily limit: {daily_limit} per account{' ' * 22}║")
    print("║  Ctrl+C to stop cleanly                      ║")
    print("╚══════════════════════════════════════════════╝")
    print()


if __name__ == "__main__":
    main()
