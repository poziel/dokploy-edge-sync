from __future__ import annotations

from app.models import ServiceTarget
from app.utils import slugify


class TraefikConfigBuilder:
    """
    Build a Traefik file-provider configuration from normalized service targets.

    This class only knows about Traefik output structure. It does not care where
    the targets came from.
    """

    def __init__(self, entrypoints: list[str], cert_resolver: str) -> None:
        self.entrypoints = entrypoints
        self.cert_resolver = cert_resolver

    def build(self, targets: list[ServiceTarget]) -> dict:
        config: dict = {
            "http": {
                "routers": {},
                "services": {},
                "middlewares": {},
            }
        }

        for target in targets:
            service_name = f"svc-{slugify(f'{target.destination_name}-{target.name}')}"
            config["http"]["services"][service_name] = {
                "loadBalancer": {
                    "passHostHeader": True,
                    "servers": [
                        {
                            "url": f"{target.scheme}://{target.target_host}:{target.target_port}"
                        }
                    ],
                }
            }

            for domain in target.domains:
                router_name = slugify(f"{target.destination_name}-{target.name}-{domain}")
                router_config = {
                    "rule": f"Host(`{domain}`)",
                    "entryPoints": self.entrypoints,
                    "service": service_name,
                    "tls": {"certResolver": self.cert_resolver},
                }

                if target.middlewares:
                    router_config["middlewares"] = target.middlewares

                config["http"]["routers"][router_name] = router_config

        return config