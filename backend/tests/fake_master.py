# -*- coding: utf-8 -*-
"""人员中台（8001 master-service）内存假实现，供测试替换 HTTP 客户端。

背景（防复发）：
    backend 的 /api/v1/basic-data/* 已改造为**代理层**，实际数据由
    services/master（8001）持有。conftest 里的 `dependency_overrides[get_db]`
    只能拦住走本地 SQLAlchemy 的接口，**拦不住代理层的 HTTP 调用**，
    因此测试一旦调用 basic-data 接口，就会真实写入 MySQL `pmwb_master`，
    在「人员中台 → 组织管理」页面留下 CRM_xxxxxxxx 之类的脏组织。

方案：
    本模块提供一份纯内存的中台实现，按 REST 语义响应 method+path，
    在 conftest 中用 autouse fixture 替换 `master_service_client._request`，
    使测试完全离线、可重复、零污染。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class FakeMasterBackend:
    """内存版人员中台：组织 / 人员 / 身份 三张表 + 选项接口。"""

    def __init__(self) -> None:
        self.orgs: Dict[int, dict] = {}
        self.staffs: Dict[int, dict] = {}
        self.roles: Dict[int, dict] = {}
        self._seq = {"org": 0, "staff": 0, "role": 0}

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _next(self, kind: str) -> int:
        self._seq[kind] += 1
        return self._seq[kind]

    def _org_out(self, org: dict) -> dict:
        out = dict(org)
        out["staff_count"] = sum(1 for s in self.staffs.values() if s["org_id"] == org["id"])
        return out

    def _staff_out(self, staff: dict) -> dict:
        out = dict(staff)
        org = self.orgs.get(staff["org_id"])
        out["org_name"] = org["name"] if org else None
        return out

    @staticmethod
    def _ok(data: Any) -> dict:
        return {"ok": True, "data": data, "error": None}

    @staticmethod
    def _fail(msg: str) -> dict:
        return {"ok": False, "data": None, "error": msg}

    # ------------------------------------------------------------------
    # 请求分发（对齐 services/master/app/routers/basic_data.py 语义）
    # ------------------------------------------------------------------
    def request(self, method: str, path: str, **kwargs) -> dict:
        method = method.upper()
        json_body: dict = kwargs.get("json") or {}
        params: dict = kwargs.get("params") or {}

        if path == "/api/v1/health":
            return self._ok({"status": "ok"})

        # ---------------- 组织 ----------------
        if path == "/api/v1/basic-data/orgs":
            if method == "GET":
                orgs = sorted(self.orgs.values(), key=lambda o: (o.get("sort") or 0, o["id"]))
                return self._ok([self._org_out(o) for o in orgs])
            if method == "POST":
                name = (json_body.get("name") or "").strip()
                if not name:
                    return self._fail("组织名称不能为空")
                if any(o["name"] == name for o in self.orgs.values()):
                    return self._fail(f"组织名称重复：{name}")
                org = {
                    "id": self._next("org"),
                    "name": name,
                    "description": json_body.get("description"),
                    "sort": json_body.get("sort") or 0,
                    "enabled": json_body.get("enabled", True),
                    "source_trace": json_body.get("source_trace") or "manual",
                    "created_at": None,
                }
                self.orgs[org["id"]] = org
                return self._ok(self._org_out(org))

        m = re.fullmatch(r"/api/v1/basic-data/orgs/(\d+)", path)
        if m:
            org_id = int(m.group(1))
            org = self.orgs.get(org_id)
            if method == "PUT":
                if not org:
                    return self._fail(f"组织不存在：id={org_id}")
                for k, v in json_body.items():
                    if k in ("name", "description", "sort", "enabled"):
                        org[k] = v
                return self._ok(self._org_out(org))
            if method == "DELETE":
                if not org:
                    return self._fail(f"组织不存在：id={org_id}")
                # 级联删除组织下人员
                for sid in [s["id"] for s in self.staffs.values() if s["org_id"] == org_id]:
                    self.staffs.pop(sid, None)
                self.orgs.pop(org_id, None)
                return self._ok({"deleted": True})

        # ---------------- 人员 ----------------
        if path == "/api/v1/basic-data/staffs":
            if method == "GET":
                rows = list(self.staffs.values())
                org_id = params.get("org_id")
                if org_id:
                    rows = [s for s in rows if s["org_id"] == int(org_id)]
                keyword = params.get("keyword")
                if keyword:
                    kw = str(keyword)
                    rows = [
                        s for s in rows
                        if kw in (s.get("name") or "")
                        or kw in (s.get("email") or "")
                        or kw in (s.get("role_hint") or "")
                    ]
                rows.sort(key=lambda s: (s["org_id"], s.get("sort") or 0, s["id"]))
                return self._ok([self._staff_out(s) for s in rows])
            if method == "POST":
                name = (json_body.get("name") or "").strip()
                org_id = json_body.get("org_id")
                if not name or not org_id:
                    return self._fail("姓名与所属组织必填")
                if any(
                    s["name"] == name and s["org_id"] == org_id for s in self.staffs.values()
                ):
                    return self._fail(f"人员已存在：{name}")
                staff = {
                    "id": self._next("staff"),
                    "name": name,
                    "org_id": org_id,
                    "email": json_body.get("email"),
                    "phone": json_body.get("phone"),
                    "role_hint": json_body.get("role_hint"),
                    "sort": json_body.get("sort") or 0,
                    "enabled": json_body.get("enabled", True),
                    "source_trace": json_body.get("source_trace") or "manual",
                    "created_at": None,
                    "updated_at": None,
                }
                self.staffs[staff["id"]] = staff
                return self._ok(self._staff_out(staff))

        m = re.fullmatch(r"/api/v1/basic-data/staffs/(\d+)", path)
        if m:
            staff_id = int(m.group(1))
            staff = self.staffs.get(staff_id)
            if method == "PUT":
                if not staff:
                    return self._fail(f"人员不存在：id={staff_id}")
                for k, v in json_body.items():
                    if k in ("name", "org_id", "email", "phone", "role_hint", "sort", "enabled"):
                        staff[k] = v
                return self._ok(self._staff_out(staff))
            if method == "DELETE":
                if not staff:
                    return self._fail(f"人员不存在：id={staff_id}")
                self.staffs.pop(staff_id, None)
                return self._ok({"deleted": True})

        # ---------------- 身份 ----------------
        if path == "/api/v1/basic-data/roles":
            if method == "GET":
                roles = sorted(self.roles.values(), key=lambda r: (r.get("sort") or 0, r["id"]))
                return self._ok(list(roles))
            if method == "POST":
                name = (json_body.get("name") or "").strip()
                if not name:
                    return self._fail("身份名称不能为空")
                role = {
                    "id": self._next("role"),
                    "name": name,
                    "sort": json_body.get("sort") or 0,
                    "enabled": json_body.get("enabled", True),
                    "created_at": None,
                }
                self.roles[role["id"]] = role
                return self._ok(dict(role))

        m = re.fullmatch(r"/api/v1/basic-data/roles/(\d+)", path)
        if m:
            role_id = int(m.group(1))
            role = self.roles.get(role_id)
            if method == "PUT":
                if not role:
                    return self._fail(f"身份不存在：id={role_id}")
                for k, v in json_body.items():
                    if k in ("name", "sort", "enabled"):
                        role[k] = v
                return self._ok(dict(role))
            if method == "DELETE":
                if not role:
                    return self._fail(f"身份不存在：id={role_id}")
                self.roles.pop(role_id, None)
                return self._ok({"deleted": True})

        # ---------------- 选项 ----------------
        if path == "/api/v1/basic-data/org-options":
            orgs = sorted(
                [o for o in self.orgs.values() if o.get("enabled", True)],
                key=lambda o: (o.get("sort") or 0, o["id"]),
            )
            return self._ok([{"id": o["id"], "name": o["name"]} for o in orgs])

        if path == "/api/v1/basic-data/role-options":
            roles = sorted(
                [r for r in self.roles.values() if r.get("enabled", True)],
                key=lambda r: (r.get("sort") or 0, r["id"]),
            )
            return self._ok([{"id": r["id"], "name": r["name"]} for r in roles])

        if path == "/api/v1/basic-data/staff-options":
            groups: List[dict] = []
            orgs = sorted(
                [o for o in self.orgs.values() if o.get("enabled", True)],
                key=lambda o: (o.get("sort") or 0, o["id"]),
            )
            for org in orgs:
                members = sorted(
                    [
                        s for s in self.staffs.values()
                        if s["org_id"] == org["id"] and s.get("enabled", True)
                    ],
                    key=lambda s: (s.get("sort") or 0, s["id"]),
                )
                options = [
                    {
                        "value": s["name"],
                        "label": s["name"],
                        "email": s.get("email"),
                        "role_hint": s.get("role_hint"),
                    }
                    for s in members
                ]
                if options:
                    groups.append(
                        {"org_id": org["id"], "org_name": org["name"], "options": options}
                    )
            return self._ok(groups)

        return self._fail(f"FakeMaster 未实现的接口：{method} {path}")


def install_fake_master(monkeypatch, client_obj) -> FakeMasterBackend:
    """把 MasterServiceClient 的所有出网调用替换为内存实现。"""
    backend = FakeMasterBackend()

    def _fake_request(method: str, path: str, **kwargs) -> dict:
        return backend.request(method, path, **kwargs)

    monkeypatch.setattr(client_obj, "_request", _fake_request, raising=True)
    # 文件类接口不走 _request，单独兜底，避免真实出网
    monkeypatch.setattr(
        client_obj,
        "upload_import_file",
        lambda content, filename: {"ok": False, "data": None, "error": "测试环境不支持导入"},
        raising=True,
    )
    monkeypatch.setattr(client_obj, "download_template", lambda: b"", raising=True)
    return backend
