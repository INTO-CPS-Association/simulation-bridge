"""REST client for sending YAML payloads and handling streaming responses."""

import asyncio
import sys
from typing import NoReturn
from pathlib import Path

import httpx


async def send_yaml_and_stream_response(yaml_path: str, url: str) -> None:
    """Send YAML payload and handle streaming response.

    Args:
        yaml_path: Path to the YAML file to send
        url: Target URL for the POST request

    Raises:
        FileNotFoundError: If the YAML file cannot be found
        httpx.RequestError: If there is an error during the HTTP request
    """
    headers = {
        "Content-Type": "application/x-yaml",
        "Accept": "application/x-ndjson"
    }

    # Load YAML file content
    try:
        yaml_data = Path(yaml_path).read_bytes()
    except FileNotFoundError:
        print(f"Error: YAML file not found at '{yaml_path}'")
        sys.exit(1)

    async with httpx.AsyncClient(verify=False) as client:
        try:
            # Send POST request with streaming response
            async with client.stream(
                "POST",
                url,
                headers=headers,
                content=yaml_data,
                timeout=30.0
            ) as response:
                print(f"Status: {response.status_code}")
                
                if response.status_code >= 400:
                    print(f"Error: Server returned status code {response.status_code}")
                    return
                    
                async for line in response.aiter_lines():
                    if line.strip():
                        print(f"Received: {line}")
        except httpx.RequestError as error:
            print(
                f"An error occurred while requesting {error.request.url!r}.\n"
                f"Error: {error}"
            )


def main() -> NoReturn:
    """Run the REST client with default configuration.
    
    This function sets up the REST client with default parameters
    and executes the main functionality.
    """
    asyncio.run(
        send_yaml_and_stream_response(
            "simulation.yaml",
            "https://localhost:5000/message"
        )
    )


if __name__ == "__main__":
    main()
