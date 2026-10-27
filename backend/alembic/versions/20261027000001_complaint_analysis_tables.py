"""客诉工单专题分析体系：分类字典 + 工单明细 + 措施台账

背景（2026-10-27 老大拍板「每周客诉专题分析体系化，核心目标压降」）：
  前两次专题分析暴露三个硬伤——口径漂移（9 类 vs 4 类，无法周环比）、
  数据不留存（每次现读 Foxmail 临时附件，复发无法识别）、措施不闭环
  （10+ 条建议无责任人/期限/验收/跟进）。本迁移落三张表解决前两个，
  第三个由 pmwb_complaint_action 与 pmwb_operation_issue 父子关联解决。

设计要点：
  - pmwb_complaint_category：两级分类字典，唯一真相源，落库值为中文名（无 code，
    零转译，同 requirement_category 决策）；keywords 为该场景识别正则，
    由 scripts/complaint/classify.py 读取执行——改字典即改口径，脚本内不留第二份；
  - pmwb_complaint_ticket：逐单明细底座，ticket_no 唯一去重，week 按创建时间归属；
    承载分类结果、批量簇标识、复发标记与关联运营工单号；
  - pmwb_complaint_action：措施台账，不重复维护措施内容（以运营工单为准），
    只记录「针对哪个场景 + 基线单量 + 目标降幅 + 观察周数 + 实际降幅」，
    解决「措施做了没有、有没有用」的闭环盲区。

  幂等性：建表/建索引/种子均先探测，存在则跳过，可安全重复执行。
  注意：本仓库存在多个 alembic head（历史坏壳 20260908105939），
  应用本迁移须显式指定 revision id：
      alembic upgrade 20261027000001

Revision ID: 20261027000001
Revises: 20261026000001
Create Date: 2026-10-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20261027000001"
down_revision: Union[str, None] = "20261026000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CAT = "pmwb_complaint_category"
TICKET = "pmwb_complaint_ticket"
ACTION = "pmwb_complaint_action"

# ─────────────────────────────────────────────────────────────
# 预置分类字典（基于 2026-10 两次专题共 338 条真实工单归纳）
# 结构：(level, parent_name, name, keywords, sort_order, note)
# sort_order 全局唯一且决定匹配优先级：先具体场景（level=2），后笼统性质（level=1 兜底）
# ─────────────────────────────────────────────────────────────
PRESET_CATEGORIES = [
    # ── 一级：问题性质（7 类锁定；keywords 仅在二级全部未命中时兜底） ──
    (1, None, "计费与出账争议", r"出账|扣费|计费|账单|退费|资费|欠费|收费", 10,
     "费用类争议：多收、错收、已关仍扣、退费未到账"),
    (1, None, "营销与活动生效异常", r"营销案|活动|订购|生效|优惠", 20,
     "营销案/活动/优惠未按预期生效，含生效时间回传错误"),
    (1, None, "数据与状态异常", r"状态|账号|同步|激活|停机|复机|实名|地址|资料", 30,
     "多系统数据不一致、账号未开通/未同步、基础资料错误"),
    (1, None, "流程与工单卡单", r"施工单|订单|待办|流程|归档|预受理|审批", 40,
     "业务受理后工单不流转、卡在中间环节、无法结单"),
    (1, None, "系统缺陷与办理受阻", r"报错|失败|异常|无法|不能|拦截", 50,
     "功能报错、接口异常、校验拦截、只能后台改库"),
    (1, None, "外部依赖与协同", r"网络部|厂家|第三方|上游|跨部门", 60,
     "责任在网络侧/厂家/第三方平台，或需跨部门协同"),
    (1, None, "操作与咨询", r"查询|核实|咨询|如何|怎么|为什么", 70,
     "纯咨询、口径解释、查询核实，系统本身无故障"),

    # ── 二级：计费与出账争议 ──
    (2, "计费与出账争议", "多出账与费用突增", r"多出账|多收|费用突增|突增出账|少收|补收费", 110,
     "同一业务重复出账或金额异常放大"),
    (2, "计费与出账争议", "已关闭仍扣费", r"关闭.{0,8}(仍|还).{0,6}(扣费|出账|收费)|停机.{0,8}(仍|还).{0,6}扣费|已撤.{0,8}(仍|还)", 120,
     "业务已停止/已撤销但计费未同步终止"),
    (2, "计费与出账争议", "计费规则执行错误", r"包天|包月.{0,6}(变|按)|未按照5折|折扣.{0,6}(未|不|错误)|按天计费|计费规则", 130,
     "资费/折扣/计费周期规则执行与产品定义不符"),
    (2, "计费与出账争议", "退费与账单争议", r"退费|退款|账单.{0,8}(不对|异常|争议)|欠费.{0,8}(原因|核查)", 140,
     "客户对账单或退费结果有异议"),
    (2, "计费与出账争议", "复机与欠费状态异常", r"充值.{0,10}(未|没有).{0,6}(复机|开机|恢复)|复机失败|欠费停机.{0,8}(未|异常)", 150,
     "缴费后未复机或欠费停机状态与事实不符"),

    # ── 二级：营销与活动生效异常 ──
    (2, "营销与活动生效异常", "营销案未生效", r"营销案.{0,12}(未生效|不生效|失败)|活动.{0,12}(未生效|不生效)|订购.{0,8}未生效", 210,
     "办理成功但营销案未生效，客户未享优惠"),
    (2, "营销与活动生效异常", "活动时间未回传或错误", r"生失效时间|生效时间.{0,8}(错|不对|未回传)|2100|以竣工时间为准|活动时间", 220,
     "上下游活动起止时间不一致或默认 2100 年"),
    (2, "营销与活动生效异常", "优惠与权益未到账", r"优惠.{0,8}(未|没).{0,6}(到账|享受)|赠费.{0,8}(未|没)|权益未到账", 230,
     "优惠、赠费、权益未按约定到账"),

    # ── 二级：数据与状态异常 ──
    (2, "数据与状态异常", "电视与机顶盒账号未同步", r"电视账号|机顶盒|电视激活|电视登录|电视未开通|服务未开通|账号不存在|未开通任何|显示未开通|上游.{0,10}同步|未收到上游", 310,
     "电视/机顶盒账号在上游开通后未同步至使用系统（批量高发）"),
    (2, "数据与状态异常", "业务状态多系统不一致", r"不同步|未同步|状态不一致|CRM.{0,12}(停机|未激活|正使用)|网络侧.{0,8}(停机|不一致)|显示.{0,6}(停机|正使用|已激活)", 320,
     "CRM/商品中心/网络侧状态互不一致"),
    (2, "数据与状态异常", "业务在用显示未激活", r"未激活|无法激活|激活失败", 330,
     "业务实际在用但系统显示未激活，导致无法销户/变更"),
    (2, "数据与状态异常", "销户残留与逾期未清理", r"销户.{0,10}(残留|未清理|不成功)|逾期多月|无故清理|仍.{0,6}停机|未停机", 340,
     "销户未彻底、账号长期残留或被误清理"),
    (2, "数据与状态异常", "实名与证件数据异常", r"实名|证件|生僻字|身份证.{0,10}(一致|更换)|高风险客户", 350,
     "实名信息、证件号、生僻字等基础资料错误"),
    (2, "数据与状态异常", "标准地址错乱或串号", r"地址.{0,12}(错乱|合并|串号|不对|不够|带不出)|ADDR_ID|addname", 360,
     "标准地址缺失/串号导致开通地址错误"),

    # ── 二级：流程与工单卡单 ──
    (2, "流程与工单卡单", "施工单未触发", r"未触发施工|收不到.{0,6}工单|没有施工单|施工单.{0,8}(未|没)", 410,
     "业务竣工后未自动生成施工单"),
    (2, "流程与工单卡单", "装维待办找不到", r"待办.{0,8}找不到|找不到待办|找不到.{0,6}(合同|任务单|工单)|装维.{0,8}(收不到|没有)", 420,
     "装维侧无待办或待办列表查不到该单"),
    (2, "流程与工单卡单", "在途单阻塞新业务", r"在途|存在未完成|未完成.{0,6}(订单|业务)|历史订单|阻塞", 430,
     "历史在途单未清理，校验拦截新业务受理"),
    (2, "流程与工单卡单", "预受理与流程滞留", r"预受理|流程节点|没有到下个流程|无法.{0,6}下一步|挂起|滞留", 440,
     "流程停在某节点不前进，长期滞留"),
    (2, "流程与工单卡单", "归档与结单失败", r"无法结单|归档失败|不能归档|结单异常|点通过|过不去", 450,
     "流程末端无法结单/归档"),
    (2, "流程与工单卡单", "商机与合同查询不到", r"商机.{0,10}(查不到|查询不到|搜不到)|合同.{0,8}(找不到|无)", 460,
     "商机/合同在系统中检索不到"),
    (2, "流程与工单卡单", "跨地市审批不回传", r"crossCityBusinessAudit|审批单号.{0,10}(未|没有)|跨地市.{0,10}审批", 470,
     "跨地市审批结果/审批单号未回传，工单无法继续"),

    # ── 二级：系统缺陷与办理受阻 ──
    (2, "系统缺陷与办理受阻", "接口报错与调用失败", r"接口.{0,10}(报错|失败|异常)|调用服务异常|接口失败", 510,
     "系统间接口调用异常，业务无法继续"),
    (2, "系统缺陷与办理受阻", "前端校验拦截或无法提交", r"报错|提示.{0,12}(异常|限制|必须)|拦截|不允许办理|无法.{0,4}(提交|办理|操作|撤单|销户|退订|变更)", 520,
     "前端校验/提示阻断正常办理"),
    (2, "系统缺陷与办理受阻", "字段映射缺失或带不出", r"带不出|取不到|字段.{0,8}(缺失|为空|不对)|属性映射|选择不了|不能选择", 530,
     "关键字段无法自动带出，需人工补录"),
    (2, "系统缺陷与办理受阻", "撤单退单接口缺失", r"撤单.{0,12}(接口|不存在|失败)|OneId.{0,12}不存在|退单失败", 540,
     "缺少撤单/退单能力或撤单后数据不一致"),
    (2, "系统缺陷与办理受阻", "超期自动归档打停业务", r"90天|自动.{0,6}归档|自动失败|打停|系统.{0,8}自动.{0,6}(关闭|终止)", 550,
     "超期未处理被系统自动归档，导致在用业务被打停"),
    (2, "系统缺陷与办理受阻", "仅能后台SQL修复", r"后台.{0,6}SQL|改库|update\s|脚本.{0,6}修复", 560,
     "前端无修复入口，只能后台改库（高风险）"),
    (2, "系统缺陷与办理受阻", "数据串号与融合单异常", r"串号|融合单|组网.{0,8}安防|两个.{0,6}账号", 570,
     "融合单/多账号数据串号，字段互相覆盖"),

    # ── 二级：外部依赖与协同 ──
    (2, "外部依赖与协同", "网络侧与厂家责任", r"请联系网络部|咨询网络部|厂家|易视腾|浩鲸|集客部", 610,
     "责任判定在网络部/厂家，需外部修复"),
    (2, "外部依赖与协同", "第三方平台同步异常", r"上游|第三方|平台.{0,8}(同步|回传)", 620,
     "第三方平台数据同步/回传异常"),
    (2, "外部依赖与协同", "跨部门协作等待", r"等待.{0,8}(反馈|回复)|跨部门|需.{0,8}确认", 630,
     "需跨部门确认，单方无法推进"),

    # ── 二级：操作与咨询 ──
    (2, "操作与咨询", "资费政策咨询", r"资费|政策|套餐.{0,8}(咨询|规定)", 710,
     "资费政策口径咨询，无系统故障"),
    (2, "操作与咨询", "查询与核实请求", r"查询|核查|核实|帮查|查一下", 720,
     "要求后台查询/核实数据，非故障"),
    (2, "操作与咨询", "操作指引", r"如何|怎么|哪里|操作", 730,
     "咨询操作路径与方法"),
]


def _has_table(bind, name: str) -> bool:
    return inspect(bind).has_table(name)


def _has_index(bind, table: str, index: str) -> bool:
    try:
        return any(ix["name"] == index for ix in inspect(bind).get_indexes(table))
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. 分类字典 ──
    if not _has_table(bind, CAT):
        op.create_table(
            CAT,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, comment="自增ID"),
            sa.Column("level", sa.Integer(), nullable=False, server_default="1", comment="层级：1=一级性质 2=二级场景"),
            sa.Column("parent_name", sa.String(64), comment="上级分类名称（level=2 必填，指向 level=1 的 name）"),
            sa.Column("name", sa.String(64), nullable=False, comment="分类名称（落库值，无 code，零转译）"),
            sa.Column("keywords", sa.Text(), comment="场景识别关键词（正则，用 | 分隔；level=2 生效）"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100", comment="排序=匹配优先级，小者优先"),
            sa.Column("enabled", sa.Integer(), nullable=False, server_default="1", comment="是否启用：1 启用 0 停用"),
            sa.Column("note", sa.String(255), comment="口径说明（判定边界）"),
            sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
            sa.UniqueConstraint("level", "name", name="uk_cc_level_name"),
            sa.Index("idx_cc_parent", "parent_name"),
            comment="客诉问题分类字典（两级，唯一真相源）",
        )

    # ── 2. 工单明细 ──
    if not _has_table(bind, TICKET):
        op.create_table(
            TICKET,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, comment="自增ID"),
            sa.Column("ticket_no", sa.String(64), nullable=False, unique=True, comment="小信工单号（去重键）"),
            sa.Column("week", sa.String(16), comment="归属自然周（ISO，如 2026-W44；按创建时间归属）"),
            sa.Column("created_time", sa.DateTime(), comment="工单创建时间"),
            sa.Column("city", sa.String(64), comment="申告地市"),
            sa.Column("channel", sa.String(64), comment="渠道"),
            sa.Column("appeal_category", sa.String(64), comment="申告类别（原始）"),
            sa.Column("biz_attr", sa.String(64), comment="工单属性（原始）"),
            sa.Column("content", sa.Text(), comment="工单内容"),
            sa.Column("solution_history", sa.Text(), comment="解决方案历史（处置链路）"),
            sa.Column("handler", sa.String(255), comment="处理人"),
            sa.Column("handle_unit", sa.String(255), comment="处理单位"),
            sa.Column("dispatch_count", sa.Integer(), server_default="1", comment="派单次数"),
            sa.Column("status", sa.String(32), comment="工单状态"),
            sa.Column("category_l1", sa.String(64), comment="一级问题性质（落字典 name）"),
            sa.Column("category_l2", sa.String(64), comment="二级问题场景（落字典 name）"),
            sa.Column("classify_by", sa.String(16), server_default="auto", comment="分类来源：auto=规则命中 / manual=人工校正"),
            sa.Column("cluster_key", sa.String(64), comment="批量异常簇标识（场景@发现日），非批量簇为空"),
            sa.Column("is_batch", sa.Integer(), nullable=False, server_default="0", comment="是否属批量异常簇：1 是 0 否"),
            sa.Column("is_recur", sa.Integer(), nullable=False, server_default="0", comment="是否措施上线后同类复发：1 是 0 否"),
            sa.Column("linked_issue_no", sa.String(64), comment="关联运营工单号（改进措施载体）"),
            sa.Column("source_file", sa.String(255), comment="源文件名（溯源）"),
            sa.Column("import_batch", sa.String(64), comment="导入批次号"),
            sa.Column("remark", sa.String(500), comment="备注/人工校正说明"),
            sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
            comment="客诉工单明细（压降分析数据底座）",
        )
    for ix, cols in (
        ("idx_ct_week", ["week"]),
        ("idx_ct_created", ["created_time"]),
        ("idx_ct_l1", ["category_l1"]),
        ("idx_ct_l2", ["category_l2"]),
        ("idx_ct_cluster", ["cluster_key"]),
    ):
        if not _has_index(bind, TICKET, ix):
            op.create_index(ix, TICKET, cols)

    # ── 3. 措施台账 ──
    if not _has_table(bind, ACTION):
        op.create_table(
            ACTION,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, comment="自增ID"),
            sa.Column("action_no", sa.String(64), nullable=False, unique=True, comment="措施编号（CACT-2026W44-01）"),
            sa.Column("title", sa.String(255), nullable=False, comment="措施标题"),
            sa.Column("category_l1", sa.String(64), comment="针对的一级问题性质"),
            sa.Column("category_l2", sa.String(64), comment="针对的二级问题场景（有效性按此场景统计）"),
            sa.Column("issue_id", sa.Integer(), comment="关联运营工单ID（父子关联）"),
            sa.Column("issue_no", sa.String(64), comment="关联运营工单号"),
            sa.Column("req_id", sa.String(64), comment="关联需求编号（需开发改造时）"),
            sa.Column("owner", sa.String(255), comment="责任人"),
            sa.Column("due_date", sa.Date(), comment="要求完成日期"),
            sa.Column("acceptance", sa.Text(), comment="验收标准（必填，可验证）"),
            sa.Column("baseline_cnt", sa.Float(), comment="措施上线前 4 周该场景周均单量（基线）"),
            sa.Column("target_drop_pct", sa.Float(), server_default="50", comment="目标降幅（%，默认 50）"),
            sa.Column("go_live_date", sa.Date(), comment="措施生效日期（有效性观察起点）"),
            sa.Column("verify_weeks", sa.Integer(), server_default="4", comment="观察周数（默认 4 周）"),
            sa.Column("last_week_cnt", sa.Float(), comment="最近一周该场景单量"),
            sa.Column("actual_drop_pct", sa.Float(), comment="实际降幅（%）"),
            sa.Column("status", sa.String(32), nullable=False, server_default="planned",
                      comment="状态：planned/in_progress/verifying/effective/ineffective/cancelled"),
            sa.Column("note", sa.Text(), comment="备注/未达标原因"),
            sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
            comment="客诉改进措施台账（有效性验证）",
        )
    for ix, cols in (
        ("idx_ca_status", ["status"]),
        ("idx_ca_l2", ["category_l2"]),
        ("idx_ca_issue", ["issue_id"]),
    ):
        if not _has_index(bind, ACTION, ix):
            op.create_index(ix, ACTION, cols)

    # ── 4. 预置分类字典（幂等：level+name 唯一，存在则跳过） ──
    stmt = sa.text(
        f"""
        INSERT INTO {CAT}
            (level, parent_name, name, keywords, sort_order, enabled, note, created_at, updated_at)
        SELECT :level, :parent_name, :name, :keywords, :sort_order, 1, :note, NOW(), NOW()
        FROM DUAL
        WHERE NOT EXISTS (
            SELECT 1 FROM {CAT} WHERE level = :level AND name = :name
        )
        """
    )
    for level, parent, name, keywords, sort_order, note in PRESET_CATEGORIES:
        bind.execute(stmt, {
            "level": level,
            "parent_name": parent,
            "name": name,
            "keywords": keywords,
            "sort_order": sort_order,
            "note": note,
        })


def downgrade() -> None:
    bind = op.get_bind()
    for tbl in (ACTION, TICKET, CAT):
        if _has_table(bind, tbl):
            op.drop_table(tbl)
