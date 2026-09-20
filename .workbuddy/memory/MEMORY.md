# PMWB 项目长期记忆

## 0. 铁律
- 邮件：AI 自测一律 dry_run（不带 confirm_send），真发仅限老大页面显式点击。
- git：禁 checkout -b/branch/worktree；一律走 `~/.workbuddy/bin/git-safe-commit.sh`；远端真态用 `git ls-remote` 判定（本地 rev-parse/status 不可信）。

## 1. 拓扑
- FastAPI+Vue3+Element Plus+MySQL；GitHub chendhxuej/pmwb (main)。
- 端口：后端 8000 / 人员中台 8001 / 前端 5173 / MySQL 3306 / 邮件中心 3210。
- 后端解释器 `backend/venv/Scripts/python.exe`；无 --reload，改 py 须重启（taskkill 8000 PID，keeper 15s 自动拉起）。改代码不生效先查旧 NSSM 服务。

## 2. 关键约定
- request.js baseURL=/api/v1，code===0 解 data.data；success() 用 message=。
- 时区用 now_cn() 禁 utcnow()；前端空日期→Update schema validator 转 None。
- SELF_NAME（默认陈大海）唯一来源，禁硬编码「我」。
- API Key XOR 加密派生自 SECRET_KEY；OS 级 SECRET_KEY 覆盖 .env 致 401，decrypt_secret 已加自愈回退。

## 3. 多负责人契约
- 逗号分隔字符串存 handler（长度 512），不建多对多。单一实现：后端 utils/owners.py、前端 utils/owner.js，禁私有副本。
- 分隔符容错 [,，;；、]+；按人筛选必须 owner_set 交集，运营工单加 handler_exact=true 防误命中；展示 owners_display（顿号）、收件人逐人展开。
- 迁移：坏壳 20260908105939 致 multiple heads，须指定 revision id；新迁移挂 a7c3e91d4b28 后。

## 4. 运营监控
- 总览单一数据源 GET /operation/stats/by-handler（summary+category_matrix+handlers[].matrix），禁另拉列表算数。
- 热力矩阵唯一实现 components/Common/OwnerMatrix.vue（运营+任务中心共用，差异走 props）；热力色 color-mix 派生 token 禁硬编码。
- 深链：格子→/operation/{category}?handler=&status=。
- 回归 verify_ops_handler_matrix.cjs（33 项）；改总览/工单子页/OwnerMatrix 必跑。
- 删除契约：DELETE issues/{id} 不存在返 deleted=False；batch-delete；删 prod 主单级联清分析明细+关联任务+知识链接。

## 5. 任务中心
- services/task_center.py 8 collector 实时采集；路由 /task-center：stats/by-owner / tasks / send / draft 等。
- 二级仅 overview+all 两页（2026-09-20 删 8 来源子路由）；来源筛选走 ?source=，深链 /task-center/all?source=&owner=&status=。
- 口径（老大拍板）：未完结=pending+in_progress（排除 done/blocked）；主指标=整体超期率；include_done=true 看全量。
- 批量督办：OwnerMatrix superviseLabel 注入按钮→TaskBatchSuperviseDialog→POST /task-center/send 逐任务落 email_records。
- 回归 verify_task_overview.cjs（50）+ verify_supervise.cjs（9）必跑。状态统一 4 态 pending/in_progress/done/blocked。

## 6. 需求与交付
- dev_ticket_no 从 SentEmail 回填；AI 故事 .env 优先、超时 900s 三方对齐、失败必降级红色告警。
- 已上线必填 delivered_date；手册归档 01-业务知识/{group}/{name}/05-交付物/，真相源 PmwbReqManual。

## 7. 邮件渲染铁律
- 发信收口 dispatch_email；正文 build_mail_body；新场景注册 MailScene+SCENE_META+SCENE_FIELDS。
- 幽灵单元格 90% 居中，_wrap_content_responsive 唯一写法；_sanitize 白名单须含 align/height；改后重启+双校验。
- 督办邮件带附件（>20MB 单/50MB 累计跳过）；EmailRecord 带 ref_type/ref_id，EmailSuperviseLog 组件已接各模块。

## 8. 重点工作
- 周计划=目标，成员待办=人事；周次 derive_iso_week 自动推算严禁手填；周报按 p.week 精确匹配。

## 9. UI 设计系统
- 令牌单一源 styles/design.css，禁硬编码十六进制；PageHeader / StatusBadge+statusConfig / CommandPalette。
- 首页看板 2.0 基准 prototype/home-dashboard-v2-r3-unified.html，回归 verify_home_v2.cjs（25）必跑。

## 10. 验证纪律
- 运行态≠代码态；前端必真实 DOM 断言；vite build 过≠页面能渲染。
- 回归工具集：frontend/tests/e2e（route-smoke / verify_home_v2 / verify_ops_handler_matrix / verify_task_overview / verify_supervise 等）；截图读图被沙箱过滤，只信文本日志。
- Windows 取数：PowerShell 中文 JSON 乱码用 python urllib；netstat GBK 需 decode('gbk')；**PowerShell 工具 stdout 常被吞 → python 直写 utf-8 文件再 Read**。
- 沙箱：Edit 回执≠落盘须 grep 复核；删目录用 [System.IO.Directory]::Delete。

## 11. 模块纪要
- AI 总结归档 15-工作总结/{类型}/{日期}.md；周报三端 900s 对齐；章节编号四处同步。
- 用户故事落库 delete+insert；MAIN_NOTE_SECTIONS 14 章节；llm_provider 注册表 call_best_available。

## 12. 运营分析工单导入·解析布局契约（2026-09-20 修复）
- 布局支持（`services/operation_analysis.py::_parse_analysis_fields`，共 5 种）：①列A=短标签+列B=值；②列A=带冒号标签+列B=值；③「填写说明」模板=列A 长描述+**列B 带冒号标签**+列C 内容（列C 若重复抄标签会自动剥前缀）；④结果区两种排布=「列C 子标题+列D 内容」与「列B 子标题+列C 内容」，逐行识别，子标题无内容时不得把子标题当正文。
- 历史事故（已修，禁复发）：旧实现只匹配列A 标签 → 列B 标签永不命中，正文七字段静默丢失（191/199）；结果区用外层行列B 匹配且命中即 break → 只落第一项（194 的规则/补盲项丢了）。现已加 `_missing_field_warnings`：正文全空必显式告警。
- 日期容错 `_parse_date`：Excel 序列号须 ≥30000 才按序列解析，否则按 M.D（9.24 / 9月24日 / 9月22号）补当年/次年——杜绝「9.24」→1900-01-08 脏日期。
- 回归测试 `backend/tests/test_operation_analysis_parse.py`（5 用例，锁两套布局 + 日期容错），改解析器必跑。
- 运维：改解析器后必须重启 8000（无 --reload）再用 HTTP `/operation/analysis/parse` 做运行态验证；工单附件自动落 `uploads/operation/{issue_id}/`，可用于事后重解析补录。
- 重导流程：`DELETE /operation/issues/{id}` 会级联清 analysis 明细 + related_req_id 关联的遗留任务 → 再走 POST `/operation/analysis/import`（带 legacy_tasks）即完整重建。
