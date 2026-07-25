# -*- coding: utf-8 -*-
"""基础数据（组织+人员）接口测试。"""


def _create_org(client, name="测试组织", sort=0):
    resp = client.post("/api/v1/basic-data/orgs", json={"name": name, "sort": sort})
    assert resp.status_code == 200
    return resp.json()["data"]


def _create_staff(client, org_id, name="张三", **kw):
    payload = {"name": name, "org_id": org_id}
    payload.update(kw)
    resp = client.post("/api/v1/basic-data/staffs", json=payload)
    assert resp.status_code == 200
    return resp.json()["data"]


class TestOrgCrud:
    def test_org_lifecycle(self, client):
        org = _create_org(client, "政企客户部")
        assert org["name"] == "政企客户部"

        # 列表
        resp = client.get("/api/v1/basic-data/orgs")
        assert resp.status_code == 200
        assert any(o["name"] == "政企客户部" for o in resp.json()["data"])

        # 更新
        resp = client.put(f"/api/v1/basic-data/orgs/{org['id']}", json={"sort": 99})
        assert resp.status_code == 200
        assert resp.json()["data"]["sort"] == 99

        # 删除
        resp = client.delete(f"/api/v1/basic-data/orgs/{org['id']}")
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] is True

    def test_update_missing_org(self, client):
        resp = client.put("/api/v1/basic-data/orgs/99999", json={"name": "x"})
        assert resp.status_code == 404


class TestStaffCrud:
    def test_staff_lifecycle(self, client):
        org = _create_org(client, "CRM")
        staff = _create_staff(client, org["id"], "郑文东", email="a@b.com")
        assert staff["org_name"] == "CRM"

        # 列表（按组织过滤 + 关键字）
        resp = client.get(f"/api/v1/basic-data/staffs?org_id={org['id']}")
        assert len(resp.json()["data"]) == 1
        resp = client.get("/api/v1/basic-data/staffs?keyword=文东")
        assert len(resp.json()["data"]) == 1

        # 更新
        resp = client.put(
            f"/api/v1/basic-data/staffs/{staff['id']}", json={"role_hint": "接口人"}
        )
        assert resp.json()["data"]["role_hint"] == "接口人"

        # 删除
        resp = client.delete(f"/api/v1/basic-data/staffs/{staff['id']}")
        assert resp.json()["data"]["deleted"] is True

    def test_delete_org_cascades_staff(self, client):
        org = _create_org(client, "BOSS")
        _create_staff(client, org["id"], "陈增明")
        client.delete(f"/api/v1/basic-data/orgs/{org['id']}")
        resp = client.get("/api/v1/basic-data/staffs")
        assert all(s["name"] != "陈增明" for s in resp.json()["data"])


class TestStaffOptions:
    def test_grouped_options(self, client):
        org1 = _create_org(client, "政企客户部", sort=0)
        org2 = _create_org(client, "CRM", sort=10)
        _create_staff(client, org1["id"], "邵建")
        _create_staff(client, org2["id"], "郑文东")
        # 停用人员不应出现
        disabled = _create_staff(client, org2["id"], "停用者")
        client.put(f"/api/v1/basic-data/staffs/{disabled['id']}", json={"enabled": False})

        resp = client.get("/api/v1/basic-data/staff-options")
        assert resp.status_code == 200
        groups = resp.json()["data"]
        assert [g["org_name"] for g in groups] == ["政企客户部", "CRM"]
        crm_names = [o["value"] for g in groups if g["org_name"] == "CRM" for o in g["options"]]
        assert "郑文东" in crm_names and "停用者" not in crm_names

    def test_disabled_org_hidden(self, client):
        org = _create_org(client, "已停用组")
        _create_staff(client, org["id"], "某人")
        client.put(f"/api/v1/basic-data/orgs/{org['id']}", json={"enabled": False})
        resp = client.get("/api/v1/basic-data/staff-options")
        assert all(g["org_name"] != "已停用组" for g in resp.json()["data"])
