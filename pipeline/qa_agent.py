import os

from PIL import Image

from pipeline.orchestrator import PLATFORM_SIZES


def validate_carousel(metadata: dict, config: dict) -> dict:
    errors = []
    warnings = []
    slides_data = metadata.get("slides", [])

    # Support new dict format {"tiktok": [...], "pinterest": [...]} and legacy list
    if isinstance(slides_data, dict):
        platform_slides = slides_data
    else:
        platform_slides = {"tiktok": slides_data}

    if not platform_slides or not any(platform_slides.values()):
        errors.append("No slides found in metadata")
        return {"passed": False, "errors": errors, "warnings": warnings}

    for platform, slides in platform_slides.items():
        expected_w, expected_h = PLATFORM_SIZES.get(platform, (1080, 1920))

        if len(slides) < 3:
            warnings.append(f"[{platform}] Only {len(slides)} slides — recommend at least 5")
        if len(slides) > 10:
            errors.append(f"[{platform}] TikTok API limit is 10 slides — got {len(slides)}")

        for path in slides:
            if not os.path.exists(path):
                errors.append(f"[{platform}] Slide file missing: {path}")
                continue

            file_size = os.path.getsize(path)
            if file_size < 10_000:
                warnings.append(f"[{platform}] Suspiciously small ({file_size} bytes): {os.path.basename(path)}")
            if file_size > 20_000_000:
                errors.append(f"[{platform}] Exceeds 20MB limit: {os.path.basename(path)}")

            try:
                with Image.open(path) as img:
                    w, h = img.size
                if w != expected_w or h != expected_h:
                    warnings.append(
                        f"[{platform}] Unexpected dimensions {w}x{h} (expected {expected_w}x{expected_h}): {os.path.basename(path)}"
                    )
            except Exception as e:
                errors.append(f"[{platform}] Cannot open {os.path.basename(path)}: {e}")

    if not metadata.get("affiliate_url"):
        warnings.append("No affiliate URL in metadata")
    if not metadata.get("title"):
        errors.append("Missing caption/title in metadata")

    return {"passed": len(errors) == 0, "errors": errors, "warnings": warnings}
