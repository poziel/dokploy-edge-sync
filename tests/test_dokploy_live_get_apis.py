from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from app.config import AppConfig
from app.dokploy_client import DokployClient
from app.parsers import decode_traefik_file_content, extract_labels, parse_servers
from app.utils import pick, unwrap_list


def _load_env_file_if_needed() -> None:
    """
    Load .env into process env only for missing keys.
    """
    env_path = Path(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _deep_pick(payload: Any, *keys: str) -> Any:
    if isinstance(payload, dict):
        for key in keys:
            if key in payload and payload[key] not in (None, ""):
                return payload[key]
        for value in payload.values():
            found = _deep_pick(value, *keys)
            if found not in (None, ""):
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _deep_pick(item, *keys)
            if found not in (None, ""):
                return found
    return None


@pytest.fixture(scope="module")
def live_client() -> tuple[DokployClient, AppConfig]:
    if os.getenv("RUN_LIVE_DOKPLOY_TESTS", "false").lower() != "true":
        pytest.skip("Set RUN_LIVE_DOKPLOY_TESTS=true to run live Dokploy GET API checks.")

    _load_env_file_if_needed()
    required = ("DOKPLOY_API_BASE", "DOKPLOY_API_TOKEN")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        pytest.skip(f"Missing required env vars for live tests: {', '.join(missing)}")

    config = AppConfig.from_env()
    return DokployClient(config), config


@pytest.mark.live_dokploy
def test_live_get_core_endpoints_and_auth(live_client):
    client, _ = live_client

    web_settings = client.get_web_server_settings()
    assert isinstance(web_settings, dict)
    assert pick(web_settings, "id", "serverId"), "web server settings must include id/serverId"
    assert pick(web_settings, "serverIp", "ipAddress", "ip"), "web server settings must include server IP"

    servers_payload = client.get_servers()
    servers = parse_servers(servers_payload)
    assert isinstance(servers, list)
    assert len(servers) >= 1, "Expected at least one parseable server from /server.all"

    destinations_payload = client.get_destinations()
    assert isinstance(destinations_payload, (list, dict))


@pytest.mark.live_dokploy
def test_live_get_containers_and_inspect_shape(live_client):
    client, _ = live_client
    web_settings = client.get_web_server_settings()
    server_id = str(pick(web_settings, "id", "serverId"))

    containers_payload = client.get_containers(server_id)
    assert isinstance(containers_payload, (list, dict))

    containers = unwrap_list(containers_payload)
    if not containers:
        pytest.skip(f"No containers found on server {server_id}")

    container_id = pick(containers[0], "Id", "id", "containerId")
    assert container_id, "Container payload should expose Id/id/containerId"

    inspect_payload = client.get_container_config(server_id, str(container_id))
    assert isinstance(inspect_payload, dict)
    assert isinstance(extract_labels(inspect_payload), dict)


@pytest.mark.live_dokploy
def test_live_get_read_endpoints_and_domain_endpoints(live_client):
    client, config = live_client
    web_settings = client.get_web_server_settings()
    server_id = str(pick(web_settings, "id", "serverId"))

    directories_payload = client.read_directories(server_id)
    assert isinstance(directories_payload, (list, dict))

    raw_traefik_content = client.read_traefik_file(server_id, config.ingress_traefik_dynamic_file)
    decoded_traefik_content = decode_traefik_file_content(raw_traefik_content)
    assert isinstance(decoded_traefik_content, str)

    app_id = None
    compose_id = None

    for container in unwrap_list(client.get_containers(server_id))[:10]:
        container_id = pick(container, "Id", "id", "containerId")
        if not container_id:
            continue
        inspect_payload = client.get_container_config(server_id, str(container_id))
        app_id = app_id or _deep_pick(inspect_payload, "applicationId", "appId")
        compose_id = compose_id or _deep_pick(inspect_payload, "composeId")
        if app_id and compose_id:
            break

    if not app_id and not compose_id:
        pytest.skip("No applicationId/appId or composeId found in inspected containers.")

    if app_id:
        app_domains_payload = client.get_application_domains(str(app_id))
        assert isinstance(app_domains_payload, (list, dict))

    if compose_id:
        compose_domains_payload = client.get_compose_domains(str(compose_id))
        assert isinstance(compose_domains_payload, (list, dict))
