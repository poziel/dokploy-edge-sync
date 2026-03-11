from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.config import AppConfig


class FakeDokployClient:
    def __init__(
        self,
        servers=None,
        containers_by_server=None,
        inspect_by_container=None,
        application_domains=None,
        compose_domains=None,
        remote_files=None,
        read_traefik_errors=None,
        web_server_settings=None,
        web_server_settings_error=None,
        update_traefik_error=None,
        reload_traefik_error=None,
    ) -> None:
        self._servers = servers or []
        self._containers_by_server = containers_by_server or {}
        self._inspect_by_container = inspect_by_container or {}
        self._application_domains = application_domains or {}
        self._compose_domains = compose_domains or {}
        self._remote_files = remote_files or {}
        self._read_traefik_errors = read_traefik_errors or {}
        self._web_server_settings = (
            {
                "id": "ingress-1",
                "host": "ingress",
                "serverIp": "192.168.1.10",
            }
            if web_server_settings is None
            else web_server_settings
        )
        self._web_server_settings_error = web_server_settings_error
        self._update_traefik_error = update_traefik_error
        self._reload_traefik_error = reload_traefik_error

        self.updated_files = []
        self.reloaded_servers = []

    def get_servers(self):
        return self._servers

    def get_web_server_settings(self):
        if self._web_server_settings_error is not None:
            raise self._web_server_settings_error
        return self._web_server_settings

    def get_containers(self, server_id: str):
        return self._containers_by_server.get(server_id, [])

    def get_container_config(self, server_id: str, container_id: str):
        return self._inspect_by_container.get((server_id, container_id), {})

    def get_application_domains(self, application_id: str):
        return self._application_domains.get(application_id, [])

    def get_compose_domains(self, compose_id: str):
        return self._compose_domains.get(compose_id, [])

    def read_traefik_file(self, server_id: str, path: str):
        error = self._read_traefik_errors.get((server_id, path))
        if error is not None:
            raise error
        return self._remote_files.get((server_id, path), "")

    def update_traefik_file(self, server_id: str, path: str, traefik_config: str):
        if self._update_traefik_error is not None:
            raise self._update_traefik_error
        self.updated_files.append(
            {
                "server_id": server_id,
                "path": path,
                "traefik_config": traefik_config,
            }
        )
        self._remote_files[(server_id, path)] = traefik_config
        return {}

    def reload_traefik(self, server_id: str):
        if self._reload_traefik_error is not None:
            raise self._reload_traefik_error
        self.reloaded_servers.append(server_id)
        return {}


@pytest.fixture
def app_config() -> AppConfig:
    tmp_path = Path("tests") / "__pycache__" / "runtime" / uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        dokploy_api_base="https://dokploy.example/api",
        dokploy_api_token="test-token",
        ingress_server_name="ingress",
        ingress_traefik_dynamic_file="/etc/dokploy/traefik/dynamic/edge-sync.yml",
        reload_on_change=True,
        traefik_cert_resolver="letsencrypt",
        traefik_entrypoints=["websecure"],
        server_map_path=tmp_path / "servers.yml",
        state_path=tmp_path / "state.json",
        run_on_startup=True,
        enable_internal_scheduler=False,
        sync_interval_seconds=300,
        idle_after_start=True,
        allowed_domain_suffixes=[".example.com", ".example.dev"],
        domain_blocklist=set(),
        exposed_by_default=False,
        skip_tls_verify=False,
        request_timeout_seconds=20,
        log_level="DEBUG",
        dry_run=False,
    )


@pytest.fixture
def fake_client_factory():
    return FakeDokployClient
