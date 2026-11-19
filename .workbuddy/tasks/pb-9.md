# pb-9（L8）回归与真实页面验证

- 级别：S2 ｜ blockedBy：pb-1~pb-8 ｜ 状态：⬜待分配
- 方案章节：10（AC-A~J）/ `.workbuddy/memory/MEMORY.md` 回归铁律

## 目标
新增模块真跑得通、既有模块不退化。

## 范围
- 新增 `scripts/verify_paiban.py`（后端口径）+ `scripts/verify_paiban_dom.mjs`（真实 DOM），覆盖 AC-A~J 组，含 **I 组准入与顺延**、**J 组反馈同步**。
- 既有回归防退化：`rootcause.mjs` / `analysis.mjs` / `module_problem.mjs` / `export_report.py` / `dashboard_consistency.py` / `overall.py` / 客类 DOM 脚本。
- 真实页面验证：5 页签、版本选择器联动、准入模拟器、自动顺延、硬门禁、督办预览 dry_run、反馈采纳/回滚。

## 铁律
- 断言函数必须收 `(name, cond, extra)`；写成 `(n, e='')` 全部恒 PASS（输出清一色 `true` 是信号）。
- 新 e2e 先确认失败条件能真失败；基线从 API 动态取，禁写死快照值。
- 前端必真实 DOM 断言（computed('字符串') 白屏且 build 无感）；SPA 首导航偶发旧上下文 → 导航重试，不放宽断言。
- 邮件相关一律 dry_run；页面「确认发送」只验证预览与计数，不真发。

## 验收
- 新增断言全绿；既有回归不新增红。
- `pytest` 既有 ~29 红（knowledge/meeting/...）属历史存量，`pytest test_complaint*` 2 红 = SQLite 不支持 SEPARATOR，勿误判。
- 交付末尾附「迁移指令 + 重启指令」（服务名 / 命令 / 验证方式），重启由老大执行。
