from app.parsers import decode_traefik_file_content, parse_servers


def test_parse_servers_supports_server_all_shape():
    payload = [
        {
            "serverId": "abc123",
            "name": "ingress",
            "ipAddress": "192.168.1.10",
            "description": "Main ingress",
        }
    ]

    servers = parse_servers(payload)

    assert len(servers) == 1
    assert servers[0].server_id == "abc123"
    assert servers[0].name == "ingress"
    assert servers[0].ip_address == "192.168.1.10"
    assert servers[0].description == "Main ingress"


def test_decode_traefik_file_content_from_json_string():
    payload = '"http:\\n  routers: {}\\n"'
    content = decode_traefik_file_content(payload)

    assert "http:" in content
    assert "routers" in content


def test_decode_traefik_file_content_from_content_field():
    payload = {"content": '"hello\\nworld"'}
    content = decode_traefik_file_content(payload)

    assert content == "hello\nworld"