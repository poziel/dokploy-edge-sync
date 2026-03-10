from __future__ import annotations

import json

import yaml

from app.sync_service import SyncService


def test_sync_service_updates_remote_file_and_reloads_when_changed(
    app_config,
    fake_client_factory,
):
    fake_client = fake_client_factory(
        servers=[
            {
                "serverId": "ingress-1",
                "name": "ingress",
                "ipAddress": "192.168.1.10",
            },
            {
                "serverId": "app-1",
                "name": "app-server",
                "ipAddress": "10.0.0.20",
            },
        ],
        containers_by_server={
            "app-1": [
                {
                    "Id": "container-1",
                    "Names": ["/gitea"],
                }
            ]
        },
        inspect_by_container={
            ("app-1", "container-1"): {
                "Config": {
                    "Labels": {
                        "edge.enabled": "true",
                        "edge.port": "3000",
                        "edge.domains": "git.example.com",
                    }
                }
            }
        },
        remote_files={
            ("ingress-1", "/etc/dokploy/traefik/dynamic/edge-sync.yml"): ""
        },
    )

    service = SyncService(app_config, fake_client)
    result = service.run()

    assert "http" in result
    assert len(fake_client.updated_files) == 1
    assert fake_client.reloaded_servers == ["ingress-1"]

    updated = fake_client.updated_files[0]["traefik_config"]
    parsed = yaml.safe_load(updated)

    assert len(parsed["http"]["routers"]) == 1
    assert len(parsed["http"]["services"]) == 1


def test_sync_service_handles_wrong_traefik_file_path_read_error(
    app_config,
    fake_client_factory,
):
    wrong_path = "/etc/dokploy/traefik/dynamic/missing-edge-sync.yml"
    app_config.ingress_traefik_dynamic_file = wrong_path

    fake_client = fake_client_factory(
        servers=[
            {
                "serverId": "ingress-1",
                "name": "ingress",
                "ipAddress": "192.168.1.10",
            },
            {
                "serverId": "app-1",
                "name": "app-server",
                "ipAddress": "10.0.0.20",
            },
        ],
        containers_by_server={
            "app-1": [
                {
                    "Id": "container-1",
                    "Names": ["/gitea"],
                }
            ]
        },
        inspect_by_container={
            ("app-1", "container-1"): {
                "Config": {
                    "Labels": {
                        "edge.enabled": "true",
                        "edge.port": "3000",
                        "edge.domains": "git.example.com",
                    }
                }
            }
        },
        read_traefik_errors={
            ("ingress-1", wrong_path): FileNotFoundError("remote file not found")
        },
    )

    service = SyncService(app_config, fake_client)
    result = service.run()

    assert "http" in result
    assert len(fake_client.updated_files) == 1
    assert fake_client.updated_files[0]["path"] == wrong_path
    assert fake_client.reloaded_servers == ["ingress-1"]


def test_sync_service_does_not_reload_when_content_is_identical(
    app_config,
    fake_client_factory,
):
    existing_yaml = """
http:
  routers:
    app-server-gitea-git-example-com:
      rule: Host(`git.example.com`)
      entryPoints:
        - websecure
      service: svc-app-server-gitea
      tls:
        certResolver: letsencrypt
  services:
    svc-app-server-gitea:
      loadBalancer:
        passHostHeader: true
        servers:
          - url: http://10.0.0.20:3000
  middlewares: {}
""".strip()

    fake_client = fake_client_factory(
        servers=[
            {
                "serverId": "ingress-1",
                "name": "ingress",
                "ipAddress": "192.168.1.10",
            },
            {
                "serverId": "app-1",
                "name": "app-server",
                "ipAddress": "10.0.0.20",
            },
        ],
        containers_by_server={
            "app-1": [
                {
                    "Id": "container-1",
                    "Names": ["/gitea"],
                }
            ]
        },
        inspect_by_container={
            ("app-1", "container-1"): {
                "Config": {
                    "Labels": {
                        "edge.enabled": "true",
                        "edge.port": "3000",
                        "edge.domains": "git.example.com",
                    }
                }
            }
        },
        remote_files={
            ("ingress-1", "/etc/dokploy/traefik/dynamic/edge-sync.yml"): existing_yaml
        },
    )

    service = SyncService(app_config, fake_client)
    service.run()

    assert fake_client.updated_files == []
    assert fake_client.reloaded_servers == []


def test_sync_service_prefers_server_override(
    app_config,
    fake_client_factory,
):
    app_config.server_map_path.write_text("app-server: 100.64.0.99\n")

    fake_client = fake_client_factory(
        servers=[
            {
                "serverId": "ingress-1",
                "name": "ingress",
                "ipAddress": "192.168.1.10",
            },
            {
                "serverId": "app-1",
                "name": "app-server",
                "ipAddress": "203.0.113.55",
            },
        ],
        containers_by_server={
            "app-1": [
                {
                    "Id": "container-1",
                    "Names": ["/api"],
                }
            ]
        },
        inspect_by_container={
            ("app-1", "container-1"): {
                "Config": {
                    "Labels": {
                        "edge.enabled": "true",
                        "edge.port": "8080",
                        "edge.domains": "api.example.com",
                    }
                }
            }
        },
    )

    service = SyncService(app_config, fake_client)
    result = service.run()

    built_service = next(iter(result["http"]["services"].values()))
    assert built_service["loadBalancer"]["servers"][0]["url"] == "http://100.64.0.99:8080"


def test_sync_service_writes_state_file(
    app_config,
    fake_client_factory,
):
    fake_client = fake_client_factory(
        servers=[
            {
                "serverId": "ingress-1",
                "name": "ingress",
                "ipAddress": "192.168.1.10",
            }
        ],
    )

    service = SyncService(app_config, fake_client)
    service.run()

    assert app_config.state_path.exists()

    state = json.loads(app_config.state_path.read_text())
    assert state["ingressServerId"] == "ingress-1"
    assert state["targetFile"] == "/etc/dokploy/traefik/dynamic/edge-sync.yml"
