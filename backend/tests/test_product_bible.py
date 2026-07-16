from fastapi.testclient import TestClient

from core.config import settings


def test_list_product_bible_catalog(client: TestClient):
    res = client.get("/api/v1/product-bible")
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 0
    keys = [c["key"] for c in body["data"]]
    assert "group-sms" in keys


def test_get_group_sms_bible(client: TestClient):
    res = client.get("/api/v1/product-bible/group-sms")
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 0
    data = body["data"]
    assert "markdown" in data
    assert "集团短信" in data["markdown"]
    assert data["title"]
    assert data["updated_at"] == "2026-07-15"


def test_get_unknown_bible_returns_404(client: TestClient):
    res = client.get("/api/v1/product-bible/does-not-exist")
    assert res.status_code == 404
    assert res.json()["code"] == 404


def test_put_update_writes_back_to_file(client: TestClient):
    """PUT 应把内容写回 Obsidian 源文件，且不污染真实业务配置。"""
    import os
    from pathlib import Path

    vault = Path(settings.OBSIDIAN_VAULT_PATH)
    tmp_rel = "_pb_test_tmp.md"
    tmp_full = vault / tmp_rel
    original_config = settings.PRODUCT_BIBLE
    try:
        tmp_full.write_text("# 测试文档\n\n原始内容\n", encoding="utf-8")
        settings.PRODUCT_BIBLE = [{"key": "test-tmp", "name": "测试", "path": tmp_rel}]

        # GET 读回
        res = client.get("/api/v1/product-bible/test-tmp")
        assert res.status_code == 200
        assert "原始内容" in res.json()["data"]["markdown"]

        # PUT 写回
        new_md = "# 测试文档\n\n已修改内容\n"
        res = client.put("/api/v1/product-bible/test-tmp", json={"markdown": new_md})
        assert res.status_code == 200
        assert res.json()["code"] == 0

        # 文件确实被改写
        assert "已修改内容" in tmp_full.read_text(encoding="utf-8")
    finally:
        settings.PRODUCT_BIBLE = original_config
        if tmp_full.exists():
            os.remove(tmp_full)
