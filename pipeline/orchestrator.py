import json
import os
import sys
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
import yaml
from dotenv import load_dotenv

from pipeline.backlog_manager import pick_next, update_status
from pipeline.model_selector import pick_model
from pipeline.template_selector import load_template, build_slide_prompts
from pipeline.image_generator import generate_slide
from pipeline.slide_assembler import build_text_only_slide, add_text_overlay
from pipeline.tryon import apply_tryon

load_dotenv()
ROOT = Path(__file__).parent.parent

# Per-platform export sizes. Add new platforms here; pipeline handles the rest.
PLATFORM_SIZES = {
    "tiktok": (1080, 1920),       # 9:16 full-screen vertical
    "pinterest": (1000, 1500),    # 2:3 optimal for Pinterest feed
}

# SDXL-native generation resolution. Close to 9:16 — avoids the vertical
# stretch that occurred with the old 832×1216 → 1080×1920 upscale.
GEN_W, GEN_H = 768, 1344


def run_one(niche_id: str = None):
    config = _load_config()
    entry = pick_next(niche_id=niche_id)

    if not entry:
        print("No queued products found.")
        return None

    product_id = entry["product_id"]
    print(f"\nProcessing: {product_id}")
    update_status(product_id, "in_progress")

    try:
        product = _load_product(entry["analysis_path"])
        niche = _find_niche(config, product["niche_id"])
        account_id = niche["account_id"]

        model = pick_model(
            niche_id=product["niche_id"],
            account_id=account_id,
            rotation_window=config["posting"]["model_rotation_window"],
        )
        template = load_template(product["slide_plan"]["template_id"])
        slides_plan = build_slide_prompts(template, product, model)

        run_id = str(uuid.uuid4())[:8]
        assets_dir = ROOT / "assets" / run_id
        os.makedirs(assets_dir, exist_ok=True)
        for platform in PLATFORM_SIZES:
            os.makedirs(ROOT / "output" / run_id / platform, exist_ok=True)

        platform_slides = {p: [] for p in PLATFORM_SIZES}

        for i, slide in enumerate(slides_plan):
            print(f"  Generating slide {i+1}/{len(slides_plan)}: {slide['role']}")
            slide_name = f"slide_{i+1:02d}.jpg"

            if slide.get("generation") == "text-only":
                lines = [v for v in slide.get("text_overlay", {}).values() if v]
                for platform, (pw, ph) in PLATFORM_SIZES.items():
                    out = str(ROOT / "output" / run_id / platform / slide_name)
                    build_text_only_slide(
                        output_path=out,
                        background_color=slide.get("background_color", "#000000"),
                        lines=lines,
                        width=pw,
                        height=ph,
                    )
                    platform_slides[platform].append(out)
                print(f"    Saved (all platforms)")

            else:
                ref_image = None
                if slide.get("use_product_reference"):
                    ref_image = _fetch_ref_image(
                        product["product"].get("primary_image_url"),
                        assets_dir / f"ref_{i+1}.jpg",
                    )

                gen_path = str(assets_dir / f"slide_{i+1:02d}_gen.jpg")
                is_hero = (slide["role"] == "hero-shot")

                # Hero shot: generate pose only, CatVTON places real product on model
                # Other slides: IP-Adapter guides color/pattern from product ref image
                generate_slide(
                    prompt=slide["prompt"],
                    negative_prompt=slide["negative_prompt"],
                    output_path=gen_path,
                    reference_image_path=None if is_hero else ref_image,
                    reference_strength=slide.get("reference_strength", 0.5),
                    width=GEN_W,
                    height=GEN_H,
                    lora_name=slide.get("lora_name"),
                    lora_weight=slide.get("lora_weight", 0.85),
                )

                if is_hero and ref_image and os.path.exists(ref_image):
                    print(f"    Applying CatVTON try-on...")
                    tryon_path = str(assets_dir / f"slide_{i+1:02d}_tryon.jpg")
                    tryon_result = apply_tryon(
                        person_image_path=gen_path,
                        garment_image_path=ref_image,
                        output_path=tryon_path,
                        cloth_type="overall",
                    )
                    # img2img sharpening pass: restores SDXL quality lost in CatVTON's SD1.5 base
                    sharpened_path = str(assets_dir / f"slide_{i+1:02d}_sharp.jpg")
                    generate_slide(
                        prompt=slide["prompt"],
                        negative_prompt=slide["negative_prompt"],
                        output_path=sharpened_path,
                        reference_image_path=tryon_result,
                        reference_strength=0.25,
                        width=GEN_W,
                        height=GEN_H,
                        lora_name=None,
                        lora_weight=0.85,
                    )
                    gen_path = sharpened_path

                # Export to each platform: cover-resize from GEN resolution
                for platform, (pw, ph) in PLATFORM_SIZES.items():
                    raw_path = str(assets_dir / f"slide_{i+1:02d}_{platform}_raw.jpg")
                    out = str(ROOT / "output" / run_id / platform / slide_name)
                    _resize_cover(gen_path, raw_path, pw, ph)
                    if slide.get("text_overlay"):
                        lines = [v for v in slide["text_overlay"].values() if v]
                        add_text_overlay(raw_path, out, lines, position="bottom")
                    else:
                        os.rename(raw_path, out)
                    platform_slides[platform].append(out)

                print(f"    Saved (all platforms)")

        metadata = {
            "run_id": run_id,
            "product_id": product_id,
            "account_id": account_id,
            "affiliate_url": product["affiliate"]["affiliate_url"],
            "title": _generate_caption(product),
            "hashtags": _generate_hashtags(niche),
            "slides": platform_slides,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        metadata_path = ROOT / "output" / run_id / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        update_status(product_id, "ready_to_post", run_id=run_id)
        print(f"\nCarousel ready: output/{run_id}/")
        return metadata

    except Exception as e:
        print(f"Pipeline failed for {product_id}: {e}")
        update_status(product_id, "failed", error=str(e))
        raise


def _resize_cover(src: str, dest: str, w: int, h: int) -> None:
    """Scale to fill w×h, center-crop any excess. No letterboxing."""
    with Image.open(src) as img:
        src_w, src_h = img.size
        scale = max(w / src_w, h / src_h)
        new_w = round(src_w * scale)
        new_h = round(src_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        img = img.crop((left, top, left + w, top + h))
        img.save(dest, "JPEG", quality=92)


def _fetch_ref_image(url: str, dest: Path) -> str | None:
    if not url:
        return None
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            dest.write_bytes(r.read())
        return str(dest)
    except Exception as e:
        print(f"    Warning: could not download reference image: {e}")
        return None


def _load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def _load_product(analysis_path: str) -> dict:
    with open(ROOT / analysis_path) as f:
        return json.load(f)


def _find_niche(config: dict, niche_id: str) -> dict:
    for niche in config["niches"]:
        if niche["id"] == niche_id:
            return niche
    raise ValueError(f"Niche not found: {niche_id}")


def _generate_caption(product: dict) -> str:
    title = product["product"]["title"][:60]
    price = product["product"]["price_usd"]
    return f"{title} — only ${price:.2f}! 🔥 Link in bio"


def _generate_hashtags(niche: dict) -> list:
    base = ["#tiktokmademebuyit", "#amazonfinds", "#affiliate"]
    niche_tags = {
        "womens-swimwear": ["#swimwear", "#bikini", "#beachlife", "#swimsuit"],
        "kitchen-gadgets": ["#kitchengadgets", "#cooking", "#amazonkitchen", "#kitchenhacks"],
        "beauty-tools": ["#beautytips", "#skincare", "#makeuptools", "#glowup"],
    }
    return base + niche_tags.get(niche["id"], [])


if __name__ == "__main__":
    niche = sys.argv[1] if len(sys.argv) > 1 else None
    run_one(niche_id=niche)
