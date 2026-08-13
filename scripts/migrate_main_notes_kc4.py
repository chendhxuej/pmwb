"""存量主笔记整合迁移（kc4 知识标准化管理）。

把旧结构主笔记（§1/§2.1/§3.1/§4.1/§10 缺失，有价值信息堆在底部
「参考资料：集客一网通宽带」迁移块）重建为标准结构：
  - 基线区（§1 业务概述 / §2.1 产品矩阵 / §2.2 资费 / §3.1 服务场景 /
    §4.1 通用规则 / §10 关联系统）回填迁移块中的人工内容；
  - 自动区（AUTO 块：场景规则/时间线/变更/交付物等）原样保留；
  - §7 关联过程性内容索引 / §8 子笔记 MOC 原样保留。

仅对带 `PMWB:MIGRATED` 标记的存量主笔记执行；执行前自动备份为 .bak。

用法：
  python scripts/migrate_main_notes_kc4.py [domain_code ...]
  不传参数则自动扫描所有带迁移标记的存量主笔记。
"""
import os
import re
import sys
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.config as cfg  # noqa: E402  (加载以初始化配置；需先设置环境变量)
from db.models import PmwbKnowledgeItem  # noqa: E402
from utils.obsidian import (  # noqa: E402
    extract_region,
    get_vault_path,
    read_auto_block,
    read_markdown,
    render_auto_block,
    write_markdown,
)

MIGRATED_MARKER = "<!-- PMWB:MIGRATED"


def _engine():
    return create_engine(cfg.settings.DATABASE_URL)


def _parse_migrated_block(content: str) -> str:
    """截取 `PMWB:MIGRATED` 标记之后的迁移内容（含业务基本信息/系统架构/流程/服务场景等）。"""
    idx = content.find(MIGRATED_MARKER)
    return content[idx:] if idx >= 0 else ""


def _build_standard(domain_name, baseline, auto, index_md, moc_md):
    """依标准章节顺序拼装主笔记正文。"""
    prod_matrix = baseline.get("product-matrix") or ""
    prod_tariff = baseline.get("product-tariff") or ""
    service = baseline.get("service-scenes") or ""
    systems = baseline.get("systems") or ""
    overview = baseline.get("overview") or ""
    general = baseline.get("general-rules") or "- （通用业务规则待补充；场景化规则见 §4.2 系统自动汇总）"

    def block(key, body):
        return render_auto_block(key, body) if body else render_auto_block(key, "_暂无数据_")

    lines = [f"# {domain_name} 业务知识主笔记", ""]
    lines.append("> 本笔记为该业务领域的唯一主入口，**不堆过程细节**；详细过程性内容请通过下方链接跳转到对应需求/工单/会议/运营笔记。")
    lines.append("")
    lines.append("## 1. 业务概述")
    lines.append("")
    lines.append(overview.strip() or "- **业务定义**：")
    lines.append("")
    lines.append("## 2. 产商品与资费体系")
    lines.append("")
    lines.append("### 2.1 产品矩阵（人工维护）")
    lines.append("")
    lines.append(prod_matrix.strip() or "| 产品 | 定位 | 目标客户 | 备注 |\n|------|------|----------|------|\n|      |      |          |      |")
    lines.append("")
    lines.append("### 2.2 资费与计费规则（人工维护）")
    lines.append("")
    lines.append(prod_tariff.strip() or "- ")
    lines.append("")
    lines.append("### 2.3 产商品变更记录（系统自动）")
    lines.append("")
    lines.append("> 🤖 系统自动汇总：来源为「已关闭且标记产商品变更」的需求，人工无需手改。")
    lines.append("")
    lines.append(block("product", auto.get("product")))
    lines.append("")
    lines.append("## 3. 客户服务场景 SOP")
    lines.append("")
    lines.append("### 3.1 常见服务场景（人工维护）")
    lines.append("")
    lines.append(service.strip() or "| 场景 | 责任角色 | 关键步骤 | SLA |\n|------|----------|----------|-----|\n|      |          |          |     |")
    lines.append("")
    lines.append("### 3.2 流程变更记录（系统自动）")
    lines.append("")
    lines.append(block("process", auto.get("process")))
    lines.append("")
    lines.append("## 4. 业务规则")
    lines.append("")
    lines.append("### 4.1 通用规则（人工维护）")
    lines.append("")
    lines.append(general.strip())
    lines.append("")
    lines.append("### 4.2 场景规则（系统自动）")
    lines.append("")
    lines.append(block("scenario_rules", auto.get("scenario_rules")))
    lines.append("")
    lines.append("## 5. 优化与变更轨迹（系统自动）")
    lines.append("")
    lines.append(block("change_log", auto.get("change_log")))
    lines.append("")
    lines.append("## 6. 关联交付物（系统自动）")
    lines.append("")
    lines.append(block("deliverables", auto.get("deliverables")))
    lines.append("")
    lines.append("## 7. 关联过程性内容索引（系统自动）")
    lines.append("")
    lines.append(index_md.strip() or "> 以下链接由系统自动维护，删除或新增关联时会同步更新。")
    lines.append("")
    lines.append("## 8. 相关子笔记 MOC（系统自动）")
    lines.append("")
    lines.append(moc_md.strip() or "")
    lines.append("")
    lines.append("## 9. 业务全过程时间线（系统自动）")
    lines.append("")
    lines.append(block("timeline", auto.get("timeline")))
    lines.append("")
    lines.append("## 10. 关联系统与接口（人工维护）")
    lines.append("")
    lines.append(systems.strip() or "- ")
    lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def _migrate_one(db, item):
    path = item.obsidian_path
    full = str(get_vault_path() / path)
    content = read_markdown(path)
    if not content or MIGRATED_MARKER not in content:
        return False, "无迁移标记，跳过"

    # 1) 保留 AUTO 块
    auto = {k: read_auto_block(content, k) for k in ("product", "process", "scenario_rules", "change_log", "deliverables", "timeline")}
    # 2) 保留 §7/§8
    index_md = extract_region(content, "关联过程性内容索引", 2) or ""
    moc_md = extract_region(content, "相关子笔记 MOC", 2) or ""
    # 3) 解析迁移块
    migrated = _parse_migrated_block(content)

    def grab(heading, level):
        return extract_region(migrated, heading, level) or ""

    overview = "- **业务定义**：" + (grab("业务介绍", 3) or "").lstrip("- ").strip()
    product_matrix = grab("产品体系", 3) + "\n\n" + grab("业务规模", 3)
    product_tariff = grab("套餐体系", 3)
    service = grab("业务服务场景", 2) + "\n\n" + grab("业务流程", 2) + "\n\n" + grab("操作手册索引", 2)
    systems = grab("系统支撑架构", 2)

    baseline = {
        "overview": overview,
        "product-matrix": product_matrix,
        "product-tariff": product_tariff,
        "service-scenes": service,
        "systems": systems,
    }

    new_md = _build_standard(item.title.replace(" 业务知识主笔记", "") if item.title else item.domain_code, baseline, auto, index_md, moc_md)

    # 备份
    bak = full + ".migrated.bak"
    if not os.path.exists(bak):
        shutil.copy2(full, bak)

    write_markdown(path, new_md)
    return True, "已重建为标准结构（备份：" + os.path.basename(bak) + "）"


def main():
    targets = sys.argv[1:]
    engine = _engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    items = db.query(PmwbKnowledgeItem).filter(PmwbKnowledgeItem.note_type == "main").all()
    if targets:
        items = [i for i in items if i.domain_code in targets]
    migrated = 0
    for it in items:
        if not it.obsidian_path:
            continue
        try:
            ok, msg = _migrate_one(db, it)
        except Exception as e:
            print(f"[FAIL] {it.domain_code}: {e}")
            continue
        print(f"[{'OK ' if ok else 'SKIP'}] {it.domain_code}: {msg}")
        if ok:
            migrated += 1
    db.close()
    print(f"\n完成：{migrated} 个主笔记已迁移重建。")


if __name__ == "__main__":
    main()
