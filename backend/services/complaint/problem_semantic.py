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
                     evidence_map: Dict[str, List[Dict[str, Any]]]) -> str:
        blocks: List[str] = []
        for t in batch:
            no = str(t.get("ticket_no") or "")
            spans = evidence_map.get(no) or []
            ev = " | ".join(_clip(str(s.get("text", "")), EVIDENCE_CHARS)
                            for s in spans[:EVIDENCE_LIMIT] if s.get("text"))
            blocks.append(
                f"【工单】单号：{no}\n"
                f"投诉原文：{_clip(str(t.get('content') or ''), self.text_limit)}\n"
                f"处理过程：{_clip(str(t.get('solution_history') or ''), SOLUTION_LIMIT)}\n"
                f"证据片段：{ev or '（无）'}"
            )
        return ("请逐单写出一句投诉问题点，单号必须原样回传，不要漏单。\n\n"
                + "\n\n".join(blocks))

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
        for bi, i in enumerate(offsets):
            batch = tickets[i:i + self.batch_size]
            try:
                res = self._caller(self.db, _SYSTEM_PROMPT,
                                   self._user_prompt(batch, evidence_map),
                                   timeout=self.timeout)
            except Exception as exc:  # noqa: BLE001 —— 通道异常一律按不可用处理
                logger.warning("客诉语义通道调用异常：%s", str(exc)[:200])
                res = {"used_llm": False, "notice": str(exc)[:300], "text": ""}
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
                if item["point"]:
                    self._cache[item["no"]] = item["point"]
        self.generated = len(self._cache)
        self.available = True
        return True

    def __call__(self, ticket: Dict[str, Any], spans: List[Dict[str, Any]]) -> str:
        """D1 生成入口；漏返返回空串（编排层标待自动补跑，绝不猜）。"""
        return self._cache.get(str(ticket.get("ticket_no") or ""), "")

    def summary(self) -> Dict[str, Any]:
        return {"channel": CHANNEL_NAME, "available": self.available,
                "provider": self.provider, "calls": self.calls,
                "generated": self.generated, "notice": self.notice,
                "batches_limit": self.max_batches,
                "policy_version": self.policy_version}
