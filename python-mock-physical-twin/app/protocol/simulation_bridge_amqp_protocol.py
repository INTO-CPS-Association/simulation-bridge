
"""Simulation Bridge protocol that exchanges messages through RabbitMQ."""

from __future__ import annotations

from pathlib import Path
from types import MethodType
from typing import TYPE_CHECKING, Any, Dict, Optional

import ssl
import threading
from uuid import uuid4

import pika
from pika.adapters.blocking_connection import BlockingChannel
import yaml

from app.device.sensor import Sensor

from app.protocol.protocol import (
    InvalidConfigurationError,
    Protocol,
    validate_dict_keys,
)
from app.utils.emulator_utils import ProtocolType

if TYPE_CHECKING:
    from app.device.iot_device import IoTDevice


class SimulationBridgeAmqpProtocol(Protocol):
    """Protocol that forwards device telemetry to the simulation bridge via AMQP."""

    def __init__(
        self,
        protocol_id: str,
        device_dict: Optional[Dict[str, "IoTDevice"]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            protocol_id,
            ProtocolType.SIMULATION_BRIDGE_AMQP_PROTOCOL_TYPE,
            device_dict,
            config,
        )

        self.base_path = Path(self.config.get("base_path", ".")).resolve()
        self.client_config_path = self._resolve_path(self.config["client_config"])
        self.simulation_api_path = self._resolve_path(self.config["simulation_api"])

        aggregate_cfg = self.config.get("aggregate", {})
        self.aggregate_device_id: str = aggregate_cfg["device_id"]
        self.aggregate_sensor_id: str = aggregate_cfg["sensor_id"]
        self.aggregate_sensor_config: Optional[Dict[str, Any]] = aggregate_cfg.get(
            "sensor_config"
        )

        self.client_config = self._load_yaml(self.client_config_path)
        self.simulation_payload = self._load_yaml(self.simulation_api_path)

        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[BlockingChannel] = None
        self.result_queue_name: Optional[str] = None

        self._consumer_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._sensor_lock = threading.Lock()
        self._aggregate_sensor: Optional[Sensor] = None

    def validate_config(self) -> None:  # type: ignore[override]
        required_keys = ["client_config", "simulation_api", "aggregate"]
        if not validate_dict_keys(self.config, required_keys):
            raise InvalidConfigurationError(required_keys)

        aggregate_cfg = self.config.get("aggregate", {})
        if not validate_dict_keys(aggregate_cfg, ["device_id", "sensor_id"]):
            raise InvalidConfigurationError(["aggregate.device_id", "aggregate.sensor_id"])

    def start(self) -> None:  # type: ignore[override]
        print(f"Starting protocol: {self.id} Type: {self.type}")
        self._stop_event.clear()
        self._ensure_connection()
        self._ensure_aggregate_sensor()
        self._publish_simulation_request()
        self._start_consumer()

    def stop(self) -> None:  # type: ignore[override]
        print(f"Stopping protocol: {self.id} Type: {self.type}")
        self._stop_event.set()

        if self.connection and self.channel and self.channel.is_open:
            def _stop_consuming() -> None:
                try:
                    self.channel.stop_consuming()
                except pika.exceptions.ChannelWrongStateError:
                    pass

            try:
                self.connection.add_callback_threadsafe(_stop_consuming)
            except pika.exceptions.ConnectionClosed:
                pass

        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5)
            self._consumer_thread = None

        if self.connection and self.connection.is_open:
            self.connection.close()

        self.channel = None
        self.connection = None

    def publish_sensor_telemetry_data(self, device_id, sensor_id, payload):  # type: ignore[override]
        pass

    def publish_device_telemetry_data(self, device_id, payload):  # type: ignore[override]
        pass

    def _resolve_path(self, relative_path: str) -> Path:
        path = Path(relative_path).expanduser()
        if not path.is_absolute():
            path = (self.base_path / path).resolve()
        return path

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValueError(f"YAML file {path} did not contain a dictionary")
        return data

    def _ensure_connection(self) -> None:
        if self.connection and self.connection.is_open and self.channel and self.channel.is_open:
            return

        rabbit_cfg = self.client_config["rabbitmq"]
        credentials = pika.PlainCredentials(
            rabbit_cfg.get("username", "guest"),
            rabbit_cfg.get("password", "guest"),
        )

        tls_enabled = bool(rabbit_cfg.get("tls", False))
        ssl_options = None
        port = rabbit_cfg.get("port", 5672)
        if tls_enabled:
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_options = pika.SSLOptions(context, rabbit_cfg.get("host", "localhost"))
            port = rabbit_cfg.get("port", 5671)

        parameters = pika.ConnectionParameters(
            host=rabbit_cfg.get("host", "localhost"),
            port=port,
            virtual_host=rabbit_cfg.get("vhost", "/"),
            credentials=credentials,
            heartbeat=rabbit_cfg.get("heartbeat", 600),
            ssl_options=ssl_options,
        )

        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        self._declare_infrastructure()

    def _declare_infrastructure(self) -> None:
        assert self.channel is not None
        exchanges = self.client_config["exchanges"]
        queue_cfg = self.client_config["queue"]

        input_bridge = exchanges["input_bridge"]
        result_exchange = exchanges["bridge_result"]

        self.channel.exchange_declare(
            exchange=input_bridge["name"],
            exchange_type=input_bridge["type"],
            durable=input_bridge.get("durable", True),
        )

        self.channel.exchange_declare(
            exchange=result_exchange["name"],
            exchange_type=result_exchange["type"],
            durable=result_exchange.get("durable", True),
        )

        self.result_queue_name = (
            f"{queue_cfg['result_queue_prefix']}."
            f"{self.client_config['digital_twin']['dt_id']}.result"
        )

        self.channel.queue_declare(
            queue=self.result_queue_name,
            durable=queue_cfg.get("durable", True),
        )

        self.channel.queue_bind(
            exchange=result_exchange["name"],
            queue=self.result_queue_name,
            routing_key=queue_cfg["routing_key"],
        )

    def _start_consumer(self) -> None:
        assert self.channel is not None
        assert self.result_queue_name is not None

        if self._consumer_thread and self._consumer_thread.is_alive():
            return

        self.channel.basic_consume(
            queue=self.result_queue_name,
            on_message_callback=self._handle_result,
        )

        self._consumer_thread = threading.Thread(
            target=self._consume,
            name=f"{self.id}-amqp-consumer",
            daemon=True,
        )
        self._consumer_thread.start()

    def _consume(self) -> None:
        if not self.channel:
            return
        try:
            self.channel.start_consuming()
        except pika.exceptions.ConnectionClosed:
            pass
        except pika.exceptions.ChannelClosedByBroker:
            pass

    def _publish_simulation_request(self) -> None:
        assert self.channel is not None
        exchanges = self.client_config["exchanges"]
        routing_key = self.client_config["digital_twin"]["routing_key_send"]
        payload_yaml = yaml.dump(self.simulation_payload, default_flow_style=False)

        properties = pika.BasicProperties(
            delivery_mode=2,
            content_type="application/x-yaml",
            message_id=str(uuid4()),
        )

        self.channel.basic_publish(
            exchange=exchanges["input_bridge"]["name"],
            routing_key=routing_key,
            body=payload_yaml,
            properties=properties,
        )

    def _handle_result(self, channel, method, properties, body):  # pylint: disable=unused-argument
        try:
            result = yaml.safe_load(body) if body else {}
        except yaml.YAMLError:
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        sensor = self._ensure_aggregate_sensor()
        if sensor is not None:
            with self._sensor_lock:
                sensor.last_value = result
                sensor.last_update_time = 0

        channel.basic_ack(delivery_tag=method.delivery_tag)

    def _ensure_aggregate_sensor(self) -> Optional[Sensor]:
        with self._sensor_lock:
            if self._aggregate_sensor is not None:
                return self._aggregate_sensor

            device = self.device_dict.get(self.aggregate_device_id)
            if device is None:
                return None

            sensor = device.get_sensor_by_id(self.aggregate_sensor_id)
            if sensor is None and self.aggregate_sensor_config is not None:
                sensor = Sensor(id=self.aggregate_sensor_id, **self.aggregate_sensor_config)
                device.sensors.append(sensor)

            if sensor is None:
                return None

            sensor.last_value = sensor.last_value or {}
            sensor.last_update_time = 0
            sensor.update_value = MethodType(lambda self_sensor: self_sensor.last_value, sensor)

            self._aggregate_sensor = sensor
            return sensor
