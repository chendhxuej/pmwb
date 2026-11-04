"""客诉 v4.2 语义生成插件（D5-1）——「一句逐单投诉问题点」的唯一语义生成入口。

设计红线（方案 §1.3「失败自动退化」，优先级最高）：

  1. **只用真实语义通道**。`call_best_available` 在所有提供方失败时会返回
     ``used_llm=False`` + 一段「已生成规则模板版（非 AI 润色）」的 notice；
     那段文本**不是语义结果**，绝不能当作逐单问题点。本插件见到
     ``used_llm=False`` 立即判定通道不可用、清空缓存并停止后续批次调用。
  2. **不降级为关键词猜测**：通道不可用时由编排层把 generator 置为 None，
     D1 自动标 ``pending_auto_rerun``，不排队等人、不编造。
  3. **生成与判定分离**：本插件只产出文本；是否成立完全由 D1 的确定性判定通道
     （``problem_point.validate_point``）裁决，本文件不做任何自证或置信度打分。
  4. **证据锚点可对齐**：prompt 强制要求引用原文原词，使 D1 的连续 4 字锚点校验
     有据可依；模型漏返的单返回空串，由编排层标「待自动补跑」而非硬猜。

批量合并调用以控成本；``caller`` 可注入，便于单测。通道恢复后由编排层自动补跑。
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from constants import complaint_problem as P
from services.llm_provider import call_best_available

logger = logging.getLogger(__name__)

BATCH_SIZE = 20                 # 与 config.LLM_BATCH_SIZE 对齐，减少全量重跑调用次数
TEXT_LIMIT = 800                # 单工单投诉原文送入上限
SOLUTION_LIMIT = 400            # 处理过程送入上限
EVIDENCE_LIMIT = 6              # 每单最多带几条证据片段
EVIDENCE_CHARS = 60             # 单条证据片段截取长度
REQUEST_TIMEOUT = 45            # 单次语义调用超时（秒）
MAX_BATCHES = 0                 # 0=不限；演练可限量，防止意外全量调用

CHANNEL_NAME = "llm-point-v1"

# ---------------------------------------------------------------------------
# 限流退避（D7 全量重跑兜底）：429 / 「频率限制」不算通道不可用，应等到重置后重试
# ---------------------------------------------------------------------------
_RATE_LIMIT_PATTERNS = ("429", "频率限制", "使用量已超出", "rate limit",
                        "too many requests", "quota", "请求过于频繁", "限流")
_RESET_TIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})")
MAX_RATE_LIMIT_RETRIES = 40
_RATE_MAX_WAIT = 6 * 3600          # 单次退避上限 6 小时
_RATE_FLOOR_WAIT = 60             # 无法解析重置时间时的指数退避底


def _is_rate_limited(notice: str, err: Optional[Exception]) -> bool:
    blob = (str(notice or "") + " " + str(err or "")).lower()
    return any(p in blob for p in _RATE_LIMIT_PATTERNS)


def _wait_seconds_for_reset(notice: str) -> int:
    """解析『将在 … 重置』的时间，返回需等待秒数（含 15s 缓冲）；解析不出返回 0。"""
    m = _RESET_TIME_RE.search(notice or "")
    if m:
        try:
            reset = datetime.strptime(m.group(1).replace("T", " "), "%Y-%m-%d %H:%M:%S")
            wait = (reset - datetime.now()).total_seconds()
            if wait > 0:
                return min(int(wait) + 15, _RATE_MAX_WAIT)
        except Exception:  # noqa: BLE001
            pass
    return 0


def _backoff_sleep(attempt: int) -> int:
    return min(_RATE_FLOOR_WAIT * (2 ** attempt), 10 * 60)

_SYSTEM_PROMPT = (
    "你是电信运营商政企/商客业务客诉工单的分析员。任务：为每张工单写出「一句逐单投诉问题点」。\n"
    "【句式】15~40 字，一句话：具体业务对象 + 客户/一线在做什么动作或处于什么场景 + "
    "出现了什么可观察的失败（报错原文、状态值、数据不一致、缺失、未生成、被拦截等）。\n"
    "【必须】使用输入里「投诉原文」或「证据片段」中出现过的原词描述对象与失败表现"
    "（至少含一处连续 4 字原词），并写出客户/一线要办的事"
    "（申请、办理、查询、开通、缴费、激活、派单、回单、提交、变更、退订等动词）。\n"
    "【禁止】① 只写「对象-机制」式标签（如「订单-未归档」「权限-使用咨询」）；"
    "② 用「其他」「使用咨询」「配置错误」「规则不合理」「系统异常」等泛词充当问题点；"
    "③ 以「属正常业务规则」「非系统缺陷」「无需处理」「已解释」等结论收尾；"
    "④ 写账号、订单号、单号、客户名、金额等用户级信息；"
    "⑤ 一句里并列多个互不相干的问题点；⑥ 编造原文里没有的事实。\n"
    "【证据不足】原文没有报错、状态值、缺失、拦截等可观察失败时，point 输出空串，不要猜。\n"
    "【输出】仅输出 JSON，不要任何其它文字："
    '{"results":[{"no":"工单号","point":"一句问题点"}]}'
)


def _parse_results(raw: str) -> List[Dict[str, str]]:
    """兼容模型带 ```json 包裹或前后解释文字的回包；解析失败一律视为漏返。"""
    s = (raw or "").strip()
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return []
    items = data.get("results") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    out: List[Dict[str, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        no = str(it.get("no") or "").strip()
        point = str(it.get("point") or "").strip().replace("\n", " ").replace("\r", " ")
        if no:
            out.append({"no": no, "point": point[:120]})
    return out


def _clip(text: str, limit: int) -> str:
    s = (text or "").replace("\r", " ").replace("\n", " ").strip()
    return s[:limit]


class SemanticPointGenerator:
    """D1 ``generator`` 插件：``__call__(ticket, spans) -> 一句问题点或空串``。

    ``prefetch`` 先批量生成并缓存；通道不可用则 ``available=False``，编排层据此
    把 generator 置 None，让 D1 自动退化到 ``pending_auto_rerun``。
    """

    channel_name = CHANNEL_NAME

    def __init__(self, db: Session, *, batch_size: int = BATCH_SIZE,
                 text_limit: int = TEXT_LIMIT, timeout: int = REQUEST_TIMEOUT,
                 max_batches: int = MAX_BATCHES,
                 caller: Optional[Callable[..., Dict[str, Any]]] = None):
        self.db = db
        self.batch_size = max(1, int(batch_size))
        self.text_limit = max(200, int(text_limit))
        self.timeout = timeout
        self.max_batches = max(0, int(max_batches))
        self._caller = caller or call_best_available
        self._cache: Dict[str, str] = {}
        self.available: Optional[bool] = None   # None=未探测 / True / False
        self.notice = ""
        self.provider: Optional[str] = None
        self.calls = 0
        self.generated = 0
        self.policy_version = P.POLICY_VERSION

    def _user_prompt(self, batch: List[Dict[str, Any]],
                     evidence_map: Dict[str, List[Dict[str, Any]]],
                     feedback: Optional[Dict[str, List[str]]] = None) -> str:
        blocks: List[str] = []
        for t in batch:
            no = str(t.get("ticket_no") or "")
            spans = evidence_map.get(no) or []
            ev = " | ".join(_clip(str(s.get("text", "")), EVIDENCE_CHARS)
                            for s in spans[:EVIDENCE_LIMIT] if s.get("text"))
            block = (
                f"【工单】单号：{no}\n"
                f"投诉原文：{_clip(str(t.get('content') or ''), self.text_limit)}\n"
                f"处理过程：{_clip(str(t.get('solution_history') or ''), SOLUTION_LIMIT)}\n"
                f"证据片段：{ev or '（无）'}"
            )
            if feedback and feedback.get(no):
                gs = feedback[no]
                blob = " ".join(gs)
                block += "\n上一轮未过自动判定的原因：" + "；".join(gs[:4])
                hints: List[str] = []
                if "P02" in blob:
                    hints.append("必须原样复制上方「证据片段」里至少连续 4 个汉字，不要同义改写")
                if "D07" in blob:
                    hints.append("必须写出一处可观察失败：报错/状态值/未收到/无法/不一致/缺失/被拦截")
                if "D03" in blob:
                    hints.append("只写一个问题点，不要用分号、以及、并且并列")
                if "P01" in blob:
                    hints.append("必须写出客户或一线要办的事：办理/查询/申请/提交/开通/核实")
                hints.append("只写一句、不以结论收尾、不写账号单号")
                block += "\n改写要求：" + "；".join(hints) + "。"
            blocks.append(block)
        lead = "请逐单写出一句投诉问题点，单号必须原样回传，不要漏单。"
        if feedback:
            lead = "以下工单上一轮未通过确定性判定，请逐单按标注的缺口改写（仍需原词锚定）。"
        return (lead + "\n\n" + "\n\n".join(blocks))

    def has(self, ticket_no: str) -> bool:
        """该单是否在回包里出现（含显式空串），用于区分「证据不足」与「漏返」。"""
        return str(ticket_no) in self._cache

    def prefetch(self, tickets: List[Dict[str, Any]],
                 evidence_map: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> bool:
        """批量生成并缓存。返回通道是否可用；不可用时**立即停止**（不做无谓重试）。"""
        self._cache.clear()
        self.available = None
        self.notice = ""
        self.provider = None
        self.calls = 0
        self.generated = 0
        evidence_map = evidence_map or {}
        if not tickets:
            self.available = False
            self.notice = "无待分析工单"
            return False

        offsets = list(range(0, len(tickets), self.batch_size))
        if self.max_batches:
            offsets = offsets[:self.max_batches]
        last_err_notice = ""
        for bi, i in enumerate(offsets):
            batch = tickets[i:i + self.batch_size]
            res = self._invoke(batch, evidence_map)
            self.calls += 1
            if not res.get("used_llm"):
                self.available = False
                self.notice = str(res.get("notice") or "语义通道不可用")[:500]
                self._cache.clear()      # 绝不让「规则模板版」混入语义结果
                return False
            self.provider = res.get("provider_name") or self.provider
            parsed = _parse_results(str(res.get("text") or ""))
            if bi == 0 and not any(x["point"] for x in parsed):
                # 回包格式/模型不匹配时立即停，避免上百批空转烧 token（真实库实测教训）
                self.available = False
                self.notice = "语义通道回包无法解析为逐单问题点（首批 0 条有效结果），已停止后续批次"
                self._cache.clear()
                return False
            for item in parsed:
                # 空串也要缓存：它代表模型按 §1.3 判「证据不足」，与漏返不同
                self._cache[item["no"]] = item["point"]
        self.generated = sum(1 for v in self._cache.values() if v)
        self.available = True
        return True

    def _invoke(self, batch: List[Dict[str, Any]],
                evidence_map: Dict[str, List[Dict[str, Any]]],
                feedback: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
        """带限流退避的语义通道调用。

        命中 429/频率限制 → 解析重置时间（或指数退避）后重试，绝不立即判死；
        仅当非限流错误、或退避耗尽仍限流时才返回 ``used_llm=False``。
        """
        last_notice = ""
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            try:
                res = self._caller(self.db, _SYSTEM_PROMPT,
                                   self._user_prompt(batch, evidence_map, feedback),
                                   timeout=self.timeout)
                err: Optional[Exception] = None
            except Exception as exc:  # noqa: BLE001 —— 通道异常按不可用/限流处理
                logger.warning("客诉语义通道调用异常：%s", str(exc)[:200])
                res = {"used_llm": False, "notice": str(exc)[:300], "text": ""}
                err = exc
            if res.get("used_llm"):
                return res
            notice = str(res.get("notice") or "")
            if _is_rate_limited(notice, err):
                wait = _wait_seconds_for_reset(notice)
                if wait <= 0:
                    wait = _backoff_sleep(attempt)
                logger.warning("客诉语义通道触发频率限制，第 %d/%d 次重试前等待 %d 秒",
                               attempt + 1, MAX_RATE_LIMIT_RETRIES, wait)
                time.sleep(wait)
                last_notice = notice
                continue
            # 非限流不可用：立即返回，交由编排层按通道不可用处理
            res.setdefault("notice", "语义通道不可用")
            return res
        return {"used_llm": False, "notice": last_notice or "语义通道持续频率限制", "text": ""}

    def regenerate(self, tickets: List[Dict[str, Any]],
                   evidence_map: Dict[str, List[Dict[str, Any]]],
                   feedback: Dict[str, List[str]],
                   max_batches: int = 0) -> Dict[str, Any]:
        """自动二轮改写（不依赖人）：把每单的确定性判定缺口回灌给模型重生成。

        只覆盖本轮回包里出现且非空的单；通道失败或回包无有效结果时原样保留，
        由编排层把未解决的单标「自动拒识」并写明缺口，绝不无限循环、绝不转人工。
        """
        offsets = list(range(0, len(tickets), self.batch_size))
        if max_batches:
            offsets = offsets[:max_batches]
        changed = 0
        batches = 0
        for i in offsets:
            batch = tickets[i:i + self.batch_size]
            res = self._invoke(batch, evidence_map, feedback)
            self.calls += 1
            batches += 1
            if not res.get("used_llm"):
                break
            parsed = _parse_results(str(res.get("text") or ""))
            if not any(x["point"] for x in parsed):
                break           # 二轮无有效回包即停，不空转烧 token
            for item in parsed:
                if item["point"] and item["no"] in self._cache:
                    self._cache[item["no"]] = item["point"]
                    changed += 1
        return {"batches": batches, "changed": changed, "calls": self.calls}

    def __call__(self, ticket: Dict[str, Any], spans: List[Dict[str, Any]]) -> str:
        """D1 生成入口；漏返返回空串（编排层标待自动补跑，绝不猜）。"""
        return self._cache.get(str(ticket.get("ticket_no") or ""), "")

    def summary(self) -> Dict[str, Any]:
        return {"channel": CHANNEL_NAME, "available": self.available,
                "provider": self.provider, "calls": self.calls,
                "generated": self.generated, "notice": self.notice,
                "batches_limit": self.max_batches,
                "policy_version": self.policy_version}
