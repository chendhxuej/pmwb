"""客诉根因深化：工单表根因字段 + 根因库表

背景（2026-11-03 老大拍板「客诉专题优化」第三轮）：
  现状问题是「归类太泛、不能细化到真实问题描述」——30 个二级现象场景承载 228 单，
  最大桶 38 单混装 6 类不相关问题，AI 置信度 <0.85 占 71%。
  根因识别是后续批量投诉识别与解决方案制定的基础数据，故新增根因层（L1）+ 根因库（L2）：
    - pmwb_complaint_ticket 增加 10 列根因字段（root_cause / fault_* / own_party /
      fix_mode / repro / rc_status / rc_confidence / rc_evidence / rootcause_no）；
    - 新建 pmwb_complaint_rootcause 根因库（自下而上归纳、人工确认入库、命中复用）。

  幂等性：加列前探测 existing_columns，建表前探测 table_names，可安全重复执行。
  多 head 仓库：须显式 `alembic upgrade 20261103000003`。

revision: 20261103000003 / down_revision: 20261103000002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20261103000003"
down_revision: Union[str, None] = "20261103000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TICKET_TABLE = "pmwb_complaint_ticket"
RC_TABLE = "pmwb_complaint_rootcause"

# (列名, 类型, 注释)
_NEW_COLUMNS = [
    ("root_cause", sa.String(length=500), "一句话真实根因（含系统+环节+具体错误现象）"),
    ("fault_stage", sa.String(length=32), "故障环节"),
    ("fault_system", sa.String(length=64), "涉及系统"),
    ("fault_type", sa.String(length=32), "缺陷性质"),
    ("own_party", sa.String(length=32), "责任归属"),
    ("fix_mode", sa.String(length=32), "处置方式"),
    ("repro", sa.String(length=8), "可复现：yes/no/unknown"),
    ("rc_status", sa.String(length=16), "根因状态：空=待分析 / ai / low / manual"),
    ("rc_confidence", sa.Float(), "根因归纳置信度"),
    ("rc_evidence", sa.Text(), "根因原文依据"),
    ("rootcause_no", sa.String(length=64), "归属根因库编号"),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # ① 工单表加根因列
    if TICKET_TABLE in inspector.get_table_names():
        existing = {c["name"] for c in inspector.get_columns(TICKET_TABLE)}
        for name, type_, comment in _NEW_COLUMNS:
            if name in existing:
                continue
            op.add_column(TICKET_TABLE, sa.Column(name, type_, nullable=True, comment=comment))
        idx_names = {i["name"] for i in inspector.get_indexes(TICKET_TABLE)}
        if "idx_ct_rootcause" not in idx_names:
            op.create_index("idx_ct_rootcause", TICKET_TABLE, ["rootcause_no"])
        if "idx_ct_rc_status" not in idx_names:
            op.create_index("idx_ct_rc_status", TICKET_TABLE, ["rc_status"])

    # ② 根因库表
    if RC_TABLE not in inspector.get_table_names():
        op.create_table(
            RC_TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
            sa.Column("rootcause_no", sa.String(length=64), nullable=False, comment="根因编号"),
            sa.Column("title", sa.String(length=200), nullable=False, comment="根因标题"),
            sa.Column("description", sa.Text(), nullable=True, comment="簇定义与判定边界"),
            sa.Column("fault_stage", sa.String(length=32), nullable=True, comment="簇级故障环节"),
            sa.Column("fault_system", sa.String(length=64), nullable=True, comment="簇级涉及系统"),
            sa.Column("fault_type", sa.String(length=32), nullable=True, comment="簇级缺陷性质"),
            sa.Column("own_party", sa.String(length=32), nullable=True, comment="簇级责任归属"),
            sa.Column("fix_mode", sa.String(length=32), nullable=True, comment="簇级处置方式"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="candidate",
                      comment="candidate/open/merged/disabled"),
            sa.Column("source", sa.String(length=16), nullable=True, server_default="ai", comment="来源"),
            sa.Column("merged_to", sa.String(length=64), nullable=True, comment="被合并到的主簇编号"),
            sa.Column("ticket_cnt", sa.Integer(), nullable=False, server_default="0", comment="当前归属单量"),
            sa.Column("sample_tickets", sa.Text(), nullable=True, comment="代表工单号 JSON 数组"),
            sa.Column("first_week", sa.String(length=16), nullable=True, comment="首见自然周"),
            sa.Column("last_week", sa.String(length=16), nullable=True, comment="最近出现自然周"),
            sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("rootcause_no", name="uk_crc_no"),
            comment="客诉根因库（根因簇）",
        )
        op.create_index("idx_crc_status", RC_TABLE, ["status"])
        op.create_index("idx_crc_last_week", RC_TABLE, ["last_week"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if RC_TABLE in inspector.get_table_names():
        op.drop_table(RC_TABLE)
    if TICKET_TABLE in inspector.get_table_names():
        existing = {c["name"] for c in inspector.get_columns(TICKET_TABLE)}
        for name, _t, _c in reversed(_NEW_COLUMNS):
            if name in existing:
                op.drop_column(TICKET_TABLE, name)
