# Task Spec: mc-opt-1 — 邮件中心统计概览卡片

## 背景上下文
邮件中心 mc-1~4 已完成基础框架（路由+日志页+4个管理页），但缺少全局数据概览。用户进入邮件中心后无法一眼看到发送量、成功率等核心指标。

## 改动范围

### 后端
1. **新增接口** `GET /mail-center/stats` — 邮件中心统计概览
   - 返回字段：
     - `todaySent` — 今日发送量
     - `weekSent` — 本周发送量
     - `successRate` — 近7天成功率（%）
     - `accountCount` — 邮件账号总数
     - `contactCount` — 通讯录联系人总数
     - `templateCount` — 模板总数
     - `pendingAlerts` — 待处理异常数（失败邮件数）
2. 在 `backend/routers/mail_center.py` 新增 `/stats` 路由
3. 使用已有 `MailCenterProxyClient` 从邮件中心(3210)拉取数据，结合本地 `EmailRecord` 计算

### 前端
1. **新增组件** `frontend/src/views/mail/MailStatsOverview.vue`
   - 6~8 个 KPI 卡片横向排列（参考截图顶部大数字风格）
   - 每个卡片：大数字 + 标签 + 环比变化（↑↓箭头+百分比）
   - 卡片hover效果：轻微上浮+阴影
2. 在 `MailCenterLayout.vue` 中 `<el-tabs>` 上方引入 `MailStatsOverview`

## 验收命令
```bash
cd backend && python -m pytest tests/ -k mail -x --tb=short
cd frontend && npx vite build 2>&1 | tail -3
cd frontend && npx vitest run 2>&1 | tail -3
# 浏览器访问 /mail-center 确认统计卡片展示正常
```

## 禁止项
- 不要修改现有管理页（MailAccountsView 等）
- 不要修改邮件中心代理路由的已有接口
- 统计计算以内存聚合为主，不要新增复杂SQL

## 起点指引
- 后端路由：`backend/routers/mail_center.py`（在文件末尾追加 `/stats` 路由）
- 前端布局：`frontend/src/views/mail/MailCenterLayout.vue`
- 代理客户端：`backend/utils/email.py` 中 `MailCenterProxyClient`
