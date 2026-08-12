"""LLM 用户故事生成客户端 —— OpenAI 兼容协议。

主要支持 Kimi Coding Plan（api.kimi.com/coding/v1），同时兼容 Moonshot / Ollama / DeepSeek / OpenAI 等。
LLM 不可用时自动降级到规则引擎 v2。
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import httpx

from core.config import settings
from services.storygen_prompt import SYSTEM_PROMPT, build_user_message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Kimi Coding Plan 特殊处理
# ---------------------------------------------------------------------------

def _is_kimi_coding() -> bool:
    """判断是否为 Kimi Coding Plan（api.kimi.com）。"""
    return "api.kimi.com" in settings.US_STORY_LLM_BASE_URL


def _effective_temperature() -> float:
    """获取生效的 temperature 值。

    Kimi Coding Plan 的 kimi-k2.6 模型仅允许 temperature=1，
    其他提供商沿用配置值。
    """
    if _is_kimi_coding():
        return 1.0
    t = settings.US_STORY_LLM_TEMPERATURE
    return max(t, 0.01) if t <= 0 else t


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def check_llm_available() -> Dict[str, Any]:
    """检查 LLM 是否可用，返回状态信息。

    Returns:
        {
            "enabled": bool,
            "provider": str,
            "model": str,
            "reachable": bool | None,   # None 表示未启用，未检测
            "error": str | None,
        }
    """
    result = {
        "enabled": settings.US_STORY_LLM_ENABLED,
        "provider": settings.US_STORY_LLM_PROVIDER,
        "model": settings.US_STORY_LLM_MODEL,
        "reachable": None,
        "error": None,
    }

    if not settings.US_STORY_LLM_ENABLED:
        return result

    try:
        base_url = settings.US_STORY_LLM_BASE_URL.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if settings.US_STORY_LLM_API_KEY:
            headers["Authorization"] = f"Bearer {settings.US_STORY_LLM_API_KEY}"

        timeout = httpx.Timeout(30.0)
        with httpx.Client(timeout=timeout) as client:
            # 用轻量探针请求验证连通性
            probe_body: Dict[str, Any] = {
                "model": settings.US_STORY_LLM_MODEL,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
            }
            # Kimi Coding Plan 要求 temperature=1
            probe_body["temperature"] = _effective_temperature()

            resp = client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=probe_body,
            )
            if resp.status_code == 200:
                result["reachable"] = True
            else:
                result["reachable"] = False
                result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except httpx.TimeoutException:
        result["reachable"] = False
        result["error"] = "连接超时（请检查网络或 API 地址）"
    except httpx.ConnectError:
        result["reachable"] = False
        result["error"] = "无法连接至 API 服务器（请检查 BASE_URL）"
    except Exception as e:
        result["reachable"] = False
        result["error"] = str(e)[:300]

    return result


def generate_with_llm(
    source: str,
    ddd: Dict[str, str],
    *,
    max_retries: int = 2,
) -> List[Dict[str, Any]]:
    """调用 LLM 生成用户故事，返回标准化列表。

    重试策略：
    - JSON 解析失败 → 重试（让 LLM 重新输出）
    - API 不可用/超时 → 直接抛异常（由外层降级到 rules_v2）

    Args:
        source: 澄清后的需求内容
        ddd: DDD 领域视角字典
        max_retries: JSON 解析失败时最大重试次数

    Returns:
        用户故事字典列表，每项包含 seq/title/desc/scene/acceptance/rules
    """
    if not settings.US_STORY_LLM_ENABLED:
        raise RuntimeError("LLM 未启用（US_STORY_LLM_ENABLED=false）")

    provider = settings.US_STORY_LLM_PROVIDER
    model = settings.US_STORY_LLM_MODEL
    logger.info("使用 %s / %s 生成用户故事（输入约 %d 字）", provider, model, len(source))

    # 输入长度预警
    _warn_input_length(source, provider, model)

    system_prompt = SYSTEM_PROMPT
    user_message = build_user_message(source, ddd)

    for attempt in range(max_retries + 1):
        try:
            raw = _call_llm(system_prompt, user_message)
            stories = _parse_llm_response(raw)
            stories = _validate_stories(stories, source)
            logger.info(
                "LLM 生成成功：%d 条用户故事（%s/%s，第 %d 次尝试）",
                len(stories), provider, model, attempt + 1,
            )
            return stories
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                "LLM 输出解析失败（%s/%s，第 %d/%d 次）: %s",
                provider, model, attempt + 1, max_retries + 1, str(e)[:150],
            )
            if attempt >= max_retries:
                raise RuntimeError(
                    f"LLM 输出解析失败（已重试 {max_retries} 次，"
                    f"将降级到规则引擎）: {e}"
                )
            time.sleep(0.5)
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.error("LLM API 请求异常（%s/%s）: %s", provider, model, e)
            raise RuntimeError(f"LLM 服务不可用（将降级到规则引擎）: {_fmt_http_error(e)}")

    raise RuntimeError("LLM 生成失败")


# ---------------------------------------------------------------------------
# 内部实现
# ---------------------------------------------------------------------------

def _warn_input_length(source: str, provider: str, model: str) -> None:
    """输入长度预警。"""
    char_count = len(source)
    if "8k" in model.lower() and char_count > 6000:
        logger.warning(
            "输入约 %d 字，接近 %s 模型 8K 上下文上限，"
            "建议精简澄清内容或切换到更大上下文模型",
            char_count, model,
        )
    elif char_count > 12000:
        logger.warning(
            "输入约 %d 字，可能超出部分模型上下文窗口，"
            "建议精简内容或使用更大上下文模型",
            char_count,
        )


def _call_llm(system_prompt: str, user_message: str) -> str:
    """调用 OpenAI 兼容 API（Kimi Coding Plan / Moonshot / Ollama / DeepSeek 等）。

    Kimi Coding Plan 特性：
    - kimi-k2.6 模型仅允许 temperature=1
    - 响应含 reasoning_content 字段（推理过程），仅取 content 字段
    - 完全兼容 OpenAI Chat Completions 协议
    """
    base_url = settings.US_STORY_LLM_BASE_URL.rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {"Content-Type": "application/json"}
    if settings.US_STORY_LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.US_STORY_LLM_API_KEY}"

    body: Dict[str, Any] = {
        "model": settings.US_STORY_LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": settings.US_STORY_LLM_MAX_TOKENS,
        "temperature": _effective_temperature(),
    }

    timeout = httpx.Timeout(settings.US_STORY_LLM_TIMEOUT)
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    # 提取响应文本
    choices = data.get("choices", [])
    if not choices:
        raise ValueError("LLM 返回空 choices")

    message = choices[0].get("message", {})
    content = message.get("content", "")

    # Kimi Coding Plan 可能把内容放在 text 字段
    if not content:
        content = choices[0].get("text", "")

    if not content:
        # 记录 reasoning_content 用于调试（但不作为正式输出）
        reasoning = message.get("reasoning_content", "")
        raise ValueError(
            f"LLM 返回空内容（reasoning_content 长度={len(reasoning)}，"
            "可能 reasoning 消耗了全部 token，请增大 max_tokens）"
        )

    # 记录 token 用量
    usage = data.get("usage", {})
    if usage:
        logger.debug(
            "LLM token 用量: prompt=%s, completion=%s, total=%s"
            "（reasoning_tokens=%s）",
            usage.get("prompt_tokens", "?"),
            usage.get("completion_tokens", "?"),
            usage.get("total_tokens", "?"),
            usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0),
        )

    return content


def _parse_llm_response(raw: str) -> List[Dict[str, Any]]:
    """从 LLM 原始响应中提取 JSON 数组。

    支持格式（按尝试顺序）：
    1. 纯 JSON 数组 / 对象
    2. Markdown 代码块包裹（```json ... ``` 或 ``` ... ```）
    3. 混合文本中提取 JSON 数组边界
    4. Kimi 常见输出："好的，以下是..." → 去除前缀后重试
    """
    raw = raw.strip()

    # 尝试 1：直接解析
    data = _try_parse_json(raw)
    if data is not None:
        return data

    # 尝试 2：Markdown 代码块
    for pattern in [r"```json\s*([\s\S]*?)```", r"```\s*([\s\S]*?)```"]:
        match = re.search(pattern, raw)
        if match:
            data = _try_parse_json(match.group(1).strip())
            if data is not None:
                return data

    # 尝试 3：提取 JSON 数组边界
    match = re.search(r"\[\s*\{[\s\S]*\}\s*\]", raw)
    if match:
        data = _try_parse_json(match.group(0))
        if data is not None:
            return data

    # 尝试 4：Kimi 特有 — 去除中文引导语后重试
    cleaned = re.sub(
        r'^[^\[\{]*?(?:好的|以下|根据|为您|这是|如下)[^\[\{]*?',
        '', raw, flags=re.DOTALL
    ).strip()
    if cleaned != raw:
        data = _try_parse_json(cleaned)
        if data is not None:
            return data
        for pattern in [r"```json\s*([\s\S]*?)```", r"```\s*([\s\S]*?)```"]:
            match = re.search(pattern, cleaned)
            if match:
                data = _try_parse_json(match.group(1).strip())
                if data is not None:
                    return data

    raise ValueError(f"无法从 LLM 输出中提取有效的用户故事 JSON（前 200 字）: {raw[:200]}")


def _try_parse_json(text: str) -> Optional[List[Dict[str, Any]]]:
    """尝试解析 JSON，返回故事列表或 None。"""
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if "stories" in data:
                return data["stories"]
            if "title" in data:
                return [data]
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _validate_stories(
    stories: List[Dict[str, Any]],
    source: str,
) -> List[Dict[str, Any]]:
    """合规校验 + 标准化 LLM 生成的用户故事。

    检查项：
    1. 每条故事必须包含角色标签（"作为"）
    2. 故事数量不超过 5（硬上限）
    3. 禁止按技术维度拆分的明显迹象
    """
    if not stories:
        raise ValueError("LLM 未生成任何用户故事")

    # 硬上限：最多 5 条
    if len(stories) > 5:
        raise ValueError(
            f"LLM 生成 {len(stories)} 条故事，超出上限 5 条，疑似过度拆分"
        )

    validated = []
    for i, s in enumerate(stories, start=1):
        title = s.get("title") or s.get("name") or f"US{i}"
        desc = s.get("desc") or s.get("description") or ""
        scene = s.get("scene") or s.get("scenario") or ""
        acceptance = s.get("acceptance") or s.get("acceptance_criteria") or []

        # 检查角色标签
        if "作为" not in title and "作为" not in desc:
            raise ValueError(f"故事 US{i} 缺少角色标签（'作为XX'），不符合管理规范")

        # 禁止技术维度拆分迹象
        tech_keywords = ["前端改造", "后端接口", "数据库变更", "API开发", "表结构"]
        if any(kw in title for kw in tech_keywords):
            raise ValueError(
                f"故事 US{i} 标题疑似按技术维度拆分（含 '{title}'），"
                f"禁止此类拆分，请合并为完整业务故事"
            )

        if isinstance(acceptance, str):
            acceptance = [acceptance]

        validated.append({
            "seq": i,
            "title": title,
            "desc": desc,
            "scene": scene,
            "acceptance": acceptance if acceptance else [f"验证故事 US{i} 的完整业务闭环"],
            "rules": s.get("rules") or s.get("business_rules") or [],
            "finalized": False,
        })

    return validated


def _fmt_http_error(e: Exception) -> str:
    """格式化 HTTP 异常为可读错误信息。"""
    if isinstance(e, httpx.HTTPStatusError):
        detail = ""
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text[:200] if e.response.text else ""
        return f"HTTP {e.response.status_code}: {detail}"
    if isinstance(e, httpx.TimeoutException):
        return "请求超时"
    return str(e)[:200]
