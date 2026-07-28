# PMWB 开发任务总表

> 集成者：Vicky2号 | 更新时间：2026-07-28
>
> **AI 开发者请先看**：`docs/COLLABORATIVE_DEV_WORKFLOW.md` 第四节「标准化任务认领与交付机制」

---

## 快速认领指南（给其他 AI 工具）

```
1. 找 ⬜待分配 且无依赖阻塞的最小编号任务
2. 把「开发者」列改成你的名字，「状态」改为 🔵开发中
3. 读 .workbuddy/tasks/<task-id>.md 获取完整开发 Spec
4. 切到指定分支开始干活
5. 完成后状态改 🟡待审查，备注写交付说明
```

---

## 当前批次：邮件中心整合（Mail Center Integration）

| task-id | 标题 | 分支 | 级别 | 状态 | 开发者 | 备注 |
|---------|------|------|------|------|--------|------|
| mc-1 | 后端代理层：配置+ProxyClient+路由 | feature/mc-1-backend-proxy | S2 | ✅已合入 | Vicky2号 | 25条路由，合并日志端点；需重启后端验证 |
| mc-2 | 前端路由与菜单：/mail-center 路由组 | feature/mc-2-frontend-route | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 审查剔除3个P0无关文件后合入 main (a5aac42→fd8afca) |
| mc-3 | 发送日志页（合并展示） | feature/mc-3-logs-view | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 812c8bc，审查移除未使用 mcError ref |
| mc-4 | 账号管理+通讯录/分组+模板管理 | feature/mc-4-admin-pages | S2 | ✅已合入 | 晓伴→Vicky2号审查 | 1cb76d3，4页CRUD完整 |
| mc-5 | 测试验证+浏览器冒烟+归档 | feature/mc-5-verify | S3 | ⬜待分配 | — | 依赖 mc-1~4 |

---

## 状态枚举
⬜待分配 → 🔵开发中 → 🟡待审查 → 🔴审查退回 → ✅已合入 / ❌已取消

## 任务 Spec 文件
存放于同目录 `.workbuddy/tasks/<task-id>.md`，每个任务一份，自包含全部开发上下文。
