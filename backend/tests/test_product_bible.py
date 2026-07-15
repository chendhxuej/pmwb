from fastapi.testclient import TestClient


def test_list_product_bible_catalog(client: TestClient):
    res = client.get("/api/v1/product-bible")
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 0
    keys = [c["key"] for c in body["data"]]
    assert "group-sms" in keys


def test_get_group_sms_bible(client: TestClient):
    res = client.get("/api/v1/product-bible/group-sms")
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 0
    data = body["data"]
    assert "markdown" in data
    assert "集团短信" in data["markdown"]
    assert data["title"]
    assert data["updated_at"] == "2026-07-15"


def test_get_unknown_bible_returns_404(client: TestClient):
    res = client.get("/api/v1/product-bible/does-not-exist")
    assert res.status_code == 404
    assert res.json()["code"] == 404
