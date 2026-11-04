"""客诉 v4.2 自动化分析链持久化（D5）

背景（2026-11-04 老大批准「工单分析过程不依赖人」）：
  D0~D4 是只读纯判定内核，没有落库、没有编排、没有自动补跑能力。本迁移补上
  编排链路所需的独立表，与旧「根因簇/问题台账」完全隔离（旧 236 个抽象名只作
  历史索引，不写入这里）。

五张表：
  - problem_point   逐单问题点（含 pending_auto_rerun 待自动补跑标记与缺口原因）
  - problem_class   问题点类 + 结构化判定卡（系统自动生成，机器可判）
  - problem_gate    每单 100% 自动门禁留痕 / 未归类清单（写明缺哪项证据）
  - problem_goldset 金标集（系统自动构建滚动扩充，无人工标注）
  - problem_run     每次运行的验收结果与发布闸门结论（不达标自动拦截）

⚠ 项目 alembic 多 head（坏壳 20260908105939 遗留），执行须显式指定：
  alembic upgrade 20261104000008
所有 SQL 走通用写法（SELECT 判定后 UPDATE/INSERT），不用 ON DUPLICATE KEY /
FIND_IN_SET / FIELD / NOW() 等 MySQL 专有语法——测试库是 SQLite。

Revision ID: 20261104000008
Revises: 20261104000007
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104000008"
down_revision = "20261104000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pmwb_complaint_problem_point",
        sa.Column("ticket_no", sa.String(64), primary_key=True, comment="工单号"),
        sa.Column("point", sa.String(500), comment="一句逐单投诉问题点"),
        sa.Column("status", sa.String(32), nullable=False, comment="ok / pending_auto_rerun / unclassified"),
        sa.Column("gaps_json", sa.Text, comment="缺口原因列表（自动判定，写明缺什么）"),
        sa.Column("evidence_json", sa.Text, comment="原文证据片段"),
        sa.Column("anchors_json", sa.Text, comment="问题点↔原文锚点映射"),
        sa.Column("old_record_conclusion", sa.Integer, nullable=False, server_default="0",
                  comment="存量逐单记录是否为结论式表述"),
        sa.Column("rewritten_from_conclusion", sa.Integer, nullable=False, server_default="0",
                  comment="是否已由系统回原文自动重写"),
        sa.Column("generator_channel", sa.String(64), comment="生成通道"),
        sa.Column("judge_channel", sa.String(64), comment="独立判定通道"),
        sa.Column("policy_version", sa.String(32), comment="口径版本"),
        sa.Column("updated_at", sa.DateTime, comment="判定时间"),
    )
    op.create_index("idx_cpp_status", "pmwb_complaint_problem_point", ["status"])

    op.create_table(
        "pmwb_complaint_problem_class",
        sa.Column("class_no", sa.String(64), primary_key=True, comment="问题点类编号"),
        sa.Column("description", sa.String(255), nullable=False, comment="一句具体投诉问题点"),
        sa.Column("elements_json", sa.Text, comment="四要素（对象/动作/失败/触发条件）"),
        sa.Column("card_json", sa.Text, comment="结构化判定卡（四项+正反例+边界+修复落点）"),
        sa.Column("fix_point", sa.String(255), comment="可指认修复落点"),
        sa.Column("ticket_cnt", sa.Integer, nullable=False, server_default="0", comment="成员工单数"),
        sa.Column("first_sight", sa.Integer, nullable=False, server_default="0", comment="首现类（1 单也立类）"),
        sa.Column("status", sa.String(32), nullable=False,
                  comment="published / draft / voided / blocked / changed（描述口径变更当期不可比）"),
        sa.Column("reasons_json", sa.Text, comment="未发布原因（自动判定）"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1",
                  comment="描述版本，口径变更时递增"),
        sa.Column("prev_description", sa.String(255), comment="上一版描述（§7.3 留痕）"),
        sa.Column("prev_card_json", sa.Text, comment="上一版判定卡（§7.3 留痕）"),
        sa.Column("policy_version", sa.String(32), comment="口径版本"),
        sa.Column("created_at", sa.DateTime, comment="建立时间/生效区间起点"),
        sa.Column("updated_at", sa.DateTime, comment="更新时间"),
    )
    op.create_index("idx_cpc_status", "pmwb_complaint_problem_class", ["status"])

    op.create_table(
        "pmwb_complaint_problem_gate",
        sa.Column("ticket_no", sa.String(64), primary_key=True, comment="工单号"),
        sa.Column("class_no", sa.String(64), comment="归入的问题点类（未归类为空）"),
        sa.Column("status", sa.String(32), nullable=False, comment="matched / matched_second / unclassified / pending_auto_rerun"),
        sa.Column("gaps_json", sa.Text, comment="未过闸原因 / 未归类缺口"),
        sa.Column("mapped_json", sa.Text, comment="描述→工单证据逐项映射"),
        sa.Column("missing_json", sa.Text, comment="未定位到的描述要素"),
        sa.Column("generator_channel", sa.String(64), comment="生成通道"),
        sa.Column("judge_channel", sa.String(64), comment="判定通道（与生成分离）"),
        sa.Column("second_channel", sa.String(64), comment="自动二次判定通道"),
        sa.Column("policy_version", sa.String(32), comment="口径版本"),
        sa.Column("updated_at", sa.DateTime, comment="判定时间"),
    )
    op.create_index("idx_cpg_status", "pmwb_complaint_problem_gate", ["status"])

    op.create_table(
        "pmwb_complaint_problem_goldset",
        sa.Column("ticket_no", sa.String(64), primary_key=True, comment="工单号"),
        sa.Column("source", sa.String(64), comment="纳入来源（core / new_class / leak / dispute）"),
        sa.Column("policy_version", sa.String(32), comment="口径版本"),
        sa.Column("added_at", sa.DateTime, comment="自动纳入时间"),
    )

    op.create_table(
        "pmwb_complaint_problem_run",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_no", sa.String(64), nullable=False, unique=True, comment="运行批次号"),
        sa.Column("dry_run", sa.Integer, nullable=False, server_default="1", comment="1=只读演练"),
        sa.Column("publish", sa.Integer, nullable=False, server_default="0", comment="1=验收闸门放行"),
        sa.Column("failed_json", sa.Text, comment="未达标项"),
        sa.Column("veto_json", sa.Text, comment="一票否决项"),
        sa.Column("metrics_json", sa.Text, comment="§5 全指标"),
        sa.Column("classes_cnt", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unclassified_cnt", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pending_cnt", sa.Integer, nullable=False, server_default="0"),
        sa.Column("channel_available", sa.Integer, nullable=False, server_default="0"),
        sa.Column("channel_notice", sa.String(500), comment="语义通道不可用原因"),
        sa.Column("policy_version", sa.String(32), comment="口径版本"),
        sa.Column("created_at", sa.DateTime, comment="运行时间"),
    )
    op.create_index("idx_cpr_created", "pmwb_complaint_problem_run", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_cpr_created", table_name="pmwb_complaint_problem_run")
    op.drop_table("pmwb_complaint_problem_run")
    op.drop_table("pmwb_complaint_problem_goldset")
    op.drop_index("idx_cpg_status", table_name="pmwb_complaint_problem_gate")
    op.drop_table("pmwb_complaint_problem_gate")
    op.drop_index("idx_cpc_status", table_name="pmwb_complaint_problem_class")
    op.drop_table("pmwb_complaint_problem_class")
    op.drop_index("idx_cpp_status", table_name="pmwb_complaint_problem_point")
    op.drop_table("pmwb_complaint_problem_point")
