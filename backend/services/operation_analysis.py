"""主动运营分析工单服务。

职责：
1. 生成优化后的分析工单 Excel 模板（填写区 + 填写说明 + 遗留任务表）。
2. 解析导入的 Excel（两步式）：
   - parse_analysis_workbook：仅解析、不落库，返回分析字段 + 遗留任务候选（含建议分类）+ 告警清单。
   - import_analysis_workbook：按确认结果落库，创建分析工单（category=prod）+ 分析明细
     + 遗留任务工单（category 由调用方指定，复用录入工单的工单类别）。
3. 详情查询 get_analysis_detail：返回主工单 + 分析明细 + 关联遗留任务（不限类别）。

容错原则：导入成功率优先，解析阶段 best-effort，任何数据质量问题降级为 warnings，绝不抛 500。
"""
from __future__ import annotations

import io
import re
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple

import openpyxl
from sqlalchemy.orm import Session

from db.models import PmwbOperationIssue, PmwbOperationAnalysis
from services.operation import operation_issue_service
from services.staff_resolver import resolve_staff_id

# (字段key, 模板列A标签) —— 顺序即模板行顺序
TEMPLATE_FIELDS: List[tuple] = [
    ("topic_name", "课题名称"),
    ("analyst_team", "运营团队"),
    ("analyst_name", "运营人员"),
    ("domain_code", "关联业务领域编码"),
    ("background", "课题背景说明"),
    ("scenario", "操作场景介绍"),
    ("biz_flow", "业务流程梳理"),
    ("biz_rule", "业务规则梳理"),
    ("monitoring", "业务监控梳理"),
    ("analysis_goal", "本次分析目标"),
    ("data_analysis", "数据分析过程"),
    ("result_flow", "分析结果-流程优化方面"),
    ("result_rule", "分析结果-规则优化方面"),
    ("result_model", "分析结果-数据模型方面"),
    ("result_abnormal_user", "分析结果-异常用户数据方面"),
    ("result_monitor_blind", "分析结果-监控补盲方面"),
    ("go_live_date", "计划完成时间(yyyy-mm-dd)"),
]

# 遗留任务表头（4 列：责任人 | 任务内容 | 任务分类 | 计划完成时间）
LEGACY_HEADER = ["责任人", "任务内容", "任务分类", "计划完成时间"]
VALID_PRIORITIES = ("P0", "P1", "P2", "P3")

# 工单大类与默认子类（与录入工单 CATEGORIES / IssueType 对齐）
VALID_CATEGORIES = {"bug", "data", "prod", "task", "complaint"}
CATEGORY_DEFAULT_TYPE = {
    "bug": "bug",
    "data": "data_abnormal",
    "prod": "topic_analysis",
    "task": "temp_task",
    "complaint": "spot_event",
}

_LABEL_TO_KEY = {label: key for key, label in TEMPLATE_FIELDS}

# 分析正文核心字段：缺失过多必须显式告警，禁止「静默丢字段」
# （2026-09-20 事故：191/199 两份「填写说明」模板文件正文七字段全空却无任何提示）
CORE_ANALYSIS_KEYS: List[tuple] = [
    ("background", "课题背景说明"),
    ("scenario", "操作场景介绍"),
    ("biz_flow", "业务流程梳理"),
    ("biz_rule", "业务规则梳理"),
    ("monitoring", "业务监控梳理"),
    ("analysis_goal", "本次分析目标"),
    ("data_analysis", "数据分析过程"),
]


def _missing_field_warnings(fields: Dict[str, str]) -> List[str]:
    """正文核心字段缺失告警：全空→强提示核对模板；部分空→提示可手工补录。"""
    missing = [label for key, label in CORE_ANALYSIS_KEYS if not fields.get(key)]
    if len(missing) >= len(CORE_ANALYSIS_KEYS) - 1:
        return [
            f"未识别到分析正文（{'、'.join(missing)} 全部为空）——该文件可能不是标准模板布局，"
            f"请核对后重新上传，勿直接确认导入"
        ]
    if missing:
        return [f"以下字段未识别到内容，可导入后在工单详情手工补录：{'、'.join(missing)}"]
    return []


_gen_counter = 0


def _gen_no(prefix: str) -> str:
    global _gen_counter
    _gen_counter += 1
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}{_gen_counter:02d}"


# Excel 日期序列号合理下限（1982-02-15 ≈ 30000）。低于该值不可能是真实日期序列号，
# 多为「9.24」这类「月.日」手写值被 Excel 存成数字，若照序列号解析会得到 1900-01-xx 的脏数据。
_MIN_EXCEL_SERIAL = 30000


def _parse_month_day(v: float) -> Optional[date]:
    """把「9.24」这类数字按 M.D 解释为当年（必要时次年）的日期。失败返回 None。"""
    try:
        iv = int(v)
        frac = round((float(v) - iv) * 100)
    except Exception:
        return None
    if not (1 <= iv <= 12 and 1 <= frac <= 31):
        return None
    today = datetime.now().date()
    for year in (today.year, today.year + 1):
        try:
            d = date(year, iv, frac)
        except ValueError:
            continue
        # 明显早于当前（>180 天）视为跨年填写，取次年
        if (today - d).days <= 180:
            return d
    return None


def _parse_date(v) -> Optional[date]:
    """容错日期解析：支持 datetime/date/Excel 序列号/多种字符串格式。失败返回 None（不抛错）。"""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)):
        fv = float(v)
        # 仅合理区间内的数值才按 Excel 序列号解析；其余按「月.日」尝试
        if fv >= _MIN_EXCEL_SERIAL:
            try:
                return (datetime(1899, 12, 30) + timedelta(days=fv)).date()
            except Exception:
                return None
        return _parse_month_day(fv)
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # 「9.24」「9-24」「9月24日」「9月22号」等缺年份写法 → 按当年/次年补全
    m = re.fullmatch(r"(\d{1,2})[.\-/月](\d{1,2})[日号]?", s)
    if m:
        return _parse_month_day(float(f"{m.group(1)}.{m.group(2)}"))
    return None


def _split_handlers(s: str) -> List[str]:
    """多责任人拆分：按 顿号/逗号/斜杠/分号/空格。"""
    if not s:
        return []
    parts = re.split(r"[、,，/;；\s]+", str(s).strip())
    return [p.strip() for p in parts if p.strip()]


def _suggest_category(content: str) -> Tuple[str, str]:
    """按任务内容关键词 best-effort 建议分类；未命中默认 task/temp_task。"""
    c = content or ""
    cl = c.lower()
    if any(k in c for k in ("投诉", "不满", "抱怨", "申诉", "舆情")):
        return "complaint", "spot_event"
    if any(k in c for k in ("数据异常", "数据不准", "数据缺失", "统计错", "口径", "数据问题")):
        return "data", "data_abnormal"
    if any(k in c for k in ("缺陷", "报错", "故障", "错误", "闪退", "崩溃")):
        return "bug", "bug"
    if any(k in cl for k in ("专题", "分析", "监控", "优化", "模型", "补盲", "梳理")):
        return "prod", "topic_analysis"
    return "task", "temp_task"


def build_analysis_template_bytes() -> bytes:
    """生成主动运营分析工单模板，返回 xlsx 字节流。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "分析工单"

    ws["A1"] = "主动运营分析工单填写模板"
    ws["A1"].font = openpyxl.styles.Font(bold=True, size=14)
    ws["A2"] = "填写说明见「填写说明」sheet；遗留任务填写在下方表格中，每行一条，可指定任务分类。"
    ws["A2"].font = openpyxl.styles.Font(italic=True, color="888888")

    start = 4
    for i, (key, label) in enumerate(TEMPLATE_FIELDS):
        r = start + i
        ws.cell(row=r, column=1, value=label).font = openpyxl.styles.Font(bold=True)
        ws.cell(row=r, column=2, value="")

    # 遗留任务表：4 列（责任人 | 任务内容 | 任务分类 | 计划完成时间）
    legacy_header_row = start + len(TEMPLATE_FIELDS) + 2
    ws.cell(row=legacy_header_row, column=1, value="遗留任务（未闭环任务登记，上传后按所选分类自动建任务工单）").font = openpyxl.styles.Font(bold=True, size=12)
    hr = legacy_header_row + 1
    for c, h in enumerate(LEGACY_HEADER, start=1):
        ws.cell(row=hr, column=c, value=h).font = openpyxl.styles.Font(bold=True)
    for k in range(1, 7):
        rr = hr + k
        ws.cell(row=rr, column=1, value="")
        ws.cell(row=rr, column=2, value="")
        ws.cell(row=rr, column=3, value="临时交办任务")
        ws.cell(row=rr, column=4, value="")

    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 60
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 18

    # 填写说明 sheet
    ws2 = wb.create_sheet("填写说明")
    notes = [
        "一、使用说明",
        "1. 在「分析工单」sheet 中按行填写分析内容，标 * 为重点字段。",
        "2. 课题名称为必填；其余分析字段尽量填全，便于沉淀与复盘。",
        "3. 「遗留任务」表格每行登记一条本周未闭环任务；上传后在预览中可逐条选择工单类别，确认后自动建对应任务工单。",
        "4. 任务分类列可选：BUG管理 / 数据异常管理 / 主动运营分析 / 临时交办任务 / 热点投诉。",
        "",
        "二、字段字典",
        "运营团队 / 运营人员：本次课题的分析团队与负责人（分析工单的处理人取运营人员）。",
        "关联业务领域编码：可选，对应业务领域 domain_code。",
        "计划完成时间：yyyy-mm-dd 格式；识别不准可留空，后续在工单详情手工修正。",
        "任务分类：遗留任务归属的工单大类，决定自动创建的工单类别。",
        "",
        "三、自动同步说明",
        "上传模板后：① 创建一条「主动运营分析」工单（含分析明细）；",
        "② 预览中确认每条遗留任务的工单类别，确认后逐条生成对应工单，责任人为填写的姓名；",
        "③ 责任人姓名若在人员中台匹配不到，工单仍会创建但会返回未匹配清单，需人工认领。",
    ]
    for i, line in enumerate(notes, start=1):
        ws2.cell(row=i, column=1, value=line)
    ws2.column_dimensions["A"].width = 100

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _parse_analysis_fields(ws) -> Dict[str, str]:
    """解析分析字段区。

    兼容四种布局：
      - 布局1 生成模板：列A=label（无冒号）、列B=value
      - 布局2 顾杨豪/网格通：列A=描述提示、列B=label（带"："）、列C=value
      - 布局3 孟华：列A=label（带"："）、列B=value
      - 布局4 方磊磊：列A=label（无冒号）、列B=label重复、列C=value

    容错优先，任何识别失败降级为 warnings，不抛错。
    """
    data: Dict[str, str] = {}

    def _strip_colon(s: str) -> str:
        """去除字符串末尾的冒号（中文或英文）。"""
        return re.sub(r"[：:]\s*$", "", s.strip())

    def _get_content(col_c, col_d) -> str:
        """从结果子标题行中提取内容：优先 col_d，否则 col_c。"""
        if col_d and str(col_d).strip():
            return str(col_d).strip()
        return str(col_c).strip() if col_c else ""

    # ========== 先处理「分析人员信息」，避免被布局解析覆盖 ==========
    pb = ws.cell(row=3, column=2).value
    pc = ws.cell(row=3, column=3).value
    person_str = None
    if pb and str(pb).strip():
        pb_s = str(pb).strip()
        if pb_s.endswith('：') or pb_s.endswith(':'):
            if pc and str(pc).strip():
                person_str = str(pc).strip()
        else:
            person_str = pb_s
    elif pc and str(pc).strip():
        person_str = str(pc).strip()

    if person_str:
        name_match = re.search(r'运营人员姓名?[：:]\s*(.+?)(?:，|、|\s|$)', person_str)
        team_match = re.search(r'运营团队[：:]\s*(.+?)(?:，|、|\s{4,}|\s*$)', person_str)
        if name_match:
            data["analyst_name"] = name_match.group(1).strip()
        if team_match:
            data["analyst_team"] = team_match.group(1).strip()

    # ========== 布局1&4：colA=label（无冒号），从 colB 或 colC 取 value ==========
    for r in range(1, ws.max_row + 1):
        a = ws.cell(row=r, column=1).value
        if not a:
            continue
        label = _strip_colon(str(a).strip())
        if label not in _LABEL_TO_KEY:
            continue
        key = _LABEL_TO_KEY[label]
        if data.get(key):  # 已解析则不覆盖
            continue
        b = ws.cell(row=r, column=2).value
        if b and str(b).strip():
            b_s = str(b).strip()
            # 若 colB 本身也是 label（以冒号结尾，或属于已知 label），跳过取 colC
            if _strip_colon(b_s) in _LABEL_TO_KEY or b_s.endswith('：') or b_s.endswith(':'):
                c = ws.cell(row=r, column=3).value
                data[key] = str(c).strip() if c else ""
            else:
                data[key] = b_s
            continue
        c = ws.cell(row=r, column=3).value
        if c and str(c).strip():
            data[key] = str(c).strip()

    # ========== 布局2&3：colA=label（带冒号），从 colB 取 value ==========
    for r in range(1, ws.max_row + 1):
        a = ws.cell(row=r, column=1).value
        if not a:
            continue
        a_stripped = _strip_colon(str(a).strip())
        if a_stripped not in _LABEL_TO_KEY:
            continue
        key = _LABEL_TO_KEY[a_stripped]
        if data.get(key):  # 已解析则不覆盖
            continue
        b = ws.cell(row=r, column=2).value
        if b and str(b).strip():
            data[key] = str(b).strip()

    # ========== 布局5「填写说明模板」：colA=长描述提示、colB=label（带"："）、colC=value ==========
    # 例：周大宁/工号权限类文件。colB 才是真标签，内容在 colC；此前只扫 colA 导致正文全丢。
    for r in range(1, ws.max_row + 1):
        b = ws.cell(row=r, column=2).value
        if not b:
            continue
        b_raw = str(b).strip()
        b_label = _strip_colon(b_raw)
        if b_label not in _LABEL_TO_KEY:
            continue
        key = _LABEL_TO_KEY[b_label]
        if data.get(key):  # 已解析则不覆盖
            continue
        c = ws.cell(row=r, column=3).value
        if c and str(c).strip():
            c_s = str(c).strip()
            # 填写说明模板里 colC 常把标签再抄一遍（如「课题背景说明：\n正文」），去掉重复前缀
            if re.match(r"^%s[：:]\s*" % re.escape(b_label), c_s):
                c_s = re.sub(r"^%s[：:]\s*" % re.escape(b_label), "", c_s, count=1).strip()
            if c_s:
                data[key] = c_s

    # ========== 特殊处理：「分析人员信息」从 row3 解析姓名/团队 ==========
    # 布局2（顾杨豪）：colB = 含人员和团队的信息
    # 布局3（孟华）：colB = 含人员和团队的信息（colC 为空）
    # 布局4（方磊磊）：colB = "分析人员信息："（label），colC = 含人员和团队的信息
    pb = ws.cell(row=3, column=2).value
    pc = ws.cell(row=3, column=3).value
    person_str = None
    if pb and str(pb).strip():
        pb_s = str(pb).strip()
        # 若 colB 本身是 label（以冒号结尾），跳过取 colC
        if pb_s.endswith('：') or pb_s.endswith(':'):
            if pc and str(pc).strip():
                person_str = str(pc).strip()
        else:
            person_str = pb_s
    elif pc and str(pc).strip():
        person_str = str(pc).strip()

    if person_str:
        name_match = re.search(r'运营人员姓名?[：:]\s*(.+?)(?:，|、|\s|$)', person_str)
        team_match = re.search(r'运营团队[：:]\s*（([^）]+)）', person_str)
        if not data.get("analyst_name") and name_match:
            data["analyst_name"] = name_match.group(1).strip()
        if not data.get("analyst_team") and team_match:
            data["analyst_team"] = team_match.group(1).strip()
        # 兜底：无括号情况
        if not data.get("analyst_team"):
            team_alt = re.search(r'运营团队[：:]\s*(.+?)(?:\s+运营|，|、|\s*$)', person_str)
            if team_alt:
                data["analyst_team"] = team_alt.group(1).strip()

    # ========== 结果区解析 ==========
    result_labels = {
        "result_flow": "流程优化方面",
        "result_rule": "规则优化方面",
        "result_model": "数据模型方面",
        "result_abnormal_user": "异常用户数据方面",
        "result_monitor_blind": "监控补盲方面",
    }

    for r in range(1, ws.max_row + 1):
        a = ws.cell(row=r, column=1).value
        b = ws.cell(row=r, column=2).value
        a_s = _strip_colon(str(a).strip()) if a else ""
        b_s = _strip_colon(str(b).strip()) if b else ""

        # 检测"分析结果"行（布局2 顾杨豪：colB；布局3 孟华：colA）
        is_result_header = (a_s == "分析结果") or (b_s == "分析结果")
        if is_result_header:
            # 逐行识别子标题与内容，兼容两种排布：
            #   ① colC=子标题、colD=内容（周大宁/工号权限「填写说明」模板）
            #   ② colB=子标题、colC=内容（孟华/顾杨豪模板）
            # 旧实现用外层行的 colB 匹配且命中即 break → 多行结果只落进第一项，其余四项静默丢失。
            label_keys = {label: key for key, label in result_labels.items()}
            for rr in range(r, ws.max_row + 1):
                aa = ws.cell(row=rr, column=1).value
                bb = ws.cell(row=rr, column=2).value
                cc = ws.cell(row=rr, column=3).value
                dd = ws.cell(row=rr, column=4).value
                bb_s = _strip_colon(str(bb).strip()) if bb else ""
                aa_s = _strip_colon(str(aa).strip()) if aa else ""
                # 区块结束：进入「遗留任务」区
                if bb_s.startswith("遗留任务") or aa_s.startswith("遗留任务"):
                    break
                cc_str = str(cc).strip() if cc else ""
                dd_str = str(dd).strip() if dd else ""
                key = label_keys.get(cc_str) or label_keys.get(bb_s)
                if not key or data.get(key):
                    continue
                if cc_str in label_keys:  # 排布①：子标题在列C，内容在列D
                    content = dd_str
                else:  # 排布②：子标题在列B，内容在列C
                    content = cc_str
                if content:
                    data[key] = content
            break

    # ========== 标题兜底 ==========
    if not data.get("topic_name"):
        b1 = ws.cell(row=1, column=2).value
        a1 = ws.cell(row=1, column=1).value
        if b1 and "：" not in str(b1) and ":" not in str(b1) and str(b1).strip():
            data["topic_name"] = str(b1).strip()
        elif a1 and "填写说明" not in str(a1) and "：" not in str(a1) and ":" not in str(a1) and str(a1).strip():
            data["topic_name"] = str(a1).strip()

    return data


def _locate_legacy_header(ws) -> Optional[Tuple[int, Dict[str, Optional[int]]]]:
    """定位「责任人」表头单元格（兼容其在任意列），并映射同行的 任务内容/计划完成时间/任务分类 列位置。

    兼容三种布局：
      - 生成模板：责任人(A) | 任务内容(B) | 任务分类(C) | 计划完成时间(D)
      - 旧模板：  责任人(A) | 任务内容(B) | 计划完成时间(C) | 优先级(D)
      - 附件示例：... 责任人(C) | 任务内容(D) | 计划完成时间(E) （表头行内偏移）
    """
    hr = hc = None
    for r in range(1, ws.max_row + 1):
        for c in range(1, min(ws.max_column, 8) + 1):
            v = ws.cell(row=r, column=c).value
            if v and str(v).strip() == "责任人":
                hr, hc = r, c
                break
        if hr is not None:
            break
    if hr is None:
        return None
    # 映射同行表头标签
    labels: Dict[str, int] = {}
    for c in range(hc, min(hc + 5, ws.max_column + 1)):
        v = ws.cell(row=hr, column=c).value
        if v:
            labels[str(v).strip()] = c
    handler = labels.get("责任人")
    content = labels.get("任务内容")
    due = labels.get("计划完成时间")
    category = labels.get("任务分类")
    if content is None:
        content = hc + 1
    if due is None:
        # 无「任务分类」列时，计划完成时间在 责任人后第 2 列；有「任务分类」时在 责任人后第 3 列
        due = (category + 1) if category else (hc + 2)
    cols = {
        "handler": handler,
        "content": content,
        "due": due,
        "category": category,
    }
    if cols["handler"] is None or cols["content"] is None:
        return None
    return hr, cols


def _parse_legacy_tasks(ws) -> Tuple[List[Dict], List[str]]:
    """解析遗留任务区，返回 (任务列表, 告警)。不落库、不抛错。"""
    located = _locate_legacy_header(ws)
    if not located:
        return [], []
    header_row, cols = located
    warnings: List[str] = []
    tasks: List[Dict] = []
    for r in range(header_row + 1, ws.max_row + 1):
        handler = ws.cell(row=r, column=cols["handler"]).value
        content = ws.cell(row=r, column=cols["content"]).value
        h = str(handler).strip() if handler else ""
        c = str(content).strip() if content else ""
        if not h and not c:
            continue
        due_raw = ws.cell(row=r, column=cols["due"]).value if cols["due"] else None
        due = _parse_date(due_raw)
        if due_raw is not None and due is None:
            warnings.append(f"第{r}行计划完成时间无法识别（{due_raw}），已置空，可手工修正")
        cat_cell = ws.cell(row=r, column=cols["category"]).value if cols["category"] else None
        cat_cell = str(cat_cell).strip() if cat_cell else ""
        suggest_cat, suggest_type = _suggest_category(c)
        effective_cat = cat_cell if cat_cell in VALID_CATEGORIES else suggest_cat
        tasks.append(
            {
                "handler_raw": h,
                "handlers": _split_handlers(h),
                "content": c,
                "due_date": due.isoformat() if due else None,
                "category_cell": cat_cell,
                "suggest_category": effective_cat,
                "suggest_issue_type": CATEGORY_DEFAULT_TYPE.get(effective_cat, "temp_task"),
            }
        )
    return tasks, warnings


def parse_analysis_workbook(file_bytes: bytes) -> Dict:
    """解析 Excel 为预览数据，不落库。返回 analysis_fields / legacy_tasks / warnings。"""
    warnings: List[str] = []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as e:
        raise ValueError(f"无法读取 Excel 文件（可能不是 xlsx 或损坏）：{e}")
    ws = wb.worksheets[0]
    fields = _parse_analysis_fields(ws)
    legacy, legacy_warnings = _parse_legacy_tasks(ws)
    warnings.extend(legacy_warnings)
    if not fields.get("topic_name"):
        warnings.append("未识别到「课题名称」，将使用兜底标题，可手工修正")
    warnings.extend(_missing_field_warnings(fields))
    preview = []
    for i, t in enumerate(legacy):
        preview.append(
            {
                "idx": i,
                "handler_raw": t["handler_raw"],
                "handlers": t["handlers"],
                "content": t["content"],
                "due_date": t["due_date"],
                "suggest_category": t["suggest_category"],
                "suggest_issue_type": t["suggest_issue_type"],
            }
        )
    return {
        "analysis_fields": fields,
        "legacy_tasks": preview,
        "warnings": warnings,
    }


def import_analysis_workbook(
    db: Session,
    file_bytes: bytes,
    legacy_tasks: Optional[List[Dict]] = None,
    source_filename: Optional[str] = None,
) -> Dict:
    """解析 Excel 并落库。

    legacy_tasks 为确认后的遗留任务列表（每项含 content/handlers/category/issue_type/due_date）；
    为空则按默认（task/temp_task）解析，兼容旧一键导入兜底。
    source_filename 为原上传文件名，非空时自动保存为工单附件。
    """
    import json as _json
    import os as _os

    warnings: List[str] = []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as e:
        raise ValueError(f"无法读取 Excel 文件（可能不是 xlsx 或损坏）：{e}")
    ws = wb.worksheets[0]
    fields = _parse_analysis_fields(ws)
    warnings.extend(_missing_field_warnings(fields))

    topic = fields.get("topic_name") or "未命名分析工单（导入）"
    issue_no = _gen_no("ANA")
    issue = PmwbOperationIssue(
        issue_no=issue_no,
        title=topic,
        category="prod",
        issue_type="topic_analysis",
        status="pending",
        source="analysis_import",
        handler=(fields.get("analyst_name") or fields.get("analyst_team") or ""),
        domain_code=fields.get("domain_code") or None,
        go_live_date=_parse_date(fields.get("go_live_date")),
    )
    db.add(issue)
    db.flush()

    detail = PmwbOperationAnalysis(
        issue_id=issue.id,
        topic_name=fields.get("topic_name") or None,
        analyst_team=fields.get("analyst_team") or None,
        analyst_name=fields.get("analyst_name") or None,
        domain_code=fields.get("domain_code") or None,
        background=fields.get("background") or None,
        scenario=fields.get("scenario") or None,
        biz_flow=fields.get("biz_flow") or None,
        biz_rule=fields.get("biz_rule") or None,
        monitoring=fields.get("monitoring") or None,
        analysis_goal=fields.get("analysis_goal") or None,
        data_analysis=fields.get("data_analysis") or None,
        result_flow=fields.get("result_flow") or None,
        result_rule=fields.get("result_rule") or None,
        result_model=fields.get("result_model") or None,
        result_abnormal_user=fields.get("result_abnormal_user") or None,
        result_monitor_blind=fields.get("result_monitor_blind") or None,
    )
    db.add(detail)
    db.flush()

    # 自动保存源文件为工单附件（若传入了文件名）
    saved_attachment = None
    if source_filename and file_bytes:
        try:
            from routers.operation import UPLOAD_ROOT, _issue_folder
            folder = _issue_folder(issue.id)
            safe_name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", source_filename)
            fp = _os.path.join(folder, safe_name)
            with open(fp, "wb") as f:
                f.write(file_bytes)
            from routers.operation import _parse_attachments, _human_size
            atts = _parse_attachments(issue)
            atts.append({
                "name": safe_name,
                "bytes": len(file_bytes),
                "size": _human_size(len(file_bytes)),
            })
            issue.attachments = _json.dumps(atts, ensure_ascii=False)
            saved_attachment = safe_name
        except Exception as e:  # noqa: BLE001
            warnings.append(f"自动保存附件失败（非阻塞）：{e}")

    if legacy_tasks:
        raw_list = legacy_tasks
        source = "analysis_legacy_confirm"
    else:
        raw, lw = _parse_legacy_tasks(ws)
        warnings.extend(lw)
        raw_list = []
        for t in raw:
            raw_list.append(
                {
                    "content": t["content"],
                    "handlers": t["handlers"],
                    "category": "task",
                    "issue_type": "temp_task",
                    "due_date": t["due_date"],
                }
            )

    unmatched: List[str] = []
    created_tasks = 0
    for item in raw_list:
        content = (item.get("content") or "").strip()
        handlers = item.get("handlers") or []
        if not content and not handlers:
            continue
        category = item.get("category") or "task"
        if category not in VALID_CATEGORIES:
            category = "task"
        issue_type = item.get("issue_type") or CATEGORY_DEFAULT_TYPE.get(category, "temp_task")
        resolved = []
        for h in handlers:
            sid = resolve_staff_id(h)
            if sid is None:
                unmatched.append(h)
            resolved.append(h)
        handler_str = ",".join(resolved)
        due = None
        dd = item.get("due_date")
        if dd:
            due = _parse_date(dd)
            if due is None:
                warnings.append(f"任务「{content}」计划完成时间无法识别（{dd}），已置空")
        task = PmwbOperationIssue(
            issue_no=_gen_no("TASK"),
            title=content or f"[待补]{(handler_str or '未命名')}",
            category=category,
            issue_type=issue_type,
            status="pending",
            source=source if legacy_tasks else "analysis_legacy",
            handler=handler_str,
            impact_level="P2",
            go_live_date=due,
            related_req_id=issue_no,
        )
        db.add(task)
        created_tasks += 1

    db.commit()
    db.refresh(issue)
    return {
        "issue_no": issue_no,
        "analysis_id": detail.id,
        "topic_name": topic,
        "legacy_task_count": created_tasks,
        "unmatched_handlers": unmatched,
        "warnings": warnings,
        "saved_attachment": saved_attachment,
    }


def get_analysis_detail(db: Session, issue_id: int) -> Dict:
    """取分析工单明细 + 关联遗留任务工单（不限类别），供前端详情展示。"""
    issue = operation_issue_service.get(db, issue_id)
    if not issue:
        return {"issue": None, "analysis": None, "legacy_tasks": []}
    detail = (
        db.query(PmwbOperationAnalysis)
        .filter(PmwbOperationAnalysis.issue_id == issue_id)
        .first()
    )
    legacy_tasks = (
        db.query(PmwbOperationIssue)
        .filter(PmwbOperationIssue.related_req_id == issue.issue_no)
        .order_by(PmwbOperationIssue.id)
        .all()
    )
    return {"issue": issue, "analysis": detail, "legacy_tasks": legacy_tasks}
