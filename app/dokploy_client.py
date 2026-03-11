from __future__ import annotations

from typing import Any

import requests

from app.config import AppConfig


class DokployClient:
    """
    Thin API client for Dokploy.
    """

    def __init__(self, config: AppConfig) -> None:
        self._base_url = config.dokploy_api_base
        self._timeout = config.request_timeout_seconds

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": config.dokploy_api_token,
                "Accept": "application/json",
                "User-Agent": "dokploy-edge-sync/2.0",
            }
        )
        self.session.verify = not config.skip_tls_verify

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.session.get(
            f"{self._base_url}{path}",
            params=params,
            timeout=self._timeout,
        )
        response.raise_for_status()

        if not response.text.strip():
            return {}

        return response.json()

    def post(self, path: str, json_body: dict[str, Any]) -> Any:
        response = self.session.post(
            f"{self._base_url}{path}",
            json=json_body,
            timeout=self._timeout,
        )
        response.raise_for_status()

        if not response.text.strip():
            return {}

        return response.json()

    def get_servers(self) -> Any:
        return self.get("/server.all")

    def get_destinations(self) -> Any:
        return self.get("/destination.all")

    def get_containers(self, server_id: str) -> Any:
        return self.get("/docker.getContainers", params={"serverId": server_id})

    def get_container_config(self, server_id: str, container_id: str) -> Any:
        return self.get(
            "/docker.getConfig",
            params={"serverId": server_id, "containerId": container_id},
        )

    def get_application_domains(self, application_id: str) -> Any:
        return self.get(
            "/domain.byApplicationId",
            params={"applicationId": application_id},
        )

    def get_compose_domains(self, compose_id: str) -> Any:
        return self.get(
            "/domain.byComposeId",
            params={"composeId": compose_id},
        )

    def read_directories(self, server_id: str) -> Any:
        return self.get(
            "/settings.readDirectories",
            params={"serverId": server_id},
        )

    def get_web_server_settings(self) -> Any:
        return self.get("/settings.getWebServerSettings")

    def read_traefik_file(self, server_id: str, path: str) -> Any:
        return self.get(
            "/settings.readTraefikFile",
            params={"serverId": server_id, "path": path},
        )

    def update_traefik_file(self, server_id: str, path: str, traefik_config: str) -> Any:
        return self.post(
            "/settings.updateTraefikFile",
            {
                "serverId": server_id,
                "path": path,
                "traefikConfig": traefik_config,
            },
        )

    def reload_traefik(self, server_id: str) -> Any:
        return self.post(
            "/settings.reloadTraefik",
            {
                "serverId": server_id,
            },
        )
