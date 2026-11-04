"""客诉改进措施台账 —— 登记、跟踪、有效性验证。

职责边界（2026-10-27 老大确认的闭环方案）：
  - 措施内容与督办状态以「运营工单 pmwb_operation_issue」为准，本台账不重复维护；
  - 本台账只回答三个问题：针对哪个客诉场景、基线多少、降了多少；
  - 到验证周次自动结算 effectiveness，未达标自动标 ineffective（催升级）。

本模块为服务层实现（scripts/complaint/actions.py 是其 CLI 薄封装）；
建运营工单走进程内 operation_issue_service，不走 HTTP 自环。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.complaint import config as C
from services.complaint.ingest import week_key
from services.complaint.metrics import latest_week, week_bounds

# 一级性质 → 运营工单子类（保持与运营监控既有枚举一致）
_ISSUE_TYPE = {
    "系统缺陷与办理受阻": ("bug", "bug"),
    "数据与状态异常": ("data", "data_abnormal"),
    "流程与工单卡单": ("bug", "bug"),
    "营销与活动生效异常": ("bug", "bug"),
    "计费与出账争议": ("bug", "bug"),
    "外部依赖与协同": ("complaint", "spot_event"),
    "操作与咨询": ("complaint", "spot_event"),
}


def _next_action_no(db: Session, week: str) -> str:
    prefix = f"CACT-{week.replace('-', '')}-"
    row = db.execute(text(
        "SELECT action_no FROM pmwb_complaint_action WHERE action_no LIKE :p ORDER BY action_no DESC LIMIT 1"
    ), {"p": prefix + "%"}).scalar()
    seq = int(row.split("-")[-1]) + 1 if row else 1
    return f"{prefix}{seq:02d}"


# 工单大类 → 单号前缀（与前端生成规则一致：BUG-20261027-573 样式）
_ISSUE_NO_PREFIX = {"bug": "BUG", "data": "DATA", "prod": "PROD",
                    "task": "TASK", "complaint": "COMP"}


def _gen_issue_no(db: Session, category: str) -> str:
    """生成运营工单号：前缀-日期-随机序号，撞号重试（原 HTTP 路径缺此逻辑，属修复）。"""
    import random
    prefix = _ISSUE_NO_PREFIX.get(category, "OPS")
    today = datetime.now().strftime("%Y%m%d")
    for _ in range(10):
        no = f"{prefix}-{today}-{random.randint(100, 999)}"
        exists = db.execute(text(
            "SELECT 1 FROM pmwb_operation_issue WHERE issue_no = :no"
        ), {"no": no}).scalar()
        if not exists:
            return no
    raise RuntimeError("运营工单号生成连续撞号，请检查 issue_no 规则")


# 工单内容自动代入的条数与单字段截断（防止 situation_desc 变成长篇没人看）
_ISSUE_TICKET_LIMIT = 8
_ISSUE_TEXT_CLAMP = 200


def build_issue_context(db: Session, problem_nos: List[str], weeks_back: int = 1) -> str:
    """为「问题 → 建运营工单」自动组装上下文：问题说明 + 指定周期关联投诉工单明细。

    为什么必须有这段（老大 2026-11-04 反馈）：运营工单接收方拿到工单时看不到客诉侧
    上下文，不知道查什么、拿什么当证据。把问题命中规则 + 周期内投诉工单（工单号/
    投诉内容/核查过程/AI 根因）直接写进工单描述，接收方按单核查即可，不必回客诉模块翻。

    周期口径：weeks_back=1 只取当周；N 取「当周往前 N-1 周」（按 created_time 过滤，
    跨库安全：不用 MySQL 日期函数）。条数超限截断并注明总数，不静默丢。
    """
    if not problem_nos:
        return ""
    marks = ",".join(f":p{i}" for i in range(len(problem_nos)))
    probs = db.execute(text(
        f"SELECT problem_no, title, category_l2, rule_hits, week_cnt, total_cnt, "
        f"first_week, COALESCE(rootcause_nos, ''), COALESCE(rootcause_no, '') "
        f"FROM pmwb_complaint_problem WHERE problem_no IN ({marks})"
    ), {f"p{i}": v for i, v in enumerate(problem_nos)}).fetchall()
    if not probs:
        return ""

    lines: List[str] = []
    for (pno, ptitle, l2, rule_hits, week_cnt, total_cnt,
         first_week, rc_nos, rc_no) in probs:
        nos = {x.strip() for x in f"{rc_nos},{rc_no}".split(",") if x.strip()}
        lines.append(
            f"【问题描述】{ptitle}（问题 {pno}；场景：{l2 or '—'}；"
            f"首见 {first_week or '—'}；当周 {int(week_cnt or 0)} 单 / 累计 {int(total_cnt or 0)} 单）"
        )
        if rule_hits:
            lines.append(f"【命中规则】{rule_hits}")
        if not nos:
            continue
        rc_marks = ",".join(f":r{i}" for i in range(len(nos)))
        rc_params = {f"r{i}": v for i, v in enumerate(nos)}
        week = latest_week(db)
        since = None
        if week:
            start, _ = week_bounds(week)
            since = start - timedelta(days=max(0, weeks_back - 1) * 7)
        if since is not None:
            cond = "created_time >= :since"
            rc_params["since"] = since
        else:
            cond = "1 = 1"
        total = db.execute(text(
            f"SELECT COUNT(*) FROM pmwb_complaint_ticket "
            f"WHERE rootcause_no IN ({rc_marks}) AND {cond}"
        ), rc_params).scalar() or 0
        trows = db.execute(text(
            f"SELECT ticket_no, created_time, city, content, solution_history, root_cause "
            f"FROM pmwb_complaint_ticket "
            f"WHERE rootcause_no IN ({rc_marks}) AND {cond} "
            f"ORDER BY created_time DESC LIMIT :lim"
        ), {**rc_params, "lim": _ISSUE_TICKET_LIMIT}).fetchall()
        if not trows:
            continue
        span = "当周" if weeks_back <= 1 else f"近 {weeks_back} 周"
        lines.append(f"【关联投诉工单（{span}，共 {int(total)} 单，列最新 {len(trows)} 条）】"
                     "—— 请按单核查，定位共性根因后反馈处理方案：")
        for i, (tno, ctime, city, content, sol, rc) in enumerate(trows, 1):
            day = ctime.strftime("%m-%d") if hasattr(ctime, "strftime") else "—"
            lines.append(
                f"{i}. {tno}（{day} {city or '—'}）\n"
                f"   投诉内容：{(content or '无')[:_ISSUE_TEXT_CLAMP]}\n"
                f"   核查过程：{(sol or '无')[:_ISSUE_TEXT_CLAMP]}\n"
                f"   AI 分析：{(rc or '待分析')[:_ISSUE_TEXT_CLAMP]}"
            )
    return "\n".join(lines)


def _create_issue(db: Session, l1: str, l2: str, title: str, owner: str,
                  due: Optional[date], desc: str,
                  problem_nos: Optional[List[str]] = None,
                  context_weeks: int = 1) -> Dict:
    """进程内建运营工单（复用 operation_issue_service，不走 HTTP 自环）。"""
    from schemas.operation import OperationIssueCreate
    from services.operation import operation_issue_service

    # 自动代入问题说明 + 指定周期关联投诉工单明细（接收方按单核查）
    context = build_issue_context(db, problem_nos or [], weeks_back=context_weeks)
    full_desc = f"{desc}\n\n{context}".strip() if context else desc

    category, issue_type = _ISSUE_TYPE.get(l1, ("complaint", "other"))
    rc_note = f"；问题 {'/'.join(problem_nos)}" if problem_nos else ""
    payload = OperationIssueCreate(
        issue_no=_gen_issue_no(db, category),
        title=title,
        category=category,
        issue_type=issue_type,
        status="pending",
        source="complaint_weekly",
        impact_level="P1",
        handler=owner,
        situation_desc=full_desc,
        root_cause=f"客诉周报归因：{l1} / {l2}{rc_note}",
        discovery_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        go_live_date=due.strftime("%Y-%m-%d 00:00:00") if due else None,
        root_cause_type="data_issue" if "数据" in l1 else "process_gap",
        impact_scope="platform" if "批量" in desc else "partial_region",
        solution_type="data_repair" if "数据" in l1 else "code_fix",
    )
    obj = operation_issue_service.create(db, payload.model_dump())
    return {"id": obj.id, "issue_no": obj.issue_no}


def add(db: Session, l2: str, title: str, owner: str, due: Optional[date],
        acceptance: str, create_issue: bool, desc: str = "",
        problem_nos: Optional[List[str]] = None,
        context_weeks: int = 1) -> Dict:
    row = db.execute(text(
        "SELECT parent_name FROM pmwb_complaint_category WHERE level = 2 AND name = :n"
    ), {"n": l2}).scalar()
    if not row:
        raise ValueError(f"二级场景不存在于字典：{l2}（请先在 pmwb_complaint_category 维护）")
    l1 = row

    week = latest_week(db) or week_key(datetime.now())
    action_no = _next_action_no(db, week)

    issue_id = issue_no = None
    if create_issue:
        issue = _create_issue(db, l1, l2, title, owner, due,
                              desc or f"客诉周报（{week}）识别的改进措施，针对场景：{l2}",
                              problem_nos=problem_nos, context_weeks=context_weeks)
        issue_id, issue_no = issue.get("id"), issue.get("issue_no")

    db.execute(text("""
        INSERT INTO pmwb_complaint_action
            (action_no, title, category_l1, category_l2, issue_id, issue_no,
             owner, due_date, acceptance, target_drop_pct, verify_weeks,
             status, created_at, updated_at)
        VALUES
            (:no, :title, :l1, :l2, :iid, :ino, :owner, :due, :acc, :target, :vw,
             'planned', :now_ts, :now_ts)
    """), {
        "no": action_no, "title": title, "l1": l1, "l2": l2,
        "iid": issue_id, "ino": issue_no, "owner": owner, "due": due,
        "acc": acceptance, "target": C.DEFAULT_TARGET_DROP_PCT, "vw": C.DEFAULT_VERIFY_WEEKS,
        "now_ts": datetime.now(),
    })
    db.commit()

    # 关联共性问题（多对多；个别关联失败不阻断措施登记，收集 warnings）
    warnings: List[str] = []
    if problem_nos:
        from services.complaint.problems import link_action
        for pno in problem_nos:
            try:
                r = link_action(db, pno, action_no, linked_by=owner,
                                note="登记措施时关联")
                if r.get("warning"):
                    warnings.append(r["warning"])
            except ValueError as e:
                warnings.append(f"问题 {pno} 关联失败：{e}")
    return {"action_no": action_no, "issue_id": issue_id, "issue_no": issue_no,
            "l1": l1, "warnings": warnings}


# ── 簇口径统计（2026-11-04 切口径；唯一实现，禁在别处另写 SQL） ──
def cluster_keys(rc_nos) -> List[str]:
    """归一化簇集合入参（支持 None / str / 逗号串 / list）。"""
    if not rc_nos:
        return []
    if isinstance(rc_nos, str):
        parts = rc_nos.split(",")
    else:
        parts = list(rc_nos)
    out: List[str] = []
    for p in parts:
        k = str(p or "").strip()
        if k and k not in out:
            out.append(k)
    return out


def clusters_of_l2(db: Session, l2: str) -> List[str]:
    """按二级场景反查根因簇（兼容未回填 rootcause_nos 的旧措施）。

    仅作兼容兜底：新措施必须显式指定簇，不走场景推断。
    """
    if not l2:
        return []
    rows = db.execute(text(
        "SELECT DISTINCT rootcause_no FROM pmwb_complaint_ticket "
        "WHERE category_l2 = :l2 AND rootcause_no IS NOT NULL AND rootcause_no <> ''"
    ), {"l2": l2}).fetchall()
    return [r[0] for r in rows]


def _in_clause(nos: List[str], prefix: str = "rc") -> tuple:
    marks = ", ".join(f":{prefix}{i}" for i in range(len(nos)))
    return f"({marks})", {f"{prefix}{i}": v for i, v in enumerate(nos)}


def week_count(db: Session, rc_nos, week: str) -> int:
    """簇集合当周单量（根因口径；替代原场景单量）。"""
    nos = cluster_keys(rc_nos)
    if not nos or not week:
        return 0
    s, e = week_bounds(week)
    cond, params = _in_clause(nos)
    params.update({"s": s, "e": e})
    return int(db.execute(text(
        f"SELECT COUNT(*) FROM pmwb_complaint_ticket "
        f"WHERE rootcause_no IN {cond} AND created_time >= :s AND created_time < :e"
    ), params).scalar() or 0)


def complete_weeks(db: Session, before: date, weeks: int = C.BASELINE_WEEKS) -> List[str]:
    """措施上线前的**完整周**（该周至少 5 天有工单，防残缺周拉低基线）。

    为什么必须判完整：历史导入常出现半周数据（实测 W42 只有 2 天 13 单），
    直接用来当基线会把基线压到接近 0，降幅算成 -246.9% 这种假结论。

    实现：日期去重放 Python 侧做——`DATE()`/`strftime()` 分属 MySQL/SQLite 专有，
    基线窗口最长 4 周量级很小，跨库一致比省一次内存遍历更重要。
    """
    start = datetime.combine(before, datetime.min.time()) - timedelta(weeks=weeks)
    rows = db.execute(text(
        "SELECT week, created_time FROM pmwb_complaint_ticket "
        "WHERE created_time >= :s AND created_time < :e"
    ), {"s": start, "e": datetime.combine(before, datetime.min.time())}).fetchall()
    days: Dict[str, set] = {}
    for wk, ct in rows:
        if not wk or not ct:
            continue
        day = ct.date() if hasattr(ct, "date") else str(ct)[:10]
        days.setdefault(wk, set()).add(day)
    return sorted(w for w, d in days.items() if len(d) >= 5)


def baseline_for(db: Session, rc_nos, go_live: date,
                 weeks: int = C.BASELINE_WEEKS) -> Optional[float]:
    """措施上线前 N 个完整周该簇集合的周均单量。

    无完整周可用 → 返回 None（调用方不得据此计算降幅，宁可不给结论）。
    """
    nos = cluster_keys(rc_nos)
    if not nos or not go_live:
        return None
    full = complete_weeks(db, go_live, weeks)
    if not full:
        return None
    total = sum(week_count(db, nos, w) for w in full)
    return round(total / len(full), 1)


def verify(db: Session) -> List[Dict]:
    """结算验证中的措施：更新基线/最近一周单量/实际降幅，到观察期满自动定论。

    状态变化一律经 services.complaint.update_status（注册表校验 + 工单联动钩子）；
    状态不变时仅刷新有效性指标。个别流转缺必填（如 owner）不阻断其余措施结算。
    """
    rows = db.execute(text("""
        SELECT id, action_no, category_l2, rootcause_nos, go_live_date, verify_weeks,
               baseline_cnt, target_drop_pct, status
        FROM pmwb_complaint_action
        WHERE status IN ('verifying', 'in_progress')
    """)).mappings().all()

    latest = latest_week(db)
    results: List[Dict] = []
    for a in rows:
        go_live = a["go_live_date"]
        # 簇口径优先；旧措施未回填时按场景反查兜底（兼容，不新增第二套口径）
        nos = cluster_keys(a["rootcause_nos"]) or clusters_of_l2(db, a["category_l2"])
        if not nos or not go_live:
            results.append({"action_no": a["action_no"], "status": a["status"],
                            "skipped": "未绑定根因簇或未标记生效"})
            continue

        baseline = a["baseline_cnt"] or baseline_for(db, nos, go_live)
        if not baseline:
            # 基线不可得（历史数据残缺/不足一个完整周）→ 不给降幅，
            # 状态不流转：宁可不结论，也不产出 -246.9% 这种假结论。
            db.execute(text(
                "UPDATE pmwb_complaint_action SET rootcause_nos = :n, updated_at = :t "
                "WHERE id = :i"
            ), {"n": ",".join(nos), "t": datetime.now(), "i": a["id"]})
            results.append({"action_no": a["action_no"], "status": a["status"],
                            "baseline": None, "skipped": "基线不可得（无完整基线周）"})
            continue

        last_cnt = float(week_count(db, nos, latest)) if latest else 0.0
        drop = round((baseline - last_cnt) / baseline * 100, 1) if baseline else None

        elapsed_weeks = (date.today() - go_live).days // 7
        new_status = a["status"]
        if a["status"] == "in_progress" and elapsed_weeks >= 0:
            new_status = "verifying"
        if elapsed_weeks >= (a["verify_weeks"] or C.DEFAULT_VERIFY_WEEKS) and drop is not None:
            new_status = "effective" if drop >= (a["target_drop_pct"] or C.DEFAULT_TARGET_DROP_PCT) else "ineffective"

        metrics_payload = {"baseline_cnt": baseline, "last_week_cnt": last_cnt,
                           "actual_drop_pct": drop}
        error = ""
        if new_status != a["status"]:
            from services.complaint import update_status  # 唯一写入口（懒加载防循环）
            try:
                update_status(db, a["action_no"], new_status, metrics_payload)
            except ValueError as e:
                error = str(e)
        db.execute(text("""
            UPDATE pmwb_complaint_action
            SET baseline_cnt = :b, last_week_cnt = :l, actual_drop_pct = :d,
                rootcause_nos = :n, updated_at = :now_ts
            WHERE id = :i
        """), {"b": baseline, "l": last_cnt, "d": drop, "n": ",".join(nos),
               "i": a["id"], "now_ts": datetime.now()})
        results.append({"action_no": a["action_no"], "clusters": nos, "baseline": baseline,
                        "last_week": last_cnt, "drop": drop,
                        "status": new_status if not error else a["status"],
                        **({"error": error} if error else {})})
    db.commit()
    return results


def mark_go_live(db: Session, action_no: str, go_live: date) -> None:
    """标记生效并绑基线（状态流转收敛到 services.complaint.update_status 唯一入口，
    自动触发工单单步推进联动）。"""
    from services.complaint import update_status  # 懒加载防循环
    update_status(db, action_no, "verifying", {
        "go_live_date": str(go_live),
        "baseline_cnt": baseline_for(
            db, cluster_keys(_clusters_of_action(db, action_no))
            or clusters_of_l2(db, _l2_of(db, action_no)), go_live),
    })


def _l2_of(db: Session, action_no: str) -> str:
    return db.execute(text(
        "SELECT category_l2 FROM pmwb_complaint_action WHERE action_no = :no"
    ), {"no": action_no}).scalar() or ""


def _clusters_of_action(db: Session, action_no: str) -> str:
    return db.execute(text(
        "SELECT rootcause_nos FROM pmwb_complaint_action WHERE action_no = :no"
    ), {"no": action_no}).scalar() or ""


def list_actions(db: Session) -> List[Dict]:
    rows = db.execute(text("""
        SELECT a.action_no, a.category_l1, a.category_l2, a.title, a.owner, a.due_date,
               a.go_live_date, a.baseline_cnt, a.target_drop_pct, a.last_week_cnt,
               a.actual_drop_pct, a.status, a.issue_no,
               (SELECT l.problem_no FROM pmwb_complaint_problem_action l
                 WHERE l.action_no = a.action_no ORDER BY l.id LIMIT 1) AS problem_no,
               (SELECT COUNT(*) FROM pmwb_complaint_problem_action l
                 WHERE l.action_no = a.action_no) AS problem_cnt
        FROM pmwb_complaint_action a
        ORDER BY FIELD(a.status,'ineffective','verifying','in_progress','planned','effective','cancelled'), a.due_date
    """)).mappings().all()
    return [dict(r) for r in rows]


