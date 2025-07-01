"""REST client module for sending YAML data and streaming responses."""

import asyncio
import sys
import os
import time
from pathlib import Path
from typing import NoReturn, Dict, Any
import yaml
import httpx
import jwt

SECRET = os.getenv("REST_JWT_SECRET", "CHANGE_ME_TO_A_LONG_RANDOM_VALUE")
ALG = "HS256"

def build_token(sub: str = "sim-client") -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "iat": now,
        "exp": now + 900,   # 15 min
        "iss": "sim-bridge-client",
    }
    return jwt.encode(payload, SECRET, algorithm=ALG)

def load_config(config_path: str = "rest_use.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Dictionary containing configuration values

    Exits:
        If file not found or YAML parsing error occurs
    """
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Error: Config file '{config_path}' not found.")
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"Error parsing YAML config: {exc}")
        sys.exit(1)


class RESTClient:
    """Client for sending YAML data to REST endpoints and streaming responses."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the REST client with configuration.

        Args:
            config: Dictionary containing client configuration
        """
        self.yaml_file = config["yaml_file"]
        self.url = config["url"]
        self.timeout = config.get("timeout", 600)
        self.token = build_token()

    async def send_yaml_and_stream_response(self) -> None:
        """Send YAML data to server and stream the response."""
        headers = {
            "Content-Type": "application/x-yaml",
            "Accept": "application/x-ndjson",
            "Authorization": f"Bearer {self.token}",
        }

        try:
            yaml_data = Path(self.yaml_file).read_bytes()
        except FileNotFoundError:
            print(f"Error: YAML file not found at '{self.yaml_file}'")
            sys.exit(1)

        async with httpx.AsyncClient(verify=False) as client:
            try:
                async with client.stream(
                    "POST", self.url,
                    headers=headers,
                    content=yaml_data,
                    timeout=self.timeout
                ) as response:
                    print(f"Status: {response.status_code}")

                    if response.status_code >= 400:
                        print(
                            f"""Error: Server returned status code {
                                response.status_code}""")
                        return

                    async for line in response.aiter_lines():
                        if line.strip():
                            print(f"Received: {line}")
            except httpx.RequestError as error:
                print(
                    f"""An error occurred while requesting {
                        error.request.url!r}.\n"""
                    f"Error: {error}"
                )

def main() -> NoReturn:
    """Run the REST client application."""
    config = load_config()
    client = RESTClient(config)
    asyncio.run(client.send_yaml_and_stream_response())


if __name__ == "__main__":
    main()
