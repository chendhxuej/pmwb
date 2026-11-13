# -*- coding: utf-8 -*-
"""客诉历史工单「是否都已重新归类」只读覆盖率核查。

只读! 不写任何表。输出 data/complaint_history_coverage.json 供报告使用。
用法: cd backend && venv/Scripts/python.exe ../scripts/complaint_history_coverage_audit.py
"""
import json
import os
import sys
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/backend")
from db.base import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data", "complaint_history_coverage.json")


def dec(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    from decimal import Decimal
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, (bytes, bytearray)):
        return v.decode("utf-8", "replace")
    return v


def rows(db, sql, params=None):
    r = db.execute(text(sql), params or {})
    return [dict((k, dec(v)) for k, v in zip(r.keys(), row)) for row in r.fetchall()]


def one(db, sql, params=None):
    r = rows(db, sql, params)
    return r[0] if r else {}


def dist(db, sql):
    return [{"k": dec(x["k"]), "n": x["n"]} for x in rows(db, sql)]


def main():
    db = SessionLocal()
    try:
        db.get_bind().echo = False
    except Exception:
        pass
    d = {"checked_at": datetime.now().isoformat(timespec="seconds")}

    tables = ["pmwb_complaint_ticket", "pmwb_complaint_problem_point",
              "pmwb_complaint_problem_gate", "pmwb_complaint_problem_class",
              "pmwb_complaint_ticket_module", "pmwb_complaint_module_problem",
              "pmwb_complaint_rootcause", "pmwb_complaint_problem",
              "pmwb_complaint_action", "pmwb_complaint_problem_run",
              "pmwb_complaint_problem_goldset"]
    d["tables"] = {}
    for t in tables:
        try:
            d["tables"][t] = one(db, "SELECT COUNT(*) AS n FROM " + t)["n"]
        except Exception as e:
            d["tables"][t] = "ERR:" + str(e)[:60]

    # 1. 工单主表总体
    d["ticket_total"] = one(db, "SELECT COUNT(*) n FROM pmwb_complaint_ticket")["n"]
    d["ticket_time"] = one(db, """SELECT MIN(created_time) first_t, MAX(created_time) last_t,
                                  COUNT(DISTINCT week) weeks FROM pmwb_complaint_ticket""")
    d["ticket_by_batch"] = dist(db, """SELECT COALESCE(import_batch,'(空)') k, COUNT(*) n
                                       FROM pmwb_complaint_ticket GROUP BY 1 ORDER BY n DESC""")

    # 2. 四条链路覆盖（以主表工单为分母）
    d["coverage"] = one(db, """SELECT
        COUNT(*) total,
        SUM(pp.ticket_no IS NOT NULL) has_point,
        SUM(tm.ticket_no IS NOT NULL) has_module,
        SUM(t.root_cause IS NOT NULL AND t.root_cause<>'') has_root_cause,
        SUM(t.rootcause_no IS NOT NULL AND t.rootcause_no<>'') has_rootcause_no,
        SUM(t.problem_no IS NOT NULL AND t.problem_no<>'') has_problem_no_old,
        SUM(t.known_flag IS NOT NULL) has_known_eval,
        SUM(t.category_l2 IS NOT NULL AND t.category_l2<>'') has_category_l2
        FROM pmwb_complaint_ticket t
        LEFT JOIN (SELECT DISTINCT ticket_no FROM pmwb_complaint_problem_point) pp
               ON pp.ticket_no=t.ticket_no
        LEFT JOIN (SELECT DISTINCT ticket_no FROM pmwb_complaint_ticket_module) tm
               ON tm.ticket_no=t.ticket_no""")

    # 3. 模块归类表孤儿 / 未归类 / 多标签
    d["module_orphan"] = one(db, """SELECT COUNT(*) n FROM pmwb_complaint_ticket_module m
                                    LEFT JOIN pmwb_complaint_ticket t ON t.ticket_no=m.ticket_no
                                    WHERE t.ticket_no IS NULL""")["n"]
    d["module_distinct_tickets"] = one(
        db, "SELECT COUNT(DISTINCT ticket_no) n FROM pmwb_complaint_ticket_module")["n"]
    d["module_multi_label"] = one(db, """SELECT COUNT(*) n FROM
        (SELECT ticket_no FROM pmwb_complaint_ticket_module
         GROUP BY ticket_no HAVING COUNT(*)>1) x""")["n"]
    d["module_by_review"] = dist(db, """SELECT COALESCE(review_status,'(空)') k, COUNT(*) n
                                        FROM pmwb_complaint_ticket_module GROUP BY 1 ORDER BY n DESC""")
    d["module_by_policy"] = dist(db, """SELECT COALESCE(policy_version,'(空)') k, COUNT(*) n
                                        FROM pmwb_complaint_ticket_module GROUP BY 1 ORDER BY n DESC""")
    d["module_unclassified"] = one(db, """SELECT COUNT(*) n FROM pmwb_complaint_ticket_module
        WHERE module_problem_id IS NULL OR module_problem_id='' """)["n"]
    d["module_suggested"] = one(db, """SELECT COUNT(*) n FROM pmwb_complaint_ticket_module
        WHERE (module_problem_id IS NULL OR module_problem_id='')
          AND suggested_id IS NOT NULL AND suggested_id<>'' """)["n"]
    d["module_top"] = dist(db, """SELECT COALESCE(module_problem_id,'(未归类)') k, COUNT(*) n
                                  FROM pmwb_complaint_ticket_module GROUP BY 1 ORDER BY n DESC LIMIT 25""")

    # 4. 问题点 / 根因 / 已知判定状态分布
    d["point_by_status"] = dist(db, """SELECT COALESCE(status,'(空)') k, COUNT(*) n
                                       FROM pmwb_complaint_problem_point GROUP BY 1 ORDER BY n DESC""")
    d["point_by_policy"] = dist(db, """SELECT COALESCE(policy_version,'(空)') k, COUNT(*) n
                                       FROM pmwb_complaint_problem_point GROUP BY 1 ORDER BY n DESC""")
    d["point_by_channel"] = dist(db, """SELECT COALESCE(generator_channel,'(空)') k, COUNT(*) n
                                        FROM pmwb_complaint_problem_point GROUP BY 1 ORDER BY n DESC""")
    d["rc_by_status"] = dist(db, """SELECT COALESCE(rc_status,'(空)') k, COUNT(*) n
                                    FROM pmwb_complaint_ticket GROUP BY 1 ORDER BY n DESC""")
    d["known_by_flag"] = dist(db, """SELECT COALESCE(CAST(known_flag AS CHAR),'(空)') k, COUNT(*) n
                                     FROM pmwb_complaint_ticket GROUP BY 1 ORDER BY n DESC""")

    # 5. 台账与措施
    d["problem_by_status"] = dist(db, """SELECT COALESCE(status,'(空)') k, COUNT(*) n
                                         FROM pmwb_complaint_problem GROUP BY 1 ORDER BY n DESC""")
    d["problem_by_source"] = dist(db, """SELECT COALESCE(source_type,'(空)') k, COUNT(*) n
                                         FROM pmwb_complaint_problem GROUP BY 1 ORDER BY n DESC""")
    d["problem_anchor"] = one(db, """SELECT COUNT(*) total,
        SUM(rootcause_no IS NOT NULL AND rootcause_no<>'') has_rc_no,
        SUM(module_problem_id IS NOT NULL AND module_problem_id<>'') has_mp_id,
        SUM(rootcause_nos IS NOT NULL AND rootcause_nos<>'') has_rc_nos
        FROM pmwb_complaint_problem""")
    d["action_cols"] = [c[0] for c in db.execute(
        text("SHOW COLUMNS FROM pmwb_complaint_action")).fetchall()]
    d["action_rows"] = rows(db, "SELECT * FROM pmwb_complaint_action ORDER BY 1")
    d["problem_run"] = rows(db, "SELECT * FROM pmwb_complaint_problem_run ORDER BY 1")

    # 6. 台账问题 ↔ 措施覆盖（用实际外键列名）
    acols = d["action_cols"]
    if "problem_no" in acols:
        d["problem_with_action"] = one(db, """SELECT
            (SELECT COUNT(*) FROM pmwb_complaint_problem) problems,
            (SELECT COUNT(DISTINCT problem_no) FROM pmwb_complaint_action) with_action,
            (SELECT COUNT(*) FROM pmwb_complaint_action) actions""")

    # 7. 本轮重发布痕迹（版本/时间）
    d["mp_by_version"] = dist(db, """SELECT CONCAT('v',COALESCE(version,'?'),'/p',COALESCE(policy_version,'?')) k,
                                     COUNT(*) n FROM pmwb_complaint_module_problem GROUP BY 1""")
    d["mp_updated"] = one(db, """SELECT MIN(updated_at) first_u, MAX(updated_at) last_u
                                 FROM pmwb_complaint_module_problem""")
    d["tm_updated"] = one(db, """SELECT MIN(updated_at) first_u, MAX(updated_at) last_u
                                 FROM pmwb_complaint_ticket_module""")
    d["point_updated"] = one(db, """SELECT MIN(updated_at) first_u, MAX(updated_at) last_u
                                    FROM pmwb_complaint_problem_point""")

    # 8. 「占位归类」按导入批次交叉定位（哪批历史没跑全链）
    d["by_batch_point"] = rows(db, """SELECT COALESCE(t.import_batch,'(空)') batch,
        COUNT(*) total,
        SUM(CASE WHEN pp.status='ok' THEN 1 ELSE 0 END) point_ok,
        SUM(CASE WHEN pp.status='unclassified' THEN 1 ELSE 0 END) point_unclassified,
        SUM(CASE WHEN pp.status='pending_auto_rerun' THEN 1 ELSE 0 END) point_pending,
        SUM(CASE WHEN tm.review_status='unclassified' THEN 1 ELSE 0 END) module_unclassified,
        SUM(CASE WHEN t.rc_status='insufficient' THEN 1 ELSE 0 END) rc_insufficient,
        SUM(CASE WHEN t.known_flag IS NULL THEN 1 ELSE 0 END) known_unevaluated
        FROM pmwb_complaint_ticket t
        LEFT JOIN pmwb_complaint_problem_point pp ON pp.ticket_no=t.ticket_no
        LEFT JOIN pmwb_complaint_ticket_module tm ON tm.ticket_no=t.ticket_no
        GROUP BY 1 ORDER BY total DESC""")
    d["by_batch_week"] = rows(db, """SELECT COALESCE(t.week,'(空)') week, COUNT(*) total,
        SUM(CASE WHEN pp.status='unclassified' THEN 1 ELSE 0 END) point_unclassified,
        SUM(CASE WHEN t.known_flag IS NULL THEN 1 ELSE 0 END) known_unevaluated
        FROM pmwb_complaint_ticket t
        LEFT JOIN pmwb_complaint_problem_point pp ON pp.ticket_no=t.ticket_no
        GROUP BY 1 ORDER BY 1""")

    # 9. 关联表探查：措施挂的 issue_no 指向哪张表 / 有无 problem_no 外键
    d["related_tables"] = [r[0] for r in db.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE() "
        "AND (table_name LIKE '%issue%' OR table_name LIKE '%dev_ticket%' "
        "OR table_name LIKE '%action%' OR table_name LIKE '%goldset%')")).fetchall()]
    d["goldset_cols"] = [c[0] for c in db.execute(
        text("SHOW COLUMNS FROM pmwb_complaint_problem_goldset")).fetchall()]
    d["goldset_sample"] = rows(db, "SELECT * FROM pmwb_complaint_problem_goldset LIMIT 3")
    d["gate_cols"] = [c[0] for c in db.execute(
        text("SHOW COLUMNS FROM pmwb_complaint_problem_gate")).fetchall()]
    d["gate_by_status"] = dist(db, """SELECT COALESCE(status,'(空)') k, COUNT(*) n
                                      FROM pmwb_complaint_problem_gate GROUP BY 1 ORDER BY n DESC""")
    d["action_anchor"] = one(db, """SELECT COUNT(*) total,
        SUM(rootcause_nos IS NOT NULL AND rootcause_nos<>'') has_rc_anchor,
        SUM(issue_no IS NOT NULL AND issue_no<>'') has_issue_no,
        SUM(req_id IS NOT NULL) has_req_id,
        SUM(problem_no IS NOT NULL) has_problem_no
        FROM pmwb_complaint_action""") if "problem_no" in acols else one(
        db, """SELECT COUNT(*) total,
        SUM(rootcause_nos IS NOT NULL AND rootcause_nos<>'') has_rc_anchor,
        SUM(issue_no IS NOT NULL AND issue_no<>'') has_issue_no,
        SUM(req_id IS NOT NULL) has_req_id
        FROM pmwb_complaint_action""")
    # 措施状态分布
    d["action_by_status"] = dist(db, """SELECT COALESCE(status,'(空)') k, COUNT(*) n
                                        FROM pmwb_complaint_action GROUP BY 1 ORDER BY n DESC""")
    # 在册台账（排除 merged/ignored）与措施锚点匹配
    d["live_problem"] = one(db, """SELECT COUNT(*) n FROM pmwb_complaint_problem
        WHERE status NOT IN ('merged','ignored')""")["n"]
    d["live_problem_detail"] = rows(db, """SELECT problem_no, title, status, source_type,
        module_problem_id, rootcause_no, rootcause_nos, week_cnt, total_cnt, owner
        FROM pmwb_complaint_problem WHERE status NOT IN ('merged','ignored')
        ORDER BY problem_no""")

    # 10. 台账旧斜杠标题 vs 当前标准名（展示遗留项，逐行对照）
    d["ledger_title_compare"] = rows(db, """SELECT p.problem_no, p.title, p.status,
        p.module_problem_id, m.name std_name, p.total_cnt
        FROM pmwb_complaint_problem p
        LEFT JOIN pmwb_complaint_module_problem m
               ON m.module_problem_id = p.module_problem_id
        WHERE p.status NOT IN ('merged','ignored') ORDER BY p.problem_no""")
    d["ledger_fuzzy_cnt"] = sum(
        1 for x in d["ledger_title_compare"] if "/" in (x["title"] or ""))
    d["ledger_empty_cnt"] = sum(
        1 for x in d["ledger_title_compare"] if not (x["total_cnt"] or 0))

    # 11. 措施关联覆盖
    d["problem_action_link"] = one(db, """SELECT COUNT(*) links,
        COUNT(DISTINCT problem_no) problems,
        COUNT(DISTINCT action_no) actions,
        SUM(is_primary=1) primary_links
        FROM pmwb_complaint_problem_action""")
    d["live_with_action"] = one(db, """SELECT COUNT(*) n FROM pmwb_complaint_problem p
        WHERE p.status NOT IN ('merged','ignored')
          AND EXISTS (SELECT 1 FROM pmwb_complaint_problem_action l
                      WHERE l.problem_no=p.problem_no)""")["n"]
    d["action_without_link"] = one(db, """SELECT COUNT(*) n FROM pmwb_complaint_action a
        WHERE NOT EXISTS (SELECT 1 FROM pmwb_complaint_problem_action l
                          WHERE l.action_no=a.action_no)""")["n"]
    d["action_issue_match"] = one(db, """SELECT COUNT(*) total,
        SUM(EXISTS(SELECT 1 FROM pmwb_operation_issue i WHERE i.issue_no=a.issue_no)) matched
        FROM pmwb_complaint_action a""")
    d["action_baseline"] = one(db, """SELECT COUNT(*) total,
        SUM(baseline_cnt IS NOT NULL) has_baseline,
        SUM(go_live_date IS NOT NULL) has_go_live,
        SUM(actual_drop_pct IS NOT NULL) has_effect
        FROM pmwb_complaint_action""")

    db.close()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    # 控制台摘要
    def p(k, v):
        print("%-28s %s" % (k, json.dumps(d.get(k, "(未采集)"), ensure_ascii=False)))

    print("=== 表行数 ===")
    for k, v in d["tables"].items():
        print("%-28s %s" % (k, json.dumps(v, ensure_ascii=False)))
    print("=== 主表 ===")
    p("ticket_total", d["ticket_total"])
    p("ticket_time", d["ticket_time"])
    print("=== 四链覆盖（分母=主表工单） ===")
    p("coverage", d["coverage"])
    print("=== 模块归类表 ===")
    for k in ["module_orphan", "module_distinct_tickets", "module_multi_label",
              "module_unclassified", "module_suggested", "module_by_review", "module_by_policy"]:
        p(k, d[k])
    print("=== 状态分布 ===")
    for k in ["point_by_status", "point_by_policy", "rc_by_status", "known_by_flag"]:
        p(k, d[k])
    print("=== 台账/措施 ===")
    for k in ["problem_by_status", "problem_by_source", "problem_anchor", "action_cols",
              "action_rows", "problem_with_action", "problem_run", "action_anchor",
              "action_by_status", "live_problem", "live_problem_detail", "related_tables"]:
        p(k, None)
    print("=== 台账旧名 / 措施关联 ===")
    for k in ["ledger_fuzzy_cnt", "ledger_empty_cnt", "ledger_title_compare",
              "problem_action_link", "live_with_action", "action_without_link",
              "action_issue_match", "action_baseline"]:
        p(k, None)
    print("=== 批次交叉（定位漏跑） ===")
    for k in ["by_batch_point", "by_batch_week"]:
        p(k, None)
    print("=== 金标/闸门 ===")
    for k in ["goldset_cols", "goldset_sample", "gate_cols", "gate_by_status"]:
        p(k, None)
    print("=== 重发布痕迹 ===")
    for k in ["mp_by_version", "mp_updated", "tm_updated", "point_updated"]:
        p(k, None)
    print("OUT", OUT)


if __name__ == "__main__":
    main()
