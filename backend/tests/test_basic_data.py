# -*- coding: utf-8 -*-
"""基础数据（组织+人员）接口测试。"""

import uuid


def _unique_name(prefix="测试"):
    """生成唯一名称避免测试间数据冲突。"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _create_org(client, name="测试组织", sort=0):
    resp = client.post("/api/v1/basic-data/orgs", json={"name": name, "sort": sort})
    assert resp.status_code == 200, f"创建组织失败: {resp.text}"
    return resp.json()["data"]


def _create_staff(client, org_id, name="张三", **kw):
    payload = {"name": name, "org_id": org_id}
    payload.update(kw)
    resp = client.post("/api/v1/basic-data/staffs", json=payload)
    assert resp.status_code == 200, f"创建人员失败: {resp.text}"
    return resp.json()["data"]


class TestOrgCrud:
    def test_org_lifecycle(self, client):
        name = _unique_name("政企客户部")
        org = _create_org(client, name)
        assert org["name"] == name

        # 列表
        resp = client.get("/api/v1/basic-data/orgs")
        assert resp.status_code == 200
        assert any(o["name"] == name for o in resp.json()["data"])

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
        org_name = _unique_name("CRM")
        org = _create_org(client, org_name)
        staff = _create_staff(client, org["id"], "郑文东", email="a@b.com")
        assert staff["org_name"] == org_name

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

        # 删除人员
        resp = client.delete(f"/api/v1/basic-data/staffs/{staff['id']}")
        assert resp.json()["data"]["deleted"] is True
        # 清理组织
        client.delete(f"/api/v1/basic-data/orgs/{org['id']}")

    def test_delete_org_cascades_staff(self, client):
        org_name = _unique_name("BOSS")
        org = _create_org(client, org_name)
        staff_name = _unique_name("成员")
        staff = _create_staff(client, org["id"], staff_name)
        client.delete(f"/api/v1/basic-data/orgs/{org['id']}")
        resp = client.get("/api/v1/basic-data/staffs")
        staff_ids = [s["id"] for s in resp.json()["data"]]
        # 删除组织应级联删除其下人员（按 id 判定，避免与真实人员重名干扰）
        assert staff["id"] not in staff_ids


class TestStaffOptions:
    def test_grouped_options(self, client):
        org1_name = _unique_name("政企客户部")
        org2_name = _unique_name("CRM")
        org1 = _create_org(client, org1_name, sort=0)
        org2 = _create_org(client, org2_name, sort=10)
        _create_staff(client, org1["id"], "邵建")
        _create_staff(client, org2["id"], "郑文东")
        # 停用人员不应出现
        disabled = _create_staff(client, org2["id"], "停用者")
        client.put(f"/api/v1/basic-data/staffs/{disabled['id']}", json={"enabled": False})

        resp = client.get("/api/v1/basic-data/staff-options")
        assert resp.status_code == 200
        groups = resp.json()["data"]
        # 只关注我们创建的测试组织
        test_groups = [g for g in groups if g["org_name"] in (org1_name, org2_name)]
        assert len(test_groups) == 2
        assert [g["org_name"] for g in test_groups] == [org1_name, org2_name]
        crm_names = [o["value"] for g in test_groups if g["org_name"] == org2_name for o in g["options"]]
        assert "郑文东" in crm_names and "停用者" not in crm_names

        # 清理
        client.delete(f"/api/v1/basic-data/orgs/{org1['id']}")
        client.delete(f"/api/v1/basic-data/orgs/{org2['id']}")

    def test_disabled_org_hidden(self, client):
        org_name = _unique_name("已停用组")
        org = _create_org(client, org_name)
        _create_staff(client, org["id"], "某人")
        client.put(f"/api/v1/basic-data/orgs/{org['id']}", json={"enabled": False})
        resp = client.get("/api/v1/basic-data/staff-options")
        assert all(g["org_name"] != org_name for g in resp.json()["data"])
        # 清理
        client.delete(f"/api/v1/basic-data/orgs/{org['id']}")
