# Dokploy Edge Sync

<p align="center">
  <b>Automatic Traefik edge routing for multi-server Dokploy deployments</b>
</p>

<p align="center">
  Discover Dokploy services and publish them through a centralized Traefik ingress using the Dokploy API.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.12-blue">
  <img alt="Docker" src="https://img.shields.io/badge/docker-ready-blue">
  <img alt="License" src="https://img.shields.io/github/license/poziel/dokploy-edge-sync">
  <img alt="Stars" src="https://img.shields.io/github/stars/poziel/dokploy-edge-sync">
</p>

---

## Overview

**Dokploy Edge Sync** is a lightweight service that discovers applications deployed through **Dokploy** and generates dynamic **Traefik routing configuration** for a single ingress server.

Instead of writing directly to a mounted Traefik directory, the service uses the **Dokploy API** to:

- discover servers
- inspect deployed services
- generate Traefik dynamic configuration
- update a managed Traefik file on the ingress server
- reload Traefik only when the generated config changes

This makes it well-suited for environments where services are distributed across multiple hosts but should be exposed through one centralized edge router.

---

## Features

- Automatic **Dokploy server discovery**
- Automatic **service and domain discovery**
- Centralized **Traefik ingress routing**
- API-based **Traefik file management**
- Reloads Traefik **only when configuration changes**
- Configurable **domain filtering and exposure rules**
- Optional **server address overrides**
- Supports both **internal scheduling** and **external scheduled jobs**
- Lightweight (**Python + Docker container**)

---

## How It Works

Dokploy Edge Sync follows this workflow:

1. Query the Dokploy API for all known servers
2. Resolve ingress server identity from `/settings.getWebServerSettings`
3. Discover eligible containers and their routing metadata
4. Build a Traefik dynamic configuration in memory
5. Read the current remote Traefik file from the ingress server
6. Compare the existing and generated configurations
7. Update the file only if the content changed
8. Reload Traefik only if an update was applied

This keeps the setup simple and avoids unnecessary reloads.

---

## Example Generated Traefik Configuration

```yaml
http:
  routers:
    example-service:
      rule: Host(`example.domain`)
      entryPoints:
        - websecure
      service: svc-example-service
      tls:
        certResolver: letsencrypt

  services:
    svc-example-service:
      loadBalancer:
        passHostHeader: true
        servers:
          - url: http://10.0.0.12:3000

  middlewares: {}
```

---

## Quick Start

```bash
git clone https://github.com/poziel/dokploy-edge-sync
cd dokploy-edge-sync

cp .env.example .env
cp config/servers.example.yml config/servers.yml

docker compose up -d
```

---

## Requirements

- A running **Dokploy** instance with API access
- A server in Dokploy designated as the **central ingress**
- **Traefik** managed by Dokploy on the ingress server
- **Docker** and **Docker Compose**

---

## Configuration

The application is configured primarily through environment variables.

### Required

- `DOKPLOY_API_BASE`
- `DOKPLOY_API_TOKEN`

### Important Optional Settings

- `INGRESS_TRAEFIK_DYNAMIC_FILE`
- `RELOAD_ON_CHANGE`
- `ALLOWED_DOMAIN_SUFFIXES`
- `DOMAIN_BLOCKLIST`
- `SERVER_MAP_PATH`
- `DRY_RUN`

See `.env.example` for the full list.

---

## Server Address Resolution

By default, the service uses the server addresses returned by Dokploy from the `server.all` endpoint.

An optional `servers.yml` file can be provided to override those addresses when needed.

This is useful when:

- Dokploy returns a public IP but you want to use a private VPN address
- you prefer LAN routing over public routing
- the discovered hostname is not the best upstream target for the ingress server

Example:

```yaml
# Optional override map for Dokploy servers.
# Keys should match the exact server names returned by Dokploy.

app-server: 192.168.1.20
production-server: 100.64.0.15
staging-server: staging.internal.example
```

If `servers.yml` is missing, Dokploy Edge Sync will fall back to the addresses returned by Dokploy.

---

## Service Exposure Rules

Applications can be included in the generated edge routing using labels.

### Recommended labels

```yaml
labels:
  - traefik.enable=true
  - edge.enabled=true
  - edge.port=3000
```

### Optional labels

```yaml
labels:
  - edge.scheme=http
  - edge.middlewares=auth-chain@file,security-headers@file
  - edge.domains=example.domain,alt.domain
```

### Label behavior

- `edge.enabled=true` explicitly marks a service for inclusion
- `edge.port` defines the upstream port used by the edge router
- `edge.scheme` overrides the upstream scheme (`http` or `https`)
- `edge.middlewares` attaches Traefik middlewares to generated routers
- `edge.domains` can be used as a fallback or override for discovered domains

If `edge.enabled` is not present, the tool falls back to `traefik.enable`, then to the global `EXPOSED_BY_DEFAULT` setting.

---

## Scheduling Modes

This project supports multiple runtime modes.

### 1. External scheduler mode

Use a platform scheduler such as **Dokploy Scheduled Tasks** and keep the container alive between runs.

Recommended settings:

```dotenv
RUN_ON_STARTUP=true
ENABLE_INTERNAL_SCHEDULER=false
IDLE_AFTER_START=true
```

Then trigger the sync with:

```bash
python /app/edge_sync.py
```

### 2. Internal scheduler mode

Let the container run the sync repeatedly on its own interval.

```dotenv
RUN_ON_STARTUP=true
ENABLE_INTERNAL_SCHEDULER=true
SYNC_INTERVAL_SECONDS=300
IDLE_AFTER_START=true
```

### 3. Manual mode

Do not run automatically. Keep the container alive and execute the sync only when needed.

```dotenv
RUN_ON_STARTUP=false
ENABLE_INTERNAL_SCHEDULER=false
IDLE_AFTER_START=true
```

---

## Testing

Install dependencies:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Run the test suite:

```bash
pytest -v
```

The test suite covers:

- configuration loading
- Dokploy response parsing
- Traefik config generation
- sync logic
- server override handling
- change detection and conditional Traefik reloads

---

## Security Notes

- Treat `DOKPLOY_API_TOKEN` as a secret
- Keep `SKIP_TLS_VERIFY=false` in normal environments
- Prefer private or internal addresses for upstream routing
- Only expose services intentionally using labels
- Do **not** use this project to manage sensitive Traefik files such as `acme.json`

Dokploy Edge Sync is designed to manage a dedicated generated file, for example:

```text
/etc/dokploy/traefik/dynamic/edge-sync.yml
```

It should not modify certificate storage or core Traefik configuration unless you explicitly extend it to do so.

---

## Use Cases

This project is useful for:

- homelabs
- distributed Docker environments
- centralized ingress architectures
- self-hosted platforms using Dokploy
- multi-server application hosting with one public edge router

---

## License

MIT
