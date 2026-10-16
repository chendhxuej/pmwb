"""组织「系统别名映射」边界规则测试。

背景：把「内部组织 → 外部工单系统名称」的映射落到 pmwb_org 本身，替代 PMWB 侧的
独立字典 pmwb_vendor_team。本文件覆盖方案第 3 节的 14 条边界规则中可在中台侧验证的部分。

⚠ 与 app/tests/test_basic_data.py 一致：本测试**直连开发库 pmwb_master**（无独立测试库）。
   所有用例自建自清，临时组织统一 `_T` 前缀，teardown 里 force 删除，不会污染真实数据。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from fastapi.testclient import TestClient

from db.base import engine
from db.models import Base
from main import app

client = TestClient(app)


def setup_module():
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _cleanup():
    """每个用例结束后清掉 `_T` 前缀的临时组织与其成员（先删成员再 force 删组织）。"""
    created = []
    yield created
    for sid, kind in list(created):
        if kind == "staff":
            client.delete(f"/api/v1/basic-data/staffs/{sid}")
    for oid, kind in list(created):
        if kind == "org":
            client.delete(f"/api/v1/basic-data/orgs/{oid}?force=true")


def _mk_org(name, **kw):
    return client.post("/api/v1/basic-data/orgs", json={"name": name, **kw})


# ---------------------------------------------------------------------------
# 多对一 / 反向查询 / 去重
# ---------------------------------------------------------------------------
def test_multi_org_to_one_target_allowed():
    """两个组织映射到同一个目标系统名 —— 这是多对一，必须允许。"""
    for n in ("_T多对一甲", "_T多对一乙"):
        resp = _mk_org(n, org_type="system", target_system_name="CRM")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["target_system_name"] == "CRM"
        # 清理由 fixture 处理（这里无法拿到 id，用名字反查）
        _force_clean_by_name(n)


def test_target_system_options_contains_real_systems():
    """候选集应覆盖 2026-10-16 摸底时的 9 个 system 类组织目标名。"""
    resp = client.get("/api/v1/basic-data/target-system-options")
    assert resp.status_code == 200
    opts = resp.json()["data"]
    for sys_name in ("CRM", "订单中心", "电子协议", "政企工作台", "BOSS", "网格通", "能运"):
        assert sys_name in opts, f"{sys_name} 不在候选集：{opts}"


def test_org_mapping_index_shape_and_order():
    """映射索引：只含 system 且启用，按 (sort, id) 升序（第一条命中即主组织）。"""
    resp = client.get("/api/v1/basic-data/org-mapping-index")
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert rows, "索引为空"
    for r in rows:
        assert r["org_type"] == "system"
        assert set(["org_id", "org_name", "target_system_name", "aliases", "sort"]) <= set(r)
    keys = [(r["sort"], r["org_id"]) for r in rows]
    assert keys == sorted(keys), "映射索引未按 (sort, id) 升序，主组织判定会漂移"


def test_org_type_options_is_single_source():
    resp = client.get("/api/v1/basic-data/org-type-options")
    assert resp.status_code == 200
    assert set(resp.json()["data"]) == {"system", "department", "branch"}


# ---------------------------------------------------------------------------
# 空值 / 清洗
# ---------------------------------------------------------------------------
def test_aliases_cleaning():
    """连续逗号 → 丢空项；重复 → 去重；首尾空格 → strip。"""
    resp = _mk_org("_T别名清洗", org_type="system", aliases="甲,,乙,甲, 丙 ")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["aliases"] == "甲,乙,丙"
    _force_clean_by_name("_T别名清洗")


def test_org_type_default_is_department():
    """不传 org_type → 默认 department（保守：不填绝不会误进厂家清单）。"""
    resp = _mk_org("_T默认类型")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["org_type"] == "department"
    _force_clean_by_name("_T默认类型")


def test_target_empty_means_map_to_self():
    """target 为空 = 映射到自身，索引里回落为 org_name。"""
    resp = _mk_org("_T空target回落", org_type="system")
    assert resp.status_code == 200, resp.text
    org = resp.json()["data"]
    assert org["target_system_name"] in (None, "")
    _force_clean_by_name("_T空target回落")


# ---------------------------------------------------------------------------
# 冲突 / 非法值
# ---------------------------------------------------------------------------
def test_alias_conflict_with_other_org_name_rejected():
    resp = _mk_org("_T别名撞名", org_type="system", aliases="CRM")
    assert resp.status_code != 200 or resp.json()["code"] != 0, "别名与其它组织同名应被拒绝"
    assert "同名" in str(resp.json()) or "占用" in str(resp.json())


def test_alias_conflict_with_other_alias_rejected():
    resp = _mk_org("_T别名重复", org_type="system", aliases="电子协议系统")
    assert resp.status_code != 200 or resp.json()["code"] != 0, "别名已被占用应被拒绝"


def test_alias_equal_self_name_is_dropped():
    """别名 == 自身名：剔除，不报错（避免与第 2 级优先级歧义）。"""
    resp = _mk_org("_T别名自剔除", org_type="system", aliases="_T别名自剔除,乙名")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["aliases"] == "乙名"
    _force_clean_by_name("_T别名自剔除")


def test_invalid_org_type_rejected():
    resp = _mk_org("_T非法类型", org_type="bogus")
    assert resp.status_code != 200 or resp.json()["code"] != 0, "非法 org_type 应被拒绝"


def test_target_not_in_candidates_rejected():
    """目标系统名必须落在候选集内 —— 禁自由文本，杜绝再造第三种脏写法。"""
    resp = _mk_org("_T非法目标", org_type="system", target_system_name="压根不存在的系统")
    assert resp.status_code != 200 or resp.json()["code"] != 0, "候选集外的目标应被拒绝"


def test_duplicate_org_name_on_update_rejected_not_500():
    """update_org 撞名必须返回业务错误，不能 500（历史上 update 未捕获 IntegrityError）。"""
    crm_id = _org_id_by_name("CRM")
    if not crm_id:
        pytest.skip("库中没有 CRM 组织，跳过")
    resp = client.put(f"/api/v1/basic-data/orgs/{crm_id}", json={"name": "订单中心"})
    # 中台约定：业务错误返回 HTTP 400 + body.code != 0（关键是不能抛成 500）
    assert resp.status_code != 500, "update 撞名不能是 500"
    assert resp.status_code == 400, f"期望业务错误 400，实际 {resp.status_code}"
    assert resp.json()["code"] != 0
    assert "重复" in resp.json()["message"]

    # 断言 CRM 未被改名破坏
    orgs = {o["id"]: o for o in client.get("/api/v1/basic-data/orgs").json()["data"]}
    assert orgs[crm_id]["name"] == "CRM", "撞名失败后不应残留半改状态"


# ---------------------------------------------------------------------------
# 删除保护（规则 9）
# ---------------------------------------------------------------------------
def test_delete_org_with_staff_rejected():
    resp = _mk_org("_T有成员", org_type="system")
    assert resp.status_code == 200, resp.text
    org_id = resp.json()["data"]["id"]
    client.post("/api/v1/basic-data/staffs", json={"name": "_临时成员", "org_id": org_id})

    resp = client.delete(f"/api/v1/basic-data/orgs/{org_id}")
    assert resp.status_code != 200 or resp.json()["code"] != 0, "有成员的组织必须拒绝删除"
    assert "成员" in str(resp.json())

    # 确认还在
    still = _org_id_by_name("_T有成员")
    assert still == org_id, "拒绝删除后组织不应消失"
    client.delete(f"/api/v1/basic-data/orgs/{org_id}?force=true")


# ---------------------------------------------------------------------------
# 目标系统更名级联（规则 8）
# ---------------------------------------------------------------------------
def test_target_rename_cascade():
    """改名时，引用旧名的 target_system_name 被级联刷 + 旧名降级为别名。"""
    a = _mk_org("_T被引用", org_type="system")
    assert a.status_code == 200, a.text
    id_a = a.json()["data"]["id"]

    b = _mk_org("_T引用方", org_type="system", target_system_name="_T被引用")
    assert b.status_code == 200, b.text
    id_b = b.json()["data"]["id"]

    resp = client.put(f"/api/v1/basic-data/orgs/{id_a}", json={"name": "_T被引用改名"})
    assert resp.status_code == 200, resp.text
    assert "同步刷新 1 条映射引用" in resp.json()["message"]

    orgs = {o["id"]: o for o in client.get("/api/v1/basic-data/orgs").json()["data"]}
    assert orgs[id_b]["target_system_name"] == "_T被引用改名"
    assert "_T被引用" in (orgs[id_b]["aliases"] or ""), "旧名应降级为别名，保证历史工单仍能归一"

    for oid in (id_b, id_a):
        client.delete(f"/api/v1/basic-data/orgs/{oid}?force=true")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _org_id_by_name(name):
    orgs = client.get("/api/v1/basic-data/orgs").json()["data"]
    for o in orgs:
        if o["name"] == name:
            return o["id"]
    return None


def _force_clean_by_name(name):
    oid = _org_id_by_name(name)
    if oid:
        client.delete(f"/api/v1/basic-data/orgs/{oid}?force=true")
