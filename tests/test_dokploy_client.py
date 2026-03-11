from __future__ import annotations

from app.dokploy_client import DokployClient


class _FakeResponse:
    def __init__(self, text: str, payload):
        self.text = text
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, get_responses=None, post_responses=None):
        self.headers = {}
        self.verify = True
        self._get_responses = get_responses or []
        self._post_responses = post_responses or []
        self.get_calls = []
        self.post_calls = []

    def get(self, url, params=None, timeout=None):
        self.get_calls.append(
            {
                "url": url,
                "params": params,
                "timeout": timeout,
            }
        )
        return self._get_responses.pop(0)

    def post(self, url, json=None, timeout=None):
        self.post_calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
            }
        )
        return self._post_responses.pop(0)


def test_get_and_post_decode_empty_or_json_response(monkeypatch, app_config):
    fake_session = _FakeSession(
        get_responses=[
            _FakeResponse("", {"ignored": True}),
            _FakeResponse('{"ok": true}', {"ok": True}),
        ],
        post_responses=[
            _FakeResponse("", {"ignored": True}),
            _FakeResponse('{"saved": true}', {"saved": True}),
        ],
    )
    monkeypatch.setattr("app.dokploy_client.requests.Session", lambda: fake_session)

    client = DokployClient(app_config)

    assert client.get("/server.all") == {}
    assert client.get("/server.all") == {"ok": True}
    assert client.post("/settings.reloadTraefik", {"serverId": "s-1"}) == {}
    assert client.post("/settings.reloadTraefik", {"serverId": "s-1"}) == {"saved": True}

    first_get = fake_session.get_calls[0]
    assert first_get["url"] == "https://dokploy.example/api/server.all"
    assert first_get["timeout"] == 20

    first_post = fake_session.post_calls[0]
    assert first_post["url"] == "https://dokploy.example/api/settings.reloadTraefik"
    assert first_post["json"] == {"serverId": "s-1"}
    assert first_post["timeout"] == 20


def test_endpoint_wrapper_paths_and_payloads(app_config):
    client = DokployClient(app_config)
    calls: list[tuple[str, str, dict | None]] = []

    client.get = lambda path, params=None: calls.append(("get", path, params)) or {}
    client.post = lambda path, json_body: calls.append(("post", path, json_body)) or {}

    client.get_servers()
    client.get_destinations()
    client.get_containers("srv-1")
    client.get_container_config("srv-1", "ct-1")
    client.get_application_domains("app-1")
    client.get_compose_domains("cmp-1")
    client.read_directories("srv-1")
    client.get_web_server_settings()
    client.read_traefik_file("srv-1", "/tmp/file.yml")
    client.update_traefik_file("srv-1", "/tmp/file.yml", "http:\n  routers: {}")
    client.reload_traefik("srv-1")

    assert calls == [
        ("get", "/server.all", None),
        ("get", "/destination.all", None),
        ("get", "/docker.getContainers", {"serverId": "srv-1"}),
        ("get", "/docker.getConfig", {"serverId": "srv-1", "containerId": "ct-1"}),
        ("get", "/domain.byApplicationId", {"applicationId": "app-1"}),
        ("get", "/domain.byComposeId", {"composeId": "cmp-1"}),
        ("get", "/settings.readDirectories", {"serverId": "srv-1"}),
        ("get", "/settings.getWebServerSettings", None),
        ("get", "/settings.readTraefikFile", {"serverId": "srv-1", "path": "/tmp/file.yml"}),
        (
            "post",
            "/settings.updateTraefikFile",
            {
                "serverId": "srv-1",
                "path": "/tmp/file.yml",
                "traefikConfig": "http:\n  routers: {}",
            },
        ),
        ("post", "/settings.reloadTraefik", {"serverId": "srv-1"}),
    ]
