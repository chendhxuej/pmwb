"""需求「厂家开发状态」相关入参模型（2026-10-16 新增）。

只承载**入参校验**；状态合法值、中文标签、流转规则的唯一真相源仍是
``constants/status_registry.py`` 的 vendor_dev 域，这里不做第二份枚举。
"""

from typing import Optional

from pydantic import BaseModel


class VendorDevCreate(BaseModel):
    system_name: str
    team_name: Optional[str] = None
    sa_name: Optional[str] = None
    dev_ticket_no: Optional[str] = None
    dev_status: Optional[str] = None


class VendorDevUpdate(BaseModel):
    dev_status: Optional[str] = None
    team_name: Optional[str] = None
    sa_name: Optional[str] = None
    dev_ticket_no: Optional[str] = None


class VendorManualUpload(BaseModel):
    """厂家操作手册上传（插件抓到手册后回传）。

    用 JSON body 而非 query：**base64 走 URL 会撞长度上限**（20MB 文件约 2700 万字符）。
    """

    filename: str
    content_base64: str


# 注：VendorTeamCreate / VendorTeamUpdate 已随本地字典 pmwb_vendor_team 一并下线
#     （2026-10-16）。「组织 → 系统名」映射改在人员中台组织管理里维护。
