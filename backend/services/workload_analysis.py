"""工作量分析：按「启动开发」环节进入月份统计每位 SA 的人天投入。

口径铁律（2026-10-16 老大拍板，改动前先读）：
1. 工作量取值：**优先 review_workload（复核工作量），NULL 回退 workload（初评工作量）**，
   两条都空才算缺失。与 services/requirement.py:312 的 `eval_workload` **同源**，
   禁止另写一份口径（否则列表页与分析页数字打架）。
2. 归月：以 `pmwb_requirement_stage_log.stage='dev'.entered_at` 归月。
   **无 dev 记录的一律排除**，单列进 `unmonth`（reason=no_dev_stage / dev_time_missing）。
3. 跨月：一个需求的全部工作量 **100% 归入其 dev 进入月，不按月摊销**。
   uk_req_stage 保证一需求仅一条 dev 记录，模型上不存在"跨月"。
4. SA 归集：`utils/owners.py::split_owners`（唯一拆分实现）拆分后 **人人计全额**，
   与 services/operation.py::get_stats_by_handler「一条挂多人则人人计数」口径一致。
   代价：`sum(by_sa.workload)` 可能大于 `summary.workload_total`，响应里带 footnote 明示。
5. workload=0 **不剔除**（与 vendor_dev 的"活跃厂家"口径刻意区分）：
   统计场景里 0 是合法评估值（"已评估，确认无需投入"），剔除会让需求凭空消失。
   需要按 vendor_dev 口径对比时用 `include_zero=false`。
6. 默认区间：**未传 month_from/month_to 时锚定 `data_range`**（全库有 dev 记录的起止月，
   不受 sa/system/keyword 筛选影响）；全库无 dev 记录才回退"近 12 个月"。
   目的：避免默认"近 12 个月"而数据只有近 3 个月导致趋势图大面积空月。

实现约束：
- **月份分桶一律在 Python 侧做**（`entered_at.strftime('%Y-%m')`）。
  ⚠ 禁止 `func.date_format`（MySQL 专有）/ `func.strftime`（SQLite 专有）：
  测试库是内存 SQLite（tests/conftest.py:34），用前者会让 pytest 全红。
"""
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.exceptions import ValidationException
from db.models import (
    PmwbRequirementEvaluation,
    PmwbRequirementStageLog,
    SentEmail,
    now_cn,
)
from utils.owners import split_owners

UNASSIGNED_LABEL = "未指派"
DEV_STAGE = "dev"

FOOTNOTE = (
    "按负责人统计时，一条评估挂多人则人人计全额，故负责人人天合计可能大于总工作量"
)


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _num(v) -> Optional[float]:
    """Numeric(10,2) → float。None / 非法值 → None（SQLite 下可能返回 str）。"""
    if v is None:
        return None
    try:
        return float(Decimal(str(v)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _validate_month(value: Optional[str], name: str) -> Optional[str]:
    if value is None or value == "":
        return None
    s = str(value).strip()
    parts = s.split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
        raise ValidationException(f"{name} 格式应为 YYYY-MM，当前：{value}")
    try:
        y, m = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValidationException(f"{name} 格式应为 YYYY-MM，当前：{value}")
    if not (1 <= m <= 12) or y < 1970:
        raise ValidationException(f"{name} 不是合法月份：{value}")
    return f"{y:04d}-{m:02d}"


def month_sequence(m_from: str, m_to: str) -> List[str]:
    """连续月份序列（含首尾），供趋势图补零、x 轴不断档。"""
    if not m_from or not m_to:
        return []
    y1, m1 = int(m_from[:4]), int(m_from[5:7])
    y2, m2 = int(m_to[:4]), int(m_to[5:7])
    out = []
    y, m = y1, m1
    while (y, m) <= (y2, m2):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _data_range_from(months: List[Optional[str]]) -> Dict[str, Any]:
    """由已有 dev 月份集合派生「数据区间」（前端首屏锚定用）。

    ⚠ 月份字符串一律 Python 侧 strftime 产出，禁 func.date_format（测试库是 SQLite）。
    """
    ms = sorted({m for m in months if m})
    if not ms:
        return {"month_from": None, "month_to": None, "month_count": 0, "has_data": False}
    return {
        "month_from": ms[0],
        "month_to": ms[-1],
        "month_count": len(month_sequence(ms[0], ms[-1])),  # 跨度月数（含中间空月）
        "has_data": True,
    }


def _default_range(months: List[Optional[str]] = None) -> tuple:
    """默认区间：优先锚定 data_range（有 dev 记录的起止月）；无数据回退近 12 个月。"""
    dr = _data_range_from(months or [])
    if dr["has_data"]:
        return dr["month_from"], dr["month_to"]
    today = now_cn().date()
    y, m = today.year, today.month - 11
    while m <= 0:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}", f"{today.year:04d}-{today.month:02d}"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class WorkloadAnalysisService:
    """工作量分析。统计的**单一数据源**：前端禁止自己算。"""

    # ---------------- 数据采集 ----------------
    @staticmethod
    def _req_universe(db: Session) -> Dict[str, str]:
        """需求宇宙：sent_emails 去重 req_id → 需求名称（首条非空）。

        唯一口径，与 services/requirement.py:24-38 同源。
        """
        name_map: Dict[str, str] = {}
        for rid, nm in db.query(SentEmail.req_id, SentEmail.req_name).all():
            if not rid:
                continue
            if rid not in name_map or (not name_map[rid] and nm):
                name_map[rid] = nm or ""
        return name_map

    @staticmethod
    def _dev_months(db: Session) -> Dict[str, Dict[str, Any]]:
        """「启动开发」环节时间：req_id → {month, entered_at, source}。"""
        rows = (
            db.query(
                PmwbRequirementStageLog.req_id,
                PmwbRequirementStageLog.entered_at,
                PmwbRequirementStageLog.source,
            )
            .filter(PmwbRequirementStageLog.stage == DEV_STAGE)
            .all()
        )
        out: Dict[str, Dict[str, Any]] = {}
        for rid, at, src in rows:
            if not rid:
                continue
            out[rid] = {
                "month": at.strftime("%Y-%m") if at else None,  # ★ Python 侧分桶
                "entered_at": at,
                "source": src or "auto",
            }
        return out

    @staticmethod
    def _eval_buckets(db: Session) -> Dict[str, Dict[str, Any]]:
        """按需求聚合团队评估：工作量求和 + SA/系统集合。"""
        buckets: Dict[str, Dict[str, Any]] = {}
        for ev in db.query(PmwbRequirementEvaluation).all():
            rid = ev.req_id
            if not rid:
                continue
            rw = _num(ev.review_workload)
            wl = _num(ev.workload)
            eff = rw if rw is not None else wl
            state = "missing" if eff is None else ("zero" if eff == 0 else "filled")
            if eff is None:
                eff = 0.0

            b = buckets.setdefault(
                rid,
                {"workload": 0.0, "sa": set(), "systems": set(), "count": 0,
                 "states": set(), "name": ""},
            )
            b["workload"] += eff
            b["count"] += 1
            b["states"].add(state)
            for n in split_owners(ev.sa_name):
                b["sa"].add(n)
            if ev.system_name and ev.system_name.strip():
                b["systems"].add(ev.system_name.strip())
            if ev.req_name and not b["name"]:
                b["name"] = ev.req_name
        return buckets

    # ---------------- 主入口 ----------------
    def get_workload_stats(
        self,
        db: Session,
        month_from: Optional[str] = None,
        month_to: Optional[str] = None,
        sa: Optional[str] = None,
        system_name: Optional[str] = None,
        req_keyword: Optional[str] = None,
        include_zero: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        # 1) 月份区间校验（兜底推迟到 dev_map 就绪后，见 2.6）
        mf = _validate_month(month_from, "month_from")
        mt = _validate_month(month_to, "month_to")
        if mf and mt and mf > mt:
            raise ValidationException(f"month_from 不能晚于 month_to（{mf} > {mt}）")

        # 2) 数据源
        name_map = self._req_universe(db)
        dev_map = self._dev_months(db)
        eval_map = self._eval_buckets(db)

        # 2.5) 数据区间：有 dev 记录的起止月（**全局**，不受 sa/system/keyword 筛选影响）
        dev_months = [v.get("month") for v in dev_map.values()]
        data_range = _data_range_from(dev_months)

        # 2.6) 区间兜底：未传 → 锚定 data_range；只传一端 → 补成单月区间
        if not mf and not mt:
            mf, mt = _default_range(dev_months)
        elif not mf:
            mf = mt
        elif not mt:
            mt = mf

        kw = (req_keyword or "").strip().lower()
        sa_kw = (sa or "").strip()
        sys_kw = (system_name or "").strip()

        # 3) 逐需求归集 → 月度明细 / 未归月
        detail: List[Dict[str, Any]] = []
        unmonth: List[Dict[str, Any]] = []
        for rid in sorted(name_map):
            b = eval_map.get(rid)
            total = b["workload"] if b else 0.0
            count = b["count"] if b else 0
            if count == 0:
                state = "missing"
            elif total > 0:
                state = "filled"
            elif b and "zero" in b["states"]:
                state = "zero"
            else:
                state = "missing"
            sa_names = sorted(b["sa"]) if b else []
            systems = sorted(b["systems"]) if b else []
            rname = (b["name"] if b else "") or name_map.get(rid) or ""

            # 过滤
            if kw and kw not in f"{rid} {rname}".lower():
                continue
            if sa_kw and not any(sa_kw in n for n in sa_names):
                continue
            if sys_kw and not any(sys_kw in s for s in systems):
                continue

            dev = dev_map.get(rid)
            month = dev.get("month") if dev else None
            if not month:
                unmonth.append(
                    {
                        "req_id": rid,
                        "req_name": rname,
                        "workload": round(total, 2),
                        "workload_state": state,
                        "sa_names": sa_names,
                        "systems": systems,
                        "reason": "dev_time_missing" if dev else "no_dev_stage",
                    }
                )
                continue
            if month < mf or month > mt:
                continue  # 区间外，直接排除（不算未归月）
            detail.append(
                {
                    "req_id": rid,
                    "req_name": rname,
                    "month": month,
                    "entered_at": dev.get("entered_at").strftime("%Y-%m-%d %H:%M") if dev.get("entered_at") else None,
                    "stage_source": dev.get("source") or "auto",
                    "workload": round(total, 2),
                    "workload_state": state,
                    "workload_missing": state == "missing",
                    "sa_names": sa_names,
                    "systems": systems,
                    "eval_count": count,
                }
            )

        detail.sort(key=lambda x: (x["month"], -(x["workload"] or 0), x["req_id"]))

        # 4) 分桶聚合
        months_seq = month_sequence(mf, mt)
        months: Dict[str, Dict[str, Any]] = {
            m: {"month": m, "req_count": 0, "workload": 0.0, "by_sa": {}} for m in months_seq
        }
        by_sa: Dict[str, Dict[str, Any]] = {}
        by_system: Dict[str, Dict[str, Any]] = {}

        for row in detail:
            eff = row["workload"] or 0.0
            # include_zero=False 时按 vendor_dev 口径只统计 >0（需求明细不受影响）
            counted = eff if (include_zero or eff > 0) else 0.0

            mb = months.setdefault(
                row["month"], {"month": row["month"], "req_count": 0, "workload": 0.0, "by_sa": {}}
            )
            mb["req_count"] += 1
            mb["workload"] += counted
            mb["by_sa"] = mb.get("by_sa") or {}

            names = row["sa_names"] or [UNASSIGNED_LABEL]
            is_unassigned = not row["sa_names"]
            for n in names:
                b = by_sa.get(n)
                if b is None:
                    b = {
                        "name": n,
                        "unassigned": is_unassigned,
                        "req_count": 0,
                        "workload": 0.0,
                        "months": {},
                    }
                    by_sa[n] = b
                b["req_count"] += 1
                b["workload"] += counted  # ★ 人人计全额，不除以人数
                b["months"][row["month"]] = round(b["months"].get(row["month"], 0.0) + counted, 2)
                mb["by_sa"][n] = round(mb["by_sa"].get(n, 0.0) + counted, 2)

            for s in row["systems"] or []:
                b = by_system.get(s)
                if b is None:
                    b = {"name": s, "req_count": 0, "workload": 0.0, "months": {}}
                    by_system[s] = b
                b["req_count"] += 1
                b["workload"] += counted
                b["months"][row["month"]] = round(b["months"].get(row["month"], 0.0) + counted, 2)

        # 5) 排序：工作量降序、「未指派」沉底（operation.get_stats_by_handler 同款排序键）
        sa_list = sorted(by_sa.values(), key=lambda x: (bool(x["unassigned"]), -x["workload"], x["name"]))
        sys_list = sorted(by_system.values(), key=lambda x: (-x["workload"], x["name"]))
        for x in sa_list:
            x["workload"] = round(x["workload"], 2)
        for x in sys_list:
            x["workload"] = round(x["workload"], 2)

        month_list = []
        for m in months_seq:
            mb = months.get(m) or {"month": m, "req_count": 0, "workload": 0.0, "by_sa": {}}
            mb["workload"] = round(mb["workload"], 2)
            mb["by_sa"] = [
                {"name": k, "workload": round(v, 2)}
                for k, v in sorted(mb["by_sa"].items(), key=lambda kv: -kv[1])
            ]
            month_list.append(mb)

        # 6) 汇总
        workload_total = round(sum(r["workload"] for r in detail if include_zero or r["workload"] > 0), 2)
        active_months = [m for m in month_list if m["req_count"] > 0]
        peak = max(month_list, key=lambda x: x["workload"]) if month_list else None
        sa_count = sum(1 for x in sa_list if not x["unassigned"])
        unassigned_total = round(sum(x["workload"] for x in sa_list if x["unassigned"]), 2)

        warnings: List[str] = []
        if unmonth:
            warnings.append(f"{len(unmonth)} 个需求无「启动开发」环节时间，未纳入月度统计")
        missing_cnt = sum(1 for r in detail if r["workload_state"] == "missing")
        if missing_cnt:
            warnings.append(f"{missing_cnt} 个需求的工作量未填写（初评与复核均为空），按 0 计入")

        total_rows = len(detail)
        pages = (total_rows + page_size - 1) // page_size if page_size > 0 else 1
        start = (page - 1) * page_size
        page_items = detail[start:start + page_size]

        return {
            "generated_at": now_cn().isoformat(),
            "data_range": data_range,
            "range": {"month_from": mf, "month_to": mt, "months": months_seq},
            "summary": {
                "req_count": total_rows,
                "eval_count": sum(r["eval_count"] for r in detail),
                "workload_total": workload_total,
                "workload_avg": round(workload_total / len(active_months), 2) if active_months else 0.0,
                "peak_month": peak["month"] if peak else None,
                "peak_month_workload": peak["workload"] if peak else 0.0,
                "missing_workload_req_count": missing_cnt,
                "zero_workload_req_count": sum(1 for r in detail if r["workload_state"] == "zero"),
                "unmonth_req_count": len(unmonth),
                "sa_count": sa_count,
                "unassigned_total": unassigned_total,
            },
            "months": month_list,
            "by_sa": sa_list,
            "by_system": sys_list,
            "requirements": {
                "total": total_rows,
                "page": page,
                "page_size": page_size,
                "pages": pages,
                "items": page_items,
            },
            "unmonth": unmonth,
            "warnings": warnings,
            "footnote": FOOTNOTE,
        }


workload_analysis_service = WorkloadAnalysisService()
