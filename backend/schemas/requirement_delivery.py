from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DDDView(BaseModel):
    """DDD 领域视角，用于用户故事聚合展示。"""

    domain: str = "政企需求交付"
    subdomain: str = "需求评估与履约"
    aggregate: str = "需求-评估-交付"
    entity: str = "需求、用户故事、开发工单"


class StorySection(BaseModel):
    """单条用户故事（固定 4 段模板 + DDD 视角）。"""

    seq: int
    title: str
    desc: str
    scene: str
    acceptance: List[str]
    ddd: DDDView


class UserStoryItem(BaseModel):
    """用户故事持久化项（入/出）。"""

    id: Optional[int] = None
    seq: int
    title: str
    desc: str
    scene: str
    acceptance: List[str] = []
    rules: List[str] = []
    finalized: bool = False


class UserStoryListOut(BaseModel):
    req_id: str
    stories: List[UserStoryItem]


class UserStorySearchItem(BaseModel):
    """全局搜索结果项（含关联需求信息与创建时间）。"""

    id: Optional[int] = None
    req_id: str = ""
    req_name: str = ""
    seq: int = 1
    title: str = ""
    desc: str = ""
    scene: str = ""
    acceptance: List[str] = []
    rules: List[str] = []
    finalized: bool = False
    created_at: Optional[str] = None


class UserStorySearchOut(BaseModel):
    items: List[UserStorySearchItem]
    total: int
    page: int
    page_size: int


class UserStoryGenIn(BaseModel):
    """用户故事生成入参：澄清后的需求内容。"""

    content: str = ""
    strategy: str = "rules_v2"  # rules_v2（默认/推荐） | rules_v1（旧版） | llm（智能拆分）


class UserStoryGenOut(BaseModel):
    req_id: str
    ddd: DDDView
    stories: List[UserStoryItem]
    strategy_used: str = "rules_v2"


class DocGenIn(BaseModel):
    """分析说明书生成入参：定稿的用户故事 + 澄清内容。"""

    stories: List[Dict[str, Any]] = []
    clarification: str = ""


class AttachmentOut(BaseModel):
    name: str
    size: str
    bytes: int


class FolderInitOut(BaseModel):
    req_id: str
    folder: str
    attachments: List[AttachmentOut]


class GenerateDocOut(BaseModel):
    req_id: str
    file: str
    path: str
    url: str


class ManualUploadOut(BaseModel):
    req_id: str
    file_name: str
    local_path: str          # 相对 vault 的需求分析说明书文件夹路径
    obsidian_path: str       # 归档到业务知识交付物目录的相对路径
    archived: bool
    main_note: Optional[str] = None
    main_note_synced: bool = False  # 是否触发并更新了 §6


# ---------------------------------------------------------------------------
# 环节时间日志 / 开发事件 / 操作手册（按系统）
# ---------------------------------------------------------------------------
class StageLogItem(BaseModel):
    stage: str
    label: str
    entered_at: Optional[str] = None
    left_at: Optional[str] = None
    source: Optional[str] = None


class StageLogOut(BaseModel):
    req_id: str
    current_stage: Optional[str] = None
    stages: List[StageLogItem]


class StageLogUpdate(BaseModel):
    """手工修正环节时间（进入/完成时间，格式 YYYY-MM-DD[ HH:MM]）。"""

    entered_at: Optional[str] = None
    left_at: Optional[str] = None


class DevEventIn(BaseModel):
    event_time: Optional[str] = Field(None, description="事件发生时间 YYYY-MM-DD[ HH:MM]，缺省为当前时间")
    event_type: str = Field("other", description="事件类型: dev_start/joint_test/test/bugfix/release_ready/other")
    title: str = Field(..., description="事件标题")
    content: str = Field("", description="事件详情")


class DevEventOut(DevEventIn):
    id: int
    req_id: str
    event_type_label: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class ManualOut(BaseModel):
    id: int
    req_id: str
    system_name: str
    file_name: Optional[str] = None
    local_path: Optional[str] = None
    obsidian_path: Optional[str] = None
    note: Optional[str] = None
    uploaded_by: Optional[str] = None
    archived_at: Optional[str] = None
    previewable: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ManualSystemItem(BaseModel):
    system_name: str
    sa_name: str = ""
    manual: Optional[ManualOut] = None


class ManualSystemsOut(BaseModel):
    req_id: str
    systems: List[ManualSystemItem]
