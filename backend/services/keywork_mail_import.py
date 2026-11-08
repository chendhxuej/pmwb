# -*- coding: utf-8 -*-
"""周反馈邮件 → 重点工作更新：解析、匹配、落库（**唯一真相源**）。

背景：专题负责人每周回一封「【周反馈请求】<专题标题> - Wxx」邮件，正文分
月计划完成情况 / 周计划完成情况 / 下周（下月）计划 / 成员待办 四段。
本服务把正文结构化，与系统内月计划、周计划、成员待办做相似度匹配，
产出「状态变更 / 备注 / 新增 / 存疑」四类草案，人工在页面确认后落库。

落库只走服务层既有入口：
  1. 反馈台账 / 状态 / 待办备注 / 新增待办 → ``keywork_service.submit_weekly_feedback``
  2. 新增月计划 / 周计划 → ORM + ``keywork_service.sync_plan_to_progress``
  3. 计划类备注 → 追加到 ``content`` 的 ``[Wxx] 说明``（计划表无 note 字段）

五条口径（与页面说明、CLI 完全一致，禁另造）：
  1. 周次按**邮件发送日期**的 ISO 周，不信主题里的 W##（负责人常写错）。
  2. 条目归类看正文标签【月计划】/【周计划】；标了月计划但内容其实是周计划的跨类回退。
  3. 状态只认显式状态位（待办的 ``| 第2段``、计划的 ``--`` 之后、行尾括号），
     标题里出现的「完成」不参与判定。
  4. **状态只进不退**：completed 是终点，重跑不得回退（STATUS_FLOW 白名单）。
  5. 新增前按归一化标题查重；下周计划命中在途项只更状态、不新建。
"""
from __future__ import annotations

import difflib
import hashlib
import html as _html
import json
import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.config import settings
from db.models import (
    PmwbKeyWork,
    PmwbKeyWorkMailImportRun,
    PmwbKeyWorkMemberTask,
    PmwbKeyWorkMonthlyPlan,
    PmwbKeyWorkWeeklyFeedback,
    PmwbKeyWorkWeeklyPlan,
    now_cn,
)
from services.keywork import derive_iso_week, keywork_service, sync_plan_to_progress

SUBJECT_KEY = "周反馈"
TOPIC_CATEGORY = "special_topic"
HI, MID = 0.82, 0.60
DEFAULT_SINCE = "2026-10-29"

# 状态词：长词优先（部分完成 > 已完成 > 完成）
STATUS_WORDS: List[Tuple[str, str]] = [
    ("部分完成", "in_progress"),
    ("已完成", "completed"),
    ("未启动", "not_started"),
    ("未开始", "not_started"),
    ("延迟", "delayed"),
    ("延期", "delayed"),
    ("进行中", "in_progress"),
    ("完成", "completed"),
]

# 状态只进不退白名单：当前状态 -> 允许流转到的状态
STATUS_FLOW: Dict[str, set] = {
    "not_started": {"in_progress", "delayed", "completed", "cancelled"},
    "in_progress": {"completed", "delayed", "cancelled"},
    "delayed": {"in_progress", "completed", "cancelled"},
    "completed": {"completed"},
    "cancelled": {"cancelled"},
}

KIND_TABLE = {
    "month_plan": (PmwbKeyWorkMonthlyPlan, "monthly"),
    "week_plan": (PmwbKeyWorkWeeklyPlan, "weekly"),
    "todo": (PmwbKeyWorkMemberTask, "task"),
}
KIND_LABEL = {"month_plan": "月计划", "week_plan": "周计划", "todo": "成员待办"}

_PERSON = r"[\u4e00-\u9fa5]{2,4}(?:[、,，/][\u4e00-\u9fa5]{2,4})*"
_BAD_NAMES = {"进行中", "已完成", "部分完成", "未开始", "未启动", "延迟", "延期", "待填写"}
_MARK = re.compile(r"^\s*(?:[*•·\-]+\s*)?(?:\u2b1c\s*)?")
_DASH_CN = re.compile(r"(?<=[\u4e00-\u9fa5])-{1,2}(?=[\u4e00-\u9fa5])")
_STATUS_IN_BRACKET = re.compile(
    r"[（(][^（()）]*(部分完成|已完成|完成|未开始|未启动|延迟|延期|进行中)[^（()）]*[)）]?"
)
_SECTION_HEAD = [
    (r"^\s*\d\s*[、.]\s*月计划完成情况", "month_review"),
    (r"^\s*\d\s*[、.]\s*周计划完成情况", "week_review"),
    (r"^\s*[一二三四五六]\s*[、.]\s*下周工作计划", "next_month"),
    (r"^\s*下月计划", "next_month"),
    (r"^\s*下周计划", "next_week"),
    (r"^\s*[三四五六]\s*[、.]\s*成员待办", "todos"),
    (r"^\s*[四五六]\s*[、.]", "stop"),
    (r"^\s*[一二三]\s*[、.]\s*本周工作进展", "reset"),
]


# ---------------------------------------------------------------- 文本工具
def unify(s: str) -> str:
    """统一各种破折号，后续正则只处理 ASCII '-'。"""
    return (s or "").replace("—", "-").replace("–", "-").replace("－", "-")


def norm_text(s: str) -> str:
    """相似度比较用：去标签/括注/空白，保留中文结构。"""
    s = (s or "").replace("【周计划】", "").replace("【月计划】", "")
    s = re.sub(r"[（(][\u4e00-\u9fa5、,，/\s]{2,12}[)）]", "", s)
    s = re.sub(r"[\s\u3000]+", "", s)
    s = unify(s)
    s = s.replace("**", "").replace("*", "").replace("⬜", "")
    return s.strip(" -*。•·")


def norm_key(s: str) -> str:
    """查重键用：连标点一起干掉，只留实义字符。"""
    return re.sub(r"[\s\u3000（）()【】\[\]，,。.、:：;；\-—_/|｜]+", "", s or "")


def status_of(line: str, is_todo: bool = False) -> Optional[str]:
    """从显式状态位取状态；标题里的「完成」不算。"""
    s = unify(line)
    if is_todo and ("|" in s or "｜" in s):
        parts = re.split(r"[|｜]", s)
        span = parts[1] if len(parts) > 1 else ""
    elif re.search(r"-{2,}", s):
        span = re.split(r"-{2,}", s, maxsplit=1)[1]
    else:
        m = re.findall(r"[（(]([^（()）]*)[)）]?", s)
        span = m[-1] if m else ""
    if not span:
        return None
    for word, st in STATUS_WORDS:
        if word in span:
            return st
    return None


def clean_title(line: str, is_todo: bool = False) -> str:
    s = unify(line).strip()
    s = _MARK.sub("", s)
    if is_todo and ("|" in s or "｜" in s):
        s = re.split(r"[|｜]", s)[0].strip()
        s = re.sub(r"-{1,3}\s*[^-\s]+\s*$", "", s).strip()
    else:
        s = s.split("--")[0].strip()
        s = _STATUS_IN_BRACKET.sub("", s).strip()
        s = re.sub(r"[（(]" + _PERSON + r"[)）][。.]?\s*$", "", s).strip()
    m = _DASH_CN.search(s)          # 中文-中文的单破折号后面是备注，截断
    if m:
        s = s[: m.start()]
    s = s.replace("【周计划】", "").replace("【月计划】", "")
    s = re.sub(r"[\s\u3000]+", "", s)
    return s.strip(" -*。•·")


def assignee_of(line: str) -> str:
    s = unify(line)
    head = re.split(r"[|｜]", s)[0]
    cand = ""
    m = re.search(r"-{1,3}\s*(" + _PERSON + r")\s*$", head.strip())
    if m:
        cand = m.group(1)
    else:
        m = re.search(r"[（(](" + _PERSON + r")[)）]\s*[。.]?$", s.strip())
        if m:
            cand = m.group(1)
    cand = cand.strip()
    if not cand or cand in _BAD_NAMES or any(b in cand for b in _BAD_NAMES):
        return ""
    return cand


def note_of(line: str, is_todo: bool = False) -> str:
    """抽备注：待办取 | 第3段，计划取 -- / - 之后的说明。"""
    s = unify(line).strip()
    n = ""
    if is_todo and re.search(r"[|｜]", s):
        parts = re.split(r"[|｜]", s)
        n = parts[2].strip() if len(parts) > 2 else ""
    else:
        m = re.search(r"-{1,2}\s*([^-].*)$", s)
        if m:
            n = m.group(1)
    n = n.replace("（无进展说明）", "").replace("(无进展说明)", "").strip(" -。")
    for w, _ in STATUS_WORDS:
        for sep in ("：", ":", " "):
            if n.startswith(w + sep):
                n = n[len(w) + 1 :]
                break
        if n == w:
            n = ""
    n = n.strip(" -。")
    return "" if len(n) < 3 else n


def strip_quote(body: str) -> Tuple[str, bool]:
    """裁掉邮件里的历史引用段落。"""
    lines, out = (body or "").split("\n"), []
    for ln in lines:
        t = ln.strip()
        if (
            re.match(r"^20\d\d年\d{1,2}月\d{1,2}日", t)
            or t.startswith("发件人：")
            or t.startswith("发件人:")
            or t.startswith("-----原始邮件-----")
            or t.startswith("________________________________")
        ):
            break
        out.append(ln)
    txt = "\n".join(out).strip()
    if len(norm_text(txt)) < 40 or ("【周计划】" not in txt and "【周计划】" in body):
        return body, False
    return txt, True


def parse_items(text: str) -> Dict[str, List[dict]]:
    res: Dict[str, List[dict]] = {
        "month_review": [],
        "week_review": [],
        "next_month": [],
        "next_week": [],
        "todos": [],
    }
    section = None
    for raw in (text or "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        hit = False
        for pat, sec in _SECTION_HEAD:
            if re.search(pat, line):
                section = None if sec in ("stop", "reset") else sec
                hit = True
                break
        if hit:
            continue
        if section is None:
            continue
        if section == "todos":
            if "|" not in line and "｜" not in line and not re.search(r"-{2,}", line):
                continue
            res["todos"].append({"raw": line})
            continue
        if not re.search(r"^\s*[*•·\-]|^\s*\u2b1c|【(周|月)计划】", line):
            continue
        body = norm_text(line)
        if not body or body.strip("（）()") in ("待填写", "暂无", "无", "）", ""):
            continue
        res[section].append({"raw": line})
    return res


def kind_of(raw: str, section: str) -> str:
    if "【月计划】" in raw:
        return "month_plan"
    if "【周计划】" in raw:
        return "week_plan"
    if section in ("month_review", "next_month"):
        return "month_plan"
    return "week_plan"


def html_to_text(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style).*?</\1>", "", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|tr|li|h\d)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return _html.unescape(s).replace("\xa0", " ")


# ---------------------------------------------------------------- 邮件读取
def mail_db_path() -> str:
    return (getattr(settings, "MAIL_CENTER_DB", "") or "").strip() or os.path.join(
        "D:", os.sep, "项目", "统一邮件中心", "server", "prisma", "local.db"
    )


def mail_db_ready() -> Tuple[bool, str]:
    p = mail_db_path()
    if not os.path.exists(p):
        return False, "邮件中心数据库不存在：%s" % p
    try:
        c = sqlite3.connect("file:%s?mode=ro" % p.replace("\\", "/"), uri=True, timeout=5)
        c.execute("SELECT 1 FROM InboxMessage LIMIT 1")
        c.close()
        return True, "ok"
    except Exception as exc:  # noqa: BLE001 - 诊断信息原样回传页面
        return False, "邮件中心数据库不可读：%s" % exc


def load_mails(since: str, until: Optional[str] = None) -> List[dict]:
    """读收件箱中区间内的周反馈邮件（只读连接，不改邮件中心任何数据）。"""
    ok, reason = mail_db_ready()
    if not ok:
        raise RuntimeError(reason)
    until = until or now_cn().strftime("%Y-%m-%d")
    p = mail_db_path().replace("\\", "/")
    c = sqlite3.connect("file:%s?mode=ro" % p, uri=True, timeout=10)
    try:
        rows = c.execute(
            """
            SELECT id, COALESCE(subject,''), COALESCE(fromEmail,''),
                   datetime(sentAt/1000,'unixepoch','+8 hours'),
                   COALESCE(textBody,''), COALESCE(htmlBody,'')
              FROM InboxMessage
             WHERE subject LIKE ?
               AND date(sentAt/1000,'unixepoch','+8 hours') BETWEEN ? AND ?
             ORDER BY sentAt
            """,
            ("%" + SUBJECT_KEY + "%", since, until),
        ).fetchall()
    finally:
        c.close()

    out = []
    for mid, subj, frm, dt, text, html in rows:
        if not dt:
            continue
        body = text if (text or "").strip() else html_to_text(html)
        out.append(
            {
                "id": mid,
                "subject": (subj or "").strip(),
                "from": frm or "",
                "date": dt[:10],
                "datetime": dt,
                "week_day": datetime.strptime(dt[:10], "%Y-%m-%d"),
                "body": body or "",
            }
        )
    return out


# ---------------------------------------------------------------- 专题匹配
def _topic_index(db: Session) -> List[dict]:
    rows = (
        db.query(PmwbKeyWork.id, PmwbKeyWork.title, PmwbKeyWork.owner)
        .filter(PmwbKeyWork.category == TOPIC_CATEGORY)
        .order_by(PmwbKeyWork.id)
        .all()
    )
    return [{"kw": r[0], "title": r[1] or "", "owner": r[2] or ""} for r in rows]


def match_topic(subject: str, topics: List[dict]) -> Optional[dict]:
    """邮件主题 → 专题（标题归一化后包含，兜底相似度 ≥0.72）。"""
    s = norm_text(subject)
    for t in topics:
        key = norm_text(t["title"])
        if key and key in s:
            return t
    best, score = None, 0.0
    for t in topics:
        r = difflib.SequenceMatcher(None, norm_text(t["title"]), s).ratio()
        if r > score:
            best, score = t, r
    return best if score >= 0.72 else None


# ---------------------------------------------------------------- 基线数据
def _load_base(db: Session) -> Dict[str, List[dict]]:
    topic_ids = [r[0] for r in db.query(PmwbKeyWork.id).filter(PmwbKeyWork.category == TOPIC_CATEGORY)]
    months = [
        {"id": r.id, "kw": r.key_work_id, "period": str(r.month), "title": r.title or "", "status": r.status}
        for r in db.query(PmwbKeyWorkMonthlyPlan).filter(PmwbKeyWorkMonthlyPlan.key_work_id.in_(topic_ids))
    ]
    weeks = [
        {"id": r.id, "kw": r.key_work_id, "period": str(r.week), "title": r.title or "", "status": r.status}
        for r in db.query(PmwbKeyWorkWeeklyPlan).filter(PmwbKeyWorkWeeklyPlan.key_work_id.in_(topic_ids))
    ]
    todos = [
        {
            "id": r.id,
            "kw": r.key_work_id,
            "period": "-",
            "status": r.status,
            "assignee": r.assignee or "",
            "title": r.title or "",
            "note": r.note or "",
        }
        for r in db.query(PmwbKeyWorkMemberTask).filter(PmwbKeyWorkMemberTask.key_work_id.in_(topic_ids))
    ]
    return {"month_plan": months, "week_plan": weeks, "todo": todos}


def _sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm_text(a), norm_text(b)).ratio()


def _best(title: str, pool: List[dict]) -> Tuple[Optional[dict], float, List[Tuple[float, dict]]]:
    scored = sorted(((_sim(title, p["title"]), p) for p in pool), key=lambda x: -x[0])
    if not scored:
        return None, 0.0, []
    return scored[0][1], scored[0][0], [s for s in scored[1:4] if s[0] >= MID]


# 页面提示（不改状态判定口径，只影响默认勾选与标签，最终人身决定）
_ROUTINE_HINT = re.compile(r"例行|按周|每周|滚动|月结|日巡")
_UNFINISHED_HINT = re.compile(r"待(验证|联调|上线|确认|测试|开发|补充|部署|评估)|测试中|开发中|预计\d|月中|月底")


def item_hint(title: str, note: str, mail_status: Optional[str], raw: str = "") -> str:
    """routine=例行滚动任务（完成本期不等于结单）；unfinished=邮件说完成但正文仍留待办。

    只用于页面默认不勾选 + 打标签，不参与状态判定——判不判仍由人在页面上决定。
    """
    if _ROUTINE_HINT.search(title or ""):
        return "routine"
    if mail_status == "completed" and _UNFINISHED_HINT.search(note or "") or (
        mail_status == "completed" and _UNFINISHED_HINT.search(raw or "")
    ):
        return "unfinished"
    return ""


def _can_transition(cur: Optional[str], new: str) -> bool:
    if not cur:
        return True
    return new in STATUS_FLOW.get(cur, {cur})


# ---------------------------------------------------------------- 预览
def build_preview(
    db: Session, since: str, until: Optional[str] = None, include_dates: Optional[Iterable[str]] = None
) -> dict:
    """解析区间邮件，产出变更草案（**不写库**）。"""
    topics = _topic_index(db)
    base = _load_base(db)
    mails_raw = load_mails(since, until)
    skip_dates = set(include_dates or [])

    changes: List[dict] = []
    pending: List[dict] = []
    doubts: List[dict] = []
    mails: List[dict] = []
    unmatched: List[dict] = []

    def pool_for(kind: str, kw: int) -> List[dict]:
        return [x for x in base[kind] if x["kw"] == kw] + [
            x for x in pending if x["kw"] == kw and x["kind"] == kind
        ]

    def handle(kind: str, raw: str, kw: int, kw_title: str, tag: str, week_no: int, period: str) -> None:
        is_todo = kind == "todo"
        title = clean_title(raw, is_todo)
        if len(norm_text(title)) < 4:
            return
        st = status_of(raw, is_todo)
        hit, score, alts = _best(title, pool_for(kind, kw))
        if hit and score >= HI:
            if hit.get("_pending"):
                hit["hits"].append(tag)
                if st:
                    hit["status"] = st
                nt = note_of(raw, is_todo)
                if nt:
                    hit.setdefault("notes", []).append(nt)
                return
            note = note_of(raw, is_todo)
            note_only = (not st) or st == hit["status"]
            if note_only:
                # 待办有 note 字段可直接比对；计划类无 note，重复由落库时按 content 行去重
                if not note or (is_todo and note == (hit.get("note") or "")):
                    return
            changes.append(
                {
                    "key": "ch:%s:%s:%s" % (kind, hit["id"], "note" if note_only else "status"),
                    "kw": kw,
                    "kw_title": kw_title,
                    "kind": kind,
                    "id": hit["id"],
                    "sys_title": hit["title"],
                    "sys_status": hit["status"],
                    "mail_title": title,
                    "mail_status": hit["status"] if note_only else st,
                    "note": note,
                    "note_only": note_only,
                    "src": tag,
                    "period": period,
                    "week": period,
                    "score": round(score, 2),
                    "blocked_from": None if note_only or _can_transition(hit["status"], st or "") else hit["status"],
                    "hint": item_hint(hit["title"], note, hit["status"] if note_only else st, raw),
                }
            )
            return
        if hit and score >= MID:
            if hit.get("_pending"):
                hit["hits"].append(tag)
                hit["low_conf"] = round(score, 2)
                if st:
                    hit["status"] = st
                return
            doubts.append(
                {
                    "key": "doubt:%d" % len(doubts),
                    "kw": kw,
                    "kw_title": kw_title,
                    "kind": kind,
                    "sys_id": hit["id"],
                    "sys_title": hit["title"],
                    "sys_status": hit["status"],
                    "mail_title": title,
                    "mail_status": st,
                    "note": note_of(raw, is_todo),
                    "assignee": assignee_of(raw),
                    "period": period,
                    "raw": raw,
                    "src": tag,
                    "score": round(score, 2),
                    "alts": [{"title": a["title"], "score": round(s, 2)} for s, a in alts],
                }
            )
            return
        # 跨类回退：标了【月计划】但内容其实是周计划（负责人常标错）
        if kind == "month_plan":
            hit2, score2, _ = _best(
                title, [x for x in pool_for("week_plan", kw) if not x.get("_pending")]
            )
            if hit2 and score2 >= HI:
                if st and st != hit2["status"]:
                    changes.append(
                        {
                            "key": "ch:week_plan:%s:status" % hit2["id"],
                            "kw": kw,
                            "kw_title": kw_title,
                            "kind": "week_plan",
                            "id": hit2["id"],
                            "sys_title": hit2["title"],
                            "sys_status": hit2["status"],
                            "mail_title": title,
                            "mail_status": st,
                            "note": "",
                            "note_only": False,
                            "src": tag,
                            "period": period,
                            "week": period,
                            "score": round(score2, 2),
                            "cross": True,
                            "blocked_from": None if _can_transition(hit2["status"], st) else hit2["status"],
                            "hint": item_hint(hit2["title"], "", st, raw),
                        }
                    )
                return
        pending.append(
            {
                "key": "add:%s:%d" % (kind, len(pending)),
                "kw": kw,
                "kw_title": kw_title,
                "kind": kind,
                "title": title,
                "status": st or "not_started",
                "assignee": assignee_of(raw),
                "period": period,
                "src": tag,
                "week": period,
                "score": round(score, 2),
                "_pending": True,
                "hits": [tag],
            }
        )

    for mail in mails_raw:
        if skip_dates and mail["date"] in skip_dates:
            continue
        topic = match_topic(mail["subject"], topics)
        if not topic:
            unmatched.append(
                {"id": mail["id"], "subject": mail["subject"], "date": mail["date"], "from": mail["from"]}
            )
            continue
        d = mail["week_day"]
        iso = d.isocalendar()
        week_no = iso[1]
        tag = "%s W%d" % (mail["date"], week_no)
        period = "%d-W%02d" % (iso[0], week_no)
        txt, trimmed = strip_quote(mail["body"])
        items = parse_items(txt)
        mails.append(
            {
                "id": mail["id"],
                "date": mail["date"],
                "datetime": mail["datetime"],
                "week": period,
                "kw": topic["kw"],
                "kw_title": topic["title"],
                "from": mail["from"],
                "trimmed": trimmed,
                "counts": {k: len(v) for k, v in items.items()},
                "raw": txt,
            }
        )
        for sec in ("month_review", "week_review"):
            for it in items[sec]:
                handle(kind_of(it["raw"], sec), it["raw"], topic["kw"], topic["title"], tag, week_no, period)
        for it in items["todos"]:
            handle("todo", it["raw"], topic["kw"], topic["title"], tag, week_no, period)
        # 下月 / 下周计划：周期取「下一期」，命中在途项只更状态
        for sec, kind, delta in (("next_month", "month_plan", 0), ("next_week", "week_plan", 1)):
            for it in items[sec]:
                t = clean_title(it["raw"])
                if len(norm_text(t)) < 4:
                    continue
                st = status_of(it["raw"])
                nxt = d + timedelta(days=7 * delta)
                niso = nxt.isocalendar()
                nperiod = (
                    "%d-W%02d" % (niso[0], niso[1])
                    if kind == "week_plan"
                    else (nxt.replace(day=1) + timedelta(days=32)).strftime("%Y-%m")
                )
                hit, sc, _ = _best(t, pool_for(kind, topic["kw"]))
                if hit and sc >= HI:
                    if hit.get("_pending"):
                        hit["hits"].append(tag)
                        if st:
                            hit["status"] = st
                        continue
                    if st and st != hit["status"]:
                        changes.append(
                            {
                                "key": "ch:%s:%s:status" % (kind, hit["id"]),
                                "kw": topic["kw"],
                                "kw_title": topic["title"],
                                "kind": kind,
                                "id": hit["id"],
                                "sys_title": hit["title"],
                                "sys_status": hit["status"],
                                "mail_title": t,
                                "mail_status": st,
                                "note": "",
                                "note_only": False,
                                "src": tag,
                                "period": nperiod,
                                "week": nperiod,
                                "score": round(sc, 2),
                                "blocked_from": None if _can_transition(hit["status"], st) else hit["status"],
                                "hint": item_hint(hit["title"], "", st, it["raw"]),
                            }
                        )
                    continue
                pending.append(
                    {
                        "key": "add:%s:%d" % (kind, len(pending)),
                        "kw": topic["kw"],
                        "kw_title": topic["title"],
                        "kind": kind,
                        "title": t,
                        "status": st or "not_started",
                        "assignee": assignee_of(it["raw"]),
                        "period": nperiod,
                        "src": tag,
                        "week": nperiod,
                        "score": round(sc, 2),
                        "_pending": True,
                        "hits": [tag],
                    }
                )

    # 同 (kind,id,维度) 取最新邮件
    order = {m["datetime"][:16]: i for i, m in enumerate(mails)}
    merged: Dict[Tuple[str, int, str], dict] = {}
    for ch in changes:
        k = (ch["kind"], ch["id"], "note" if ch["note_only"] else "status")
        if k not in merged or order.get(ch["src"][:16], 0) >= order.get(merged[k]["src"][:16], 0):
            merged[k] = ch
    changes = list(merged.values())

    # 新建前查重：库内已有同名 或 本轮已建过
    existing: Dict[Tuple[int, str], set] = {}
    for kind, items in base.items():
        for x in items:
            existing.setdefault((x["kw"], kind), set()).add(norm_key(x["title"]))
    batch_seen: set = set()
    adds: List[dict] = []
    dups: List[dict] = []
    for x in pending:
        k = (x["kw"], x["kind"])
        nk = norm_key(x["title"])
        if nk in existing.get(k, set()) or (k[0], k[1], nk) in batch_seen:
            dups.append({"kw": x["kw"], "kind": x["kind"], "title": x["title"]})
            continue
        batch_seen.add((k[0], k[1], nk))
        x.pop("_pending", None)
        x.pop("hits", None)
        adds.append(x)

    for ch in changes:
        if ch.get("blocked_from"):
            ch["blocked_reason"] = "系统已是「%s」，状态只进不退，本次仅可写备注" % ch["blocked_from"]

    snapshot = hashlib.sha1(
        ("|".join([since, until or "", ",".join(m["id"] for m in mails)])).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "since": since,
        "until": until or now_cn().strftime("%Y-%m-%d"),
        "snapshot_id": snapshot,
        "mails": [{k: v for k, v in m.items() if k != "raw"} for m in mails],
        "unmatched_mails": unmatched,
        "changes": changes,
        "adds": adds,
        "duplicates": dups,
        "doubts": doubts,
        "summary": {
            "mail_count": len(mails),
            "unmatched_count": len(unmatched),
            "status_count": len([c for c in changes if not c["note_only"] and not c.get("blocked_from")]),
            "note_count": len([c for c in changes if c["note_only"]]),
            "blocked_count": len([c for c in changes if c.get("blocked_from")]),
            "add_count": len(adds),
            "duplicate_count": len(dups),
            "doubt_count": len(doubts),
        },
    }


# ---------------------------------------------------------------- 落库
def _merge_json(old_raw: Optional[str], new_items: List[dict], key_name: str) -> List[dict]:
    out: Dict[str, dict] = {}
    for x in json.loads(old_raw or "[]"):
        out[json.dumps(x.get(key_name))] = x
    for x in new_items:
        out[json.dumps(x.get(key_name))] = x
    return list(out.values())


def apply_import(
    db: Session,
    since: str,
    until: Optional[str] = None,
    exclude: Optional[Iterable[str]] = None,
    doubt_actions: Optional[Dict[str, str]] = None,
    snapshot_id: Optional[str] = None,
    operator: Optional[str] = None,
) -> dict:
    """按预览结果落库。``exclude`` 为取消勾选的 key；``doubt_actions`` 为存疑裁定。

    存疑裁定：``add_todo`` 建成员待办 / ``update_status`` 按邮件状态更新系统条目 / 其余忽略。
    """
    preview = build_preview(db, since, until)
    if snapshot_id and snapshot_id != preview["snapshot_id"]:
        raise ValueError("邮件内容已变化（期间可能同步了新邮件），请刷新预览后重试")
    exclude = set(exclude or [])
    doubt_actions = doubt_actions or {}

    owner_of = dict(
        (r[0], r[1] or "")
        for r in db.query(PmwbKeyWork.id, PmwbKeyWork.owner)
        .filter(PmwbKeyWork.category == TOPIC_CATEGORY)
        .all()
    )

    stats = {
        "feedback": 0,
        "status": 0,
        "note": 0,
        "task": 0,
        "week_plan": 0,
        "month_plan": 0,
        "skipped_feedback": 0,
        "skipped_items": len(exclude),
        "doubt_applied": 0,
        "failed": [],
    }

    status_ops: List[dict] = []
    note_ops: List[dict] = []
    for ch in preview["changes"]:
        if ch["key"] in exclude or ch.get("blocked_from"):
            continue
        (status_ops if not ch["note_only"] else note_ops).append(ch)

    # 存疑裁定并入
    for d in preview["doubts"]:
        act = (doubt_actions.get(d["key"]) or "skip").strip()
        if act == "update_status" and d.get("mail_status"):
            status_ops.append(
                {
                    "key": d["key"],
                    "kw": d["kw"],
                    "kind": d["kind"],
                    "id": d["sys_id"],
                    "sys_title": d["sys_title"],
                    "sys_status": d["sys_status"],
                    "mail_title": d["mail_title"],
                    "mail_status": d["mail_status"],
                    "note": d.get("note") or "",
                    "note_only": False,
                    "src": d["src"],
                    "period": d["period"],
                    "adjudicated": True,
                }
            )
            stats["doubt_applied"] += 1
        elif act == "add_todo":
            preview["adds"].append(
                {
                    "key": d["key"],
                    "kw": d["kw"],
                    "kind": "todo",
                    "title": d["mail_title"],
                    "status": d.get("mail_status") or "not_started",
                    "assignee": d.get("assignee") or "",
                    "period": d.get("period") or "-",
                    "src": d["src"],
                    "adjudicated": True,
                }
            )
            stats["doubt_applied"] += 1

    adds = [a for a in preview["adds"] if a["key"] not in exclude]

    # 按 (专题, 邮件日期) 归组写反馈台账
    def group_key(x: dict) -> Optional[Tuple[int, str]]:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", x.get("src") or "")
        return (x["kw"], m.group(1)) if m else None

    groups: Dict[Tuple[int, str], dict] = {}

    def bucket(k: Tuple[int, str]) -> dict:
        return groups.setdefault(k, {"status": [], "note": [], "task": []})

    # 每封匹配到专题的邮件都要留痕（即使正文没抽出可用条目），形成原文追溯链
    bodies = {(m["kw"], m["date"]): m.get("raw", "") for m in _preview_raw_mails(db, since, until)}
    for k in bodies:
        bucket(k)

    for x in status_ops:
        k = group_key(x)
        if k:
            bucket(k)["status"].append(x)
    for x in note_ops:
        k = group_key(x)
        if k:
            bucket(k)["note"].append(x)
    new_todo_adds = [a for a in adds if a["kind"] == "todo"]
    for a in new_todo_adds:
        k = group_key(a)
        if k:
            bucket(k)["task"].append(a)

    for (kw, day), g in sorted(groups.items()):
        dt = datetime.strptime(day, "%Y-%m-%d")
        week = "%d-W%02d" % (dt.isocalendar()[0], dt.isocalendar()[1])
        assignee = owner_of.get(kw, "")

        item_updates = [
            {
                "type": KIND_TABLE[x["kind"]][1],
                "id": x["id"],
                "status": x["mail_status"],
            }
            for x in g["status"]
            if x["kind"] in ("month_plan", "week_plan")
        ]
        task_notes = [
            {"task_id": x["id"], "status": x["mail_status"], "note": x.get("note") or None}
            for x in g["status"]
            if x["kind"] == "todo"
        ]
        task_notes += [
            {"task_id": x["id"], "note": x["note"], "status": None} for x in g["note"] if x["kind"] == "todo"
        ]
        new_tasks = [
            {
                "title": a["title"],
                "assignee": a.get("assignee") or None,
                "status": a.get("status") or "not_started",
                "note": "",
            }
            for a in g["task"]
        ]

        prev = (
            db.query(PmwbKeyWorkWeeklyFeedback)
            .filter(
                PmwbKeyWorkWeeklyFeedback.key_work_id == kw,
                PmwbKeyWorkWeeklyFeedback.week == week,
                PmwbKeyWorkWeeklyFeedback.assignee == assignee,
            )
            .first()
        )
        merged_updates = _merge_json(prev.item_updates if prev else None, item_updates, "id")
        merged_notes = _merge_json(prev.member_task_notes if prev else None, task_notes, "task_id")
        raw_text = (bodies.get((kw, day)) or "").strip()
        old_raw = (prev.raw_text or "") if prev else ""
        unchanged = (
            prev is not None
            and json.dumps(merged_updates, sort_keys=True, ensure_ascii=False)
            == json.dumps(json.loads(prev.item_updates or "[]"), sort_keys=True, ensure_ascii=False)
            and json.dumps(merged_notes, sort_keys=True, ensure_ascii=False)
            == json.dumps(json.loads(prev.member_task_notes or "[]"), sort_keys=True, ensure_ascii=False)
            and len(raw_text) <= len(old_raw)
            and not new_tasks
        )
        if unchanged:
            stats["skipped_feedback"] += 1
        else:
            payload = {
                "week": week,
                "assignee": assignee,
                "source": "email",
                "feedback_date": day,
                "done_summary": "邮件反馈归档：状态更新 %d 项／备注 %d 项／新增待办 %d 项"
                % (len(item_updates) + len([t for t in task_notes if t.get("status")]), len(g["note"]), len(new_tasks)),
                "item_updates": merged_updates or None,
                "member_task_notes": merged_notes or None,
                "new_tasks": new_tasks or None,
                "raw_text": raw_text or None,
            }
            try:
                keywork_service.submit_weekly_feedback(db, kw, payload)
                stats["feedback"] += 1
                stats["status"] += len(item_updates) + len([t for t in task_notes if t.get("status")])
                stats["note"] += len([t for t in task_notes if t.get("note")])
                stats["task"] += len(new_tasks)
            except Exception as exc:  # noqa: BLE001 - 单组失败不影响其余
                db.rollback()
                stats["failed"].append("kw%d %s 反馈：%s" % (kw, week, exc))

    # 计划类备注：计划表无 note 字段 → 追加到 content 形成进展留痕
    for x in note_ops:
        if x["kind"] not in ("month_plan", "week_plan") or not x.get("note"):
            continue
        model = KIND_TABLE[x["kind"]][0]
        row = db.query(model).filter(model.id == x["id"], model.key_work_id == x["kw"]).first()
        if not row:
            stats["failed"].append("kw%d %s#%s 不存在" % (x["kw"], x["kind"], x["id"]))
            continue
        period = x.get("period") or x.get("week") or ""
        wtag = period.split("-")[-1] if period else "W?"
        line = "[%s] %s" % (wtag, x["note"])
        if line in (row.content or ""):
            continue
        row.content = ((row.content or "") + "\n" + line).strip()
        db.add(row)
        stats["note"] += 1
    db.commit()

    # 新增周计划 / 月计划
    for a in adds:
        if a["kind"] == "week_plan":
            row = PmwbKeyWorkWeeklyPlan(
                key_work_id=a["kw"],
                title=a["title"],
                status=a.get("status") or "not_started",
                week=a.get("period") or derive_iso_week(),
                task_date=datetime.strptime(a["src"][:10], "%Y-%m-%d").date() if a.get("src") else None,
                assignee=a.get("assignee") or None,
            )
            db.add(row)
            db.flush()
            if row.status == "completed":
                sync_plan_to_progress(db, a["kw"], "weekly", row)
            stats["week_plan"] += 1
        elif a["kind"] == "month_plan":
            row = PmwbKeyWorkMonthlyPlan(
                key_work_id=a["kw"],
                title=a["title"],
                status=a.get("status") or "not_started",
                month=a.get("period"),
                task_date=datetime.strptime(a["src"][:10], "%Y-%m-%d").date() if a.get("src") else None,
                assignee=a.get("assignee") or None,
            )
            db.add(row)
            db.flush()
            if row.status == "completed":
                sync_plan_to_progress(db, a["kw"], "monthly", row)
            stats["month_plan"] += 1
    db.commit()

    run = PmwbKeyWorkMailImportRun(
        since_date=datetime.strptime(since, "%Y-%m-%d").date(),
        until_date=datetime.strptime((until or now_cn().strftime("%Y-%m-%d")), "%Y-%m-%d").date(),
        mail_count=preview["summary"]["mail_count"],
        status_count=stats["status"],
        note_count=stats["note"],
        add_count=stats["task"] + stats["week_plan"] + stats["month_plan"],
        doubt_count=len(preview["doubts"]),
        skipped_count=stats["skipped_feedback"] + stats["skipped_items"],
        detail=json.dumps(stats, ensure_ascii=False),
        operator=operator or "",
    )
    db.add(run)
    db.commit()

    stats["run_id"] = run.id
    return stats


def _preview_raw_mails(db: Session, since: str, until: Optional[str]) -> List[dict]:
    """取每封邮件的截断正文，用于写进 weekly_feedback.raw_text 留痕。"""
    topics = _topic_index(db)
    out = []
    for m in load_mails(since, until):
        topic = match_topic(m["subject"], topics)
        if not topic:
            continue
        txt, _ = strip_quote(m["body"])
        out.append({"kw": topic["kw"], "date": m["date"], "raw": txt})
    return out


# ---------------------------------------------------------------- 运行状态
def last_run_date(db: Session) -> str:
    """上次收口日：取导入运行记录的最大截止日，无记录时退回邮件反馈最大日期。"""
    d = db.query(func.max(PmwbKeyWorkMailImportRun.until_date)).scalar()
    if not d:
        d = (
            db.query(func.max(PmwbKeyWorkWeeklyFeedback.feedback_date))
            .filter(PmwbKeyWorkWeeklyFeedback.source == "email")
            .scalar()
        )
    return d.strftime("%Y-%m-%d") if d else DEFAULT_SINCE


def list_runs(db: Session, limit: int = 20) -> List[dict]:
    rows = (
        db.query(PmwbKeyWorkMailImportRun)
        .order_by(PmwbKeyWorkMailImportRun.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "since": r.since_date.strftime("%Y-%m-%d") if r.since_date else "",
            "until": r.until_date.strftime("%Y-%m-%d") if r.until_date else "",
            "mail_count": r.mail_count,
            "status_count": r.status_count,
            "note_count": r.note_count,
            "add_count": r.add_count,
            "doubt_count": r.doubt_count,
            "skipped_count": r.skipped_count,
            "operator": r.operator,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        }
        for r in rows
    ]


def status(db: Session) -> dict:
    ok, reason = mail_db_ready()
    since = last_run_date(db)
    try:
        mails = load_mails(since) if ok else []
    except Exception:  # noqa: BLE001
        mails = []
    return {
        "mail_db_ready": ok,
        "mail_db_reason": reason,
        "mail_db_path": mail_db_path(),
        "last_run": since,
        "pending_mail_count": len(mails),
        "pending_dates": sorted({m["date"] for m in mails}),
    }
