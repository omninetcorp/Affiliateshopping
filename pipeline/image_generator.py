import json
import os
import random
import urllib.request
import urllib.parse
import uuid

import websocket


COMFYUI_HOST = "localhost:8188"

IPADAPTER_MODEL = "ip-adapter_sdxl.safetensors"
CLIP_VISION_MODEL = "ip-adapter-clip-vision-sdxl.safetensors"
CHECKPOINT = "RealVisXL_V4.0.safetensors"


def generate_slide(
    prompt: str,
    negative_prompt: str,
    output_path: str,
    reference_image_path: str = None,
    reference_strength: float = 0.55,
    width: int = 768,
    height: int = 1344,
    steps: int = 30,
    cfg: float = 6.5,
    lora_name: str = None,
    lora_weight: float = 0.85,
) -> str:
    client_id = str(uuid.uuid4())

    # Only use reference if the local file actually exists
    if reference_image_path and not os.path.exists(reference_image_path):
        reference_image_path = None

    # Upload reference image to ComfyUI before building workflow
    uploaded_ref_name = None
    if reference_image_path:
        uploaded_ref_name = _upload_image(reference_image_path)

    workflow = _build_workflow(
        prompt=prompt,
        negative_prompt=negative_prompt,
        uploaded_ref_name=uploaded_ref_name,
        reference_strength=reference_strength,
        width=width,
        height=height,
        steps=steps,
        cfg=cfg,
        lora_name=lora_name,
        lora_weight=lora_weight,
    )

    ws = websocket.WebSocket()
    ws.connect(f"ws://{COMFYUI_HOST}/ws?clientId={client_id}")

    prompt_id = _queue_prompt(workflow, client_id)
    image_data = _wait_for_image(ws, prompt_id)
    ws.close()

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(image_data)

    return output_path


def _upload_image(local_path: str) -> str:
    with open(local_path, "rb") as f:
        data = f.read()
    filename = os.path.basename(local_path)
    boundary = "----FormBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"http://{COMFYUI_HOST}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["name"]


def _queue_prompt(workflow: dict, client_id: str) -> str:
    data = json.dumps({"prompt": workflow, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(
        f"http://{COMFYUI_HOST}/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
            if result.get("node_errors"):
                raise RuntimeError(f"ComfyUI node errors: {result['node_errors']}")
            return result["prompt_id"]
    except urllib.request.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"ComfyUI rejected workflow: {body}") from e


def _wait_for_image(ws, prompt_id: str) -> bytes:
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message["type"] == "executing":
                data = message["data"]
                if data["node"] is None and data["prompt_id"] == prompt_id:
                    break

    history = _get_history(prompt_id)
    for node_output in history[prompt_id]["outputs"].values():
        if "images" in node_output:
            image_info = node_output["images"][0]
            return _get_image(
                image_info["filename"],
                image_info["subfolder"],
                image_info["type"],
            )

    raise RuntimeError(f"No image output found for prompt {prompt_id}")


def _get_history(prompt_id: str) -> dict:
    url = f"http://{COMFYUI_HOST}/history/{prompt_id}"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())


def _get_image(filename: str, subfolder: str, folder_type: str) -> bytes:
    params = urllib.parse.urlencode(
        {"filename": filename, "subfolder": subfolder, "type": folder_type}
    )
    url = f"http://{COMFYUI_HOST}/view?{params}"
    with urllib.request.urlopen(url) as response:
        return response.read()


def _build_workflow(
    prompt: str,
    negative_prompt: str,
    uploaded_ref_name: str,
    reference_strength: float,
    width: int,
    height: int,
    steps: int,
    cfg: float,
    lora_name: str,
    lora_weight: float,
) -> dict:
    seed = random.randint(0, 2**32 - 1)

    workflow = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": CHECKPOINT},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["1", 1], "text": prompt},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["1", 1], "text": negative_prompt},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"images": ["6", 0], "filename_prefix": "tiktok_slide"},
        },
    }

    # Wire in LoRA before IP-Adapter so both benefit
    model_node = "1"
    if lora_name:
        workflow["20"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["1", 0],
                "clip": ["1", 1],
                "lora_name": lora_name,
                "strength_model": lora_weight,
                "strength_clip": lora_weight,
            },
        }
        model_node = "20"
        workflow["2"]["inputs"]["clip"] = ["20", 1]
        workflow["3"]["inputs"]["clip"] = ["20", 1]

    # Use IP-Adapter when product reference image is provided
    if uploaded_ref_name:
        workflow["10"] = {
            "class_type": "IPAdapterModelLoader",
            "inputs": {"ipadapter_file": IPADAPTER_MODEL},
        }
        workflow["11"] = {
            "class_type": "CLIPVisionLoader",
            "inputs": {"clip_name": CLIP_VISION_MODEL},
        }
        workflow["12"] = {
            "class_type": "LoadImage",
            "inputs": {"image": uploaded_ref_name, "upload": "image"},
        }
        workflow["13"] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": [model_node, 0],
                "ipadapter": ["10", 0],
                "image": ["12", 0],
                "clip_vision": ["11", 0],
                "weight": reference_strength,
                "weight_type": "style transfer",
                "combine_embeds": "concat",
                "start_at": 0.0,
                "end_at": 0.8,
                "embeds_scaling": "V only",
            },
        }
        workflow["5"]["inputs"]["model"] = ["13", 0]
    else:
        workflow["5"]["inputs"]["model"] = [model_node, 0]

    return workflow
