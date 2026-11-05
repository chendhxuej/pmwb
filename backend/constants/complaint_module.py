# -*- coding: utf-8 -*-
"""
客诉「功能模块问题」闭集字典 —— 唯一真相源。

设计原则（对应 v4.2 复盘与老大 2026-11-05 要求）：
1. 归并键 = 业务功能模块 × 失效对象 × 失效性质；表象文案 / 涉及系统 / 客户 / 地市 / 时间
   一律不参与键。按技术系统切分正是上一轮（v4.2）偏差根因，本字典显式规避。
2. 闭集（closed-set）：LLM / 规则只允许输出本字典内已存在的 ID，越界即无效，
   绝不自由建类（否则退化回 1 单 1 簇）。
3. 落地即中文名，零转译；禁止第二份真相源（其他代码不得硬编码同类名）。
4. 字典由人在「过程外」一次性定口径、版本化；链路内无人工队列。
5. 字典条目按 priority 升序判定，命中即采用 —— 越具体/越优先（含老大举的「账号未同步」例子）。
6. is_defect=False 的咨询类单列隔离，不进缺陷主 KPI（沿用 CP-S10）。

匹配信号来源（确定性，不依赖 LLM）：
- point（v4.2 单工单 AI 简述，已是规范化表达）
- fault_stage（业务链环节，1476/1486 有值，作失效性质回退锚点）
- category_l1（一级分类，仅用于咨询类识别）

version: 字典口径版本，口径调整时 +1，便于历史漂移比对。
"""
from typing import List, Dict, Optional

MODULE_DICT_VERSION = 1

# 失效性质回退：fault_stage -> 失效性质族（仅当 point 无明确性质关键词时使用）
STAGE_TO_NATURE = {
    "业务激活": "ACT",
    "订单开通": "ACT",
    "数据同步": "SYNC",
    "装维交付": "CLOSE",
    "计费出账": "BILL",
    "账务结算": "BILL",
    "协议签约": "SIGN",
    "产品配置": "CONFIG",
    "前台受理": "ORDERFAIL",
    "使用咨询": "CONSULT",
    "操作咨询": "CONSULT",
    "规则咨询": "CONSULT",
}

# 咨询类一级分类
CONSULT_CATEGORY_L1 = {"使用咨询", "操作咨询", "规则咨询"}

# 模块问题条目。priority 越小越优先（具体条目在前）。
# 字段：
#   id            模块问题 ID（MP- 前缀，稳定不变）
#   name          中文名（落地即展示，禁转译）
#   module        业务功能模块
#   fail_object   失效对象
#   fail_nature   失效性质
#   systems       涉及系统（仅作证据展示，不参与归并键）
#   is_defect     是否业务缺陷（False=咨询类，隔离不进主 KPI）
#   objects       对象锚点关键词（point 命中任一即算命中对象）
#   natures       失效性质关键词（point 命中任一即算命中性质）
#   stages        fault_stage 回退锚点（point 无性质关键词时用）
#   exclude       排除关键词（point 含任一则该条目不命中，用于消歧）
#   priority      判定优先级（升序，命中即采用）
MODULE_PROBLEMS: List[Dict] = [
    # —— 老大举例同模块问题：一网通宽带/电视 开户激活后账号未同步 ——
    {
        "id": "MP-BROADBAND-ACT",
        "name": "一网通宽带/电视开户激活后账号未同步（业务未开通）",
        "module": "一网通宽带开户激活",
        "fail_object": "宽带账号/电视账号",
        "fail_nature": "数据不同步·业务未开通",
        "systems": ["订单中心", "CRM", "BOSS", "电视平台", "宽带平台"],
        "is_defect": True,
        "objects": ["一网通宽带", "宽带", "宽带账号", "电视", "机顶盒", "互联网电视",
                     "电视业务", "电视账号", "宽带电视", "账号", "FTTO", "光纤"],
        "natures": ["未开通", "未激活", "激活", "认证不成功", "查不到", "无记录",
                     "一起同步", "已开通", "未同步", "同步结果", "同步失败", "同步"],
        "stages": ["业务激活", "订单开通", "数据同步"],
        # 关键边界：账户(财务/计费) ≠ 账号(宽带电视激活目标)；出账/折后/计费属计费类，不并入
        "exclude": ["账户", "销户", "退订", "资费更改", "欠费", "改密码", "发票", "账单", "退款",
                     "网元", "撤单", "超1年", "过户", "出账", "折后", "计费", "金额",
                     "营销案", "打折", "带宽", "配置", "缴费", "商品中心"],
        "priority": 10,
    },
    # —— 集团业务 ——
    {
        "id": "MP-GROUP-ACT",
        "name": "集团业务开通激活/数据同步异常",
        "module": "集团业务",
        "fail_object": "集团产品/集团账号",
        "fail_nature": "开通激活异常·数据不同步",
        "systems": ["CRM", "订单中心", "BOSS"],
        "is_defect": True,
        "objects": ["集团"],
        "natures": ["未开通", "未激活", "激活", "同步", "查不到", "无记录", "已开通"],
        "stages": ["业务激活", "订单开通", "数据同步"],
        "exclude": ["销户", "退订", "资费", "账单", "出账", "退款"],
        "priority": 20,
    },
    {
        "id": "MP-GROUP-BILL",
        "name": "集团计费出账/账单异常",
        "module": "集团业务",
        "fail_object": "集团账单",
        "fail_nature": "计费出账错误",
        "systems": ["计费系统", "CRM"],
        "is_defect": True,
        "objects": ["集团"],
        "natures": ["出账", "账单", "资费", "计费", "折后", "质疑", "不符"],
        "stages": ["计费出账", "账务结算"],
        "exclude": ["开通", "激活", "同步"],
        "priority": 21,
    },
    # —— 订单流程 ——
    {
        "id": "MP-ORDER-FAIL",
        "name": "订单下单/受理失败",
        "module": "订单开通流程",
        "fail_object": "订单/购物车",
        "fail_nature": "下单受理失败",
        "systems": ["订单中心", "商品中心"],
        "is_defect": True,
        "objects": ["订单", "购物车", "融合订单", "子订单", "购物车订单"],
        "natures": ["受理", "下单", "无法下单", "受理失败", "拒单", "未触发", "商品中心"],
        "stages": ["前台受理", "订单开通"],
        "exclude": ["结单", "回单", "完工", "在途", "撤单"],
        "priority": 30,
    },
    {
        "id": "MP-ORDER-CLOSE",
        "name": "订单结单/回单卡单/在途",
        "module": "订单开通流程",
        "fail_object": "订单/施工单",
        "fail_nature": "结单回单卡单",
        "systems": ["订单中心", "CRM", "工维"],
        "is_defect": True,
        "objects": ["订单", "购物车", "施工单", "工维"],
        "natures": ["无法结单", "回单", "在途", "卡单", "结单", "超时", "完工", "审核"],
        "stages": ["装维交付"],
        "exclude": ["受理", "下单", "开户工单查不到"],
        "priority": 31,
    },
    {
        "id": "MP-ORDER-WITHDRAW",
        "name": "订单撤单/退订异常",
        "module": "订单开通流程",
        "fail_object": "订单",
        "fail_nature": "撤单退订失败",
        "systems": ["订单中心", "CRM"],
        "is_defect": True,
        # 撤单/退订/退单 等极强的终结性动作词，本身即对象+性质，独立可命中
        "objects": ["订单", "一网通", "撤单", "退订", "退单"],
        "natures": ["撤单", "退订", "退单"],
        "stages": [],
        "exclude": [],
        "priority": 32,
    },
    # —— 计费资费 ——
    {
        "id": "MP-BILL-ERR",
        "name": "计费出账/账单金额错误",
        "module": "计费出账",
        "fail_object": "账单/账务",
        "fail_nature": "计费出账错误",
        "systems": ["计费系统", "CRM"],
        "is_defect": True,
        "objects": ["资费", "账单", "计费", "出账", "发票", "账务", "折后", "缴费"],
        "natures": ["错误", "不符", "质疑", "少出", "多出", "未出", "异常", "返还"],
        "stages": ["计费出账", "账务结算"],
        "exclude": ["套餐变更未生效", "配置未生效", "销户"],
        "priority": 40,
    },
    {
        "id": "MP-BILL-CONFIG",
        "name": "资费/带宽/套餐配置未生效",
        "module": "产品配置",
        "fail_object": "资费/带宽/套餐",
        "fail_nature": "配置未生效",
        "systems": ["CRM", "订单中心"],
        "is_defect": True,
        "objects": ["资费", "带宽", "套餐", "产品"],
        "natures": ["未生效", "未更改", "更改失败", "配置", "未同步", "不一致", "做不了", "未成功", "未变更成功", "变更成功"],
        "stages": ["产品配置"],
        "exclude": ["出账错误", "账单金额"],
        "priority": 41,
    },
    # —— 电子协议 ——
    {
        "id": "MP-AGREEMENT",
        "name": "电子协议签约/起草卡住",
        "module": "电子协议",
        "fail_object": "电子协议",
        "fail_nature": "协议签约卡住",
        "systems": ["电子协议"],
        "is_defect": True,
        "objects": ["电子协议", "协议", "一网通协议", "起草"],
        "natures": ["加盖公章", "无法提交", "拒绝请求", "签约", "起草", "卡住", "无法推进", "推进"],
        "stages": ["协议签约"],
        "exclude": [],
        "priority": 50,
    },
    # —— 安防监控 ——
    {
        "id": "MP-SECURITY-ACT",
        "name": "安防/监控/全屋智能开通激活异常",
        "module": "安防监控",
        "fail_object": "安防/监控设备",
        "fail_nature": "开通激活异常·数据不同步",
        "systems": ["第三方厂家系统", "CRM"],
        "is_defect": True,
        "objects": ["安防", "监控", "全屋智能"],
        "natures": ["未开通", "激活", "未激活", "同步", "查不到", "报错", "无法", "异常"],
        "stages": ["业务激活", "订单开通", "数据同步"],
        "exclude": ["资费", "账单"],
        "priority": 60,
    },
    # —— 手机卡 ——
    {
        "id": "MP-SIM-ACT",
        "name": "手机卡入网/开通异常（黑名单/失信）",
        "module": "手机卡入网",
        "fail_object": "手机卡/号码",
        "fail_nature": "入网开通异常",
        "systems": ["CRM", "BOSS"],
        "is_defect": True,
        "objects": ["手机卡", "号卡", "手机", "sim", "SIM"],
        "natures": ["无法办卡", "入网", "失信", "黑名单", "无法入网", "开通", "禁止"],
        "stages": ["业务激活", "订单开通", "前台受理"],
        "exclude": ["卡单"],
        "priority": 70,
    },
    {
        "id": "MP-SIM-FAIL",
        "name": "手机卡办理报错/失败",
        "module": "手机卡入网",
        "fail_object": "手机卡/号码",
        "fail_nature": "办理报错失败",
        "systems": ["CRM", "BOSS"],
        "is_defect": True,
        "objects": ["手机卡", "号卡", "手机", "sim", "SIM"],
        "natures": ["报错", "失败", "无法办理", "禁止", "异常"],
        "stages": [],
        "exclude": ["卡单", "入网", "开通"],
        "priority": 71,
    },
    # —— 专线固话 ——
    {
        "id": "MP-LEASE",
        "name": "专线/固话开通异常",
        "module": "专线固话",
        "fail_object": "专线/固话",
        "fail_nature": "开通激活异常",
        "systems": ["CRM", "BOSS"],
        "is_defect": True,
        "objects": ["专线", "固话"],
        "natures": ["无法", "报错", "失败", "开通", "激活", "未开通"],
        "stages": ["业务激活", "订单开通"],
        "exclude": [],
        "priority": 80,
    },
    # —— 短信物联网 ——
    {
        "id": "MP-IOT",
        "name": "短信/物联网(CMIOT)业务异常",
        "module": "短信物联网",
        "fail_object": "短信/物联网卡",
        "fail_nature": "开通激活异常·数据不同步",
        "systems": ["短信平台", "CMIOT"],
        "is_defect": True,
        "objects": ["短信", "物联网", "CMIOT"],
        "natures": ["无法", "失败", "报错", "开通", "激活", "同步", "查不到"],
        "stages": ["业务激活", "订单开通", "数据同步"],
        "exclude": [],
        "priority": 90,
    },
    # —— 销户/过户/退费（跨模块终结类）——
    {
        "id": "MP-TERMINATE",
        "name": "销户/过户/退费办理异常",
        "module": "账户终结与变更",
        "fail_object": "账户/订单",
        "fail_nature": "销户过户退费失败",
        "systems": ["CRM", "计费系统", "订单中心"],
        "is_defect": True,
        "objects": ["销户", "过户", "退费", "退订", "退款"],
        "natures": ["失败", "报错", "无法", "禁止", "异常", "不符", "无法销", "无法过户"],
        "stages": [],
        "exclude": [],
        "priority": 100,
    },
    # —— 信控停机/黑名单/缴费 ——
    {
        "id": "MP-CREDIT",
        "name": "信控停机/黑名单/缴费恢复异常",
        "module": "信控与缴费",
        "fail_object": "账户状态",
        "fail_nature": "停机黑名单缴费异常",
        "systems": ["CRM", "计费系统", "BOSS"],
        "is_defect": True,
        "objects": ["信控", "停机", "黑名单", "失信", "缴费", "欠费"],
        "natures": ["停机", "全停", "恢复", "解除", "充值", "未恢复", "显示在使用", "禁止过户"],
        "stages": [],
        "exclude": ["开通", "激活"],
        "priority": 110,
    },
    # —— 增值权益 ——
    {
        "id": "MP-VALUEADD",
        "name": "增值/权益业务异常",
        "module": "增值权益",
        "fail_object": "增值/权益产品",
        "fail_nature": "开通激活异常",
        "systems": ["CRM", "订单中心"],
        "is_defect": True,
        "objects": ["增值", "权益"],
        "natures": ["无法", "失败", "报错", "开通", "激活", "未生效"],
        "stages": ["业务激活", "订单开通", "产品配置"],
        "exclude": [],
        "priority": 120,
    },
    # —— 订单提交/转单/派单/权限报错（跨系统的提交类异常）——
    {
        "id": "MP-ORDER-SUBMIT",
        "name": "订单提交/转单/派单/权限报错",
        "module": "订单开通流程",
        "fail_object": "订单/转单/权限",
        "fail_nature": "提交转单派单失败",
        "systems": ["订单中心", "CRM", "政企工作台"],
        "is_defect": True,
        "objects": ["转订单", "转单", "派单", "提交", "菜单", "审批", "处理人", "区县编码",
                     "REGION_ID", "AMS", "编排", "跨地市", "导出", "稽核"],
        "natures": ["失败", "报错", "无法提交", "无法选择", "处理中", "提示", "无法查到", "无法导出"],
        "stages": ["前台受理", "订单开通", "数据同步"],
        "exclude": ["回单", "完工", "在途"],
        "priority": 33,
    },
    # —— 政企工作台权限/登录异常 ——
    {
        "id": "MP-WORKBENCH",
        "name": "政企工作台权限/登录异常",
        "module": "政企工作台",
        "fail_object": "政企工作台/4A/工号",
        "fail_nature": "权限登录异常",
        "systems": ["政企工作台", "4A"],
        "is_defect": True,
        "objects": ["政企工作台", "4A", "网格通", "工号", "登录页面", "免审批"],
        "natures": ["权限", "登录", "已存在", "没有", "无法选择", "出库", "高额欠费"],
        "stages": ["业务激活", "前台受理"],
        "exclude": [],
        "priority": 130,
    },
    # —— 咨询类（非缺陷，隔离不进主 KPI）——
    {
        "id": "MP-CONSULT",
        "name": "使用/操作/规则咨询（非缺陷）",
        "module": "咨询类",
        "fail_object": "—",
        "fail_nature": "咨询问答",
        "systems": [],
        "is_defect": False,
        "objects": [],
        "natures": [],
        "stages": [],
        "exclude": [],
        "priority": 999,
    },
]


def get_module_problem(mp_id: str) -> Optional[Dict]:
    for m in MODULE_PROBLEMS:
        if m["id"] == mp_id:
            return m
    return None


def all_module_ids() -> List[str]:
    return [m["id"] for m in MODULE_PROBLEMS]


# 判定优先级排序（升序，命中即采用）
_SORTED = sorted(MODULE_PROBLEMS, key=lambda m: m["priority"])


def match_module_problem(point: str, fault_stage: Optional[str], category_l1: Optional[str]):
    """确定性闭集匹配：返回 (mp_id, confidence, reason)。

    - confidence: 'high' 对象+性质均显式命中；'medium' 性质由 fault_stage 回退；
      None 表示未匹配（需进入未归类/人工管理）。
    - 咨询类（category_l1 命中且非缺陷）单独隔离返回 MP-CONSULT。
    """
    point = point or ""
    stage = fault_stage or ""
    cat = category_l1 or ""

    # 咨询类隔离
    if cat in CONSULT_CATEGORY_L1:
        return ("MP-CONSULT", "high", "咨询类(一级分类=%s)" % cat)

    matched = None
    conf = None
    for m in _SORTED:
        # 排除词优先
        if any(ex in point for ex in m.get("exclude", [])):
            continue
        obj_hit = [o for o in m["objects"] if o in point]
        if not obj_hit:
            continue
        nat_hit = [n for n in m["natures"] if n in point]
        stage_hit = stage in m.get("stages", [])
        if nat_hit:
            matched = m
            conf = "high"
            break
        if stage_hit:
            matched = m
            conf = "medium"
            # 不 break：优先找有显式性质的更具体条目
            continue
    if matched:
        return (matched["id"], conf, "对象=%s;性质=%s" % ("/".join(obj_hit), "/".join(nat_hit) if nat_hit else "stage:%s" % stage))
    # 使用咨询（fault_stage）作为咨询类回退锚点：未命中任何缺陷条目时隔离
    if stage == "使用咨询":
        return ("MP-CONSULT", "high", "咨询类(fault_stage=使用咨询)")
    return (None, None, "无模块问题锚点(对象或失效性质未命中字典)")
