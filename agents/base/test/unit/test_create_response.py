"""Tests for shared create_response utility."""

from unittest.mock import patch

from base_agent.utils.create_response import create_response


@patch("base_agent.utils.create_response.datetime")
def test_create_success_response_in_base(mock_datetime):
    """Verify shared response formatter returns expected success payload."""
    mock_datetime.now.return_value.strftime.return_value = "2024-01-01T00:00:00Z"
    templates = {
        "success": {
            "status": "success",
            "timestamp_format": "%Y-%m-%dT%H:%M:%SZ",
            "include_metadata": True,
        }
    }

    response = create_response(
        template_type="success",
        sim_file="SimulationBatch.m",
        sim_type="batch",
        response_templates=templates,
        bridge_meta="meta",
        request_id="req-1",
        outputs={"o1": 1},
        metadata={"execution_time": 1.2},
    )

    assert response["status"] == "completed"
    assert response["simulation"]["outputs"] == {"o1": 1}
    assert response["metadata"]["execution_time"] == 1.2
    assert response["timestamp"] == "2024-01-01T00:00:00Z"
