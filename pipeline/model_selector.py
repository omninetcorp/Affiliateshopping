import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
CATALOG_PATH = ROOT / "characters" / "catalog.json"
ROTATION_LOG_PATH = ROOT / "characters" / "rotation_log.json"


def pick_model(niche_id: str, account_id: str, rotation_window: int = 5) -> dict:
    catalog = _load_catalog()
    rotation_log = _load_rotation_log()

    eligible = [m for m in catalog["models"] if niche_id in m.get("suitable_niches", [])]
    if not eligible:
        eligible = catalog["models"]

    recent = rotation_log.get(account_id, [])[-rotation_window:]
    available = [m for m in eligible if m["id"] not in recent] or eligible
    selected = available[0]

    recent_list = rotation_log.get(account_id, [])
    recent_list.append(selected["id"])
    rotation_log[account_id] = recent_list[-(rotation_window * 2):]
    _save_rotation_log(rotation_log)

    return selected


def _load_catalog() -> dict:
    with open(CATALOG_PATH) as f:
        return json.load(f)


def _load_rotation_log() -> dict:
    if not ROTATION_LOG_PATH.exists():
        return {}
    with open(ROTATION_LOG_PATH) as f:
        return json.load(f)


def _save_rotation_log(log: dict):
    with open(ROTATION_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)
