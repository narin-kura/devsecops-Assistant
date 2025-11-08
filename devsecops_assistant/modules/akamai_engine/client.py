import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from ...config import load_yaml, getenv_required
from ...logging_utils import get_logger

log = get_logger(__name__)


@dataclass
class AkamaiConfig:
    base_url: str
    client_token: str
    client_secret: str
    access_token: str


class AkamaiClient:
    """Thin wrapper around Akamai APIs using API credentials.

    This is intentionally minimal; extend for PAPI, Property Manager, DNS, etc.
    """

    def __init__(self, config: AkamaiConfig) -> None:
        self.config = config

    @classmethod
    def from_yaml(cls, path: str) -> "AkamaiClient":
        data = load_yaml(path)
        base_url = data.get("base_url", "https://akab-xxxxxxxx.luna.akamaiapis.net")
        # In a real system, you'd use Akamai EdgeGrid signing. Here we keep it simple.
        cfg = AkamaiConfig(
            base_url=base_url,
            client_token=data.get("client_token", getenv_required("AKAMAI_CLIENT_TOKEN")),
            client_secret=data.get("client_secret", getenv_required("AKAMAI_CLIENT_SECRET")),
            access_token=data.get("access_token", getenv_required("AKAMAI_ACCESS_TOKEN")),
        )
        return cls(cfg)

    def _headers(self) -> Dict[str, str]:
        # Placeholder auth header; replace with EdgeGrid if needed.
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config.access_token}",
        }

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        log.debug("Akamai GET %s params=%s", url, params)
        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        log.debug("Akamai POST %s payload=%s", url, json.dumps(payload))
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()


def akamai_cli(args) -> int:
    """Entry point for `devsecops-assistant akamai ...` commands.

    For now this just demonstrates a `list-properties` placeholder.
    Extend with real PAPI/DNS operations as needed.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="devsecops-assistant akamai",
        description="Akamai DevOps engine commands",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to Akamai config YAML (or use env vars)",
    )

    subparsers = parser.add_subparsers(dest="akamai_command", metavar="<akamai-command>")

    list_props = subparsers.add_parser("list-properties", help="List Akamai properties (placeholder)")
    list_props.set_defaults(akamai_func="list_properties")  # type: ignore[attr-defined]

    parsed = parser.parse_args(sys.argv[2:])  # reuse remaining argv

    client = AkamaiClient.from_yaml(parsed.config)

    if parsed.akamai_command == "list_properties":
        # Placeholder path, adapt to real API endpoint.
        data = client.get("/papi/v1/properties" )
        print(json.dumps(data, indent=2))
        return 0

    parser.print_help()
    return 1
