# -*- coding: utf-8 -*-
"""把 diff.json 渲染成 markdown 报告（只做渲染，不含任何解析/判定逻辑）。

用法：python gen_report.py [diff.json] [输出.md]
默认读 import_plan.py 产出的 diff.json，输出 dryrun-YYYY-MM-DD.md。
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

ST = {
    "completed": "已完成",
    "in_progress": "进行中",
    "not_started": "未开始",
    "delayed": "已延期",
    "cancelled": "已作废",
}
KIND = {"month_plan": "月计划", "week_plan": "周计划", "todo": "成员待办"}


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "diff.json")
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "dryrun-%s.md" % time.strftime("%Y-%m-%d"))
    d = json.load(io.open(src, encoding="utf-8"))

    out = []
    w = out.append
    w("# 每人一件事 · 周反馈邮件 → 重点工作更新草案（dry-run）")
    w("")
    w(
        "生成时间：%s　｜　区间：%s → %s　｜　状态：**未写入数据库**"
        % (time.strftime("%Y-%m-%d %H:%M"), d.get("since", ""), d.get("until", ""))
    )
    w("")

    w("## 一、这批邮件从哪来")
    w("")
    w("| 日期 | 周次 | 专题 | 发件人 | 抓到条目 |")
    w("|---|---|---|---|---|")
    for m in d["mails"]:
        tot = sum((m.get("counts") or {}).values())
        w(
            "| %s | %s | %s | %s | %d 条 |"
            % (
                m["date"][:10],
                (m.get("week") or "").split("-")[-1],
                (m.get("kw_title") or "")[:16],
                (m.get("from") or "").split("@")[0],
                tot,
            )
        )
    w("")

    w("## 二、处理口径（5 条，唯一实现在 backend/services/keywork_mail_import.py）")
    w("")
    w("1. **周次按邮件发送日期算 ISO 周**，不信主题里的 W##（负责人常写错）。")
    w("2. **条目归类看正文标签**【月计划】/【周计划】，标了月计划但内容其实是周计划的自动回退按周计划处理。")
    w("3. **状态只认显式状态位**（待办的 `| 第2段`、计划的 `--` 之后、行尾括号），标题里的「完成」不算。")
    w("4. **状态只进不退**：已完成是终点，退不回进行中/未开始，这类条目只保留备注。")
    w("5. **新增前按归一化标题查重**；下周计划命中在途项只更状态、不新建。")
    w("")

    ch, ad, db = d["changes"], d["adds"], d["doubts"]
    sx = [x for x in ch if not x.get("note_only")]
    nx = [x for x in ch if x.get("note_only")]
    w("## 三、结论")
    w("")
    w("- 解析邮件 **%d 封**，抽出条目 **%d 条**"
      % (len(d["mails"]), sum(sum((m.get("counts") or {}).values()) for m in d["mails"])))
    w("- **状态变更 %d 条**（相似度 ≥0.82 自动判定）" % len(sx))
    w("- **备注更新 %d 条**（状态没变，但邮件给了进展说明）" % len(nx))
    w("- **拟新增 %d 条**（库里无对应同名条目）" % len(ad))
    w("- **存疑 %d 条**（相似度 0.6~0.82，需人工裁定）" % len(db))
    if d.get("duplicates"):
        w("- **查重跳过 %d 条**（系统已有同名）" % len(d["duplicates"]))
    w("")

    # 按专题分组（专题名来自 diff，不在此硬编码）
    order, names = [], {}
    for x in ch + ad + db:
        kw = x["kw"]
        if kw not in names:
            names[kw] = x.get("kw_title") or ("专题 %s" % kw)
            order.append(kw)
    for kw in sorted(order):
        cs = [x for x in sx if x["kw"] == kw]
        ns = [x for x in nx if x["kw"] == kw]
        as_ = [x for x in ad if x["kw"] == kw]
        ds = [x for x in db if x["kw"] == kw]
        w("## %s · %s" % (kw, names[kw]))
        w("")
        if cs:
            w("**状态变更 %d 条**" % len(cs))
            w("")
            w("| 现状 → 邮件口径 | 类型 | 系统条目 | 来源 | 提示 |")
            w("|---|---|---|---|---|")
            for x in cs:
                flag = " ⚠️回退被拦" if x.get("blocked_from") else ""
                hint = {"routine": "例行任务", "unfinished": "仍待办"}.get(x.get("hint") or "", "")
                w(
                    "| %s → **%s**%s | %s#%s | %s | %s | %s |"
                    % (
                        ST.get(x["sys_status"], x["sys_status"]),
                        ST.get(x["mail_status"], x["mail_status"]),
                        flag,
                        KIND.get(x["kind"], x["kind"]),
                        x["id"],
                        (x.get("sys_title") or "")[:44],
                        x.get("src") or "",
                        hint,
                    )
                )
            w("")
        if ns:
            w("**备注更新 %d 条**（只写进展说明，不改状态）" % len(ns))
            w("")
            w("| 类型 | 系统条目 | 邮件里的进展说明 | 来源 |")
            w("|---|---|---|---|")
            for x in ns:
                w("| %s#%s | %s | %s | %s |"
                  % (KIND.get(x["kind"], x["kind"]), x["id"],
                     (x.get("sys_title") or "")[:40], (x.get("note") or "")[:58], x.get("src") or ""))
            w("")
        if as_:
            w("**拟新增 %d 条**" % len(as_))
            w("")
            w("| 类型 | 归属 | 标题 | 负责人 | 初态 | 来源 |")
            w("|---|---|---|---|---|---|")
            for x in as_:
                per = {"month_plan": "月计划", "week_plan": "周计划"}.get(x["kind"], "待办池")
                per = "%s %s" % (per, x.get("period") or "")
                w("| %s | %s | %s | %s | %s | %s |"
                  % (KIND.get(x["kind"], x["kind"]), per, (x.get("title") or "")[:52],
                     x.get("assignee") or "—", ST.get(x["status"], x["status"]), x.get("src") or ""))
            w("")
        if ds:
            w("**存疑 %d 条（未自动判定，需人工裁定）**" % len(ds))
            w("")
            for x in ds:
                w("- %s#%s　系统：%s　←　邮件：%s（%s）　相似度 %s"
                  % (KIND.get(x["kind"], x["kind"]), x.get("sys_id"),
                     (x.get("sys_title") or "")[:40], (x.get("mail_title") or "")[:40],
                     ST.get(x.get("mail_status"), x.get("mail_status") or "无状态"), x.get("score")))
            w("")

    w("## 四、怎么落库")
    w("")
    w("打开「重点工作」页 → 工具栏「从邮件导入」→ 核对区间 → 逐条勾选 → 执行导入。")
    w("")
    w("计划类备注会追加到任务描述的 `[Wxx] 说明` 行；每封邮件原文写进 `weekly_feedback.raw_text`（source=email）。")
    w("")

    io.open(dst, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    print("written", dst, len(out), "lines")


if __name__ == "__main__":
    main()
