"""Tests for shared batch helper utilities."""

from unittest.mock import Mock

from base_agent.utils.batch_helpers import send_progress_update


def test_send_progress_update_publishes_when_enabled() -> None:
    """Progress helper should build and send progress payload when enabled."""
    broker = Mock()
    response_builder = Mock(return_value={"status": "in_progress"})
    templates = {"progress": {"include_percentage": True}}

    send_progress_update(
        broker=broker,
        source="source.queue",
        sim_file="model.m",
        percentage=50,
        response_templates=templates,
        response_builder=response_builder,
        bridge_meta="meta",
        request_id="req-1",
    )

    response_builder.assert_called_once_with(
        "progress",
        "model.m",
        "batch",
        templates,
        percentage=50,
        bridge_meta="meta",
        request_id="req-1",
    )
    broker.send_result.assert_called_once_with("source.queue", {"status": "in_progress"})


def test_send_progress_update_skips_when_disabled() -> None:
    """Progress helper should skip response generation when disabled."""
    broker = Mock()
    response_builder = Mock(return_value={"status": "in_progress"})

    send_progress_update(
        broker=broker,
        source="source.queue",
        sim_file="model.m",
        percentage=50,
        response_templates={"progress": {"include_percentage": False}},
        response_builder=response_builder,
    )

    response_builder.assert_not_called()
    broker.send_result.assert_not_called()
