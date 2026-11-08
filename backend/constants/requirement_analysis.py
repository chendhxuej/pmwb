"""需求分析专题（AI 总结）的语义字典与口径常量。

单一真相源：环节/事件的成效表述、新增资费类识别关键词、篇幅上限。
改这里即全局生效，禁止在其他模块另存一份（第二份真相必然漂移）。

口径归属：2026-11-08 老大确认（已上线纠偏 + 在途过程进展 + 下周计划三通道）。
"""
from __future__ import annotations

# 需求 6 环节中文名（与 pmwb_requirement_stage_log.stage 取值对齐）
STAGE_LABELS = {
    "collect": "需求受理",
    "evaluate": "方案评估",
    "story": "用户故事",
    "doc": "需求方案",
    "dev": "系统开发",
    "deploy": "生产部署",
}

# 进入环节 → 成效表述（团队成效反馈口吻，一律正向动词）
STAGE_ACTIONS = {
    "collect": "完成需求受理登记",
    "evaluate": "完成需求澄清与落地方案评估",
    "story": "输出需求用户故事与验收标准",
    "doc": "输出需求方案说明书",
    "dev": "启动系统开发",
    "deploy": "进入生产部署环节",
}

# 开发事件类型 → 成效表述（见 pmwb_req_dev_event.event_type）
DEV_EVENT_ACTIONS = {
    "dev_start": "启动系统开发",
    "joint_test": "完成接口联调验证",
    "test": "完成测试验证",
    "bugfix": "完成问题修复",
    "release_ready": "完成开发部署，具备上线条件",
}

# 「新增资费类快速配置」识别：需求分类命中 或 名称/澄清命中关键词（任一即算）
TARIFF_CATEGORY = "商品体系建设"
TARIFF_KEYWORDS = (
    "新增资费",
    "新增套餐",
    "新增产品资费",
    "调整资费",
    "资费调整",
    "调测费",
    "资费方案",
)

# 需求作废/不开发标记：命中则不进任何章节（避免把已取消的功能写成团队成果）
SKIP_KEYWORDS = (
    "申请不开发",
    "暂不开发",
    "无需开发",
    "不开发",
    "需求作废",
    "已作废",
    "取消需求",
)

# 在途状态（未上线、仍需推进）：见 constants/status_registry.py::requirement
INFLIGHT_STATUSES = ("proposed", "accepted", "dev", "partial_live", "live_failed")
# 不参与任何章节的状态
EXCLUDED_STATUSES = ("paused", "suspended", "closed")

# 篇幅上限：报告是团队成效反馈，宁少勿多（超出写「其余推进中」）
MAX_DELIVERED = 12
MAX_INFLIGHT = 8
MAX_PLANNED = 10
# 单条能力概述字数上限（模型与规则统一口径）
CAP_CAPABILITY = 40
# 单条在途进展最多串几个动作（再多就啰嗦）
MAX_INFLIGHT_ACTIONS = 3
