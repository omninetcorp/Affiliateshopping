import json
import os
import sys
import tempfile

sys.path.insert(0, '..')
from phase1.research_agent import write_product, load_backlog, is_already_queued


def test_write_product_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        product = {
            "product_id": "test-001",
            "status": "queued",
            "scoring": {"total_score": 7.5},
        }
        path = write_product(product, products_dir=tmpdir)
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["product_id"] == "test-001"


def test_is_already_queued_detects_duplicate():
    backlog = [{"product_id": "test-001"}, {"product_id": "test-002"}]
    assert is_already_queued("test-001", backlog) is True
    assert is_already_queued("test-999", backlog) is False


def test_load_backlog_returns_empty_for_missing_file():
    result = load_backlog("/nonexistent/path/backlog.json")
    assert result == []
