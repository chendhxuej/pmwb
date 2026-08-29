"""生成周报/月报邮件的可视化预览页（含屏幕宽度模拟）。

用途：改动 `backend/utils/markdown_mail.py` 的邮件排版后，重新生成本预览页，
在浏览器中切换「宽屏 1920 / 笔记本 1440 / 小窗 1024 / 手机 375」验证
居中效果与占屏比，避免每次都要真发一封邮件去客户端里看。

用法（从任意目录执行均可）：
    <backend venv python> scripts/gen_work_report_preview.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path

# 定位项目根目录与 backend 目录（与脚本所在位置无关，便于从任意目录执行）
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
# core.config 在导入时从「当前工作目录」读取 .env，因此必须先切到 backend 目录，
# 否则会报 SECRET_KEY / DB_PASSWORD 缺失
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))

from utils.markdown_mail import _sanitize, render_work_report_html  # noqa: E402

MD_WEEKLY = """# 商客市场能力建设与运营工作周报（统计区间：2026-08-23 ~ 2026-08-29）

> 需求交付节奏平稳但 P0 在途积压明显，运营工单总量高位运行，重点工作整体推进偏慢，需聚焦 P0 风险与逾期事项强力攻坚。

**Part A 工作成效**

| 领域/模块 | 具体成果 | 量化数据 | 负责人 |
|---|---|---|---|
| 需求与交付 | 完成商客业务 CRM 订购底线资费调整并上线 | 1 项交付，上线日期 8/20 | 吴雨霜 |
| 运营支撑 | 批量宽带销户、数据割接评估等批量任务闭环 | 6 项工单已解决 | 方磊磊 |
| 重点工作 | 一网通选址能力完成需求梳理与接口联调，原型已出 | 进度 20% | 吴雨霜 |
| 会议协同 | 组织专题会议，覆盖需求评审、方案评估、专题对接 | 12 场 | 陈大海 |

**Part B 待改进问题**

| 问题描述 | 负责人/责任方 | 改进要求 |
|---|---|---|
| 高敏工单（P0/P1）处置时效不达标 | 王嘉锌 | 本周内闭环存量高敏单 |
| 合同金额计算差异工单积压 | 秦新 | 8/31 前给出核查结论 |
| 商客专区待办任务流监控缺失告警 | 王嘉锌 | 本周补齐监控规则 |

## 二、需求与交付

本期新增需求 3 项，完成开发交付 1 项，进行中 12 项。PO 级交付风险 1 项（商客专区智能报价二期联调延期）。

## 三、下周重点计划

1. 一网通选址能力：完成 9 类业务地址属性梳理，输出接口规范初稿。
2. 商客维系单体系：完成需求评审并启动开发排期。
3. 存量高敏工单清零冲刺，逐单确认闭环时间。
"""

MD_MONTHLY = """# 商客市场能力建设与运营工作月报（统计区间：2026-08-01 ~ 2026-08-31）

> 本月商客专区智能化试点稳步推进，AI 商机推荐覆盖率由 62% 提升至 74%，但交付一次成功率仍有差距。

**Part A 工作成效**

| 领域 | 成果 | 数据 |
|---|---|---|
| 商客专区 | 智能报价能力上线试点 | 覆盖 3 个地市 |
| 交付质量 | 一次交付成功率提升 | 80% → 87% |

**Part B 待改进问题**

| 问题 | 责任方 | 要求 |
|---|---|---|
| 融合开通流程长 | 王辅松 | 9 月中旬前压缩至 3 环节 |

## 二、下月重点工作与趋势研判

重点推进商客专区智能应用完善与交付流程升级。
"""

# 预览必须走 _sanitize —— 真实发送前后端会过 bleach 净化，白名单外的属性
# （如 align="center"）会被剥掉，不过一遍预览就会与实际收到的效果不符
weekly_html = _sanitize(render_work_report_html(MD_WEEKLY, "weekly", "陈大海"))
monthly_html = _sanitize(render_work_report_html(MD_MONTHLY, "monthly", "陈大海"))

SHELL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>周报邮件排版预览</title>
<style>
  body {{ margin:0; padding:24px; background:#1f2329; color:#e5e6eb;
         font-family:"Microsoft YaHei",Arial,sans-serif; }}
  h1 {{ font-size:16px; font-weight:600; margin:0 0 4px; }}
  .sub {{ font-size:12px; color:#86909c; margin-bottom:18px; }}
  .bar {{ margin-bottom:18px; }}
  .bar button {{ background:#2a2f36; color:#cfd3d9; border:1px solid #3a4048;
                 padding:6px 14px; margin-right:8px; cursor:pointer; font-size:13px; }}
  .bar button.on {{ background:#165dff; color:#fff; border-color:#165dff; }}
  .pane-wrap {{ display:flex; justify-content:center; }}
  .pane {{ background:#ffffff; overflow:auto; transition:width .25s ease; }}
  .pane-label {{ text-align:center; font-size:12px; color:#86909c; margin-top:8px; }}
  .hint {{ margin-top:22px; font-size:12px; color:#86909c; line-height:1.8; }}
  .hint code {{ background:#2a2f36; padding:1px 6px; color:#7cd6ff; }}
</style>
</head>
<body>
  <h1>周报邮件排版预览</h1>
  <div class="sub">生成时间：{gen_time} ｜ 方案A：内容容器 width=&quot;90%&quot; + align=&quot;center&quot;</div>
  <div class="bar">
    <button class="on" onclick="setW(1920,this)">宽屏 1920px</button>
    <button onclick="setW(1440,this)">笔记本 1440px</button>
    <button onclick="setW(1024,this)">小窗 1024px</button>
    <button onclick="setW(375,this)">手机 375px</button>
  </div>
  <div class="pane-wrap">
    <div class="pane" id="pane" style="width:1920px;max-width:100%;height:620px;">{body}</div>
  </div>
  <div class="pane-label" id="plabel">邮件客户端阅读窗格宽度：1920px</div>
  <div class="hint">
    验证要点：<br>
    ① 内容区应<strong>居中</strong>且左右留白均等（不再挤在左半边）；<br>
    ② 内容区宽度约占窗格 <strong>90%</strong>；<br>
    ③ 抬头为「品牌色带 + 两栏元信息」，无重复文案、无 emoji；<br>
    ④ 一级标题为「商客市场能力建设与运营工作周报」。<br>
    兼容性：本方案仅用 <code>width=&quot;90%&quot;</code> 与 <code>align=&quot;center&quot;</code>，
    Outlook / Foxmail / Gmail / 手机端均支持。
  </div>
<script>
function setW(w, btn) {{
  document.getElementById('pane').style.width = w + 'px';
  document.getElementById('plabel').textContent = '邮件客户端阅读窗格宽度：' + w + 'px';
  document.querySelectorAll('.bar button').forEach(function(b){{ b.classList.remove('on'); }});
  btn.classList.add('on');
}}
</script>
</body>
</html>
"""

gen_time = datetime.now().strftime("%Y-%m-%d %H:%M")
out_dir = ROOT / "prototype"
out_weekly = out_dir / "work-report-email-preview.html"
out_monthly = out_dir / "work-report-email-preview-monthly.html"

out_weekly.write_text(SHELL.format(gen_time=gen_time, body=weekly_html), encoding="utf-8")
out_monthly.write_text(SHELL.format(gen_time=gen_time, body=monthly_html), encoding="utf-8")

print("预览已生成:")
print(f"  {out_weekly} (周报)")
print(f"  {out_monthly} (月报)")
