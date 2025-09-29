from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from app.protocol.protocol import (
    InvalidConfigurationError,
    Protocol,
    validate_dict_keys,
)
from app.utils.emulator_utils import ProtocolType

if TYPE_CHECKING:
    from app.device.iot_device import IoTDevice


class SimulationBridgeAMQPProtocol(Protocol):
    """Protocol adapter that proxies device telemetry to the Simulation Bridge."""

    _REQUIRED_SIM_BRIDGE_KEYS = ["client_config", "simulation_api"]

    def __init__(
        self,
        protocol_id: str,
        device_dict: Optional[Dict[str, IoTDevice]] = None,
        config: Optional[Dict] = None,
        simulation_bridge_config: Optional[Dict[str, str]] = None,
    ) -> None:
        self.simulation_bridge_config = simulation_bridge_config or {}
        super().__init__(
            protocol_id,
            ProtocolType.SIMULATION_BRIDGE_AMQP,
            device_dict,
            config or {},
        )
        self._validate_simulation_bridge_config()
        self.client_config_path = Path(self.simulation_bridge_config["client_config"]).resolve()
        self.simulation_api_path = Path(self.simulation_bridge_config["simulation_api"]).resolve()

    def start(self) -> None:  # pragma: no cover - integration handled by adapter runtime
        print(
            "Starting Simulation Bridge AMQP protocol with client config "
            f"{self.client_config_path} and API {self.simulation_api_path}"
        )

    def stop(self) -> None:  # pragma: no cover - lifecycle managed externally
        print("Stopping Simulation Bridge AMQP protocol")

    def validate_config(self) -> None:
        """Validate that the protocol specific configuration is present."""
        # No mandatory keys defined yet for the AMQP adapter configuration.
        # The Simulation Bridge configuration contains the mandatory information.
        if self.config is None:
            self.config = {}

    def publish_sensor_telemetry_data(self, device_id, sensor_id, payload):
        """Placeholder for future per-sensor telemetry publishing."""
        pass

    def publish_device_telemetry_data(self, device_id, payload):
        """Placeholder for future aggregated telemetry publishing."""
        pass

    def _validate_simulation_bridge_config(self) -> None:
        if not validate_dict_keys(self.simulation_bridge_config, self._REQUIRED_SIM_BRIDGE_KEYS):
            raise InvalidConfigurationError(self._REQUIRED_SIM_BRIDGE_KEYS)
