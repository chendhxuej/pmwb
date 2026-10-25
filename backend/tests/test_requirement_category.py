"""需求分类字典 CRUD 回归（2026-10-25）。

覆盖：列表带引用计数 / options 只含启用 / 新增去重 400 / 改名级联更新工单 /
被引用禁删 400 / 未引用可删。
"""
from fastapi.testclient import TestClient

from db.models import PmwbRequirementCategory
from tests.factories import RequirementExtFactory


def _seed_req(client, db, req_id: str, category: str = None):
    """造一个带分类的需求工单（直接写 ext，模拟已登记工单）。"""
    from tests.test_requirement import _create_sent_email

    _create_sent_email(db, req_id=req_id)
    RequirementExtFactory.create(db, req_id=req_id, status="proposed", category=category)


def test_category_list_and_options(client: TestClient, db):
    """列表含 ref_count；options 只含启用的 name（预置 7 类由迁移种子保证，
    测试库为 create_all 空库不含种子，预置校验在真实环境冒烟执行）。"""
    create = client.post("/api/v1/requirements/categories", json={"name": "业务流程优化", "sort_order": 10})
    assert create.status_code == 200
    cid = create.json()["data"]["id"]
    client.post("/api/v1/requirements/categories", json={"name": "智能应用", "sort_order": 20})

    resp = client.get("/api/v1/requirements/categories")
    assert resp.status_code == 200
    cats = resp.json()["data"]
    names = [c["name"] for c in cats]
    assert {"业务流程优化", "智能应用"} <= set(names)
    assert all("ref_count" in c for c in cats)

    resp2 = client.get("/api/v1/requirements/categories/options")
    assert resp2.status_code == 200
    opts = resp2.json()["data"]
    assert {"业务流程优化", "智能应用"} <= {o["name"] for o in opts}

    for i in (cid,):
        client.delete(f"/api/v1/requirements/categories/{i}")
    cats2 = client.get("/api/v1/requirements/categories").json()["data"]
    zid = next(c["id"] for c in cats2 if c["name"] == "智能应用")
    client.delete(f"/api/v1/requirements/categories/{zid}")


def test_category_create_duplicate_rejected(client: TestClient, db):
    """重名 400；新建成功后出现在列表。"""
    resp = client.post("/api/v1/requirements/categories", json={"name": "测试新分类", "sort_order": 99})
    assert resp.status_code == 200
    new_id = resp.json()["data"]["id"]

    dup = client.post("/api/v1/requirements/categories", json={"name": "测试新分类"})
    assert dup.status_code == 400
    assert "已存在" in dup.json()["detail"]

    empty = client.post("/api/v1/requirements/categories", json={"name": "  "})
    assert empty.status_code == 400

    # 清理
    client.delete(f"/api/v1/requirements/categories/{new_id}")


def test_category_rename_cascades_ext(client: TestClient, db):
    """改名级联：存量工单 ext.category 同步更新（统计口径不分裂）。"""
    _seed_req(client, db, "REQ-CATC-001", category="旧分类名")

    create = client.post("/api/v1/requirements/categories", json={"name": "旧分类名", "sort_order": 98})
    assert create.status_code == 200
    cat_id = create.json()["data"]["id"]

    resp = client.put(f"/api/v1/requirements/categories/{cat_id}", json={"name": "新分类名"})
    assert resp.status_code == 200

    detail = client.get("/api/v1/requirements/REQ-CATC-001").json()["data"]
    assert detail["ext"]["category"] == "新分类名"

    ref = client.get("/api/v1/requirements/categories").json()["data"]
    row = next(c for c in ref if c["id"] == cat_id)
    assert row["ref_count"] == 1

    # 被引用 → 禁删 400；先清工单分类再删成功
    del_resp = client.delete(f"/api/v1/requirements/categories/{cat_id}")
    assert del_resp.status_code == 400
    assert "停用" in del_resp.json()["detail"]

    client.put("/api/v1/requirements/REQ-CATC-001", json={"category": ""})
    del_resp2 = client.delete(f"/api/v1/requirements/categories/{cat_id}")
    assert del_resp2.status_code == 200
    assert del_resp2.json()["data"]["deleted"] is True


def test_category_delete_not_found(client: TestClient, db):
    resp = client.delete("/api/v1/requirements/categories/999999")
    assert resp.status_code == 400


def test_category_disable_hides_from_options(client: TestClient, db):
    """停用后 options 不再出现；列表仍可见（存量工单保留展示）。"""
    create = client.post("/api/v1/requirements/categories", json={"name": "待停用分类", "sort_order": 97})
    cat_id = create.json()["data"]["id"]

    resp = client.put(f"/api/v1/requirements/categories/{cat_id}", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False

    opts = client.get("/api/v1/requirements/categories/options").json()["data"]
    assert "待停用分类" not in {o["name"] for o in opts}
    cats = client.get("/api/v1/requirements/categories").json()["data"]
    assert "待停用分类" in {c["name"] for c in cats}

    client.delete(f"/api/v1/requirements/categories/{cat_id}")
