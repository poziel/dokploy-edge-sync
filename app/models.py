from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(slots=True)
class Server:
    """
    Represents a Dokploy server returned by /server.all.

    The ip_address is the preferred upstream candidate coming from Dokploy,
    but it can still be overridden by the optional servers.yml mapping.
    """

    server_id: str
    name: str
    ip_address: str | None = None
    description: str | None = None


@dataclass(slots=True)
class ServiceTarget:
    """
    Represents one backend service that should be exposed through the edge Traefik.
    """

    name: str
    server_name: str
    target_host: str
    target_port: str
    scheme: str = "http"
    domains: list[str] = field(default_factory=list)
    middlewares: list[str] = field(default_factory=list)