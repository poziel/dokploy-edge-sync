from __future__ import annotations

from app.models import ServiceTarget
from app.traefik_builder import TraefikConfigBuilder


def test_build_generates_routers_and_services():
    builder = TraefikConfigBuilder(
        entrypoints=["websecure"],
        cert_resolver="letsencrypt",
    )

    targets = [
        ServiceTarget(
            name="gitea",
            server_name="app-server",
            target_host="192.168.1.20",
            target_port="3000",
            scheme="http",
            domains=["git.example.com"],
            middlewares=["auth@file"],
        )
    ]

    result = builder.build(targets)

    services = result["http"]["services"]
    routers = result["http"]["routers"]

    assert "svc-app-server-gitea" in services
    assert len(routers) == 1

    router = next(iter(routers.values()))
    assert router["rule"] == "Host(`git.example.com`)"
    assert router["entryPoints"] == ["websecure"]
    assert router["tls"]["certResolver"] == "letsencrypt"
    assert router["middlewares"] == ["auth@file"]

    service = services["svc-app-server-gitea"]
    assert service["loadBalancer"]["servers"][0]["url"] == "http://192.168.1.20:3000"
