"""客诉工单分析流水线 —— 全局配置（口径参数的唯一来源）。

改动此处即改动全流水线口径，脚本内禁止另写阈值/路径常量。
"""

from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────────
# 原始导出归档根目录：文件类数据一律落 D:\项目 之下（受 NAS 整盘备份覆盖）
ARCHIVE_ROOT = Path(r"D:\项目\个人工作台系统\data\complaint")
# 报告输出目录
REPORT_DIR = Path(r"D:\项目\个人工作台系统\docs\客诉周报")


# ── 判定阈值 ──────────────────────────────────────────────────
# 批量异常簇：同一二级场景 + 同一自然日，工单数 >= 阈值 → 判为批量异常
BATCH_DAILY_THRESHOLD = 5
# 批量簇「组织修复」判定：簇内解决方案出现下列话术，视为已采取批量处置。
# 注意：不含裸「批量」二字——「批量转派/批量分派」是逐单流转动作，不是修复。
BATCH_FIX_KEYWORDS = ("批量同步", "批量修复", "批量处理", "批量补", "批量开通",
                      "统一处理", "集中修复", "全量同步", "一键处理", "一键修复")
# 出现下列话术说明只是逐单转派，不计入组织修复
BATCH_TRANSFER_KEYWORDS = ("批量转派", "批量分派")

# 完结状态（小信导出真实取值只有 已回复/关闭/预处理；「已回复」不等于结单）
TERMINAL_STATUSES = ("关闭", "已归档", "已办结", "已关闭", "已完成")

# 滞留：创建超过 N 天仍未完结
RETENTION_DAYS = 3
# 处理链条过长：处理意见条数 >= N
LONG_CHAIN_OPINIONS = 5
# 首轮返工：首条处理意见出现下列「要材料」话术 → 视为首轮无效返工
REWORK_KEYWORDS = ("请提供", "请上传", "请确认", "请核实", "麻烦提供", "麻烦确认",
                   "请详细说明", "附件无法打开", "请补充")
# 互推外部：首条处理意见出现下列话术
PUSHOUT_KEYWORDS = ("请联系网络部", "请咨询网络部", "请前台", "请走审批", "属于正常业务规则",
                    "请自行", "操作咨询")
# 挂起类回复（未在工单内闭环）
PENDING_KEYWORDS = ("预计1-2个工作日", "预计1-3个工作日", "预计本周内", "正在流程处理中",
                    "预计今天", "次日处理")

# ── 措施有效性 ────────────────────────────────────────────────
DEFAULT_TARGET_DROP_PCT = 50.0   # 目标降幅（%）
DEFAULT_VERIFY_WEEKS = 4         # 连续观察周数
BASELINE_WEEKS = 4               # 基线取措施上线前 N 周均值

# ── 共性问题识别（problems.py 唯一读取处；R1 日阈值复用 BATCH_DAILY_THRESHOLD） ──
PROBLEM_BATCH_WEEK_MIN = 8       # R1 批量簇：除日阈值外，当周该场景累计 >= 8 单
PROBLEM_TOP_SCENE_N = 3          # R2 场景TOP：取当周场景 TOP N
PROBLEM_TOP_SCENE_MIN = 8        # R2 且单量 >= 8（防小基数误报）
PROBLEM_SURGE_PCT = 100.0        # R3 环比激增：环比 >= 100%
PROBLEM_SURGE_MIN = 5            # R3 且当周绝对量 >= 5
PROBLEM_CLOSE_QUIET_WEEKS = 2    # 闭环建议：连续 N 周零复发
PROBLEM_ACTIVE_MAX_WEEKS = 12    # 在办超 N 周 → 台账/周报标"长期未闭环"
# 多规则同命中时的主规则强度序（高→低）
PROBLEM_SOURCE_STRENGTH = ("batch_cluster", "surge", "top_scene", "recur")

# ── 接口 ──────────────────────────────────────────────────────
API_BASE = "http://127.0.0.1:8000/api/v1"


# ── 列名映射（小信工单导出模板，字段名变则只改这里） ──────────
COL_TICKET_NO = "BOMC流水号"
COL_CREATED = "创建时间"
COL_CITY = "申告地市"
COL_CHANNEL = "渠道"
COL_APPEAL = "申告类别"
COL_BIZ_ATTR = "工单属性"
COL_CONTENT = "工单内容"
COL_SOLUTION = "解决方案历史"
COL_HANDLER = "处理人"
COL_UNIT = "处理单位"
COL_DISPATCH = "派单次数"
COL_STATUS = "状态"
COL_SATISFY = "处理满意度评分"
COL_HEADER_CANDIDATES = (COL_TICKET_NO, COL_CONTENT, COL_CREATED)
