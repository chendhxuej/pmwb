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


class UserStoryGenIn(BaseModel):
    """用户故事生成入参：澄清后的需求内容。"""

    content: str = ""


class UserStoryGenOut(BaseModel):
    req_id: str
    ddd: DDDView
    stories: List[StorySection]


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
    attachment_folder: str
    doc_folder: str
    attachments: List[AttachmentOut]


class GenerateDocOut(BaseModel):
    req_id: str
    file: str
    path: str
    url: str
