import pandas as pd
import re
from pathlib import Path
from datetime import datetime

base = Path("C:/Users/chend/Desktop/集团商客交接材料/商客产商品信息")
out_dir = Path("D:/项目/个人工作台系统/tmp_excel_extract")
out_dir.mkdir(exist_ok=True)


def clean_val(v):
    if pd.isna(v):
        return ""
    if isinstance(v, (int, float)):
        if v == int(v):
            return str(int(v))
        return str(v)
    s = str(v).replace("\r", " ").replace("\n", " ")
    return s.strip()


def to_markdown_table(df, columns=None, max_rows=None):
    if columns:
        df = df[[c for c in columns if c in df.columns]].copy()
    df = df.fillna("")
    if max_rows and len(df) > max_rows:
        df = df.head(max_rows)
    headers = [str(c) for c in df.columns]
    rows = []
    for _, row in df.iterrows():
        rows.append([clean_val(row[c]) for c in df.columns])
    if not rows:
        return ""
    md = "| " + " | ".join(headers) + " |\n"
    md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    for r in rows:
        md += "| " + " | ".join(r) + " |\n"
    return md


now_str = datetime.now().strftime("%Y-%m-%d")
source_note = f"来源：{base}（导入日期：{now_str}）"

# ============== 一网通宽带 ==============
df_bb = pd.read_excel(base / "一网通宽带资费列表v4.xlsx", sheet_name="资费列表")
pm_bb = df_bb.groupby(["集团主体商品包编码", "集团主体商品包名称", "集团主体商品编码", "集团主体商品名称"]).agg({
    "集团增值套餐名称": lambda x: "、".join([str(i) for i in x.dropna().unique()]),
    "集团增值套餐类型": lambda x: "、".join([str(i) for i in x.dropna().unique()]),
}).reset_index()
price_bb = df_bb[["集团主体商品名称", "集团增值套餐类型", "集团增值套餐编码", "集团增值套餐名称",
                   "集团增值套餐描述", "资费出账类型（属性编码=RateCycleType、字典组GrpRatePropMap）",
                   "月消费(元)", "标准资费", "折扣属性", "集团增值套餐状态"]].copy()
price_bb.columns = ["主体商品", "套餐类型", "套餐编码", "套餐名称", "套餐描述", "出账类型",
                    "月消费(元)", "标准资费", "折扣属性", "状态"]

bb_md = f"""### 2.1 产品矩阵（人工维护）

{source_note}

| 主体商品包 | 主体商品 | 套餐类型 | 包含套餐 |
|------------|----------|----------|----------|
"""
for _, r in pm_bb.iterrows():
    bb_md += (f"| {clean_val(r['集团主体商品包名称'])} | {clean_val(r['集团主体商品名称'])} | "
              f"{clean_val(r['集团增值套餐类型'])} | {clean_val(r['集团增值套餐名称'])} |\n")

bb_md += f"""
### 2.2 资费与计费规则（人工维护）

{source_note}

"""
bb_md += to_markdown_table(price_bb)

# ============== 一网通组网 ==============
df_zu1 = pd.read_excel(base / "一网通组网资费信息v15.xlsx", sheet_name="Sheet1")
df_zu3 = pd.read_excel(base / "一网通组网资费信息v15.xlsx", sheet_name="Sheet3")
pm_zu = df_zu3[["增值商品编码", "新增值商品名称", "增值商品描述", "月消费(元)",
                  "折扣", "科目", "限制不允许提前注销的协议期"]].copy()
pm_zu.columns = ["商品编码", "商品名称", "商品描述", "月消费(元)", "折扣", "科目", "协议期"]
price_zu = df_zu1[["主体产品名称", "增值产品编码", "增值产品名称", "增值产品描述",
                    "设备安装类型（NetWorkOfferCode）", "标准资费", "月消费(元)",
                    "议价金额（属性编码=900000010142、属性类型=311）",
                    "资费出账类型（属性编码=RateCycleType、字典组GrpRatePropMap）",
                    "限制不允许提前注销的协议期（AgreementPeriod）", "依赖业务", "子业务编码"]].copy()
price_zu.columns = ["主体产品", "增值产品编码", "增值产品名称", "描述", "设备安装类型",
                    "标准资费", "月消费(元)", "议价金额", "出账类型", "协议期", "依赖业务", "子业务编码"]

zu_md = f"""### 2.1 产品矩阵（人工维护）

{source_note}

"""
zu_md += to_markdown_table(pm_zu)
zu_md += f"""
### 2.2 资费与计费规则（人工维护）

{source_note}

"""
zu_md += to_markdown_table(price_zu)

# ============== 云无线 ==============
df_ywx_price = pd.read_excel(base / "云无线列表v4.xlsx", sheet_name="云无线资费列表")
pm_ywx = df_ywx_price[["主体商品名称", "增值商品编码", "增值商品名称", "增值商品描述",
                         "目录价（只读）（属性编码=992025012110370001）", "合同期",
                         "设备类型属性值（只读）",
                         "产品类别属性值（只读）（属性编码=992025012110370002）",
                         "状态"]].copy()
pm_ywx.columns = ["主体商品", "增值商品编码", "增值商品名称", "商品描述", "目录价",
                   "合同期", "设备类型", "产品类别", "状态"]
price_ywx = df_ywx_price[["主体商品名称", "增值商品编码", "增值商品名称",
                           "目录价（只读）（属性编码=992025012110370001）",
                           "折扣（步长1折）（属性编码=900000010042）",
                           "议价金额（属性编码=900000010142、属性类型=311）",
                           "资费出账类型（属性编码=RateCycleType、字典组GrpRatePropMap）",
                           "合同期", "订购生效方式", "退订失效方式", "重复订购", "状态"]].copy()
price_ywx.columns = ["主体商品", "增值商品编码", "增值商品名称", "目录价", "折扣",
                      "议价金额", "出账类型", "合同期", "订购生效方式", "退订失效方式",
                      "重复订购", "状态"]

ywx_md = f"""### 2.1 产品矩阵（人工维护）

{source_note}

"""
ywx_md += to_markdown_table(pm_ywx)
ywx_md += f"""
### 2.2 资费与计费规则（人工维护）

{source_note}

"""
ywx_md += to_markdown_table(price_ywx)

# ============== 手机看店和目 ==============
df_hm = pd.read_excel(base / "手机看店和目资费汇总v14.xlsx", sheet_name="商品规格")
df_hm_rule = pd.read_excel(base / "手机看店和目资费汇总v14.xlsx", sheet_name="业务规则")
pm_hm = df_hm[["主体商品编码", "主体商品名称", "分类", "增值商品编码", "增值商品名称",
                "商品描述", "新商品描述", "资费", "存储时长", "状态"]].copy()
pm_hm.columns = ["主体商品编码", "主体商品名称", "分类", "增值商品编码", "增值商品名称",
                  "商品描述", "新商品描述", "资费", "存储时长", "状态"]
price_hm = df_hm[["主体商品名称", "分类", "增值商品编码", "增值商品名称", "资费",
                    "议价金额（900000011141）",
                    "资费出账类型（属性编码=RateCycleType、字典组GrpRatePropMap）",
                    "重复订购", "生效方式", "科目", "营销案打折子业务编码",
                    "存储时长", "状态"]].copy()
price_hm.columns = ["主体商品", "分类", "增值商品编码", "增值商品名称", "资费",
                     "议价金额", "出账类型", "重复订购", "生效方式", "科目",
                     "营销案子业务编码", "存储时长", "状态"]

hm_md = f"""### 2.1 产品矩阵（人工维护）

{source_note}

"""
hm_md += to_markdown_table(pm_hm)
hm_md += f"""
### 2.2 资费与计费规则（人工维护）

{source_note}

"""
hm_md += to_markdown_table(price_hm)
hm_md += "\n#### 业务规则\n\n"
hm_md += to_markdown_table(df_hm_rule[["序号", "规则说明", "商品关系"]])

# Save outputs
(out_dir / "broadband.md").write_text(bb_md, encoding="utf-8")
(out_dir / "networking.md").write_text(zu_md, encoding="utf-8")
(out_dir / "cloud_wireless.md").write_text(ywx_md, encoding="utf-8")
(out_dir / "hemu.md").write_text(hm_md, encoding="utf-8")

print("Generated files:")
for p in sorted(out_dir.glob("*.md")):
    print(f"  {p.name}: {len(p.read_text(encoding='utf-8').splitlines())} lines")
