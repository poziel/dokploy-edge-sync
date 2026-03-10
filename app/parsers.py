from __future__ import annotations

import json
import re
from typing import Any

from app.models import Server
from app.utils import pick, unwrap_list


def parse_servers(payload: Any) -> list[Server]:
    """
    Parse /server.all response into Server models.

    Expected fields are based on the Dokploy API response shape:
    - serverId
    - name
    - ipAddress
    """
    servers: list[Server] = []

    for item in unwrap_list(payload):
        server_id = pick(item, "serverId", "id")
        name = pick(item, "name", default="")
        ip_address = pick(item, "ipAddress", "ip", "host", "hostname")
        description = pick(item, "description")

        if not server_id or not name:
            continue

        servers.append(
            Server(
                server_id=str(server_id),
                name=str(name),
                ip_address=str(ip_address) if ip_address else None,
                description=str(description) if description else None,
            )
        )

    return servers


def extract_container_name(container: dict[str, Any]) -> str:
    name = pick(container, "Names", "Name", "name")

    if isinstance(name, list) and name:
        return str(name[0]).lstrip("/")

    return str(name or "container").lstrip("/")


def extract_labels(payload: dict[str, Any]) -> dict[str, str]:
    if "Config" in payload and isinstance(payload["Config"], dict):
        labels = payload["Config"].get("Labels")
        if isinstance(labels, dict):
            return {str(k): str(v) for k, v in labels.items()}

    for key in ("labels", "Labels"):
        labels = payload.get(key)
        if isinstance(labels, dict):
            return {str(k): str(v) for k, v in labels.items()}

    for nested_key in ("data", "inspect"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            return extract_labels(nested)

    return {}


def extract_domains_from_rule(rule: str) -> list[str]:
    matches: list[str] = []

    for host_call in re.findall(r"Host\((.*?)\)", rule):
        for domain in re.findall(r"[`'\"]([^`'\"]+)[`'\"]", host_call):
            matches.append(domain)

    return matches


def normalize_domain(domain: str | None) -> str | None:
    if not domain:
        return None

    value = str(domain).strip().lower().rstrip(".")
    value = value.replace("https://", "").replace("http://", "")

    if "/" in value:
        value = value.split("/", 1)[0]

    return value or None


def extract_domains_from_labels(labels: dict[str, str]) -> list[str]:
    domains: list[str] = []

    for key, value in labels.items():
        if key.startswith("traefik.http.routers.") and key.endswith(".rule"):
            domains.extend(extract_domains_from_rule(value))

    extra_domains = labels.get("edge.domains")
    if extra_domains:
        domains.extend(
            part.strip()
            for part in re.split(r"[,;\s]+", extra_domains)
            if part.strip()
        )

    seen: set[str] = set()
    result: list[str] = []

    for domain in domains:
        normalized = normalize_domain(domain)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    return result


def extract_domain_values(payload: Any) -> list[str]:
    domains: list[str] = []

    for item in unwrap_list(payload):
        if isinstance(item, str):
            domains.append(item)
            continue

        if isinstance(item, dict):
            for key in ("domain", "host", "hostname", "name"):
                value = item.get(key)
                if value:
                    domains.append(str(value))
                    break

    return domains


def extract_target_port(labels: dict[str, str], payload: dict[str, Any]) -> str | None:
    explicit_port = labels.get("edge.port")
    if explicit_port:
        return explicit_port

    for key, value in labels.items():
        if key.endswith(".loadbalancer.server.port"):
            return str(value)

    exposed_ports: list[str] = []

    config = payload.get("Config") or {}
    if isinstance(config, dict):
        ports = config.get("ExposedPorts") or {}
        if isinstance(ports, dict):
            exposed_ports.extend(str(port).split("/", 1)[0] for port in ports.keys())

    network_settings = payload.get("NetworkSettings") or {}
    if isinstance(network_settings, dict):
        ports = network_settings.get("Ports") or {}
        if isinstance(ports, dict):
            exposed_ports.extend(str(port).split("/", 1)[0] for port in ports.keys())

    unique_ports = sorted(set(exposed_ports), key=lambda p: int(p) if p.isdigit() else p)

    if len(unique_ports) == 1:
        return unique_ports[0]

    return None


def extract_scheme(labels: dict[str, str]) -> str:
    for key, value in labels.items():
        if key.endswith(".loadbalancer.server.scheme"):
            scheme = value.strip().lower()
            return scheme if scheme in {"http", "https"} else "http"

    scheme = labels.get("edge.scheme", "http").strip().lower()
    return scheme if scheme in {"http", "https"} else "http"


def extract_middlewares(labels: dict[str, str]) -> list[str]:
    refs: list[str] = []

    custom = labels.get("edge.middlewares")
    if custom:
        refs.extend(item.strip() for item in custom.split(",") if item.strip())
    else:
        for key, value in labels.items():
            if key.startswith("traefik.http.routers.") and key.endswith(".middlewares"):
                refs.extend(item.strip() for item in value.split(",") if item.strip())

    seen: set[str] = set()
    result: list[str] = []

    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            result.append(ref)

    return result


def should_expose(labels: dict[str, str], exposed_by_default: bool) -> bool:
    edge_enabled = labels.get("edge.enabled")
    if edge_enabled is not None:
        return edge_enabled.lower() == "true"

    traefik_enabled = labels.get("traefik.enable")
    if traefik_enabled is not None:
        return traefik_enabled.lower() == "true"

    return exposed_by_default


def is_domain_allowed(
    domain: str,
    allowed_suffixes: list[str],
    blocklist: set[str],
) -> bool:
    normalized = normalize_domain(domain)
    if not normalized:
        return False

    if normalized in blocklist:
        return False

    if not allowed_suffixes:
        return True

    return any(normalized.endswith(suffix) for suffix in allowed_suffixes)


def decode_traefik_file_content(payload: Any) -> str:
    """
    Decode the response from /settings.readTraefikFile.

    Dokploy returns the file content as a JSON string containing escaped content.
    This helper normalizes that into plain file text.

    Examples:
    - {"content":"..."} -> use content
    - "...\n..." -> decode JSON string
    - plain text -> return as-is
    """
    if isinstance(payload, dict):
        for key in ("content", "data", "value"):
            value = payload.get(key)
            if isinstance(value, str):
                return decode_traefik_file_content(value)

    if isinstance(payload, str):
        try:
            decoded = json.loads(payload)
            if isinstance(decoded, str):
                return decoded
        except json.JSONDecodeError:
            return payload

        return payload

    return ""