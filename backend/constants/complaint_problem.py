"""投诉问题点分析（方案 v4.2）——口径、判定规则与验收阈值的**唯一真相源**。

背景（2026-11-04 三次评估，老大批准「工单分析过程不依赖人」为最高约束）：
  v4.1 把精准押在「人逐单复核 / 人工确认队列 / 人工编制判定卡」上，与最高约束冲突。
  v4.2 改为：生成与判定分离 + 证据锚点强制 + 确定性规则优先 + 可复现 + 失败自动退化。
  本文件只放**口径与确定性规则**：不访问数据库、不调用语义通道、不含任何「等人看一眼」的分支。
  语义生成/判定是 D1~D3 的可插拔插件；插件不可用时链路照常跑完，产出「待自动补跑」清单。

单一真相源铁律：
  - 禁用词、结论词、阈值、正反例规则只在此声明一次，prompt / 服务 / 前端 / 脚本一律派生；
  - 机制词与环节词复用 constants/complaint_pattern.py，不另抄第二份；
  - 新增一条口径 = 本文件加一行，并同步方案文档与回归断言。

对应文档：docs/客诉工单分析总结与问题归类汇总方案.md（§1.3 / §2 / §3 / §5）
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from constants.complaint_pattern import MECHANISMS, STAGES

# 口径版本：随每条结论留痕，用于「同输入 + 同口径版本 → 同结果」的可复现校验
POLICY_VERSION = "v4.2-20261104"

# ── §2.1 一句描述的句式 ─────────────────────────────────────────
DESC_MIN_CHARS = 15
DESC_MAX_CHARS = 40
DESC_HARD_MAX_CHARS = 45
# 三要素（机器可判的键名；判定卡、证据锚点、门禁映射都沿用这组键，禁另造）
ELEMENT_KEYS: Tuple[str, ...] = ("object", "action", "failure", "trigger")
ELEMENT_LABELS: Dict[str, str] = {
    "object": "具体对象",
    "action": "动作/场景",
    "failure": "可观察失败",
    "trigger": "触发条件",
}

# ── §2.2 硬性禁止 ───────────────────────────────────────────────
# 这些词可作句中的谓语，不得作整句名称或整句只有「对象-机制」。
BANNED_STANDALONE_TERMS: Tuple[str, ...] = (
    "其他", "综合", "异常", "问题", "失败", "不一致", "系统问题", "数据问题",
    "配置错误", "规则不合理", "使用咨询", "未同步", "未回写", "未归档", "未生成",
)
# 与 complaint_rootcause.GENERIC_TERMS 取并集，避免两处清单漂移（此处只追加不复制）
from constants.complaint_rootcause import GENERIC_TERMS  # noqa: E402  (置于常量后以便注释分组)

GENERIC_WORDS: Tuple[str, ...] = tuple(dict.fromkeys(
    BANNED_STANDALONE_TERMS + GENERIC_TERMS + ("未下发", "未级联", "未触发", "无缺陷")
))

# 不得出现在 L2 一句描述里的用户级信息（L1 允许，且鼓励带）
_USER_LEVEL_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"\d{8,}"),               # 订单号 / 账号 / 协议号 / 长编号
    re.compile(r"1[3-9]\d{9}"),          # 手机号
    re.compile(r"\d+元|\d+\.\d{2}元"),   # 具体金额
)

# §2.5 诉求动词（L1 问题点必须含「客户/一线要办的事」）
# 2026-11-05 真实库 20 单诊断补词：「客户商务快线发施工单」「选同样的地址」
# 这类真实业务动作此前全被判 P01（未写出诉求），属确定性漏词而非模型生成问题。
APPEAL_VERBS: Tuple[str, ...] = (
    "办", "查", "退", "改", "开", "装", "催", "申请", "查询", "提交",
    "销户", "复机", "退订", "变更", "激活", "派发", "回单", "缴费", "充值",
    "搜索", "关联", "核实", "处理", "开通", "删除", "生成", "回传",
    "办理", "发单", "选", "选择", "勾选", "领取", "录入", "补录", "添加",
    "上传", "下载", "同步", "核查", "协助", "反馈", "找回", "恢复", "调取",
    "导出", "打印", "签署", "绑定", "解绑", "续费", "过户", "移机", "退费",
    "加急", "开户", "催收", "报障", "咨询", "纠错",
)

# 不得作描述收尾的结论式表述（§2.5：写的是「是否缺陷的结论」，不是投诉问题点）
CONCLUSION_ENDINGS: Tuple[str, ...] = (
    "非系统缺陷", "系统无缺陷", "无系统错误", "非缺陷",
    "属正常业务规则", "属正常", "规则解释", "属规则解释",
    "无需处理", "不需处理", "信息不足", "原因不明", "未定位", "待查",
)

# 禁「多问题点并列」：一句里串两个不同失败表现。
# 顿号不在此列：「系统显示正使用、客户端显示停机」是同一失败表现的两侧对比，
# 属合法写法；真正的多问题点由 D2 按证据要素数量判定，D0 不做语义猜测。
MULTI_ISSUE_MARKERS: Tuple[str, ...] = ("；", "以及", "并且", "同时", " / ")

# 「可观察失败」的弱词面标记（强校验由证据锚点完成，见 D1/D3）
# 2026-11-05 真实库诊断补词：规则阻断/审批拦截是「被什么规则挡住」的可观察事实
# （方案 §2.5 明确咨询类也算事实），此前「被要求请走审批流程」被判 D07。
FAILURE_MARKERS: Tuple[str, ...] = (
    "提示", "报错", "显示", "仍", "停在", "滞留", "未", "无", "空", "收不到",
    "查不到", "搜不到", "无法", "不能", "没有", "失败", "拦截", "超时",
    "不一致", "重复", "缺失", "多收费", "不生效", "未收到", "未回传",
    "阻断", "受阻", "卡在", "不支持", "不允许", "需先", "请走", "需走",
    "被要求", "被退回", "驳回", "不通过", "无记录", "查无", "掉单",
    "未到账", "未生效", "未开通", "空白", "未释放", "无法触发", "只选了",
    "审批拦截", "走审批", "退不了", "办不了", "回不了单", "提交不了",
)

# 泛词剥离后有效字数下限：低于此值说明整句只是「对象-机制」或空话
MIN_EFFECTIVE_CHARS = 8

# 「对象-机制」形态：两个短词用连字符直接拼接（「订单-未归档」这类旧名称）
_SHORT_LABEL_RE = re.compile(r"^[\u4e00-\u9fa5A-Za-z0-9]{1,8}\s*[-－—]\s*[\u4e00-\u9fa5A-Za-z0-9]{1,8}$")

# ── §3 归入四项 / 排除七条（机器可判条件，服务层按 code 实现，禁另造清单）──
INCLUDE_RULES: Tuple[Dict[str, str], ...] = (
    {"code": "I1", "name": "主诉相同", "criterion": "要解决的是同一个卡点，不是都提到同一个词"},
    {"code": "I2", "name": "断点相同", "criterion": "失败发生在同一业务动作、同一环节"},
    {"code": "I3", "name": "可观察表现相同", "criterion": "报错文本/状态值/缺失字段/未收到方一致或同义"},
    {"code": "I4", "name": "修复落点相同", "criterion": "可指认到一个字段、一条规则、一次修复动作或一处提示"},
)

EXCLUDE_RULES: Tuple[Dict[str, str], ...] = (
    {"code": "E1", "name": "现象相似但断点不同", "criterion": "未下发/未接收/未回传/未释放四者必分"},
    {"code": "E2", "name": "缺陷与咨询混装", "criterion": "缺陷与规则咨询、操作指引不得同类"},
    {"code": "E3", "name": "触发条件本质不同", "criterion": "同现象不同触发条件必分"},
    {"code": "E4", "name": "上位词相同", "criterion": "订单与订单状态等只共享上位词不得合并"},
    {"code": "E5", "name": "系统名/环节名/关键词相同", "criterion": "不得作为归入依据"},
    {"code": "E6", "name": "证据不足", "criterion": "无报错/无状态值/无处理结论 → 未归类清单"},
    {"code": "E7", "name": "兜底吸收", "criterion": "不得设其他/综合/零星/待定类，不得近似并入"},
)

# §7.3 指称词表（拼写层）：只做写法归一，不命名、不作归并键、不限制新对象出现。
# 未登记的新对象/新说法原样保留，因此新业务不会被词表挡住。
TERM_SYNONYMS: Dict[str, str] = {
    "施工工单": "施工单", "派单": "施工单",
    "未触发": "未生成", "没生成": "未生成", "无单号": "未生成",
    "没收到": "未收到", "未接收到": "未收到",
    "无法提交": "拦截", "被拦截": "拦截",
    "已回复": "已回单", "已回传": "已回单",
    "状态不同步": "状态不一致", "数据不一致": "状态不一致",
}

# 忽略差异（不因此拆类）
IGNORABLE_DIFFS: Tuple[str, ...] = (
    "措辞差异", "单号/账号差异", "客户差异", "地市差异", "日期差异",
    "金额差异", "同一报错的不同写法",
)

# ── §3.5 结构化判定卡（机器可判，系统建类时自动生成，禁人工编制）──
CARD_REQUIRED_FIELDS: Tuple[str, ...] = (
    "description", "version", "effective_from",
    "appeal", "breakpoint", "observable", "fix_point",
    "positives", "negatives", "boundary",
)
CARD_POSITIVE_MIN = 2
CARD_NEGATIVE_MIN = 2
CARD_EXAMPLE_FIELDS: Tuple[str, ...] = ("ticket_no", "evidence", "reason", "exclude_code")

# 修复落点必须是可指认对象；这些空话视为「未判定」
VAGUE_FIX_POINTS: Tuple[str, ...] = (
    "优化流程", "完善机制", "系统改造", "加强管理", "提升体验", "后续优化", "需进一步排查",
)

# ── §7.3 新类准入三问 / 首现类 ──────────────────────────────────
ADMISSION_RULES: Tuple[Dict[str, str], ...] = (
    {"code": "A1", "question": "是否存在旧类描述里没有的新的可观察失败？"},
    {"code": "A2", "question": "是否有独立且可指认的修复落点？"},
    {"code": "A3", "question": "是否有至少 1 张能完整举证的真实工单？"},
)
FIRST_SIGHT_MIN_MEMBERS = 1     # 1 单也立类，不降格、不并「其他」、不删除
NO_CLUSTER_LIMIT = True         # 类数不设上限、不设配额、不触发压缩

# ── §1.3 自动化五条硬约束 ───────────────────────────────────────
AUTOMATION_CONSTRAINTS: Tuple[str, ...] = (
    "生成与判定分离", "证据锚点强制", "确定性规则优先", "可复现", "失败自动退化",
)
# 失败自动退化的唯一处置：不臆造、不猜关键词、不转人工，进未归类清单待自动补跑
DEGRADED_STATUS = "pending_auto_rerun"
DEGRADED_REASON_CHANNEL = "语义通道不可用"
DEGRADED_REASON_EVIDENCE = "证据不足"
UNCLASSIFIED_STATUS = "unclassified"

# 明确禁止的人工触点（出现即违反最高约束，供验收闸门检测）
FORBIDDEN_HUMAN_TOUCHES: Tuple[str, ...] = (
    "manual_review", "human_confirm", "human_blind_eval", "manual_card",
    "manual_rewrite", "human_arbitration", "manual_sample_pick", "reviewer",
)

# ── §5 验收阈值（唯一一处定义；数值与方案逐项对应）────────────────
ACCEPTANCE: Dict[str, float] = {
    "no_human_touch": 100.0,          # 最高一票否决
    "point_pass_rate": 100.0,         # 逐单问题点合格率
    "gate_coverage": 100.0,           # 归入门禁覆盖率
    "card_complete": 100.0,           # 判定卡完备率
    "evidence_anchor": 100.0,         # 证据锚点覆盖率
    "separation": 100.0,              # 生成/判定分离率
    "reproducible": 99.0,             # 可复现率（下限）
    "desc_concrete": 100.0,           # 描述具体率
    "accuracy": 95.0,                 # 归入准确率（下限）
    "gate_leak_max": 2.0,             # 门禁漏判率（上限）
    "overwide_max": 3.0,              # A 型过宽率（上限）
    "mispoint_max": 1.0,              # B 型错指率（上限）
    "hardstuff_max": 0.0,             # C 型硬塞率（上限，一票否决）
    "one_ticket_one_class": 100.0,
    "unclassified_max": 10.0,         # 未归类率（上限，分母=应归类单量）
    # 2026-11-05 分母澄清：写不出合格问题点的单不藏在 100% 合格率里，
    # 单列「自动拒识率」与「证据不足率」，同样受闸门约束、同样进未归类清单。
    "auto_reject_max": 10.0,          # 自动拒识率（上限）
    "count_closure": 100.0,           # 数量闭合（必要但不充分）
    "content_closure": 95.0,          # 内容闭合（下限）
    "head_rerun": 100.0,
    "drift_rerun": 100.0,
    "first_sight_admission": 100.0,
    "goldset_new_coverage": 100.0,
    "representative_verifiable": 100.0,
    # 2026-11-05 分母澄清新增：「已分析单量 / 全部工单」。语义通道不可用或漏返
    # 的单属于「分析未完成」，不进任何质量指标的分母，但由本指标如实约束——
    # 通道全挂时覆盖率 0，整期自动拦截，不靠把待补跑单算成「不合格」蒙混。
    "analysis_coverage": 95.0,
}
# 六项一票否决（任一不达标 → 自动闸门拦截，不得退回人工重判）
VETO_KEYS: Tuple[str, ...] = (
    "no_human_touch", "point_pass_rate", "gate_coverage",
    "card_complete", "evidence_anchor", "separation",
)
# §5 性质列「观测 + 禁止掩盖」：超标只如实标注并列出未归类清单，不拦截发布，
# 更不能为压数值而塞兜底类。此前实现误把它们当硬门槛，导致真实库永远不发布。
OBSERVATION_KEYS: Tuple[str, ...] = ("unclassified_max", "auto_reject_max")
HEAD_CLASS_MIN_CNT = 20              # 头部类阈值
WEEKLY_SAMPLE_SIZE = 70              # 自动分层抽样量
GOLDSET_CORE_SIZE = 50               # 金标集核心样本量
GATE_LEAK_REWRITE = True             # 漏判自动回写为判定卡反例
DRIFT_MAX_MISMATCH = 2               # 同类错配累计 2 单 → 描述自动作废


# ── 确定性规则函数（不访问 DB、不调语义通道、同输入必同输出）────────
def conclusion_hits(text: str) -> List[str]:
    """命中「结论式收尾」的词（§2.5）。只做包含匹配，判定交给服务层。"""
    s = (text or "").strip()
    return [w for w in CONCLUSION_ENDINGS if w in s]


def has_user_level_info(text: str) -> bool:
    """L2 描述是否含用户级信息（§2.2 第 2 条）。"""
    s = text or ""
    return any(p.search(s) for p in _USER_LEVEL_PATTERNS)


def effective_chars(text: str) -> int:
    """剥离泛词后的有效字数：低于阈值说明整句是空话或「对象-机制」标签。"""
    s = text or ""
    for w in GENERIC_WORDS:
        s = s.replace(w, "")
    return len(re.sub(r"[\s，,。.、；;：:！!？?「」\"'（）()\-－—]", "", s))


def description_violations(text: str, *, allow_user_level: bool = False,
                           min_chars: int | None = None,
                           max_chars: int | None = None) -> List[str]:
    """§2 一句描述规范的**确定性**校验，返回违规码列表；空列表 = 通过。

    只判不需要语义理解的部分：句式、长度、并列、泛词、用户级信息、结论式收尾、
    可观察失败词面。三要素与证据锚点的强校验由 D1/D3 完成（本函数不含任何人判）。
    L2 归类描述与 L1 逐单问题点共用本函数，但 L1 允许带账号/单号且可更长，
    故用 allow_user_level / min_chars / max_chars 三个参数区分，避免第二套规则。
    """
    s = (text or "").strip()
    lo = DESC_MIN_CHARS if min_chars is None else min_chars
    hi = DESC_HARD_MAX_CHARS if max_chars is None else max_chars
    out: List[str] = []
    if not s:
        return ["D00 描述为空"]
    if len(s) < lo:
        out.append(f"D01 描述过短（{len(s)}字 < {lo}）")
    if len(s) > hi:
        out.append(f"D01 描述过长（{len(s)}字 > {hi}）")
    # 夹在汉字之间的「？」是生僻字占位符（如「康？兴」），不是句末标点；
    # 2026-11-05 真实库诊断发现它会被误判成多句，导致整单被拦。
    endings = re.sub(r"(?<=[\u4e00-\u9fa5])[？?](?=[\u4e00-\u9fa5])", "", s)
    if endings.count("。") + endings.count("！") + endings.count("？") > 1:
        out.append("D02 不是一句话（多个句末标点）")
    if any(m in s for m in MULTI_ISSUE_MARKERS):
        out.append("D03 多问题点并列（一句一事）")
    if not allow_user_level and has_user_level_info(s):
        out.append("D04 含用户级信息（账号/单号/金额只留在 L1）")
    hits = conclusion_hits(s)
    if hits:
        out.append("D05 结论式表述：" + "/".join(hits[:3]))
    if effective_chars(s) < MIN_EFFECTIVE_CHARS or _SHORT_LABEL_RE.match(s):
        out.append("D06 泛词单独作描述或整句只是「对象-机制」标签")
    if not any(m in s for m in FAILURE_MARKERS):
        out.append("D07 无「可观察失败」词面（报错/状态/缺失/未收到等）")
    return out


def check_description(text: str) -> Dict[str, Any]:
    """D0 对外主入口：L2 归类的一句描述是否可发布。"""
    v = description_violations(text)
    return {"ok": not v, "violations": v, "version": POLICY_VERSION}


def check_l1_point(text: str) -> Dict[str, Any]:
    """L1 逐单问题点的确定性校验：允许账号/单号/报错原文，长度放宽到 120 字。"""
    v = description_violations(text, allow_user_level=True, min_chars=12, max_chars=120)
    return {"ok": not v, "violations": v, "version": POLICY_VERSION}


def is_vague_fix_point(text: str) -> bool:
    """修复落点是否不可指认（§3.1 第 4 项：视为未判定，不得据此归入）。"""
    s = (text or "").strip()
    return (not s) or any(w in s for w in VAGUE_FIX_POINTS)


def meta() -> Dict[str, Any]:
    """供 prompt / 前端 / 服务派生，避免另写第二份清单。"""
    return {
        "policy_version": POLICY_VERSION,
        "desc_chars": [DESC_MIN_CHARS, DESC_MAX_CHARS, DESC_HARD_MAX_CHARS],
        "element_keys": list(ELEMENT_KEYS),
        "banned_standalone": list(BANNED_STANDALONE_TERMS),
        "conclusion_endings": list(CONCLUSION_ENDINGS),
        "include_rules": [dict(r) for r in INCLUDE_RULES],
        "exclude_rules": [dict(r) for r in EXCLUDE_RULES],
        "card_required": list(CARD_REQUIRED_FIELDS),
        "admission": [dict(r) for r in ADMISSION_RULES],
        "automation_constraints": list(AUTOMATION_CONSTRAINTS),
        "acceptance": dict(ACCEPTANCE),
        "veto_keys": list(VETO_KEYS),
        "mechanisms": list(MECHANISMS),
        "stages": list(STAGES),
    }
