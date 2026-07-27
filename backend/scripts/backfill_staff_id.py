#!/usr/bin/env python
"""业务表 staff_id 回填脚本。

从人员中台（master service）拉取 name -> staff_id 映射，
遍历所有含人名字符串的业务表，回填 staff_id 列。

用法：
  python backfill_staff_id.py --dry-run    # 只出报告
  python backfill_staff_id.py --fix        # 正式写入

要求：人员中台服务（localhost:8001）已启动且数据已导入。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

# 添加 backend 路径
sys.path.insert(0, ".")
from db.base import SessionLocal

MASTER_URL = "http://localhost:8001/api/v1/basic-data"


def fetch_staff_map() -> Dict[str, int]:
    """从人员中台拉取 name -> staff_id 映射（只取第一个 enabled）。"""
    try:
        resp = httpx.get(f"{MASTER_URL}/staffs", timeout=10.0)
        resp.raise_for_status()
        body = resp.json()
        staffs = body.get("data", [])
    except Exception as e:
        print(f"[ERROR] 无法连接人员中台 {MASTER_URL}: {e}")
        print("请先启动人员中台服务并导入数据")
        sys.exit(1)

    name_map: Dict[str, int] = {}
    name_dupes: Dict[str, list] = defaultdict(list)

    for s in staffs:
        if not s.get("enabled", True):
            continue
        name = s["name"]
        name_dupes[name].append(s["id"])

    for name, ids in name_dupes.items():
        name_map[name] = ids[0]  # 同名多人默认取第一个

    print(f"[INFO] 人员映射: {len(name_map)} 个姓名 -> staff_id")
    return name_map


def backfill_table(
    db: Session,
    name_map: Dict[str, int],
    table: str,
    name_col: str,
    staff_col: str,
    dry_run: bool = False,
) -> Tuple[int, int, List[str]]:
    """回填单值字段。返回 (matched, unmatched, errors)。"""
    matched = 0
    unmatched = 0
    errors = []

    rows = db.execute(text(f"SELECT id, `{name_col}` FROM `{table}` WHERE `{name_col}` IS NOT NULL AND `{name_col}` != '' AND `{staff_col}` IS NULL")).fetchall()

    for row in rows:
        name = (row[1] or "").strip()
        sid = name_map.get(name)
        if sid:
            if not dry_run:
                db.execute(text(f"UPDATE `{table}` SET `{staff_col}` = :sid WHERE id = :id"), {"sid": sid, "id": row[0]})
            matched += 1
        else:
            unmatched += 1

    if not dry_run and matched > 0:
        db.commit()

    return matched, unmatched, errors


def backfill_json_array(
    db: Session,
    name_map: Dict[str, int],
    table: str,
    name_col: str,
    json_col: str,
    dry_run: bool = False,
) -> Tuple[int, int, List[str]]:
    """回填逗号分隔→JSON 数组字段。"""
    matched = 0
    total_rows = 0

    rows = db.execute(
        text(f"SELECT id, `{name_col}` FROM `{table}` WHERE `{name_col}` IS NOT NULL AND `{name_col}` != '' AND `{json_col}` IS NULL")
    ).fetchall()

    for row in rows:
        names_str = (row[1] or "").strip()
        names = [n.strip() for n in names_str.split(",") if n.strip()]
        ids = [name_map[n] for n in names if n in name_map]
        if ids:
            if not dry_run:
                db.execute(
                    text(f"UPDATE `{table}` SET `{json_col}` = :ids WHERE id = :id"),
                    {"ids": json.dumps(ids), "id": row[0]},
                )
            matched += len(ids)
        total_rows += 1

    if not dry_run and matched > 0:
        db.commit()

    return matched, 0, []


def main():
    parser = argparse.ArgumentParser(description="业务表 staff_id 回填")
    parser.add_argument("--dry-run", action="store_true", help="只生成报告，不写入")
    parser.add_argument("--fix", action="store_true", help="正式写入")
    args = parser.parse_args()

    if not args.dry_run and not args.fix:
        print("请指定 --dry-run 或 --fix")
        sys.exit(1)

    mode = "DRY-RUN" if args.dry_run else "WRITE"
    print(f"[INFO] 模式: {mode}")

    name_map = fetch_staff_map()
    if not name_map:
        print("[ERROR] 无人员映射数据")
        sys.exit(1)

    db = SessionLocal()

    # 单值字段回填配置
    single_fields = [
        ("pmwb_requirement_ext", "sa_name", "sa_staff_id"),
        ("pmwb_dev_ticket_log", "operator", "operator_staff_id"),
        ("pmwb_meeting", "host", "host_staff_id"),
        ("pmwb_meeting", "convener", "convener_staff_id"),
        ("pmwb_meeting", "recorder", "recorder_staff_id"),
        ("pmwb_meeting_attendee", "name", "staff_id"),
        ("pmwb_meeting_action", "owner", "owner_staff_id"),
        ("pmwb_requirement_evaluation", "proposer", "proposer_staff_id"),
        ("pmwb_requirement_evaluation", "sa_name", "sa_staff_id"),
        ("sent_emails", "proposer", "proposer_staff_id"),
        ("sent_emails", "sa_name", "sa_staff_id"),
        ("email_records", "sender", "sender_staff_id"),
        ("sa_info", "sa_name", "staff_id"),
        ("pmwb_key_work", "owner", "owner_staff_id"),
        ("pmwb_key_work_member", "name", "staff_id"),
        ("pmwb_key_work_progress", "reporter", "reporter_staff_id"),
        ("pmwb_key_work_member_task", "assignee", "assignee_staff_id"),
    ]

    # JSON 数组字段回填配置
    json_fields = [
        ("pmwb_operation_issue", "handler", "handler_staff_ids"),
        ("pmwb_meeting", "absentees", "absentee_staff_ids"),
    ]

    total_matched = 0
    total_unmatched = 0
    all_unmatched: List[Tuple[str, str, str]] = []

    print("\n=== 单值字段回填 ===")
    for table, name_col, staff_col in single_fields:
        try:
            matched, unmatched, errors = backfill_table(db, name_map, table, name_col, staff_col, dry_run=args.dry_run)
            total_matched += matched
            total_unmatched += unmatched
            if matched > 0 or unmatched > 0:
                print(f"  {table}.{staff_col}: matched={matched}, unmatched={unmatched}")
        except Exception as e:
            print(f"  {table}.{staff_col}: ERROR - {e}")

    print("\n=== JSON 数组字段回填 ===")
    for table, name_col, json_col in json_fields:
        try:
            matched, _, errors = backfill_json_array(db, name_map, table, name_col, json_col, dry_run=args.dry_run)
            total_matched += matched
            if matched > 0:
                print(f"  {table}.{json_col}: matched_ids={matched}")
        except Exception as e:
            print(f"  {table}.{json_col}: ERROR - {e}")

    db.close()

    print(f"\n=== 汇总 ===")
    print(f"  匹配: {total_matched}")
    print(f"  未匹配: {total_unmatched}")
    if args.dry_run:
        print("  (dry-run 模式，未实际写入)")
    else:
        print("  (已写入数据库)")


if __name__ == "__main__":
    main()
