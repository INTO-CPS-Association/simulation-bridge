"""Integration tests for *MessageHandler* and *SimpleUsageMatlabAgent*."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, cast
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml


@pytest.fixture
def mock_config_manager(dummy_credentials):
    """Mock configuration-manager fixture."""
    # Retrieve credentials safely, with fallback to "guest/guest".
    rabbit_creds: Dict[str, str] = dummy_credentials.get("rabbitmq", {})
    username = rabbit_creds.get("username", "guest")
    password = rabbit_creds.get("password", "guest")

    mock = MagicMock()
    mock.get_config.return_value = {
        "simulation_bridge": {"bridge_id": "test-bridge"},
        "rabbitmq": {
            "host": "localhost",
            "port": 5672,
            "username": username,
            "password": password,
            "vhost": "/",
            "infrastructure": {"exchanges": [], "queues": [], "bindings": []},
        },
    }
    mock.get_rabbitmq_config.return_value = mock.get_config.return_value["rabbitmq"]
    return mock


@pytest.fixture(autouse=True)
def _attach_fixtures(request, dummy_credentials, mock_config_manager):
    """
    Make the fixtures available as attributes on unittest.TestCase
    instances (created by pytest) **before** their setUp() runs.
    """
    testcase = getattr(request.node, "_testcase", None)
    if testcase is not None:
        testcase.dummy_credentials = dummy_credentials
        testcase.mock_config_manager = mock_config_manager
    # Nothing to return; autouse fixture


class MockRabbitMQManager:
    """Collect calls to *send_result* and *send_message*."""

    def __init__(self) -> None:
        self.sent_results: List[Dict[str, Any]] = []
        self.sent_messages: List[Dict[str, Any]] = []

    def send_result(self, source: str, response: Dict[str, Any]) -> None:  # noqa: D401
        self.sent_results.append({"source": source, "response": response})

    def send_message(self, routing_key: str, message: Dict[str, Any]) -> None:  # noqa: D401
        self.sent_messages.append({"routing_key": routing_key, "message": message})


class MockSimulationInputs:
    def __init__(self, **kwargs: Any) -> None:  # noqa: D401
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockSimulationOutputs(MockSimulationInputs):
    pass


class MockSimulationData:
    def __init__(
        self,
        request_id: str,
        client_id: str,
        simulator: str,
        type_: str,
        file: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any] | None = None,
        bridge_meta: Dict[str, Any] | None = None,
    ) -> None:
        self.request_id = request_id
        self.client_id = client_id
        self.simulator = simulator
        self.type = type_
        self.file = file
        self.inputs = MockSimulationInputs(**inputs)
        self.outputs = MockSimulationOutputs(**outputs) if outputs else None
        self.bridge_meta = bridge_meta


class MockMessagePayload:
    def __init__(self, **kwargs: Any) -> None:  # noqa: D401
        sim = kwargs.get("simulation", {})
        self.simulation = MockSimulationData(
            request_id=sim.get("request_id", ""),
            client_id=sim.get("client_id", ""),
            simulator=sim.get("simulator", ""),
            type_=sim.get("type", "batch"),
            file=sim.get("file", ""),
            inputs=sim.get("inputs", {}),
            outputs=sim.get("outputs"),
            bridge_meta=sim.get("bridge_meta"),
        )
        self.request_id = kwargs.get("request_id", self.simulation.request_id)


class MockMessageHandler:
    """Lightweight replacement for the real *MessageHandler*."""

    def __init__(self, agent_id: str, rabbitmq_manager: Any, config: Dict[str, Any]):
        self.agent_id = agent_id
        self.rabbitmq_manager = rabbitmq_manager
        self.path_simulation = config.get("simulation", {}).get("path")
        self.response_templates = config.get("response_templates", {})
        self.processed_messages: List[Dict[str, Any]] = []

    def get_agent_id(self) -> str:  # noqa: D401
        return self.agent_id

    def handle_message(self, ch, method, properties, body: bytes) -> None:  # noqa: ANN001,E501
        try:
            msg_dict = yaml.safe_load(body)
            self.processed_messages.append(msg_dict)

            sim = msg_dict.get("simulation", {})
            required = {"request_id", "client_id", "simulator", "type", "file", "inputs"}
            missing = required - sim.keys()
            if missing:
                response = {
                    "status": "error",
                    "error": {
                        "message": "Message validation failed",
                        "details": f"Missing required fields: {sorted(missing)}",
                        "type": "validation_error",
                    },
                }
            else:
                payload = MockMessagePayload(**msg_dict)
                match payload.simulation.type:
                    case "streaming":
                        response = {
                            "request_id": payload.simulation.request_id,
                            "status": "streaming_started",
                            "simulation_type": "streaming",
                            "file": payload.simulation.file,
                        }
                    case "batch":
                        response = {
                            "request_id": payload.simulation.request_id,
                            "status": "completed",
                            "simulation_type": "batch",
                            "file": payload.simulation.file,
                            "results": {
                                "time": 1.23,
                                "current_step": 200,
                                "positions": [[1.0, 2.0], [3.0, 4.0]],
                                "velocities": [[0.1, 0.2], [0.3, 0.4]],
                                "running": False,
                            },
                        }
                    case _:
                        response = {
                            "request_id": payload.simulation.request_id,
                            "status": "error",
                            "error": f"Unknown simulation type: {payload.simulation.type}",
                        }

            self.rabbitmq_manager.send_result(method.routing_key.split(".")[0], response)
            ch.basic_ack(method.delivery_tag)

        except yaml.YAMLError as exc:
            self._send_error(ch, method, "yaml_parse_error", str(exc))
        except Exception as exc:  # noqa: BLE001
            self._send_error(ch, method, "execution_error", str(exc))

    def _send_error(self, ch, method, err_type: str, details: str) -> None:  # noqa: ANN001
        err = {"status": "error", "error": {"message": "Error processing message", "details": details, "type": err_type}}
        try:
            self.rabbitmq_manager.send_result(method.routing_key.split(".")[0], err)
        finally:
            ch.basic_nack(method.delivery_tag, requeue=False)


@pytest.mark.usefixtures("dummy_credentials")
class IntegrationTest(TestCase):
    """End-to-end tests for the mock handler."""

    def setUp(self):  # noqa: D401
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config_file = self.temp_dir / "conf.yaml"
        self.sim_file = self.temp_dir / "sim.yaml"

        # Credentials obtained via autouse fixture
        creds: Dict[str, Any] = cast(Dict[str, Any], getattr(self, "dummy_credentials", {})).get("rabbitmq", {})

        cfg = {
            "rabbitmq": {
                "host": "localhost",
                "port": 5672,
                "username": creds.get("username", "guest"),
                "password": creds.get("password", "guest"),
                "vhost": "/test",
                "heartbeat": 600,
            }
        }
        self.config_file.write_text(yaml.dump(cfg), encoding="utf-8")

        sim = {
            "simulation": {
                "request_id": "req1",
                "client_id": "dt",
                "simulator": "matlab",
                "type": "streaming",
                "file": "sim.m",
                "inputs": {"time_step": 0.05},
            }
        }
        self.sim_file.write_text(yaml.dump(sim), encoding="utf-8")

        # Mocks
        self.channel = Mock()
        self.manager = MockRabbitMQManager()

    def tearDown(self):  # noqa: D401
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("resources.use_matlab_agent.pika.BlockingConnection")
    def test_init(self, _):  # noqa: ANN001
        handler = MockMessageHandler("id", self.manager, {"simulation": {"path": "/a"}})
        self.assertEqual(handler.path_simulation, "/a")

    @patch("resources.use_matlab_agent.pika.BlockingConnection")
    def test_invalid_yaml(self, _):  # noqa: ANN001
        handler = MockMessageHandler("id", self.manager, {})
        method = Mock(routing_key="dt.m", delivery_tag="t")
        handler.handle_message(self.channel, method, Mock(), b":::bad:::yaml")
        self.assertEqual(self.manager.sent_results[0]["response"]["error"]["type"], "execution_error")

    @patch("resources.use_matlab_agent.pika.BlockingConnection")
    def test_missing_fields(self, _):  # noqa: ANN001
        handler = MockMessageHandler("id", self.manager, {})
        body = yaml.dump({"simulation": {"request_id": "x"}}).encode()
        method = Mock(routing_key="dt.m", delivery_tag="t")
        handler.handle_message(self.channel, method, Mock(), body)
        self.assertEqual(self.manager.sent_results[0]["response"]["error"]["type"], "validation_error")

    def test_dummy_result_callback(self):  # noqa: D401
        result = {"status": "completed"}
        agent = Mock()
        agent.handle_result = Mock()
        agent.handle_result(Mock(), Mock(), Mock(), yaml.dump(result).encode())
        agent.handle_result.assert_called_once()

    def test_read_config(self):  # noqa: D401
        with open(self.config_file, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        self.assertIn("rabbitmq", cfg)

        bad = self.temp_dir / "bad.yaml"
        bad.write_text(": [", encoding="utf-8")
        with pytest.raises(yaml.YAMLError):
            yaml.safe_load(bad.read_text())


if __name__ == "__main__":  # pragma: no cover
    import unittest

    unittest.main(verbosity=2)
