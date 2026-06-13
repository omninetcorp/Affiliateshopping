"""
Virtual try-on using CatVTON.
Takes a generated person image + product garment image,
outputs the person wearing the actual product.
"""

import sys
import os
import numpy as np
from pathlib import Path
from PIL import Image, ImageFilter

# Add CatVTON to path
CATVTON_DIR = Path(r"C:\Users\james\CatVTON")
CATVTON_CKPT = CATVTON_DIR / "ckpt" / "CatVTON"
SD_INPAINT_CKPT = CATVTON_DIR / "ckpt" / "stable-diffusion-inpainting"

sys.path.insert(0, str(CATVTON_DIR))

_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    import torch
    from model.pipeline import CatVTONPipeline

    print("  Loading CatVTON pipeline...")
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    _pipeline = CatVTONPipeline(
        base_ckpt=str(SD_INPAINT_CKPT),
        attn_ckpt=str(CATVTON_CKPT),
        attn_ckpt_version="mix",
        weight_dtype=dtype,
        device="cuda",
        skip_safety_check=True,
        use_tf32=True,
    )
    print("  CatVTON ready.")
    return _pipeline


def _make_clothing_mask(person_img: Image.Image, cloth_type: str = "overall") -> Image.Image:
    """
    Generate a clothing mask from a person image using rembg for silhouette,
    then mask out the clothing region based on cloth_type.
    """
    from rembg import remove

    w, h = person_img.size

    # Get person silhouette
    rgba = remove(person_img.convert("RGBA"))
    alpha = np.array(rgba)[:, :, 3]  # Alpha channel = person mask

    # Build clothing region based on cloth_type
    mask = np.zeros((h, w), dtype=np.uint8)

    if cloth_type == "upper":
        # Top ~25% to ~60% of the person bounding box
        rows = np.where(alpha > 10)[0]
        if len(rows):
            top = rows.min()
            bottom = rows.max()
            body_h = bottom - top
            start = top + int(body_h * 0.12)   # below neck
            end = top + int(body_h * 0.60)     # waist
            mask[start:end, :] = alpha[start:end, :]
    elif cloth_type == "lower":
        rows = np.where(alpha > 10)[0]
        if len(rows):
            top = rows.min()
            bottom = rows.max()
            body_h = bottom - top
            start = top + int(body_h * 0.50)   # waist
            end = bottom
            mask[start:end, :] = alpha[start:end, :]
    else:  # overall — full body (swimwear, dresses)
        rows = np.where(alpha > 10)[0]
        if len(rows):
            top = rows.min()
            bottom = rows.max()
            body_h = bottom - top
            start = top + int(body_h * 0.12)   # below neck/face
            end = bottom
            mask[start:end, :] = alpha[start:end, :]

    # Threshold and dilate slightly so edges blend
    mask = (mask > 50).astype(np.uint8) * 255
    mask_img = Image.fromarray(mask, mode="L")
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=3))
    mask_img = mask_img.point(lambda p: 255 if p > 30 else 0)

    return mask_img


def apply_tryon(
    person_image_path: str,
    garment_image_path: str,
    output_path: str,
    cloth_type: str = "overall",
    num_steps: int = 50,
    guidance_scale: float = 2.5,
    seed: int = 42,
) -> str:
    """
    Run CatVTON virtual try-on.

    person_image_path: AI-generated base pose (from ComfyUI)
    garment_image_path: Amazon product photo (flat-lay or model shot)
    output_path: where to write result
    cloth_type: "upper", "lower", or "overall"
    Returns output_path on success, person_image_path on failure (fallback).
    """
    import torch
    from diffusers.image_processor import VaeImageProcessor
    from utils import resize_and_padding

    try:
        pipeline = _get_pipeline()

        person_img = Image.open(person_image_path).convert("RGB")
        garment_img = Image.open(garment_image_path).convert("RGB")

        # CatVTON works at 768x1024
        TW, TH = 768, 1024
        person_resized = resize_and_padding(person_img, (TW, TH))
        garment_resized = resize_and_padding(garment_img, (TW, TH))

        mask = _make_clothing_mask(person_resized, cloth_type)

        vae_processor = VaeImageProcessor(vae_scale_factor=8)
        mask_processor = VaeImageProcessor(
            vae_scale_factor=8,
            do_normalize=False,
            do_binarize=True,
            do_convert_grayscale=True,
        )

        person_tensor = vae_processor.preprocess(person_resized, TH, TW)
        garment_tensor = vae_processor.preprocess(garment_resized, TH, TW)
        mask_tensor = mask_processor.preprocess(mask, TH, TW)

        generator = torch.Generator(device="cuda").manual_seed(seed)
        result = pipeline(
            image=person_tensor,
            condition_image=garment_tensor,
            mask=mask_tensor,
            num_inference_steps=num_steps,
            guidance_scale=guidance_scale,
            height=TH,
            width=TW,
            generator=generator,
        )[0]

        # Scale back to original person size
        out_img = result.resize(person_img.size, Image.LANCZOS)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        out_img.save(output_path, "JPEG", quality=92)
        return output_path

    except Exception as e:
        print(f"  CatVTON failed ({e}), using base image instead")
        return person_image_path
