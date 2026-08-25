from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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
