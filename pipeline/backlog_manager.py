import json
from pathlib import Path

ROOT = Path(__file__).parent.parent


def pick_next(backlog_path=None, niche_id: str = None) -> dict | None:
    if backlog_path is None:
        backlog_path = ROOT / "backlog.json"
    backlog = _load(backlog_path)
    candidates = [e for e in backlog if e["status"] == "queued"]
    if niche_id:
        candidates = [e for e in candidates if e["niche_id"] == niche_id]
    if not candidates:
        return None
    candidates.sort(key=lambda e: e["total_score"], reverse=True)
    return candidates[0]


def update_status(product_id: str, status: str, backlog_path=None, **kwargs):
    if backlog_path is None:
        backlog_path = ROOT / "backlog.json"
    backlog = _load(backlog_path)
    for entry in backlog:
        if entry["product_id"] == product_id:
            entry["status"] = status
            entry.update(kwargs)
            break
    _save(backlog, backlog_path)


def _load(path) -> list:
    if not Path(path).exists():
        return []
    with open(path) as f:
        return json.load(f)


def _save(backlog: list, path):
    with open(path, "w") as f:
        json.dump(backlog, f, indent=2)
