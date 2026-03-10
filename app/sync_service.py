from __future__ import annotations

import json
import logging

import yaml

from app.config import AppConfig
from app.dokploy_client import DokployClient
from app.models import ServiceTarget
from app.parsers import (
    decode_traefik_file_content,
    extract_container_name,
    extract_domain_values,
    extract_domains_from_labels,
    extract_labels,
    extract_middlewares,
    extract_scheme,
    extract_target_port,
    is_domain_allowed,
    normalize_domain,
    parse_servers,
    should_expose,
)
from app.traefik_builder import TraefikConfigBuilder
from app.utils import looks_like_ip_or_host, pick, unwrap_list

logger = logging.getLogger(__name__)


class SyncService:
    """
    Main orchestration service for the Dokploy -> Traefik edge sync workflow.

    New flow:
    1. Discover servers with /server.all
    2. Discover services from Dokploy
    3. Generate one Traefik file for the ingress server
    4. Read current remote file
    5. Update only if changed
    6. Reload Traefik only if needed
    """

    def __init__(self, config: AppConfig, client: DokployClient) -> None:
        self.config = config
        self.client = client
        self.server_overrides = config.load_server_overrides()

    def run(self) -> dict:
        servers = parse_servers(self.client.get_servers())
        logger.info("Discovered %s servers", len(servers))

        ingress_server = self.find_ingress_server(servers)
        logger.info(
            "Using ingress server: %s (%s)",
            ingress_server.name,
            ingress_server.server_id,
        )

        targets = self.build_targets(servers)

        builder = TraefikConfigBuilder(
            entrypoints=self.config.traefik_entrypoints,
            cert_resolver=self.config.traefik_cert_resolver,
        )
        generated_config = builder.build(targets)
        rendered_config = yaml.safe_dump(
            generated_config,
            sort_keys=False,
            allow_unicode=True,
        )

        current_config = self.read_current_remote_file(
            ingress_server.server_id,
            self.config.ingress_traefik_dynamic_file,
        )

        changed = self.normalize_yaml_text(current_config) != self.normalize_yaml_text(rendered_config)

        logger.info("Generated config changed: %s", changed)

        if self.config.dry_run:
            print(rendered_config)
            self.write_state(generated_config, changed, ingress_server.server_id)
            return generated_config

        if changed:
            self.client.update_traefik_file(
                ingress_server.server_id,
                self.config.ingress_traefik_dynamic_file,
                rendered_config,
            )
            logger.info("Updated remote Traefik file: %s", self.config.ingress_traefik_dynamic_file)

            if self.config.reload_on_change:
                self.client.reload_traefik(ingress_server.server_id)
                logger.info("Reloaded Traefik on ingress server")

        self.write_state(generated_config, changed, ingress_server.server_id)
        return generated_config

    def build_targets(self, servers: list) -> list[ServiceTarget]:
        """
        Build normalized backend targets from Dokploy-discovered servers and containers.
        """
        targets: list[ServiceTarget] = []

        for server in servers:
            target_host = self.resolve_server_host(server.name, server.ip_address)
            if not target_host:
                logger.warning("Skipping server %s: no usable host found", server.name)
                continue

            try:
                containers_payload = self.client.get_containers(server.server_id)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to list containers for %s: %s", server.name, exc)
                continue

            containers = unwrap_list(containers_payload)
            logger.info("Server %s: found %s containers", server.name, len(containers))

            for container in containers:
                container_id = pick(container, "Id", "id", "containerId")
                container_name = extract_container_name(container)

                if not container_id:
                    continue

                try:
                    inspect_payload = self.client.get_container_config(server.server_id, str(container_id))
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Failed to inspect container %s on %s: %s",
                        container_name,
                        server.name,
                        exc,
                    )
                    continue

                labels = extract_labels(inspect_payload)

                if not should_expose(labels, self.config.exposed_by_default):
                    continue

                domains = self.discover_domains(inspect_payload, labels)
                domains = [
                    domain
                    for domain in domains
                    if is_domain_allowed(
                        domain,
                        self.config.allowed_domain_suffixes,
                        self.config.domain_blocklist,
                    )
                ]

                if not domains:
                    continue

                port = extract_target_port(labels, inspect_payload)
                if not port:
                    logger.warning(
                        "Skipping container %s on %s: no target port found",
                        container_name,
                        server.name,
                    )
                    continue

                targets.append(
                    ServiceTarget(
                        name=container_name,
                        server_name=server.name,
                        target_host=target_host,
                        target_port=port,
                        scheme=extract_scheme(labels),
                        domains=domains,
                        middlewares=extract_middlewares(labels),
                    )
                )

        return targets

    def discover_domains(self, inspect_payload: dict, labels: dict[str, str]) -> list[str]:
        """
        Discover domains for a service.

        Priority:
        1. Dokploy domain endpoints
        2. Traefik or edge labels
        """
        domains: list[str] = []

        application_id = self.deep_pick(inspect_payload, "applicationId", "appId")
        compose_id = self.deep_pick(inspect_payload, "composeId")

        if application_id:
            try:
                domains.extend(
                    extract_domain_values(
                        self.client.get_application_domains(str(application_id))
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Could not fetch application domains for %s: %s", application_id, exc)

        if compose_id:
            try:
                domains.extend(
                    extract_domain_values(
                        self.client.get_compose_domains(str(compose_id))
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Could not fetch compose domains for %s: %s", compose_id, exc)

        if not domains:
            domains = extract_domains_from_labels(labels)

        seen: set[str] = set()
        result: list[str] = []

        for domain in domains:
            normalized = normalize_domain(domain)
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)

        return result

    def find_ingress_server(self, servers: list):
        """
        Find the configured ingress server by exact name match.
        """
        wanted = self.config.ingress_server_name.strip().lower()

        for server in servers:
            if server.name.strip().lower() == wanted:
                return server

        raise ValueError(
            f'Could not find ingress server named "{self.config.ingress_server_name}"'
        )

    def resolve_server_host(self, server_name: str, discovered_ip: str | None) -> str | None:
        """
        Resolve the preferred backend address for a server.

        Order:
        1. optional override from servers.yml
        2. discovered ipAddress from /server.all
        """
        override = self.server_overrides.get(server_name.strip().lower())
        if override:
            return override

        if discovered_ip and looks_like_ip_or_host(discovered_ip):
            return discovered_ip

        return None

    def read_current_remote_file(self, server_id: str, path: str) -> str:
        """
        Read the current Traefik file content from Dokploy.

        If the file does not exist or cannot be read, return an empty string so
        the next write behaves like a create.
        """
        try:
            payload = self.client.read_traefik_file(server_id, path)
            return decode_traefik_file_content(payload)
        except Exception as exc:  # noqa: BLE001
            logger.info("Could not read remote file %s: %s", path, exc)
            return ""

    def write_state(self, output: dict, changed: bool, ingress_server_id: str) -> None:
        self.config.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.state_path.write_text(
            json.dumps(
                {
                    "changed": changed,
                    "ingressServerId": ingress_server_id,
                    "targetFile": self.config.ingress_traefik_dynamic_file,
                    "routers": list(output.get("http", {}).get("routers", {}).keys()),
                    "services": list(output.get("http", {}).get("services", {}).keys()),
                },
                indent=2,
            )
        )

    @staticmethod
    def normalize_yaml_text(content: str) -> str:
        """
        Normalize YAML before comparing to avoid false positives caused only by
        formatting differences.
        """
        if not content.strip():
            return ""

        try:
            parsed = yaml.safe_load(content)
            return yaml.safe_dump(parsed, sort_keys=True, allow_unicode=True).strip()
        except Exception:  # noqa: BLE001
            return content.strip()

    @staticmethod
    def deep_pick(payload: dict, *keys: str):
        """
        Recursively search nested dictionaries/lists for the first matching key.

        This is helpful because Dokploy inspect payloads can wrap metadata in
        slightly different shapes.
        """
        if not isinstance(payload, (dict, list)):
            return None

        if isinstance(payload, dict):
            for key in keys:
                if key in payload and payload[key] not in (None, ""):
                    return payload[key]

            for value in payload.values():
                found = SyncService.deep_pick(value, *keys)
                if found not in (None, ""):
                    return found

        if isinstance(payload, list):
            for item in payload:
                found = SyncService.deep_pick(item, *keys)
                if found not in (None, ""):
                    return found

        return None
