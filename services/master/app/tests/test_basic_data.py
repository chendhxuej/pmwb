"""人员中台 Master Service 基础测试。"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from main import app
from db.models import Base
from db.base import engine

client = TestClient(app)


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_staff_options_empty():
    resp = client.get("/api/v1/basic-data/staff-options")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0


def test_org_crud():
    # Create
    resp = client.post("/api/v1/basic-data/orgs", json={"name": "测试组织", "sort": 1})
    assert resp.status_code == 200
    data = resp.json()["data"]
    org_id = data["id"]
    assert data["name"] == "测试组织"

    # List
    resp = client.get("/api/v1/basic-data/orgs")
    assert resp.status_code == 200
    orgs = resp.json()["data"]
    assert len(orgs) >= 1

    # Update
    resp = client.put(f"/api/v1/basic-data/orgs/{org_id}", json={"sort": 99})
    assert resp.status_code == 200
    assert resp.json()["data"]["sort"] == 99

    # Delete
    resp = client.delete(f"/api/v1/basic-data/orgs/{org_id}")
    assert resp.status_code == 200


def test_staff_crud():
    # Create org first
    resp = client.post("/api/v1/basic-data/orgs", json={"name": "测试组织2"})
    org_id = resp.json()["data"]["id"]

    # Create staff
    resp = client.post("/api/v1/basic-data/staffs", json={
        "name": "张三", "org_id": org_id, "email": "zs@test.com"
    })
    assert resp.status_code == 200
    staff = resp.json()["data"]
    assert staff["name"] == "张三"
    assert staff["email"] == "zs@test.com"
    staff_id = staff["id"]

    # List
    resp = client.get("/api/v1/basic-data/staffs", params={"org_id": org_id})
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1

    # Staff options
    resp = client.get("/api/v1/basic-data/staff-options")
    assert resp.status_code == 200
    groups = resp.json()["data"]
    assert len(groups) >= 1
    assert groups[0]["options"][0]["value"] == "张三"

    # Update
    resp = client.put(f"/api/v1/basic-data/staffs/{staff_id}", json={"role_hint": "产品经理"})
    assert resp.status_code == 200

    # Delete
    resp = client.delete(f"/api/v1/basic-data/staffs/{staff_id}")
    assert resp.status_code == 200

    # Cleanup org
    client.delete(f"/api/v1/basic-data/orgs/{org_id}")


def test_template_download():
    resp = client.get("/api/v1/basic-data/template")
    assert resp.status_code == 200
    assert "spreadsheet" in resp.headers.get("content-type", "")
