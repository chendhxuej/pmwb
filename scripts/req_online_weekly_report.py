# -*- coding: utf-8 -*-
"""
需求上线周报统计脚本（只读，供定时任务每周四 16:00 调用）
=============================================================
输出两块内容：
  一、近 5 天已上线需求（delivered_date >= 今天-5天 且已交付/关闭）
  二、预测下下周计划上线需求（开发中 status='dev' 且开发周期 > 15 天）

统计口径（与人工查询一致）：
  - 开发单号取 sent_emails.dev_ticket_no
  - dev 环节进入时间取 pmwb_requirement_stage_log stage='dev' 的 entered_at
  - 需求提出时间取 sent_emails MIN(propose_time)
  - 开发周期 = 今天 - max(dev进入时间, 提出时间) 的自然日，>15 天命中
  - 功能提炼素材：sent_emails.background / description / clarification
  - 数据库只读，凭据从 backend/.env 读取，不硬编码
"""
import pymysql
import os
import sys
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env(path):
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main():
    today = date.today()
    env = load_env(os.path.join(ROOT, "backend", ".env"))
    conn = pymysql.connect(
        host=env.get("DB_HOST", "127.0.0.1"),
        port=int(env.get("DB_PORT", "3306")),
        user=env.get("DB_USER", "root"),
        password=env.get("DB_PASSWORD", ""),
        database=env.get("DB_NAME", "yxtyg_db"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    cur = conn.cursor()

    # 开发单号
    dev_no = {}
    cur.execute("SELECT req_id, dev_ticket_no FROM sent_emails WHERE dev_ticket_no IS NOT NULL AND dev_ticket_no<>''")
    for r in cur.fetchall():
        dev_no.setdefault(r["req_id"], r["dev_ticket_no"])

    # dev 环节进入时间
    dev_stage = {}
    cur.execute("SELECT req_id, entered_at FROM pmwb_requirement_stage_log WHERE stage='dev'")
    for r in cur.fetchall():
        dev_stage.setdefault(r["req_id"], r["entered_at"])

    # 需求提出时间
    propose = {}
    cur.execute(
        "SELECT req_id, MIN(propose_time) p FROM sent_emails "
        "WHERE propose_time IS NOT NULL AND propose_time<>'' GROUP BY req_id"
    )
    for r in cur.fetchall():
        propose[r["req_id"]] = r["p"]

    # 澄清内容（去重，保留首条）
    clarify = {}
    cur.execute(
        "SELECT req_id, background, description, clarification FROM sent_emails "
        "WHERE background IS NOT NULL OR description IS NOT NULL OR clarification IS NOT NULL"
    )
    for r in cur.fetchall():
        if r["req_id"] not in clarify:
            clarify[r["req_id"]] = r

    d5 = today - timedelta(days=5)

    def parse_date(s):
        if not s:
            return None
        s = str(s)[:10]
        for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    # ---------- 一、近5天已上线 ----------
    cur.execute("""
        SELECT e.req_id, e.req_name, e.status, e.priority, e.version_required_date,
               e.delivered_date, e.system_name, e.sa_name, e.updated_at
        FROM pmwb_requirement_ext e
        WHERE (e.delivered_date IS NOT NULL AND e.delivered_date >= %s)
           OR (e.status='closed' AND e.updated_at >= %s)
        ORDER BY e.delivered_date DESC, e.updated_at DESC
    """, (d5, d5.strftime("%Y-%m-%d") + " 00:00:00"))
    delivered = cur.fetchall()
    # 过滤：delivered 未填、closed 但 delivered 填早期日期的（老数据被更新误入）剔除
    delivered = [r for r in delivered
                 if r["delivered_date"] is not None and r["delivered_date"] >= d5]

    # ---------- 二、开发中且开发周期>15天 ----------
    cur.execute("""
        SELECT e.req_id, e.req_name, e.status, e.priority, e.version_required_date,
               e.delivered_date, e.system_name, e.sa_name, e.updated_at
        FROM pmwb_requirement_ext e
        WHERE e.status='dev'
        ORDER BY e.version_required_date IS NULL, e.version_required_date, e.updated_at DESC
    """)
    dev_rows = cur.fetchall()

    forecast = []
    for r in dev_rows:
        req = r["req_id"]
        span = None
        st = dev_stage.get(req)
        if st:
            d = st.date() if hasattr(st, "date") else parse_date(st)
            if d:
                span = (today - d).days
        pt = propose.get(req)
        if pt:
            d = parse_date(pt)
            if d and (span is None or (today - d).days > span):
                span = (today - d).days
        if span is not None and span > 15:
            forecast.append((span, r))
    forecast.sort(key=lambda x: -x[0])

    conn.close()

    # ---------- 输出 ----------
    print(f"# 需求上线周报统计（统计日期：{today.isoformat()}）")
    print(f"\n## 一、近 {5} 天已上线需求（{len(delivered)} 条）")
    for i, r in enumerate(delivered, 1):
        dd = r["delivered_date"].strftime("%Y-%m-%d")
        c = clarify.get(r["req_id"]) or {}
        print(f"\n[{i}] {r['req_id']}")
        print(f"需求名称：{r['req_name']}")
        print(f"实际上线：{dd} | 状态：{r['status']} | 优先级：{r['priority']} | "
              f"系统：{r['system_name'] or '-'} | SA：{r['sa_name'] or '-'} | 开发单：{dev_no.get(r['req_id'], '-')}")
        bg = (c.get("background") or "").strip()
        ds = (c.get("description") or "").strip()
        cl = (c.get("clarification") or "").strip()
        print(f"背景：{bg[:500] if bg else '无'}")
        print(f"描述：{ds[:800] if ds else '无'}")
        print(f"澄清：{cl[:800] if cl else '无'}")

    print(f"\n## 二、预测下下周计划上线需求（开发中且开发周期>15 天，{len(forecast)} 条）")
    for i, (span, r) in enumerate(forecast, 1):
        vd = r["version_required_date"].strftime("%Y-%m-%d") if r["version_required_date"] else "未填"
        c = clarify.get(r["req_id"]) or {}
        print(f"\n[{i}] {r['req_id']}")
        print(f"需求名称：{r['req_name']}")
        print(f"开发周期：{span} 天 | 期望上线：{vd} | 状态：{r['status']} | 优先级：{r['priority']} | "
              f"系统：{r['system_name'] or '-'} | SA：{r['sa_name'] or '-'} | 开发单：{dev_no.get(r['req_id'], '-')}")
        bg = (c.get("background") or "").strip()
        ds = (c.get("description") or "").strip()
        cl = (c.get("clarification") or "").strip()
        print(f"背景：{bg[:500] if bg else '无'}")
        print(f"描述：{ds[:800] if ds else '无'}")
        print(f"澄清：{cl[:800] if cl else '无'}")

    print(f"\n# 统计口径说明")
    print("一：delivered_date >= 统计日-5 天的需求；二：status='dev' 且开发周期(dev进入或提出时间到今天)>15 天。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)