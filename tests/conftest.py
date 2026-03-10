from __future__ import annotations

from pathlib import Path

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
    ) -> None:
        self._servers = servers or []
        self._containers_by_server = containers_by_server or {}
        self._inspect_by_container = inspect_by_container or {}
        self._application_domains = application_domains or {}
        self._compose_domains = compose_domains or {}
        self._remote_files = remote_files or {}

        self.updated_files = []
        self.reloaded_servers = []

    def get_servers(self):
        return self._servers

    def get_containers(self, server_id: str):
        return self._containers_by_server.get(server_id, [])

    def get_container_config(self, server_id: str, container_id: str):
        return self._inspect_by_container.get((server_id, container_id), {})

    def get_application_domains(self, application_id: str):
        return self._application_domains.get(application_id, [])

    def get_compose_domains(self, compose_id: str):
        return self._compose_domains.get(compose_id, [])

    def read_traefik_file(self, server_id: str, path: str):
        return self._remote_files.get((server_id, path), "")

    def update_traefik_file(self, server_id: str, path: str, traefik_config: str):
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
        self.reloaded_servers.append(server_id)
        return {}


@pytest.fixture
def app_config(tmp_path: Path) -> AppConfig:
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