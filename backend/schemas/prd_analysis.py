"""PRD 需求分析入/出参 schema。"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PrdAnalyzeIn(BaseModel):
    """提交需求分析。

    req_id 走 URL path（/prd/analyze/{req_id}），body 只带分析输入。
    """

    raw_requirement: str = Field("", description="澄清后需求原文")
    systems: List[str] = Field(default_factory=list, description="涉及系统 ID 列表（1-5 个）")
    mode: str = "qa"  # qa（一次性问卷） | fast（快速自决）
    profile: str = "concise"  # concise | deep
    answers: Dict[str, str] = Field(default_factory=dict, description="十维问卷答案 {key: 选项或自定义文本}")
    req_name: str = ""
    special_notes: str = ""
    prototype: bool = False
    selected_dirs: List[str] = Field(default_factory=list, description="业务子目录筛选，形如 CRM/base_custinfo；留空=全部")


class PrdSyncIn(BaseModel):
    systems: List[str] = Field(default_factory=list, description="要同步的系统 ID，留空=全部 3 个")


class PrdConflict(BaseModel):
    level: str = ""
    type: str = ""
    desc: str = ""
    evidence: str = ""


class PrdSource(BaseModel):
    sys_id: str = ""
    repo_id: str = ""
    sha: str = ""
    path: str = ""
    clause: str = ""
    quote: str = ""


class PrdAnalyzeOut(BaseModel):
    trace_id: str
    req_id: str
    prd_markdown: str
    conflicts: List[PrdConflict] = []
    sources: List[PrdSource] = []
    assumptions: List[str] = []
    open_items: List[str] = []
    status: str = "generated"  # generated | fallback
    gen_strategy: str = ""  # llm | rules_fallback
    gen_provider: Optional[str] = None
    gen_model: Optional[str] = None
    gen_fallback_reason: Optional[str] = None
    knowledge_mode: str = "none"  # git | none
    knowledge_files: int = 0
    notice: str = ""


class PrdMetaOut(BaseModel):
    """十维问卷维度元数据（前端一次性问卷渲染用，单一真相源在 constants.prd_prompt）。"""

    dimensions: List[Dict[str, str]] = []
    systems: List[str] = []
    knowledge_status: str = "none"  # git | none
    knowledge_root: str = ""
    knowledge_synced_at: Optional[str] = None
    knowledge_files: int = 0
    llm_available: bool = False
    llm_notice: str = ""


class PrdStatusOut(BaseModel):
    trace_id: str
    req_id: str
    status: str
    gen_strategy: str = ""
    gen_provider: Optional[str] = None
    gen_model: Optional[str] = None
    finalized: bool = False
    created_at: Optional[str] = None


class PrdSourcesOut(BaseModel):
    trace_id: str
    req_id: str
    sources: List[PrdSource] = []
    conflicts: List[PrdConflict] = []
    assumptions: List[str] = []
    open_items: List[str] = []
