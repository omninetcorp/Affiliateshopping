import json
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def load_template(template_id: str) -> dict:
    path = TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {template_id}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_slide_prompts(template: dict, product: dict, model: dict) -> list:
    slides = []
    product_desc = product["slide_plan"]["product_description"]
    price = product["product"]["price_usd"]
    review_count = product["product"]["review_count"]
    product_title = product["product"]["title"][:50]

    for slide_def in template["slides"]:
        # Skip meta/note slides (roundup repeat blocks)
        if not isinstance(slide_def.get("index"), int):
            continue

        slide = dict(slide_def)

        if slide.get("prompt_template"):
            slide["prompt"] = (
                slide["prompt_template"]
                .replace("{model_base_prompt}", model["base_prompt"])
                .replace("{product_description}", product_desc)
            )

        if slide.get("text_overlay"):
            overlay = {}
            for k, v in slide["text_overlay"].items():
                overlay[k] = (
                    str(v)
                    .replace("{price_usd}", str(price))
                    .replace("{review_count}", str(review_count))
                    .replace("{product_title}", product_title)
                )
            slide["text_overlay"] = overlay

        slide["negative_prompt"] = model.get("negative_prompt", "ugly, deformed, blurry, watermark")
        slide["lora_name"] = model.get("lora")
        slide["lora_weight"] = model.get("lora_weight", 0.85)
        slides.append(slide)

    return slides
