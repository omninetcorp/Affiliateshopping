import os
import sys
import tempfile

sys.path.insert(0, '..')
from PIL import Image
from pipeline.slide_assembler import build_text_only_slide, add_text_overlay


def test_build_text_only_slide_creates_image():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "slide.jpg")
        build_text_only_slide(
            output_path=output_path,
            background_color="#FF0050",
            lines=["Get yours 👇", "$39.99", "Link in bio"],
            width=1080,
            height=1920,
        )
        assert os.path.exists(output_path)
        with Image.open(output_path) as img:
            assert img.size == (1080, 1920)


def test_add_text_overlay_returns_image():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Image.new("RGB", (1080, 1920), color="#333333")
        base_path = os.path.join(tmpdir, "base.jpg")
        base.save(base_path)
        output_path = os.path.join(tmpdir, "overlay.jpg")
        add_text_overlay(
            input_path=base_path,
            output_path=output_path,
            lines=["CUPSHE Bikini", "$39.99"],
            position="bottom",
        )
        assert os.path.exists(output_path)
        with Image.open(output_path) as img:
            assert img.size == (1080, 1920)


def test_text_only_slide_multiple_positions():
    with tempfile.TemporaryDirectory() as tmpdir:
        for position in ["top", "bottom", "center"]:
            base = Image.new("RGB", (1080, 1920), color="#111111")
            base_path = os.path.join(tmpdir, "base.jpg")
            base.save(base_path)
            output_path = os.path.join(tmpdir, f"overlay_{position}.jpg")
            add_text_overlay(
                input_path=base_path,
                output_path=output_path,
                lines=["Test Line"],
                position=position,
            )
            assert os.path.exists(output_path)
