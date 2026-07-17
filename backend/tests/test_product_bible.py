import os
import zipfile
from pathlib import Path

import pytest
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


def _make_minimal_docx(path: str):
    """构造一个最小可用 docx（标题+正文+表格），用于离线验证解析器。"""
    ct = (
        '<?xml version="1.0"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )
    styles = (
        '<?xml version="1.0"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:outlineLvl w:val="0"/></w:style>'
        '</w:styles>'
    )
    doc = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>第一章 测试</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>正文段落内容</w:t></w:r></w:p>'
        '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>单元格A</w:t></w:r></w:p></w:tc>'
        '<w:tc><w:p><w:r><w:t>单元格B</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
        '</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", styles)


def test_docx_to_html_minimal():
    """极简 docx 应能解析出 h1 / 正文 / 表格（不依赖大文件）。"""
    from core.docx_convert import docx_to_html

    fd, p = __import__("tempfile").mkstemp(suffix=".docx")
    os.close(fd)
    try:
        _make_minimal_docx(p)
        res = docx_to_html(p)
        assert "<h1" in res["html"]
        assert "第一章" in res["html"]
        assert "<table" in res["html"]
        assert "单元格A" in res["html"]
    finally:
        os.remove(p)


def _econtract_cfg():
    for i in settings.PRODUCT_BIBLE:
        if i["key"] == "e-contract":
            return i
    return None


def test_get_e_contract_is_docx(client: TestClient):
    cfg = _econtract_cfg()
    if not cfg:
        pytest.skip("无 e-contract 配置")
    full = Path(settings.OBSIDIAN_VAULT_PATH) / cfg["path"]
    if not full.exists():
        pytest.skip("e-contract docx 不存在")
    res = client.get("/api/v1/product-bible/e-contract")
    assert res.status_code == 200
    d = res.json()["data"]
    assert d["format"] == "docx"
    assert ("<h2" in d["markdown"]) or ("<h1" in d["markdown"])
    assert "<table" in d["markdown"]
    assert "img" in d["markdown"]


def test_get_e_contract_media_png(client: TestClient):
    cfg = _econtract_cfg()
    if not cfg:
        pytest.skip("无 e-contract 配置")
    full = Path(settings.OBSIDIAN_VAULT_PATH) / cfg["path"]
    if not full.exists():
        pytest.skip("e-contract docx 不存在")
    res = client.get("/api/v1/product-bible/e-contract/media/image2.png")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert len(res.content) > 0


def test_put_e_contract_readonly(client: TestClient):
    cfg = _econtract_cfg()
    if not cfg:
        pytest.skip("无 e-contract 配置")
    res = client.put("/api/v1/product-bible/e-contract", json={"markdown": "x"})
    assert res.status_code == 404
