"""
Minimal REST client for sending YAML data and streaming responses.
This version supports only HS256 JWT signing.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Dict, NoReturn
import httpx
import jwt
import yaml


def load_config(path: str = "rest_use.yaml") -> Dict[str, Any]:
    """Load YAML configuration and return a dict; terminate on error."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        print(f"Config file not found: {path}")
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"YAML parse error: {exc}")
        sys.exit(1)


def build_token(cfg: Dict[str, Any]) -> str:
    """Return an HS256‑signed JWT using *cfg* values."""

    # Get the JWT secret from environment or fallback to config
    secret = cfg.get("secret", "")
    if len(secret) < 32:
        print("HS256 requires JWT secret ≥ 32 characters (256 bits).")
        sys.exit(1)

    now = int(time.time())

    payload = {
        # "sub" (Subject): Identifies the principal (e.g., user or service)
        # that is the subject of the JWT. Must be unique within the issuer's
        # context.
        "sub": cfg.get("subject", "client-123"),

        # "iss" (Issuer): Identifies the principal that issued the JWT.
        # Used to verify the origin of the token.
        "iss": cfg.get("issuer", "simulation-bridge"),

        # "iat" (Issued At): The timestamp when the JWT was issued.
        "iat": now,

        # "exp" (Expiration Time): The timestamp after which the token must not be accepted.
        # This defines how long the token is valid (default is 15 minutes).
        "exp": now + int(cfg.get("ttl", 900)),
    }

    # Encode and sign the JWT using HS256 algorithm
    return jwt.encode(payload, secret, algorithm="HS256")


class RESTClient:
    """Minimal REST client for sending YAML data and streaming responses."""

    def __init__(self, cfg: Dict[str, Any]):
        self.url = cfg["url"]
        self.yaml_file = cfg["yaml_file"]
        self.timeout = int(cfg.get("timeout", 600))
        self.ssl_verify = cfg.get("ssl_verify", False)
        self.token = build_token(cfg)

    async def run(self) -> None:
        headers = {
            "Content-Type": "application/x-yaml",
            "Accept": "application/x-ndjson",
            "Authorization": f"Bearer {self.token}",
        }

        try:
            payload = Path(self.yaml_file).read_bytes()
        except FileNotFoundError:
            print(f"YAML file not found: {self.yaml_file}")
            sys.exit(1)

        async with httpx.AsyncClient(timeout=self.timeout, verify=self.ssl_verify) as client:
            try:
                async with client.stream("POST", self.url, headers=headers,
                                         content=payload) as resp:
                    print(f"← {resp.status_code} {resp.reason_phrase}")
                    if resp.status_code >= 400:
                        print(await resp.aread())
                        return
                    async for line in resp.aiter_lines():
                        if line.strip():
                            print(line)
            except httpx.RequestError as exc:
                print(f"Network error contacting {self.url}: {exc}")


def main() -> NoReturn:  # pragma: no cover
    cfg = load_config()
    asyncio.run(RESTClient(cfg).run())


if __name__ == "__main__":
    main()
