from __future__ import annotations

import re
import socket
from typing import Any


def pick(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Return the first non-empty value found for any of the provided keys.

    This is useful because Dokploy responses may vary slightly by endpoint
    or version.
    """
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def unwrap_list(payload: Any) -> list[dict[str, Any]]:
    """
    Normalize various API response shapes into a list of dictionaries.

    Supported examples:
    - [...]
    - {"data": [...]}
    - {"items": [...]}
    - {"containers": [...]}
    - {"destinations": [...]}
    """
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("data", "items", "results", "destinations", "containers"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

        return [payload]

    return []


def slugify(value: str) -> str:
    """Convert a string to a Traefik-safe identifier."""
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def looks_like_ip_or_host(value: str) -> bool:
    """
    Return True if the value resolves like a hostname/IP or at least matches
    a valid host-like pattern.
    """
    try:
        socket.getaddrinfo(value, None)
        return True
    except socket.gaierror:
        return bool(re.match(r"^[a-z0-9.-]+$", value, re.IGNORECASE))