import os
import zipfile

import pytest
from fastapi.testclient import TestClient

from core.config import settings
from db.models import PmwbBusinessDomain, PmwbKnowledgeItem
from utils.obsidian import AUTO_BEGIN_TPL, AUTO_END_TPL, render_auto_block


@pytest.fixture
def vault_tmp(tmp_path, monkeypatch):
    """把 Obsidian vault 指向临时目录，避免污染真实知识库。"""
    monkeypatch.setattr(settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    return tmp_path


def _create_domain(db, code="ywt", name="一网通", group="政企业务"):
    d = PmwbBusinessDomain(
        domain_code=code, domain_name=name, domain_group=group, enabled=1
    )
    db.add(d)
    db.commit()
    return d


from services.knowledge_link_service import ensure_domain_main_note


def _write_main_note(db, vault_tmp, domain, product_md: str) -> PmwbKnowledgeItem:
    """在 vault 内构造一个带 §2 产商品章节与 AUTO 块的主笔记，并返回 ORM 记录。"""
    ensure_domain_main_note(db, domain.domain_code)
    item = (
        db.query(PmwbKnowledgeItem)
        .filter(
            PmwbKnowledgeItem.domain_code == domain.domain_code,
            PmwbKnowledgeItem.note_type == "main",
        )
        .first()
    )
    note_path = item.obsidian_path
    full = os.path.join(str(vault_tmp), note_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    content = (
        "---\n"
        "auto_sections_generated_at: 2026-07-15\n"
        "---\n\n"
        f"# {domain.domain_name} 业务知识主笔记\n\n"
        "## 1. 概述\n\n人工维护概述。\n\n"
        "## 2. 产商品与资费体系\n\n"
        f"{render_auto_block('product', product_md)}\n\n"
        "## 3. SOP\n\n人工维护。\n"
    )
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return item


def test_list_product_bible_catalog(client: TestClient, db):
    _create_domain(db, "ywt", "一网通")
    _create_domain(db, "ftto", "FTTO")
    res = client.get("/api/v1/product-bible")
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 0
    keys = [c["key"] for c in body["data"]]
    assert "ywt" in keys
    assert "ftto" in keys
    # 不再依赖硬编码配置，format 统一为 markdown
    assert all(c["format"] == "markdown" for c in body["data"])


def test_get_unknown_bible_returns_404(client: TestClient, db):
    res = client.get("/api/v1/product-bible/does-not-exist")
    assert res.status_code == 404
    assert res.json()["code"] == 404


def test_get_bible_reads_product_section(client: TestClient, db, vault_tmp):
    """GET 应返回主笔记 §2 产商品 AUTO 块内容，且不含其它章节。"""
    domain = _create_domain(db)
    item = _write_main_note(db, vault_tmp, domain, "### 一网通宽带\n- 资费档位A\n- 资费档位B")

    res = client.get("/api/v1/product-bible/ywt")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["key"] == "ywt"
    assert "一网通宽带" in data["markdown"]
    assert "资费档位A" in data["markdown"]
    assert "人工维护概述" not in data["markdown"]  # 仅 §2 章节
    assert data["title"]
    assert data["updated_at"] == "2026-07-15"


def test_get_bible_without_auto_block_falls_back_to_section(client: TestClient, db, vault_tmp):
    """无 AUTO 块时退回整章 §2 内容。"""
    domain = _create_domain(db)
    ensure_domain_main_note(db, domain.domain_code)
    item = (
        db.query(PmwbKnowledgeItem)
        .filter(
            PmwbKnowledgeItem.domain_code == domain.domain_code,
            PmwbKnowledgeItem.note_type == "main",
        )
        .first()
    )
    note_path = item.obsidian_path
    full = os.path.join(str(vault_tmp), note_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(
            f"# {domain.domain_name} 业务知识主笔记\n\n"
            "## 1. 概述\n\n人工维护概述。\n\n"
            "## 2. 产商品与资费体系\n\n### 旧版产商品\n- 档位X\n\n"
            "## 3. SOP\n\n人工维护。\n"
        )

    res = client.get("/api/v1/product-bible/ywt")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "档位X" in data["markdown"]
    assert "人工维护概述" not in data["markdown"]


def test_put_bible_writes_back_to_auto_block(client: TestClient, db, vault_tmp):
    """PUT 应把内容写回主笔记 §2 产商品 AUTO 块，且保留人工区。"""
    domain = _create_domain(db)
    item = _write_main_note(db, vault_tmp, domain, "### 原产商品\n- 旧档位")

    new_md = "### 新产商品\n- 新档位1\n- 新档位2"
    res = client.put("/api/v1/product-bible/ywt", json={"markdown": new_md})
    assert res.status_code == 200
    assert res.json()["code"] == 0

    # 重新读取文件，确认 AUTO 块被替换，人工区未动
    note_path = item.obsidian_path
    full = os.path.join(str(vault_tmp), note_path)
    content = open(full, encoding="utf-8").read()
    assert new_md in content
    assert "旧档位" not in content
    assert "人工维护概述" in content  # 人工区保留
    # AUTO 标记仍存在
    assert AUTO_BEGIN_TPL.format(key="product") in content
    assert AUTO_END_TPL.format(key="product") in content


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
