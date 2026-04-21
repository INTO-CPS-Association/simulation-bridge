"""Unit tests for Python Agent batch handler."""

from pathlib import Path
from unittest.mock import Mock

from src.core.batch import handle_batch_simulation


def test_handle_batch_simulation_sends_success(tmp_path: Path):
    script_path = tmp_path / "ok.py"
    script_path.write_text("print('hello')\n", encoding="utf-8")

    broker = Mock()
    broker.send_result.return_value = True

    payload = {
        "simulation": {
            "request_id": "req-1",
            "client_id": "client-1",
            "simulator": "python",
            "type": "batch",
            "file": "ok.py",
            "inputs": {},
            "outputs": [],
            "bridge_meta": {"source": "test"},
        }
    }

    templates = {
        "success": {"include_metadata": True},
        "progress": {"include_percentage": True},
        "error": {"include_stacktrace": False, "error_codes": {"execution_error": 500}},
    }

    handle_batch_simulation(payload, "caller", broker, str(tmp_path), templates)

    assert broker.send_result.call_count >= 1
