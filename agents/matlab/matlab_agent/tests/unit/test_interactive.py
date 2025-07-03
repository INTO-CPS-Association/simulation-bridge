import yaml
from src.core.interactive import _parse_frame, MatlabInteractiveController


def test_parse_frame_valid():
    body = b"simulation:\n  inputs:\n    val: 1\n"
    assert _parse_frame(body) == {"simulation": {"inputs": {"val": 1}}}


def test_parse_frame_invalid(caplog):
    result = _parse_frame(b": [")
    assert result == {}
    assert "Bad frame" in caplog.text


def test_only_inputs_extracts_inputs():
    frame = {"simulation": {"inputs": {"a": 2}}}
    assert MatlabInteractiveController._only_inputs(frame) == {"a": 2}


def test_only_inputs_passthrough():
    frame = {"x": 1}
    assert MatlabInteractiveController._only_inputs(frame) == {"x": 1}
