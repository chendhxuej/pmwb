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
#
# 2026-11-04 老大要求「适当细化」：原「订单受理与开通交付」一个族吃掉 45% 单量
# （560/1226 单），受理、施工、交付三拨人混在一张表里谁也看不清自己的问题；
# 「计费与账务」同理（账单算错 vs 对账结算，处理团队不同）。故按**责任环节**拆开：
#   订单受理与提交  ← 前台受理、订单开通
#   施工与装维交付  ← 派单调度、装维交付、施工交付
#   计费出账 / 账务结算  ← 原「计费与账务」拆二
# 只拆有独立责任主体的环节，不按 fault_system（系统是技术视角，会把同一件事切两半）。
THEMES = [
    ("order_intake", "订单受理与提交", 10),
    ("fulfillment", "施工与装维交付", 20),
    ("activation", "业务激活与状态回写", 30),
    ("data_sync", "数据同步与建档", 40),
    ("agreement", "电子协议签约", 50),
    ("product_config", "产品与资费配置", 60),
    ("billing_charge", "计费出账", 70),
    ("billing_settle", "账务结算", 80),
    ("consult", "咨询与操作指引", 90),
    ("other", "其他", 99),
]

THEME_NAME = {k: n for k, n, _ in THEMES}
THEME_ORDER = {k: o for k, _, o in THEMES}
THEME_KEYS = [k for k, _, _ in THEMES]

# fault_stage → 族。新增环节只需在这里加一行；未覆盖的落 other。
STAGE_TO_THEME = {
    # 订单受理与提交：客户侧发起的录单、提交、规则校验
    "前台受理": "order_intake",
    "订单开通": "order_intake",
    # 施工与装维交付：派单到装维上门、施工完成回单
    "派单调度": "fulfillment",
    "装维交付": "fulfillment",
    "施工交付": "fulfillment",
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
    # 计费出账：账单生成、金额错误
    "计费出账": "billing_charge",
    # 账务结算：对账、销账、回款
    "账务结算": "billing_settle",
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
