"""多负责人字段工具（后端单一实现）。

存储约定：多选责任人在库中以逗号分隔字符串保存（沿用运营监控工单 handler 的既有做法），
接口出入参均可用逗号 / 顿号 / 分号连接，历史单值数据天然兼容。

被以下位置复用：
- services/meeting.py（会议行动项 owner：督办收件人、派发分流、纪要展示）
- services/keywork_excel.py（成员待办导入规范化）
- services/task_center.py（任务中心按人筛选时求交集）
- routers/keywork.py（成员待办 assignee 入库规范化）
"""
import re
from typing import Any, Iterable, List

_SPLIT_RE = re.compile(r"[,，;；、]+")


def split_owners(raw: Any) -> List[str]:
    """多负责人字段 → 姓名列表（去空白、去重、剔除空项）。"""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        parts: Iterable[str] = [str(x) for x in raw]
    else:
        parts = _SPLIT_RE.split(str(raw))
    names: List[str] = []
    for part in parts:
        name = part.strip()
        if name and name not in names:
            names.append(name)
    return names


def join_owners(raw: Any) -> str:
    """姓名列表 / 任意分隔串 → 逗号分隔字符串（落库用）。"""
    return ",".join(split_owners(raw))


def owners_display(raw: Any) -> str:
    """多负责人展示文案（顿号连接），空值返回 ''。"""
    return "、".join(split_owners(raw))


def owner_set(raw: Any) -> set:
    """多负责人字段 → 姓名集合（按人筛选时用，保证一条任务挂多人时人人命中）。"""
    return set(split_owners(raw))
