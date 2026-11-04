"""客诉「问题族」（业务链路/域）口径——唯一真相源

背景（老大 2026-11-04 拍板）：根因簇颗粒度是「具体个案」（实测 776 个簇只有 1 单，
标题精确到订单号/账号），直接平铺到报表里看着又散又不准。业务上真正要看的粒度是
**业务链路/域**——"订单受理与开通交付"这一类一周出了多少单、比上周多还是少。

族的定义方式：
  族 = fault_stage（故障环节）归并到业务链路。选 fault_stage 而不是 fault_system，
  因为系统是技术视角（CRM/订单中心都是同一件事的两端），环节才是业务语言。
  映射表固定在这里，不落库、不让 AI 每次重新命名——族名漂移比族不够细更伤报表可读性。

簇级不存 theme 字段：族完全由 stage 派生（GROUP BY），避免第二份真相。
个别 stage 取值异常时落 OTHER，不允许静默丢弃。
"""

# (key, 中文名, 排序)  —— 排序即报表展示顺序，按业务链路先后
THEMES = [
    ("order_fulfill", "订单受理与开通交付", 10),
    ("activation", "业务激活与状态回写", 20),
    ("data_sync", "数据同步与建档", 30),
    ("agreement", "电子协议签约", 40),
    ("product_config", "产品与资费配置", 50),
    ("billing", "计费与账务", 60),
    ("consult", "咨询与操作指引", 90),
    ("other", "其他", 99),
]

THEME_NAME = {k: n for k, n, _ in THEMES}
THEME_ORDER = {k: o for k, _, o in THEMES}
THEME_KEYS = [k for k, _, _ in THEMES]

# fault_stage → 族。新增环节只需在这里加一行；未覆盖的落 other。
STAGE_TO_THEME = {
    # 订单受理与开通交付：从受理到施工交付的整条链路
    "订单开通": "order_fulfill",
    "装维交付": "order_fulfill",
    "前台受理": "order_fulfill",
    "施工交付": "order_fulfill",
    "派单调度": "order_fulfill",
    # 业务激活与状态回写
    "业务激活": "activation",
    "状态回写": "activation",
    # 数据同步与建档
    "数据同步": "data_sync",
    "资料建档": "data_sync",
    # 电子协议签约
    "协议签约": "agreement",
    "协议起草": "agreement",
    # 产品与资费配置
    "产品配置": "product_config",
    "资费配置": "product_config",
    # 计费与账务
    "计费出账": "billing",
    "账务结算": "billing",
    # 咨询与操作指引（非缺陷，默认不进台账）
    "使用咨询": "consult",
    "操作咨询": "consult",
}

# 非缺陷族：不进问题台账、也不计入「系统缺陷单量」口径
NON_DEFECT_THEMES = {"consult"}


def theme_of(stage: str) -> str:
    """环节 → 族 key（未覆盖落 other，不抛错、不丢数据）。"""
    return STAGE_TO_THEME.get((stage or "").strip(), "other")


def theme_name(key: str) -> str:
    return THEME_NAME.get(key, THEME_NAME["other"])


def sort_key(key: str) -> int:
    return THEME_ORDER.get(key, THEME_ORDER["other"])
