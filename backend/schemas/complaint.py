"""客诉专题 Pydantic 模型（白名单显式声明，防字段静默丢失）。"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class CategoryCorrectIn(BaseModel):
    """人工校正分类（classify_by 置 manual，reclassify 不覆盖）。"""
    category_l1: str = Field(..., max_length=64, description="一级性质")
    category_l2: str = Field("", max_length=64, description="二级场景（可为空）")
    remark: Optional[str] = Field(None, description="校正备注")


class CategoryEnabledIn(BaseModel):
    enabled: int = Field(..., ge=0, le=1, description="1 启用 / 0 停用")


class ActionCreateIn(BaseModel):
    """登记改进措施。"""
    l2: str = Field(..., max_length=64, description="二级问题场景（须在字典中）")
    title: str = Field(..., max_length=255)
    owner: str = Field(..., max_length=255, description="责任人（多负责人逗号分隔）")
    due_date: Optional[date] = Field(None, description="要求完成日期")
    acceptance: str = Field(..., description="验收标准（可验证）")
    desc: str = Field("", description="情况说明（前端把自动总结+手工补充整合后的最终文本）")
    create_issue: bool = Field(False, description="是否同步创建运营工单父子关联")
    problem_nos: list[str] = Field(default_factory=list, description="所属共性问题编号（多选）")
    context_weeks: int = Field(1, ge=1, le=26,
                               description="建工单时自动代入关联投诉工单的周期（1=当周，N=近N周）")
    context_tickets: Optional[str] = Field(None,
                                           description="关联投诉工单明细(JSON数组串，前端预览确认后传回；不传则后端按 context_weeks 自动收集)")


class ActionUpdateIn(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    owner: Optional[str] = Field(None, max_length=255)
    due_date: Optional[date] = None
    acceptance: Optional[str] = None
    note: Optional[str] = None
    target_drop_pct: Optional[float] = Field(None, ge=0, le=100)
    verify_weeks: Optional[int] = Field(None, ge=1, le=26)


class GoLiveIn(BaseModel):
    go_live_date: date = Field(..., description="措施生效日")


class ReportGenIn(BaseModel):
    week: Optional[str] = Field(None, description="周次（默认库内最新周）")
    with_pdf: bool = Field(True, description="是否导出 PDF（失败自动降级仅 HTML）")


class UrgePreviewIn(BaseModel):
    """客诉措施督办邮件（默认 dry_run；真发须前端显式 confirm_send=True）。"""
    owner: Optional[str] = Field(None, description="仅督办指定责任人（空=全部超期措施）")
    subject: Optional[str] = Field(None, description="自定义主题（默认场景主题）")
    confirm_send: bool = Field(False, description="确认真发（False 仅 dry_run 落库验证）")


# ── 共性问题台账（闭环管理） ──────────────────────────────────
class ProblemCreateIn(BaseModel):
    """手工立问题（source_type=manual）。"""
    category_l2: str = Field(..., max_length=64, description="二级问题场景（须在字典中）")
    title: str = Field(..., max_length=255)
    owner: str = Field("", max_length=255, description="责任人（带则直接入账 open）")
    note: Optional[str] = Field(None, description="备注")


class ProblemUpdateIn(BaseModel):
    """编辑基础字段（不含 status）。"""
    title: Optional[str] = Field(None, max_length=255)
    category_l1: Optional[str] = Field(None, max_length=64)
    owner: Optional[str] = Field(None, max_length=255)
    note: Optional[str] = None


class ProblemStatusIn(BaseModel):
    """问题状态流转（status_registry complaint_problem 域校验）。"""
    status: str = Field(..., max_length=32)
    owner: Optional[str] = Field(None, max_length=255)
    conclusion: Optional[str] = Field(None, max_length=500, description="闭环结论（closed 必填）")
    closed_week: Optional[str] = Field(None, max_length=16)
    note: Optional[str] = None


class ProblemConfirmIn(BaseModel):
    """候选确认：open（入账）/ merge（合并）/ ignore（忽略）。"""
    decision: str = Field(..., pattern="^(open|merge|ignore)$")
    owner: str = Field("", max_length=255, description="decision=open 必填")
    merged_into: str = Field("", max_length=64, description="decision=merge 必填")
    note: Optional[str] = None
    confirm_by: str = Field("", max_length=64, description="确认人")


class ProblemActionLinkIn(BaseModel):
    action_no: str = Field(..., max_length=64)
    is_primary: bool = Field(False, description="主措施标记（同问题至多一条）")
    note: Optional[str] = None


class ProblemUrgeIn(BaseModel):
    """问题级督办（复用 complaint_action_urge 场景，dry_run 默认）。"""
    confirm_send: bool = Field(False, description="确认真发（False 仅 dry_run）")


# ── 根因层（2026-11-03 客诉根因深化）────────────────────────────
class TicketRootcauseIn(BaseModel):
    """单条工单根因人工校正（落 rc_status='manual'，重跑不覆盖）。"""
    root_cause: str = Field("", max_length=500, description="一句话真实根因")
    fault_stage: str = Field("", max_length=32, description="故障环节")
    fault_system: str = Field("", max_length=64, description="涉及系统")
    fault_type: str = Field("", max_length=32, description="缺陷性质")
    own_party: str = Field("", max_length=32, description="责任归属")
    fix_mode: str = Field("", max_length=32, description="处置方式")
    repro: str = Field("unknown", max_length=8, description="可复现：yes/no/unknown")
    evidence: str = Field("", description="原文依据")
    has_defect: Optional[bool] = Field(None, description="是否存在缺陷（None=按 fault_type 推断）")


class RootcauseConfirmIn(BaseModel):
    """根因簇人工确认入账（可同时改名/补判定边界/校正标签）。"""
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    fault_type: Optional[str] = Field(None, max_length=32)
    own_party: Optional[str] = Field(None, max_length=32)
    fix_mode: Optional[str] = Field(None, max_length=32)


class RootcauseMergeIn(BaseModel):
    """同义簇合并：本簇并入 dst_no（工单指针统一改指主簇）。"""
    dst_no: str = Field(..., max_length=64, description="主簇 rootcause_no")


class RootcauseDisableIn(BaseModel):
    """簇停用/恢复（停用后不再参与匹配，存量指针保留）。"""
    reopen: bool = Field(False, description="True=恢复为已入账")


class RootcauseClusterIn(BaseModel):
    """人工新建根因簇（新业务/新场景先立簇后挂单）。"""
    fault_stage: str = Field("", max_length=32, description="订单环节（受控枚举）")
    mechanism: str = Field("", max_length=32, description="失败机制（受控枚举）")
    biz_object: str = Field("", max_length=32, description="业务对象（人工可自由命名）")
    trigger: str = Field("", max_length=32, description="触发条件/场景限定（可空）")
    title: str = Field("", max_length=200, description="簇标题；空=按 {对象}-{机制} 生成")
    description: str = Field("", max_length=500, description="判定边界：什么算、什么不算")
    fault_type: str = Field("", max_length=32)
    own_party: str = Field("", max_length=32)
    fix_mode: str = Field("", max_length=32)
    is_defect: Optional[bool] = Field(None, description="None=按机制推断（使用咨询=非缺陷）")
    ticket_nos: List[str] = Field(default_factory=list, description="建簇后直接挂入的工单号")


class RootcauseClusterUpdateIn(BaseModel):
    """人工编辑根因簇（只提交要改的字段；改三要素会重算 pattern_key 并查重）。"""
    fault_stage: Optional[str] = Field(None, max_length=32)
    mechanism: Optional[str] = Field(None, max_length=32)
    biz_object: Optional[str] = Field(None, max_length=32)
    trigger: Optional[str] = Field(None, max_length=32)
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    fault_type: Optional[str] = Field(None, max_length=32)
    own_party: Optional[str] = Field(None, max_length=32)
    fix_mode: Optional[str] = Field(None, max_length=32)
    is_defect: Optional[bool] = None


class RootcauseSplitIn(BaseModel):
    """簇内拆单：并入 target_no，或按 new_cluster 新建一个簇。"""
    ticket_nos: List[str] = Field(default_factory=list)
    target_no: str = Field("", max_length=64, description="目标簇号（空=新建簇）")
    new_cluster: Optional[RootcauseClusterIn] = Field(None, description="target_no 为空时用")


class TicketsMoveIn(BaseModel):
    """批量把工单改指到指定簇（人工纠偏）。"""
    ticket_nos: List[str] = Field(default_factory=list)
    target_no: str = Field("", max_length=64)


class ProblemV42RunIn(BaseModel):
    """客诉 v4.2 全链运行入参（方案 §1.3：分析过程不依赖人；dry_run 默认）。"""
    dry_run: bool = True
    force: bool = False                 # True=忽略已存 L1 结论，全量重算
    limit: int = 0                      # 0=全量
    allow_semantic: bool = True         # False=只用确定性规则层（演练用）
    max_semantic_batches: int = 1       # 默认最多 1 批，防误触全量调用；0=不限
