import os

from PIL import Image, ImageDraw, ImageFont


DEFAULT_FONT_SIZE = 64
DEFAULT_TEXT_COLOR = "#FFFFFF"
DEFAULT_SHADOW_COLOR = "#000000"


def build_text_only_slide(
    output_path: str,
    background_color: str,
    lines: list,
    width: int = 1080,
    height: int = 1920,
    font_path: str = None,
) -> str:
    img = Image.new("RGB", (width, height), color=background_color)
    draw = ImageDraw.Draw(img)
    font = _load_font(font_path, DEFAULT_FONT_SIZE)

    line_height = DEFAULT_FONT_SIZE + 24
    total_height = len(lines) * line_height
    y = (height - total_height) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        _draw_text_with_shadow(draw, x, y, line, font)
        y += line_height

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, "JPEG", quality=95)
    return output_path


def add_text_overlay(
    input_path: str,
    output_path: str,
    lines: list,
    position: str = "bottom",
    font_path: str = None,
    font_size: int = 48,
) -> str:
    img = Image.open(input_path).convert("RGB")
    width, height = img.size
    font = _load_font(font_path, font_size)

    padding = 40
    line_height = font_size + 16
    total_height = len(lines) * line_height

    if position == "bottom":
        y = height - total_height - padding * 2
    elif position == "top":
        y = padding
    else:
        y = (height - total_height) // 2

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(
        [(0, y - padding), (width, y + total_height + padding)],
        fill=(0, 0, 0, 140),
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        _draw_text_with_shadow(draw, x, y, line, font, size=font_size)
        y += line_height

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, "JPEG", quality=95)
    return output_path


def _load_font(font_path: str = None, size: int = DEFAULT_FONT_SIZE):
    if font_path and os.path.exists(font_path):
        return ImageFont.truetype(font_path, size)
    for fallback in ["arial.ttf", "Arial.ttf", "DejaVuSans-Bold.ttf"]:
        try:
            return ImageFont.truetype(fallback, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_text_with_shadow(draw, x, y, text, font, size=DEFAULT_FONT_SIZE, offset=3):
    draw.text((x + offset, y + offset), text, font=font, fill=DEFAULT_SHADOW_COLOR)
    draw.text((x, y), text, font=font, fill=DEFAULT_TEXT_COLOR)
