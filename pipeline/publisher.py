import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


def post_carousel(metadata_path: str, accounts_catalog_path: str = None) -> dict:
    with open(metadata_path) as f:
        metadata = json.load(f)

    account = _load_account(metadata["account_id"], accounts_catalog_path)
    access_token = _get_access_token(account)

    slides_data = metadata["slides"]
    slide_paths = slides_data["tiktok"] if isinstance(slides_data, dict) else slides_data
    caption = _build_caption(metadata)

    print(f"  Posting {len(slide_paths)} slides to @{account['tiktok_username']}")
    print(f"  Caption preview: {caption[:80]}...")

    publish_id, upload_urls = _init_photo_post(slide_paths, caption, access_token)
    print(f"  Initialized post: {publish_id}")

    for i, (path, upload_url) in enumerate(zip(slide_paths, upload_urls)):
        print(f"  Uploading slide {i+1}/{len(slide_paths)}: {os.path.basename(path)}")
        _upload_image(path, upload_url)

    _wait_for_publish(publish_id, access_token)
    print(f"  Live: https://www.tiktok.com/@{account['tiktok_username']}")
    return {"publish_id": publish_id, "account_id": metadata["account_id"]}


def _build_caption(metadata: dict) -> str:
    title = metadata.get("title", "")
    hashtags = " ".join(metadata.get("hashtags", []))
    # TikTok captions don't support clickable links — direct to bio
    return f"{title}\n\nLink in bio! 👆\n\n{hashtags}"[:2200]


def _init_photo_post(slide_paths: list, caption: str, access_token: str) -> tuple:
    """One call to init the entire carousel. Returns (publish_id, [upload_url, ...])."""
    payload = {
        "media_type": "PHOTO",
        "post_info": {
            "title": caption,
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "auto_add_music": True,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "photo_images": [{"size": os.path.getsize(p)} for p in slide_paths],
            "photo_cover_index": 0,
        },
    }
    resp = requests.post(
        f"{TIKTOK_API_BASE}/post/publish/photo/init/",
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    return data["publish_id"], data["upload_url"]


def _upload_image(image_path: str, upload_url: str) -> None:
    file_size = os.path.getsize(image_path)
    with open(image_path, "rb") as f:
        image_data = f.read()
    resp = requests.put(
        upload_url,
        data=image_data,
        headers={
            "Content-Type": "image/jpeg",
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            "Content-Length": str(file_size),
        },
        timeout=60,
    )
    resp.raise_for_status()


def _wait_for_publish(publish_id: str, access_token: str, max_wait: int = 90) -> None:
    for _ in range(max_wait // 5):
        time.sleep(5)
        resp = requests.post(
            f"{TIKTOK_API_BASE}/post/publish/status/fetch/",
            json={"publish_id": publish_id},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            continue
        status = resp.json().get("data", {}).get("status", "")
        print(f"    Publish status: {status}")
        if status == "PUBLISH_COMPLETE":
            return
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"TikTok publish failed: {status}")
    print("  Warning: status check timed out — post likely still processing")


def _load_account(account_id: str, catalog_path: str = None) -> dict:
    if not catalog_path:
        catalog_path = Path(__file__).parent.parent / "accounts" / "catalog.json"
    with open(catalog_path) as f:
        catalog = json.load(f)
    for account in catalog["accounts"]:
        if account["id"] == account_id:
            return account
    raise ValueError(f"Account not found: {account_id}")


def _get_access_token(account: dict) -> str:
    suffix = account["credentials_env_suffix"]
    token = os.environ.get(f"TIKTOK_ACCESS_TOKEN_{suffix}")
    if not token:
        raise EnvironmentError(
            f"Missing env var: TIKTOK_ACCESS_TOKEN_{suffix}\n"
            "Get credentials at: https://developers.tiktok.com → Content Posting API"
        )
    return token


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.publisher output/<run_id>/metadata.json")
        sys.exit(1)
    result = post_carousel(sys.argv[1])
    print(result)
