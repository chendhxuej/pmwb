#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""3210 统一邮件中心模板幂等同步脚本（T-A，2026-08-17）。

背景：PMWB 邮件统一治理第二阶段——将 SCENES 场景与 3210 模板打通。
本脚本职责：
  1. 幂等创建 7 个新模板（meeting_minutes / action_dispatch / action_supervise /
     supervise_urge / supervise_sync / task_center_notify / task_center_urge），
     按 type 查重：已存在则跳过（校验内容一致性并提示），不存在则 POST 创建。
  2. 校验现有 3 个模板变量匹配（meeting_notice / task_reminder / xqemail_reminder）。
  3. 对每个模板用示例变量做 render smoke，断言无 "{{" 残留（引擎不支持块级语法）。

约束（实测 3210 模板引擎）：
  - 仅支持 {{var}}（转义）/ {{{var}}}（原始 HTML）插值，禁止块级 helper。
  - 列表/条件由调用方格式化为字符串/HTML 后传入。

用法：
  python sync_email_templates.py            # 同步 + 校验 + smoke（默认全流程）
  python sync_email_templates.py --dry-run  # 只打印将执行的操作，不写 3210
  python sync_email_templates.py --check-only  # 只校验现有 3 模板 + smoke，不创建
  python sync_email_templates.py --sync-only   # 只同步创建，跳过 smoke
  python sync_email_templates.py --base-url http://localhost:3210  # 覆盖 3210 地址

依赖：仅标准库（urllib）。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Optional

BASE_URL = "http://localhost:3210"
TEMPLATES_API = "/api/templates"

# ---------------------------------------------------------------------------
# 7 个新建模板（内容严格按 docs/邮件场景模板设计方案.md §2.4-2.10）
# 注：supervise_urge / supervise_sync 设计文档原为 text+Markdown 表格，
#     实测 text 渲染后端包 pre-wrap 纯文本，Markdown 表格源码会原样展示，
#     故改为 HTML 表格（与 action_supervise 风格一致），预览更专业。
# ---------------------------------------------------------------------------
NEW_TEMPLATES: list[dict] = [
    {
        "type": "meeting_minutes",
        "name": "会议纪要",
        "subjectTemplate": "【会议纪要】{{meetingTitle}} ({{meetingDate}})",
        "bodyFormat": "html",
        "description": "PMWB 会议纪要分发（meeting_minutes）",
        "bodyTemplate": (
            '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;">'
            '<h2 style="color:#1a1a3e;">{{meetingTitle}}</h2>'
            '<p><strong>日期：</strong>{{meetingDate}}</p>'
            '<p><strong>参会人：</strong>{{attendees}}</p>'
            "<hr>"
            '<div>{{{content}}}</div>'
            "<h3>行动项</h3>"
            '<div>{{{actionItems}}}</div>'
            "</div>"
        ),
    },
    {
        "type": "action_dispatch",
        "name": "会议行动项派发",
        "subjectTemplate": "【任务派发】{{meetingTitle}}",
        "bodyFormat": "html",
        "description": "PMWB 会议行动项派发（action_dispatch）",
        "bodyTemplate": (
            '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;">'
            '<h2 style="color:#1a1a3e;">会议行动项派发</h2>'
            "<p>以下行动项需要您跟进，请及时处理：</p>"
            '<div>{{{actions}}}</div>'
            "</div>"
        ),
    },
    {
        "type": "action_supervise",
        "name": "会议行动项督办",
        "subjectTemplate": "{{sceneLabel}}：{{content}}",
        "bodyFormat": "html",
        "description": "PMWB 会议行动项督办/同步（action_supervise）",
        "bodyTemplate": (
            '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;">'
            '<h2 style="color:#1a1a3e;">{{sceneLabel}}通知</h2>'
            "<p>以下会议行动项需要{{sceneLabel}}，详情如下：</p>"
            '<table style="border-collapse:collapse;width:100%;font-size:14px;">'
            '<tr><td style="padding:6px;border:1px solid #ddd;width:100px;"><strong>行动项</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{content}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>负责人</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{owner}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>截止日期</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{dueDate}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>当前状态</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{status}}</td></tr>'
            "</table>"
            "<p>请及时处理并反馈进展，辛苦了！</p>"
            "</div>"
        ),
    },
    {
        "type": "supervise_urge",
        "name": "工单催办",
        "subjectTemplate": "催办：{{title}}",
        "bodyFormat": "html",
        "description": "PMWB 运营工单催办（supervise_urge）",
        "bodyTemplate": (
            '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;">'
            '<h2 style="color:#1a1a3e;">催办通知</h2>'
            '<table style="border-collapse:collapse;width:100%;font-size:14px;">'
            '<tr><td style="padding:6px;border:1px solid #ddd;width:100px;"><strong>工单编号</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{no}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>标题</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{title}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>类型</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{category}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>处理人</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{handler}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>计划完成日期</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{resolveDate}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>当前状态</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{status}}</td></tr>'
            "</table>"
            "<h3>问题描述</h3>"
            '<div>{{{description}}}</div>'
            "<hr>"
            "<p>请尽快处理该工单，如有疑问请及时沟通。</p>"
            "</div>"
        ),
    },
    {
        "type": "supervise_sync",
        "name": "工单进展同步",
        "subjectTemplate": "同步：{{title}}",
        "bodyFormat": "html",
        "description": "PMWB 运营工单进展同步（supervise_sync）",
        "bodyTemplate": (
            '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;">'
            '<h2 style="color:#1a1a3e;">工单进展同步</h2>'
            '<table style="border-collapse:collapse;width:100%;font-size:14px;">'
            '<tr><td style="padding:6px;border:1px solid #ddd;width:100px;"><strong>工单编号</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{no}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>标题</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{title}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>类型</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{category}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>处理人</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{handler}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>计划完成日期</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{resolveDate}}</td></tr>'
            '<tr><td style="padding:6px;border:1px solid #ddd;"><strong>当前状态</strong></td>'
            '<td style="padding:6px;border:1px solid #ddd;">{{status}}</td></tr>'
            "</table>"
            '<div>{{{description}}}</div>'
            "<hr>"
            "<p>请知悉该工单最新进展。</p>"
            "</div>"
        ),
    },
    {
        "type": "task_center_notify",
        "name": "任务同步通知",
        "subjectTemplate": "任务同步通知",
        "bodyFormat": "html",
        "description": "PMWB 任务中心同步（task_center_notify）",
        "bodyTemplate": (
            '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;">'
            '<h2 style="color:#1a1a3e;">任务同步通知</h2>'
            "<p>同步以下任务的当前情况，请知悉。</p>"
            '<div>{{{tasks}}}</div>'
            "</div>"
        ),
    },
    {
        "type": "task_center_urge",
        "name": "任务催办提醒",
        "subjectTemplate": "任务催办提醒",
        "bodyFormat": "html",
        "description": "PMWB 任务中心催办（task_center_urge）",
        "bodyTemplate": (
            '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;">'
            '<h2 style="color:#1a1a3e;">任务催办提醒</h2>'
            "<p>以下任务已到跟进节点，麻烦尽快处理并反馈进展，辛苦了！</p>"
            '<div>{{{tasks}}}</div>'
            "</div>"
        ),
    },
]

# ---------------------------------------------------------------------------
# 现有 3 个模板校验（不修改，仅验证变量匹配 + smoke）
# ---------------------------------------------------------------------------
EXISTING_CHECKS: list[dict] = [
    {
        "type": "meeting_notice",
        "expect_vars": ["meetingTopic", "meetingTime", "meetingLocation", "host", "body"],
        "sample": {
            "meetingTopic": "一网通产品需求评审会",
            "meetingTime": "2026-08-17 14:00",
            "meetingLocation": "会议室A",
            "host": "陈大海",
            "body": "## 会议信息\n- **参会人**：张三、李四\n## 会议议题\n（待补充）",
        },
    },
    {
        "type": "task_reminder",
        "expect_vars": ["taskTitle", "assignee", "status", "planEnd"],
        "sample": {
            "taskTitle": "商客专区运营方案",
            "assignee": "张三",
            "status": "进行中",
            "planEnd": "2026-08-20",
        },
    },
    {
        "type": "xqemail_reminder",
        "expect_vars": ["reqId", "reqName", "saName", "proposeTime", "items"],
        "sample": {
            "reqId": "R001",
            "reqName": "一网通报价工具优化",
            "saName": "李四",
            "proposeTime": "2026-08-10",
            "items": "请尽快补充报价规则",
        },
    },
]

# 每个新模板的 smoke 示例变量（与模板变量一一对应）
SMOKE_SAMPLES: dict[str, dict] = {
    "meeting_minutes": {
        "meetingTitle": "商客专区智能化专题会",
        "meetingDate": "2026-08-17",
        "attendees": "陈大海、张三、李四",
        "content": "<p>讨论了商客专区智能化试点方案。</p>",
        "actionItems": '<ul><li>张三：输出报价规则 v2</li><li>李四：确认数据口径</li></ul>',
    },
    "action_dispatch": {
        "meetingTitle": "商客专区智能化专题会",
        "actions": '<ul><li><strong>张三</strong>：输出报价规则 v2（截止 08-20）</li>'
                   '<li><strong>李四</strong>：确认数据口径（截止 08-22）</li></ul>',
    },
    "action_supervise": {
        "sceneLabel": "催办",
        "content": "输出商客专区报价规则 v2",
        "owner": "张三",
        "dueDate": "2026-08-20",
        "status": "进行中",
        "body": "请尽快完成该行动项。",
    },
    "supervise_urge": {
        "no": "WO-2026-0817-001",
        "title": "一网通订单开通失败",
        "category": "订单开通",
        "handler": "王五",
        "resolveDate": "2026-08-18",
        "status": "处理中",
        "description": "<p>客户反馈订单开通失败，请尽快排查。</p>",
        "body": "请尽快处理该工单。",
    },
    "supervise_sync": {
        "no": "WO-2026-0817-001",
        "title": "一网通订单开通失败",
        "category": "订单开通",
        "handler": "王五",
        "resolveDate": "2026-08-18",
        "status": "已修复",
        "description": "<p>已完成网络侧配置修复，等待客户验证。</p>",
        "body": "同步工单最新进展。",
    },
    "task_center_notify": {
        "tasks": "<ul><li><strong>商客专区运营方案</strong>（进行中，截止 08-20）</li>"
                 "<li><strong>数据看板优化</strong>（已完成）</li></ul>",
        "sendType": "notify",
    },
    "task_center_urge": {
        "tasks": "<ul><li><strong>商客专区运营方案</strong>（进行中，已逾期）</li></ul>",
        "sendType": "urge",
    },
}


# ---------------------------------------------------------------------------
# HTTP 工具
# ---------------------------------------------------------------------------
def _request(method: str, url: str, payload: Optional[dict] = None, timeout: int = 15):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, {"error": raw[:300]}
    except Exception as e:  # noqa: BLE001
        return 0, {"error": str(e)}


def list_templates(base: str) -> list[dict]:
    code, data = _request("GET", base + TEMPLATES_API)
    if code != 200:
        raise RuntimeError(f"GET {TEMPLATES_API} 失败 ({code}): {data}")
    if isinstance(data, list):
        return data
    return data.get("items", data.get("templates", []))


def find_by_type(templates: list[dict], ttype: str) -> Optional[dict]:
    return next((t for t in templates if t.get("type") == ttype), None)


def create_template(base: str, tpl: dict) -> tuple[int, dict]:
    return _request("POST", base + TEMPLATES_API, tpl)


def render_template(base: str, tpl_id: str, variables: dict) -> tuple[int, dict]:
    return _request("POST", f"{base}{TEMPLATES_API}/{tpl_id}/render", {"variables": variables})


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="3210 邮件模板幂等同步（T-A）")
    parser.add_argument("--base-url", default=BASE_URL, help="3210 服务地址")
    parser.add_argument("--dry-run", action="store_true", help="只打印将执行的操作")
    parser.add_argument("--check-only", action="store_true", help="只校验现有模板 + smoke，不创建")
    parser.add_argument("--sync-only", action="store_true", help="只同步创建，跳过 smoke")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    errors: list[str] = []

    print(f"== 3210: {base} ==")
    try:
        existing = list_templates(base)
    except RuntimeError as e:
        print(f"[FATAL] 无法连接 3210: {e}")
        return 2
    existing_types = {t.get("type") for t in existing}
    print(f"现有模板 {len(existing)} 个: {sorted(existing_types)}")

    # ---- 1) 同步新建 7 个模板 ----
    if args.check_only:
        print("\n== [check-only] 跳过创建 ==")
    else:
        print("\n== 同步新建模板 ==")
        for tpl in NEW_TEMPLATES:
            ttype = tpl["type"]
            found = find_by_type(existing, ttype)
            if found:
                same = (
                    found.get("subjectTemplate") == tpl["subjectTemplate"]
                    and found.get("bodyTemplate") == tpl["bodyTemplate"]
                )
                status = "内容一致" if same else "内容不一致(需人工核对)"
                print(f"  [skip] {ttype}: 已存在，{status} (id={found.get('id')})")
                if not same:
                    errors.append(f"{ttype}: 已存在但内容不一致")
                continue
            if args.dry_run:
                print(f"  [dry-run] 将创建 {ttype}: {tpl['name']}")
                continue
            code, data = create_template(base, tpl)
            if code in (200, 201):
                print(f"  [created] {ttype}: {tpl['name']} (id={data.get('id') or data.get('data', {}).get('id')})")
            else:
                print(f"  [FAIL] {ttype}: HTTP {code} {data}")
                errors.append(f"{ttype}: 创建失败 HTTP {code}")

    if args.dry_run:
        print("\n== [dry-run] 校验 + smoke 也跳过 ==")
        return 0 if not errors else 1

    # ---- 2) 校验现有 3 个模板变量匹配 ----
    print("\n== 校验现有模板 ==")
    for chk in EXISTING_CHECKS:
        found = find_by_type(existing, chk["type"])
        if not found:
            print(f"  [FAIL] {chk['type']}: 3210 中不存在")
            errors.append(f"{chk['type']}: 模板缺失")
            continue
        tpl_body = found.get("bodyTemplate") or ""
        missing = []
        for v in chk["expect_vars"]:
            has_escaped = "{{" + v + "}}" in tpl_body
            has_raw = "{{{" + v + "}}}" in tpl_body
            if not has_escaped and not has_raw:
                missing.append(v)
        if missing:
            print(f"  [WARN] {chk['type']}: 模板缺少变量 {missing}")
        else:
            print(f"  [ok] {chk['type']}: 变量匹配 {chk['expect_vars']}")

    # ---- 3) smoke 渲染（新建 7 + 现有 3） ----
    if args.sync_only:
        print("\n== [sync-only] 跳过 smoke ==")
    else:
        print("\n== smoke 渲染 ==")
        smoke_targets = [(t["type"], SMOKE_SAMPLES[t["type"]]) for t in NEW_TEMPLATES]
        smoke_targets += [
            (chk["type"], chk["sample"])
            for chk in EXISTING_CHECKS
            if find_by_type(existing, chk["type"])
        ]
        all_templates = {t.get("type"): t for t in list_templates(base)}  # 重新拉取（含刚创建的）
        for ttype, sample in smoke_targets:
            tpl = all_templates.get(ttype)
            if not tpl:
                continue
            code, data = render_template(base, tpl["id"], sample)
            if code != 200:
                print(f"  [FAIL] {ttype}: render HTTP {code} {data}")
                errors.append(f"{ttype}: render 失败 HTTP {code}")
                continue
            subject = data.get("subject", "")
            body = data.get("body", "")
            leftover = body.count("{{") + subject.count("{{")
            if leftover:
                brace = "{{"
                print(f"  [FAIL] {ttype}: 渲染结果残留 {brace} x{leftover} → subject='{subject[:60]}' body='{body[:80]}...'")
                errors.append(f"{ttype}: 模板残留 {leftover} 个双花括号")
            else:
                print(f"  [ok] {ttype}: subject='{subject}' body_len={len(body)}")

    # ---- 汇总 ----
    print("\n" + "=" * 50)
    if errors:
        print(f"结果: FAIL ({len(errors)} 项问题)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("结果: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
