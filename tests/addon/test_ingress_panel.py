import re

from fastapi.testclient import TestClient

from app.main import create_app


def test_ingress_serves_panel_and_built_assets() -> None:
    client = TestClient(create_app(require_token=False))

    response = client.get("/")

    assert response.status_code == 200
    assert "<mp-app></mp-app>" in response.text

    assets = re.findall(r'(?:src|href)="\./(assets/[^"]+)"', response.text)
    assert assets
    for asset in assets:
        asset_response = client.get(f"/{asset}")
        assert asset_response.status_code == 200
        assert asset_response.content


def test_ingress_unknown_api_route_keeps_json_not_found() -> None:
    client = TestClient(create_app(require_token=False))

    response = client.get("/api/not-a-route")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found", "details": {}}
    }


def test_internal_listener_does_not_serve_panel() -> None:
    client = TestClient(create_app(require_token=True, token="internal-test-token"))

    response = client.get("/")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
