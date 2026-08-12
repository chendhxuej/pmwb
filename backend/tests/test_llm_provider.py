"""大模型提供方注册表：密钥混淆、CRUD 脱敏、多模型 fallback、种子。"""
import pytest

from services import llm_provider as svc
from utils.secret import encrypt_secret, decrypt_secret, mask_secret


def test_secret_roundtrip():
    c = encrypt_secret("sk-abc123")
    assert c != "sk-abc123"
    assert decrypt_secret(c) == "sk-abc123"
    assert decrypt_secret(None) is None
    assert mask_secret(c) == "***"
    assert mask_secret(None) == ""


def test_pick_provider_first_wins():
    calls = []

    class P:
        def __init__(self, name):
            self.name = name
            self.id = id(self)

    def call_fn(p, s, u):
        calls.append(p.name)
        return f"txt-{p.name}"

    res = svc.pick_provider([P("A"), P("B")], call_fn, "s", "u")
    assert res["used_llm"] is True
    assert res["provider_name"] == "A"
    assert res["text"] == "txt-A"
    assert calls == ["A"]


def test_pick_provider_fallback_then_fail():
    class P:
        def __init__(self, name):
            self.name = name
            self.id = id(self)

    def call_fn(p, s, u):
        raise RuntimeError("boom")

    res = svc.pick_provider([P("A"), P("B")], call_fn, "s", "u")
    assert res["used_llm"] is False
    assert "A" in res["notice"] and "B" in res["notice"]


def test_pick_provider_empty():
    res = svc.pick_provider([], lambda p, s, u: "x", "s", "u")
    assert res["used_llm"] is False
    assert "未配置" in res["notice"]


def test_crud_and_mask(db):
    p = svc.create_provider(db, {
        "name": "腾讯混元", "provider_type": "hunyuan",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "model": "hunyuan-turbos-latest", "api_key": "sk-hunyuan",
        "temperature": 0.5, "priority": 1, "is_default": True,
    })
    assert p["api_key_masked"] == "***" and p["api_key_set"] is True
    # 列表不回显明文
    rows = svc.list_providers(db)
    assert rows[0]["api_key_masked"] == "***"
    # 更新时传 "***" 保留原密钥
    svc.update_provider(db, p["id"], {"name": "混元", "api_key": "***"})
    row = svc.get_provider_row(db, p["id"])
    assert decrypt_secret(row.api_key) == "sk-hunyuan"
    # 设主用互斥
    p2 = svc.create_provider(db, {
        "name": "Kimi", "provider_type": "kimi",
        "base_url": "https://api.kimi.com/coding/v1", "model": "kimi-k2.6",
        "is_default": True,
    })
    assert svc.get_provider(db, p["id"])["is_default"] is False
    assert svc.get_provider(db, p2["id"])["is_default"] is True
    svc.delete_provider(db, p2["id"])
    assert svc.get_provider(db, p2["id"]) is None


def test_call_best_available_fallback(db, monkeypatch):
    svc.create_provider(db, {
        "name": "A", "provider_type": "kimi",
        "base_url": "https://api.kimi.com/coding/v1", "model": "kimi-k2.6",
        "priority": 0,
    })
    svc.create_provider(db, {
        "name": "B", "provider_type": "hunyuan",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1", "model": "hunyuan-turbos-latest",
        "priority": 1,
    })

    def fake_call(p, s, u):
        if p.name == "A":
            raise RuntimeError("A down")
        return "llm-ok"

    monkeypatch.setattr(svc, "call_provider", fake_call)
    res = svc.call_best_available(db, "sys", "user")
    assert res["used_llm"] is True
    assert res["provider_name"] == "B"
    assert res["text"] == "llm-ok"


def test_call_best_available_all_fail(db, monkeypatch):
    svc.create_provider(db, {
        "name": "A", "provider_type": "kimi",
        "base_url": "https://api.kimi.com/coding/v1", "model": "kimi-k2.6",
    })

    def fake_call(p, s, u):
        raise RuntimeError("down")

    monkeypatch.setattr(svc, "call_provider", fake_call)
    res = svc.call_best_available(db, "sys", "user")
    assert res["used_llm"] is False
    assert "A" in res["notice"]


def test_ensure_seed(db, monkeypatch):
    monkeypatch.setattr(svc.settings, "US_STORY_LLM_ENABLED", True)
    monkeypatch.setattr(svc.settings, "US_STORY_LLM_API_KEY", "seed-key")
    monkeypatch.setattr(svc.settings, "US_STORY_LLM_PROVIDER", "kimi")
    monkeypatch.setattr(svc.settings, "US_STORY_LLM_BASE_URL", "https://api.kimi.com/coding/v1")
    monkeypatch.setattr(svc.settings, "US_STORY_LLM_MODEL", "kimi-k2.6")
    monkeypatch.setattr(svc.settings, "US_STORY_LLM_TEMPERATURE", 0.3)
    monkeypatch.setattr(svc.settings, "US_STORY_LLM_MAX_TOKENS", 4096)
    monkeypatch.setattr(svc.settings, "US_STORY_LLM_TIMEOUT", 120)
    svc.ensure_seed(db)
    rows = svc.list_providers(db)
    assert len(rows) == 1
    assert rows[0]["api_key_set"] is True
    row = svc.get_provider_row(db, rows[0]["id"])
    assert decrypt_secret(row.api_key) == "seed-key"
