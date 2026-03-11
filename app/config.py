from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(slots=True)
class AppConfig:
    """
    Application configuration loaded from environment variables.
    """

    dokploy_api_base: str
    dokploy_api_token: str

    ingress_traefik_dynamic_file: str
    reload_on_change: bool

    traefik_cert_resolver: str
    traefik_entrypoints: list[str]

    server_map_path: Path
    state_path: Path

    run_on_startup: bool
    enable_internal_scheduler: bool
    sync_interval_seconds: int
    idle_after_start: bool

    allowed_domain_suffixes: list[str]
    domain_blocklist: set[str]

    exposed_by_default: bool
    skip_tls_verify: bool
    request_timeout_seconds: int
    log_level: str
    dry_run: bool

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            dokploy_api_base=os.environ["DOKPLOY_API_BASE"].rstrip("/"),
            dokploy_api_token=os.environ["DOKPLOY_API_TOKEN"],

            ingress_traefik_dynamic_file=os.getenv(
                "INGRESS_TRAEFIK_DYNAMIC_FILE",
                "/etc/dokploy/traefik/dynamic/edge-sync.yml",
            ),
            reload_on_change=os.getenv("RELOAD_ON_CHANGE", "true").lower() == "true",

            traefik_cert_resolver=os.getenv("TRAEFIK_CERT_RESOLVER", "letsencrypt"),
            traefik_entrypoints=[
                item.strip()
                for item in os.getenv("TRAEFIK_ENTRYPOINTS", "websecure").split(",")
                if item.strip()
            ],

            server_map_path=Path(os.getenv("SERVER_MAP_PATH", "/app/config/servers.yml")),
            state_path=Path(os.getenv("STATE_PATH", "/app/data/last_generated.json")),

            run_on_startup=os.getenv("RUN_ON_STARTUP", "true").lower() == "true",
            enable_internal_scheduler=os.getenv("ENABLE_INTERNAL_SCHEDULER", "false").lower() == "true",
            sync_interval_seconds=int(os.getenv("SYNC_INTERVAL_SECONDS", "300")),
            idle_after_start=os.getenv("IDLE_AFTER_START", "true").lower() == "true",

            allowed_domain_suffixes=[
                item.strip().lower()
                for item in os.getenv("ALLOWED_DOMAIN_SUFFIXES", "").split(",")
                if item.strip()
            ],
            domain_blocklist={
                item.strip().lower()
                for item in os.getenv("DOMAIN_BLOCKLIST", "").split(",")
                if item.strip()
            },

            exposed_by_default=os.getenv("EXPOSED_BY_DEFAULT", "false").lower() == "true",
            skip_tls_verify=os.getenv("SKIP_TLS_VERIFY", "false").lower() == "true",
            request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
        )

    def load_server_overrides(self) -> dict[str, str]:
        """
        Load the optional server override map.

        This file is not required. If present, it overrides the IP/hostname
        returned by Dokploy for matching server names.
        """
        if not self.server_map_path.exists():
            return {}

        data = yaml.safe_load(self.server_map_path.read_text()) or {}
        if not isinstance(data, dict):
            raise ValueError("servers.yml must be a mapping of server name -> host/ip")

        return {
            str(key).strip().lower(): str(value).strip()
            for key, value in data.items()
            if str(value).strip()
        }
