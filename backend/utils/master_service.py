"""Master Service HTTP 客户端 — PMWB 后端调用人员中台。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


class MasterServiceClient:
    """封装对 pmwb-master-service 的 HTTP 调用。

    所有方法返回 (ok: bool, data: Any, error_msg: str)。
    """

    def __init__(self, base_url: str = ""):
        self.base_url = base_url or settings.MASTER_SERVICE_URL.rstrip("/")
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=10.0)
        return self._client

    def _request(self, method: str, path: str, timeout: Optional[float] = None, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        try:
            resp = self.client.request(method, url, timeout=timeout, **kwargs)
            resp.raise_for_status()
            body = resp.json()
            if body.get("code") == 0:
                return {"ok": True, "data": body.get("data"), "error": None}
            return {"ok": False, "data": None, "error": body.get("message", "Unknown error")}
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            logger.warning("Master service HTTP error: %s %s -> %s", method, path, detail)
            return {"ok": False, "data": None, "error": detail}
        except httpx.RequestError as e:
            logger.warning("Master service unreachable: %s %s -> %s", method, path, e)
            return {"ok": False, "data": None, "error": f"人员中台服务不可用: {e}"}

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------
    def health(self) -> dict:
        return self._request("GET", "/api/v1/health")

    # ------------------------------------------------------------------
    # 组织
    # ------------------------------------------------------------------
    def list_orgs(self, timeout: Optional[float] = None) -> List[dict]:
        r = self._request("GET", "/api/v1/basic-data/orgs", timeout=timeout)
        return r["data"] if r["ok"] else []

    def get_org(self, org_id: int) -> Optional[dict]:
        orgs = self.list_orgs()
        for o in orgs:
            if o.get("id") == org_id:
                return o
        return None

    def create_org(self, data: dict) -> Optional[dict]:
        r = self._request("POST", "/api/v1/basic-data/orgs", json=data)
        return r["data"] if r["ok"] else None

    def update_org(self, org_id: int, data: dict) -> Optional[dict]:
        r = self._request("PUT", f"/api/v1/basic-data/orgs/{org_id}", json=data)
        return r["data"] if r["ok"] else None

    def delete_org(self, org_id: int) -> bool:
        r = self._request("DELETE", f"/api/v1/basic-data/orgs/{org_id}")
        return r["ok"]

    # ------------------------------------------------------------------
    # 人员
    # ------------------------------------------------------------------
    def list_staffs(self, org_id: Optional[int] = None, keyword: Optional[str] = None, timeout: Optional[float] = None) -> List[dict]:
        params = {}
        if org_id:
            params["org_id"] = org_id
        if keyword:
            params["keyword"] = keyword
        r = self._request("GET", "/api/v1/basic-data/staffs", timeout=timeout, params=params or None)
        return r["data"] if r["ok"] else []

    def get_staff(self, staff_id: int) -> Optional[dict]:
        staffs = self.list_staffs()
        for s in staffs:
            if s.get("id") == staff_id:
                return s
        return None

    def create_staff(self, data: dict) -> Optional[dict]:
        r = self._request("POST", "/api/v1/basic-data/staffs", json=data)
        return r["data"] if r["ok"] else None

    def update_staff(self, staff_id: int, data: dict) -> Optional[dict]:
        r = self._request("PUT", f"/api/v1/basic-data/staffs/{staff_id}", json=data)
        return r["data"] if r["ok"] else None

    def delete_staff(self, staff_id: int) -> bool:
        r = self._request("DELETE", f"/api/v1/basic-data/staffs/{staff_id}")
        return r["ok"]

    # ------------------------------------------------------------------
    # 角色/身份定义
    # ------------------------------------------------------------------
    def list_roles(self) -> List[dict]:
        r = self._request("GET", "/api/v1/basic-data/roles")
        return r["data"] if r["ok"] else []

    def create_role(self, data: dict) -> Optional[dict]:
        r = self._request("POST", "/api/v1/basic-data/roles", json=data)
        return r["data"] if r["ok"] else None

    def update_role(self, role_id: int, data: dict) -> Optional[dict]:
        r = self._request("PUT", f"/api/v1/basic-data/roles/{role_id}", json=data)
        return r["data"] if r["ok"] else None

    def delete_role(self, role_id: int) -> bool:
        r = self._request("DELETE", f"/api/v1/basic-data/roles/{role_id}")
        return r["ok"]

    # ------------------------------------------------------------------
    # 轻量选项（选人组件下拉用）
    # ------------------------------------------------------------------
    def org_options(self) -> List[dict]:
        """返回启用的组织名称列表（轻量，不加载人员明细）。"""
        r = self._request("GET", "/api/v1/basic-data/org-options")
        return r["data"] if r["ok"] else []

    def role_options(self) -> List[dict]:
        """返回启用的身份名称列表（轻量，不加载人员明细）。"""
        r = self._request("GET", "/api/v1/basic-data/role-options")
        return r["data"] if r["ok"] else []

    # ------------------------------------------------------------------
    # 选人组件
    # ------------------------------------------------------------------
    def staff_options(self) -> List[dict]:
        r = self._request("GET", "/api/v1/basic-data/staff-options")
        return r["data"] if r["ok"] else []

    # ------------------------------------------------------------------
    # 批量导入
    # ------------------------------------------------------------------
    def import_orgs_staffs(self, rows: List[dict]) -> dict:
        """通过 Excel-like 行数据导入，暂不支持直接传 rows。
        走文件上传路径或由 PMWB 本地 BasicDataService 处理。
        这里提供占位，实际走 POST /api/v1/basic-data/import 文件上传。
        """
        return {"ok": False, "error": "请使用文件上传接口"}

    def upload_import_file(self, file_content: bytes, filename: str) -> dict:
        """上传 Excel 文件到 master 服务导入。"""
        try:
            files = {"file": (filename, file_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            resp = self.client.post(
                f"{self.base_url}/api/v1/basic-data/import",
                files=files,
                timeout=30.0,
            )
            resp.raise_for_status()
            body = resp.json()
            if body.get("code") == 0:
                return {"ok": True, "data": body.get("data"), "error": None}
            return {"ok": False, "data": None, "error": body.get("message", "Unknown error")}
        except Exception as e:
            logger.warning("Master service import failed: %s", e)
            return {"ok": False, "data": None, "error": str(e)}

    def download_template(self) -> Optional[bytes]:
        try:
            resp = self.client.get(f"{self.base_url}/api/v1/basic-data/template")
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.warning("Master service template download failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # 人员解析
    # ------------------------------------------------------------------
    def resolve_staff_id(self, name: str) -> Optional[int]:
        """按姓名解析 staff_id。同名多人时返回第一个 enabled。"""
        staffs = self.list_staffs(keyword=name)
        for s in staffs:
            if s.get("name") == name and s.get("enabled", True):
                return s["id"]
        return None

    def staff_email_index(self) -> Dict[str, str]:
        """返回 {姓名: 邮箱} 索引（仅启用且有邮箱的人员）。

        用于邮件收件人按姓名解析邮箱，避免逐个姓名发起 HTTP 请求。
        """
        try:
            staffs = self.list_staffs() or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("人员中台拉取人员失败: %s", exc)
            return {}
        idx: Dict[str, str] = {}
        for s in staffs:
            if s.get("enabled", True) and s.get("email"):
                idx[s.get("name")] = s["email"]
        return idx

    def resolve_staff_emails(self, names: List[str]) -> Dict[str, Optional[str]]:
        """按姓名列表解析人员中台邮箱，返回 {姓名: 邮箱|None}。

        同名多人时取第一个启用的匹配。姓名大小写精确匹配。
        """
        idx = self.staff_email_index()
        result: Dict[str, Optional[str]] = {}
        for name in names or []:
            if not name or not str(name).strip():
                continue
            target = str(name).strip()
            result[target] = idx.get(target)
        return result

    def list_sa_staffs(self) -> List[dict]:
        """返回所有 role_hint 为 SA 且启用的人员（团队 SA 数据源）。"""
        try:
            staffs = self.list_staffs() or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("人员中台拉取 SA 人员失败: %s", exc)
            return []
        return [
            s for s in staffs
            if (s.get("role_hint") or "").strip() == "SA"
            and s.get("enabled", True)
            and s.get("email")
        ]


master_service_client = MasterServiceClient()
