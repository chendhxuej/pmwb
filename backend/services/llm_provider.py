"""底层大模型提供方注册表服务（多模型管理）。

- 支持 Kimi / 腾讯混元 / TokenHub / DeepSeek / 任意 OpenAI 兼容接口。
- 提供 CRUD、连通性探测、按优先级多模型 fallback 调用。
- API Key 采用轻量混淆存储（utils.secret），接口返回脱敏，绝不回显明文。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from core.config import settings
from db.models import PmwbLlmProvider
from utils.secret import decrypt_secret, encrypt_secret, mask_secret

logger = logging.getLogger(__name__)

PROVIDER_PRESETS: Dict[str, Dict[str, str]] = {
    "kimi": {
        "label": "Kimi (Moonshot)",
        "base_url": "https://api.kimi.com/coding/v1",
        "model": "kimi-k2.6",
        "note": "Kimi Coding Plan，仅允许 temperature=1；带 reasoning 建议 timeout≥120",
    },
    "hunyuan": {
        "label": "腾讯混元 (Hunyuan)",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "model": "hunyuan-turbos-latest",
        "note": "OpenAI 兼容，Bearer APIKey；turbos 性价比高，pro 更强",
    },
    "tokenhub": {
        "label": "腾讯云 TokenHub",
        "base_url": "https://tokenhub.tencentmaas.com/v1",
        "model": "hy3",
        "note": "一个 key 托管 hy3/kimi-k2.6/deepseek/glm 等多模型，便于统一切换",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "note": "OpenAI 兼容",
    },
    "agnes": {
        "label": "Agnes AI",
        "base_url": "https://apihub.agnes-ai.com/v1",
        "model": "agnes-2.5-flash",
        "note": "OpenAI 兼容；当前免费模型：agnes-2.5-flash / agnes-2.0-flash；Pro 系列需账户有额度",
    },
    "openai": {
        "label": "OpenAI 兼容",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "note": "通用 OpenAI 兼容端点",
    },
    "ollama": {
        "label": "Ollama (本地)",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen2.5:7b",
        "note": "本地模型，无需 API Key",
    },
    "custom": {
        "label": "自定义",
        "base_url": "",
        "model": "",
        "note": "自行填写 Base URL 与模型",
    },
}


def _is_kimi_coding(p: PmwbLlmProvider) -> bool:
    if p.provider_type == "kimi":
        return True
    return "api.kimi.com" in (p.base_url or "")


def _effective_temperature(p: PmwbLlmProvider) -> float:
    if _is_kimi_coding(p):
        return 1.0
    t = float(p.temperature or 0.3)
    return max(t, 0.01) if t <= 0 else t


# ---------------------------------------------------------------------------
# 查询 / 序列化
# ---------------------------------------------------------------------------

def _to_view(p: PmwbLlmProvider) -> Dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "provider_type": p.provider_type,
        "base_url": p.base_url,
        "model": p.model,
        "api_key_masked": mask_secret(p.api_key),
        "api_key_set": bool(p.api_key),
        "temperature": p.temperature,
        "max_tokens": p.max_tokens,
        "timeout": p.timeout,
        "is_enabled": bool(p.is_enabled),
        "is_default": bool(p.is_default),
        "priority": p.priority,
        "last_error": p.last_error,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def list_providers(db: Session) -> List[Dict[str, Any]]:
    rows = db.query(PmwbLlmProvider).order_by(
        PmwbLlmProvider.is_default.desc(),
        PmwbLlmProvider.priority.asc(),
        PmwbLlmProvider.id.asc(),
    ).all()
    return [_to_view(r) for r in rows]


def get_status(db: Session) -> Dict[str, Any]:
    """返回 AI 问答可用的大模型状态概览（供 ai_qa /status 端点使用）。"""
    rows = list_providers(db)
    enabled = [r for r in rows if r.get("is_enabled")]
    default = next((r for r in rows if r.get("is_default")), None)
    if enabled:
        best = default if (default and default.get("is_enabled")) else enabled[0]
        return {
            "available": True,
            "provider_name": best.get("name"),
            "provider_count": len(enabled),
            "notice": "",
        }
    return {
        "available": False,
        "provider_name": None,
        "provider_count": 0,
        "notice": "未配置任何可用的大模型（请到「大模型管理」添加并启用一个）",
    }


def get_provider(db: Session, pid: int) -> Optional[Dict[str, Any]]:
    r = db.query(PmwbLlmProvider).filter(PmwbLlmProvider.id == pid).first()
    return _to_view(r) if r else None


def get_provider_row(db: Session, pid: int) -> Optional[PmwbLlmProvider]:
    return db.query(PmwbLlmProvider).filter(PmwbLlmProvider.id == pid).first()


# ---------------------------------------------------------------------------
# 写操作
# ---------------------------------------------------------------------------

def create_provider(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    p = PmwbLlmProvider(
        name=data["name"],
        provider_type=data.get("provider_type", "openai"),
        base_url=data.get("base_url", ""),
        model=data.get("model", ""),
        api_key=encrypt_secret(data.get("api_key")) if data.get("api_key") else None,
        temperature=float(data.get("temperature", 0.3)),
        max_tokens=int(data.get("max_tokens", 4096)),
        timeout=int(data.get("timeout", 120)),
        is_enabled=1 if data.get("is_enabled", True) else 0,
        is_default=1 if data.get("is_default") else 0,
        priority=int(data.get("priority", 0)),
    )
    if p.is_default:
        _clear_defaults(db, None)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_view(p)


def update_provider(db: Session, pid: int, data: Dict[str, Any]) -> Dict[str, Any]:
    p = db.query(PmwbLlmProvider).filter(PmwbLlmProvider.id == pid).first()
    if not p:
        raise ValueError("大模型提供方不存在")
    if "name" in data:
        p.name = data["name"]
    if "provider_type" in data:
        p.provider_type = data["provider_type"]
    if "base_url" in data:
        p.base_url = data["base_url"]
    if "model" in data:
        p.model = data["model"]
    # api_key: 传 "***" 或空表示不修改（保留原值）；传其他值表示更新
    ak = data.get("api_key")
    if ak and ak != "***":
        p.api_key = encrypt_secret(ak)
    if "temperature" in data:
        p.temperature = float(data["temperature"])
    if "max_tokens" in data:
        p.max_tokens = int(data["max_tokens"])
    if "timeout" in data:
        p.timeout = int(data["timeout"])
    if "is_enabled" in data:
        p.is_enabled = 1 if data["is_enabled"] else 0
    if "priority" in data:
        p.priority = int(data["priority"])
    if data.get("is_default"):
        _clear_defaults(db, p.id)
        p.is_default = 1
    db.commit()
    db.refresh(p)
    return _to_view(p)


def delete_provider(db: Session, pid: int) -> None:
    p = db.query(PmwbLlmProvider).filter(PmwbLlmProvider.id == pid).first()
    if not p:
        raise ValueError("大模型提供方不存在")
    db.delete(p)
    db.commit()


def set_default(db: Session, pid: int) -> Dict[str, Any]:
    p = db.query(PmwbLlmProvider).filter(PmwbLlmProvider.id == pid).first()
    if not p:
        raise ValueError("大模型提供方不存在")
    _clear_defaults(db, p.id)
    p.is_default = 1
    p.is_enabled = 1
    db.commit()
    db.refresh(p)
    return _to_view(p)


def _clear_defaults(db: Session, except_id: Optional[int]) -> None:
    q = db.query(PmwbLlmProvider).filter(PmwbLlmProvider.is_default == 1)
    if except_id is not None:
        q = q.filter(PmwbLlmProvider.id != except_id)
    q.update({PmwbLlmProvider.is_default: 0})


# ---------------------------------------------------------------------------
# 种子（向后兼容：从 settings.US_STORY_LLM_* 迁移一条 Kimi）
# ---------------------------------------------------------------------------

def ensure_seed(db: Session) -> None:
    try:
        cnt = db.query(PmwbLlmProvider).count()
    except Exception:  # noqa: BLE001
        return
    if cnt > 0:
        return
    if not settings.US_STORY_LLM_ENABLED:
        return
    p = PmwbLlmProvider(
        name="默认 Kimi (迁移自配置)",
        provider_type=settings.US_STORY_LLM_PROVIDER or "kimi",
        base_url=settings.US_STORY_LLM_BASE_URL,
        model=settings.US_STORY_LLM_MODEL,
        api_key=encrypt_secret(settings.US_STORY_LLM_API_KEY) if settings.US_STORY_LLM_API_KEY else None,
        temperature=settings.US_STORY_LLM_TEMPERATURE,
        max_tokens=settings.US_STORY_LLM_MAX_TOKENS,
        timeout=settings.US_STORY_LLM_TIMEOUT,
        is_enabled=1,
        is_default=1,
        priority=0,
    )
    db.add(p)
    db.commit()


# ---------------------------------------------------------------------------
# 调用 / 连通性
# ---------------------------------------------------------------------------

def _load_enabled_providers(db: Session) -> List[PmwbLlmProvider]:
    return db.query(PmwbLlmProvider).filter(PmwbLlmProvider.is_enabled == 1).order_by(
        PmwbLlmProvider.is_default.desc(),
        PmwbLlmProvider.priority.asc(),
        PmwbLlmProvider.id.asc(),
    ).all()


def call_provider(p: PmwbLlmProvider, system: str, user: str, max_tokens: int | None = None, timeout: int | None = None) -> str:
    """调用单个提供方（OpenAI 兼容）。失败抛异常由上层 fallback。

    timeout 参数优先级：显式传入 > 模型配置 > 默认180秒（报告生成需要更长时间）
    """
    base_url = (p.base_url or "").rstrip("/")
    if not base_url:
        raise ValueError("未配置 Base URL")
    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    key = decrypt_secret(p.api_key)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    _max_tokens = int(max_tokens) if max_tokens is not None else int(p.max_tokens or 4096)
    body = {
        "model": p.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": _max_tokens,
        "temperature": _effective_temperature(p),
    }
    # 超时优先级：显式传入 > 模型配置 > 默认180秒
    effective_timeout = timeout or int(p.timeout or 180)
    timeout_config = httpx.Timeout(effective_timeout)
    with httpx.Client(timeout=timeout_config) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        raise ValueError("模型返回空 choices")
    message = choices[0].get("message", {})
    content = message.get("content", "") or message.get("text", "")
    if not content:
        raise ValueError("模型返回空内容")
    return content


def pick_provider(providers, call_fn, system: str, user: str, max_tokens: int | None = None, timeout: int | None = None) -> Dict[str, Any]:
    """纯函数：按序尝试 providers，返回首个成功或失败汇总。便于单测。"""
    if not providers:
        return {
            "text": "", "used_llm": False, "provider_name": None, "provider_id": None,
            "notice": "未配置任何可用的大模型（请到「大模型管理」添加并启用一个）",
        }
    errors: List[str] = []
    for p in providers:
        try:
            text = call_fn(p, system, user, max_tokens=max_tokens, timeout=timeout)
            if text and text.strip():
                return {
                    "text": text.strip(), "used_llm": True,
                    "provider_name": getattr(p, "name", None),
                    "provider_id": getattr(p, "id", None), "notice": "",
                }
            raise ValueError("模型返回空内容")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{getattr(p, 'name', '?')}: {str(e)[:200]}")
    notice = "所有已启用的大模型均不可用，已生成规则模板版（非 AI 润色）。" + "；".join(errors)
    return {"text": "", "used_llm": False, "provider_name": None, "provider_id": None, "notice": notice}


def call_best_available(db: Session, system: str, user: str, max_tokens: int | None = None, timeout: int | None = None) -> Dict[str, Any]:
    """按优先级尝试已启用提供方，全失败返回 used_llm=False + notice，并记录失败原因。

    timeout 参数会传递给 call_provider，用于控制 HTTP 请求超时。
    """
    providers = _load_enabled_providers(db)
    res = pick_provider(providers, lambda p, s, u, max_tokens=max_tokens, timeout=timeout: call_provider(p, s, u, max_tokens=max_tokens, timeout=timeout), system, user, max_tokens=max_tokens, timeout=timeout)
    if not res["used_llm"]:
        prefix = "所有已启用的大模型均不可用，已生成规则模板版（非 AI 润色）。"
        rest = res["notice"]
        if rest.startswith(prefix):
            rest = rest[len(prefix):]
        for chunk in rest.split("；"):
            if ": " in chunk:
                name, err = chunk.split(": ", 1)
                for p in providers:
                    if p.name == name:
                        p.last_error = err
                        break
        try:
            db.commit()
        except Exception:  # noqa: BLE001
            pass
    return res


def test_provider(p: PmwbLlmProvider) -> Dict[str, Any]:
    base_url = (p.base_url or "").rstrip("/")
    if not base_url:
        return {"reachable": False, "error": "未配置 Base URL"}
    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    key = decrypt_secret(p.api_key)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = {
        "model": p.model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
        "temperature": _effective_temperature(p),
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
            resp = client.post(url, headers=headers, json=body)
        if resp.status_code == 200:
            return {"reachable": True, "error": None}
        return {"reachable": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except httpx.TimeoutException:
        return {"reachable": False, "error": "连接超时（请检查网络或 API 地址）"}
    except httpx.ConnectError:
        return {"reachable": False, "error": "无法连接至 API 服务器（请检查 Base URL）"}
    except Exception as e:  # noqa: BLE001
        return {"reachable": False, "error": str(e)[:300]}
