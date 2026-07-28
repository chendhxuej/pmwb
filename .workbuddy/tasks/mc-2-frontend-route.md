# mc-2: 前端路由与菜单框架

> **状态**：🔵 开发中 | **分配**：其他 AI 开发者 | **SLA**：mc-3 依赖此框架

---

## 一、背景上下文

PMWB 前端技术栈：Vue3 + Element Plus + JavaScript，路由驱动菜单。当前 "邮件记录" 是单页面 `/mail-records` → `MailRecordsView.vue`，只读展示 email_records 表最近 N 条。

**本次目标**：将 "邮件记录" 升级为 "邮件中心"，包含 5 个子 Tab（发送日志 / 账号管理 / 通讯录 / 分组 / 模板），对接 mc-1 已完成的后端代理层。

**mc-1 后端代理层已合入 main**，所有接口前缀 `/api/v1/mail-center/`，共 25 条路由：

| 模块 | 代理路由 | 对应邮件中心 API |
|------|---------|------------------|
| 健康检查 | `GET /api/v1/mail-center/health` | `/api/health` |
| 账号 | `GET/POST /.../accounts`、`GET/PUT/DELETE /.../accounts/{id}`、`POST set-default`、`POST test` | `/api/accounts` |
| 通讯录 | `GET/POST /.../contacts`、`PUT/DELETE /.../contacts/{id}` | `/api/contacts` |
| 分组 | `GET/POST /.../contact-groups`、`PUT/DELETE /.../contact-groups/{id}` | `/api/contact-groups` |
| 模板 | `GET/POST /.../templates`、`GET/PUT/DELETE /.../templates/{id}`、`POST render` | `/api/templates` |
| 日志 | `GET /.../logs`、`GET /.../logs/merged`、`GET /.../logs/{id}` | `/api/logs` |

---

## 二、精确改动范围

### 2.1 修改文件：`frontend/src/router/index.js`

**新增路由组**，替代旧的 `mail-records` 单页路由：

```javascript
// 删除旧代码（约第 138-143 行）：
{
  path: 'mail-records',
  name: 'MailRecords',
  component: () => import('@/views/MailRecordsView.vue'),
  meta: { title: '邮件记录', icon: 'Message' },
},

// 替换为：
{
  path: 'mail-records',  // 兼容旧链接，重定向
  redirect: '/mail-center/logs',
  meta: { hidden: true },
},
{
  path: 'mail-center',
  name: 'MailCenter',
  component: () => import('@/views/mail/MailCenterLayout.vue'),
  redirect: '/mail-center/logs',
  meta: { title: '邮件中心', icon: 'Message' },
  children: [
    {
      path: 'logs',
      name: 'MailLogs',
      component: () => import('@/views/mail/MailLogsPlaceholder.vue'),
      meta: { title: '发送日志', icon: 'Tickets' },
    },
    {
      path: 'accounts',
      name: 'MailAccounts',
      component: () => import('@/views/mail/MailPlaceholder.vue'),
      meta: { title: '邮件账号', icon: 'User' },
    },
    {
      path: 'contacts',
      name: 'MailContacts',
      component: () => import('@/views/mail/MailPlaceholder.vue'),
      meta: { title: '通讯录', icon: 'Avatar' },
    },
    {
      path: 'groups',
      name: 'MailGroups',
      component: () => import('@/views/mail/MailPlaceholder.vue'),
      meta: { title: '联系人分组', icon: 'Grid' },
    },
    {
      path: 'templates',
      name: 'MailTemplates',
      component: () => import('@/views/mail/MailPlaceholder.vue'),
      meta: { title: '邮件模板', icon: 'Memo' },
    },
  ],
},
```

**说明**：
- `mail-records` 保留为隐藏重定向路由，兼容旧书签/深链
- `mail-center` 是父路由，菜单自动展示为一级菜单 "邮件中心"（MainLayout 的 `menuItems` computed 自动从 router 提取，无需手动改 MainLayout.vue）
- 只有 `logs` 需要占位组件（mc-3 会替换为真实实现），其余 4 个是占位（mc-4 替换）
- **子路由的 title 会作为 Tab 页签名称展示**

### 2.2 新建文件：`frontend/src/views/mail/MailCenterLayout.vue`

邮件中心 Tab 容器，类似 `OperationLayout.vue` 的 Tab 模式：

**功能规格**：
- 顶部 5 个 Tab：发送日志、邮件账号、通讯录、联系人分组、邮件模板
- Tab 切换 URL 同步（用 `router-link` 或 `el-tabs` + `router`）
- 内容区 `<router-view />` 渲染子路由
- Bento 风格：卡片容器 + 页面标题 "邮件中心"
- 左侧显示页面标题（从 `$route.meta.title` 取），右侧预留操作区 slot

**参考模式**：看 `OperationLayout.vue` 的 Tab 实现（如有），或使用 `el-tabs` 的 `v-model` 绑定 `$route.path`。

```vue
<template>
  <div class="mail-center-layout">
    <div class="page-header">
      <h2>邮件中心</h2>
      <span class="link-hint">统一邮件中心管理</span>
    </div>
    <el-tabs :model-value="$route.path" @tab-click="onTabClick" class="mail-tabs">
      <el-tab-pane label="发送日志" name="/mail-center/logs" />
      <el-tab-pane label="邮件账号" name="/mail-center/accounts" />
      <el-tab-pane label="通讯录" name="/mail-center/contacts" />
      <el-tab-pane label="联系人分组" name="/mail-center/groups" />
      <el-tab-pane label="邮件模板" name="/mail-center/templates" />
    </el-tabs>
    <div class="tab-content">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

function onTabClick(tab) {
  router.push(tab.props.name)
}
</script>

<style scoped>
.mail-center-layout {
  padding: 16px;
}
.page-header {
  margin-bottom: 12px;
}
.page-header h2 {
  margin: 0 0 4px 0;
  font-size: 18px;
  color: var(--text-primary, #303133);
}
.link-hint {
  font-size: 12px;
  color: var(--text-secondary, #909399);
}
.mail-tabs {
  margin-bottom: 16px;
}
.tab-content {
  min-height: 400px;
}
</style>
```

### 2.3 新建文件：`frontend/src/views/mail/MailLogsPlaceholder.vue`

发送日志占位组件，mc-3 会替换为完整实现。当前内容：

```vue
<template>
  <el-empty description="发送日志页面开发中（mc-3 任务）" />
</template>
```

### 2.4 新建文件：`frontend/src/views/mail/MailPlaceholder.vue`

通用占位组件，用于 mc-3/mc-4 前的四个子页面：

```vue
<template>
  <el-empty description="该页面待后续任务（mc-4）实现" />
</template>
```

### 2.5 修改文件：`frontend/src/api/mailCenter.js`

从当前的 1 个函数扩展到覆盖所有 25 条后端代理路由：

```javascript
import request from './request.js'

const BASE = '/mail-center'

// ── 健康检查 ──
export function getHealth() {
  return request.get(`${BASE}/health`)
}

// ── 邮件账号 ──
export function getAccounts(params) {
  return request.get(`${BASE}/accounts`, { params })
}
export function getAccount(id) {
  return request.get(`${BASE}/accounts/${id}`)
}
export function createAccount(data) {
  return request.post(`${BASE}/accounts`, data)
}
export function updateAccount(id, data) {
  return request.put(`${BASE}/accounts/${id}`, data)
}
export function deleteAccount(id) {
  return request.delete(`${BASE}/accounts/${id}`)
}
export function setDefaultAccount(id) {
  return request.post(`${BASE}/accounts/${id}/set-default`)
}
export function testAccount(id) {
  return request.post(`${BASE}/accounts/${id}/test`)
}

// ── 通讯录 ──
export function getContacts(params) {
  return request.get(`${BASE}/contacts`, { params })
}
export function createContact(data) {
  return request.post(`${BASE}/contacts`, data)
}
export function updateContact(id, data) {
  return request.put(`${BASE}/contacts/${id}`, data)
}
export function deleteContact(id) {
  return request.delete(`${BASE}/contacts/${id}`)
}

// ── 联系人分组 ──
export function getContactGroups() {
  return request.get(`${BASE}/contact-groups`)
}
export function createContactGroup(data) {
  return request.post(`${BASE}/contact-groups`, data)
}
export function updateContactGroup(id, data) {
  return request.put(`${BASE}/contact-groups/${id}`, data)
}
export function deleteContactGroup(id) {
  return request.delete(`${BASE}/contact-groups/${id}`)
}

// ── 邮件模板 ──
export function getTemplates(params) {
  return request.get(`${BASE}/templates`, { params })
}
export function getTemplate(id) {
  return request.get(`${BASE}/templates/${id}`)
}
export function createTemplate(data) {
  return request.post(`${BASE}/templates`, data)
}
export function updateTemplate(id, data) {
  return request.put(`${BASE}/templates/${id}`, data)
}
export function deleteTemplate(id) {
  return request.delete(`${BASE}/templates/${id}`)
}
export function renderTemplate(id, data) {
  return request.post(`${BASE}/templates/${id}/render`, data)
}

// ── 发送日志 ──
export function getLogs(params) {
  return request.get(`${BASE}/logs`, { params })
}
export function getMergedLogs(params) {
  return request.get(`${BASE}/logs/merged`, { params })
}
export function getLog(id) {
  return request.get(`${BASE}/logs/${id}`)
}
```

### 2.6 创建目录

```
mkdir frontend\src\views\mail
```

---

## 三、改动总览

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `frontend/src/router/index.js` | 删除旧 `/mail-records` 路由，新增 `/mail-center` 路由组 + 重定向兼容 |
| 新建 | `frontend/src/views/mail/MailCenterLayout.vue` | Tab 容器布局 |
| 新建 | `frontend/src/views/mail/MailLogsPlaceholder.vue` | 发送日志占位 |
| 新建 | `frontend/src/views/mail/MailPlaceholder.vue` | 通用占位（4 子页） |
| 修改 | `frontend/src/api/mailCenter.js` | 扩展全部 CRUD API 函数 |

**无需修改的文件**：
- `MainLayout.vue` — 菜单由 `menuItems` computed 从 router 自动生成，无需手动改
- `MailRecordsView.vue` — 保留不删（后续 mc-3 可能参考其代码，完成后统一清理）

---

## 四、可执行验收命令

```bash
# 1. 前端 build 无报错
cd frontend && npx vite build 2>&1 | tail -5
# 期望：✓ built in xxx ms

# 2. 前端 vitest 全绿
cd frontend && npx vitest run 2>&1 | tail -5
# 期望：Tests  4 passed (4)

# 3. 浏览器无头冒烟验证
# 启动前端后（npm run dev），打开浏览器访问：
# - http://localhost:5173/mail-center/logs → 看到 "邮件中心" + 5 个 Tab + 占位提示
# - http://localhost:5173/mail-center/accounts → Tab 切换到 "邮件账号" + 占位提示
# - http://localhost:5173/mail-records → 自动重定向到 /mail-center/logs
# - 左侧菜单出现 "邮件中心" 而非 "邮件记录"

# 4. API 函数可用性验证（Node 脚本）
node -e "
const mod = require('./src/api/mailCenter.js');
console.log(Object.keys(mod).join(', '));
"
# 期望输出包含：getHealth, getAccounts, getContacts, getContactGroups, getTemplates, getLogs, getMergedLogs 等
```

---

## 五、禁止项清单

- ❌ **禁止修改** `MainLayout.vue` — 菜单自动生成，不需要手动改
- ❌ **禁止删除** `MailRecordsView.vue` — 保留给后续参考
- ❌ **禁止修改** `frontend/src/api/request.js` — 拦截器已处理 code===0 返回 data.data，无需二次解包
- ❌ **禁止修改** `frontend/vite.config.js` — 代理配置 `'/api' → localhost:8000` 已正确
- ❌ **禁止新增** `docs/` 或 `README` 文件
- ❌ **禁止使用** Emoji 在代码中
- ❌ **禁止修改** 任何后端文件 — 这是纯前端任务

---

## 六、起点指引

- **分支**：`feature/mc-2-frontend-route`（已创建并推送到 origin）
- **clone 后操作**：`git checkout feature/mc-2-frontend-route`，分支基于最新 main
- **前端开发环境**：`D:\项目\个人工作台系统\frontend`
- **启动前端**：`npx vite --host 0.0.0.0 --port 5173`（已在 vite.config.js 配置代理到 8000）
- **后端需运行**：确保 PMWB 后端 8000 和邮件中心 3210 都在运行（否则 API 调用 502，不影响路由验证）
- **Element Plus 图标**：icon 名字参考 Element Plus Icons 文档（如 `Message`、`Tickets`、`User`、`Avatar`、`Grid`、`Memo`）
- **约定了 title 用中文**，meta.icon 用 Element Plus 图标组件名（字符串）

---

## 七、交付要求

完成开发后：
1. 依次执行验收命令全部通过
2. commit message 格式：`feat(mail-center): mc-2 前端路由与菜单框架 — /mail-center 路由组 + API 层 + Tab 布局`
3. 推送到 `origin/feature/mc-2-frontend-route`
4. 将 TASKS.md 中 mc-2 状态改为 🟡待审查，备注栏写 "分支已推送"

---

_Vicky2号 创建于 2026-07-28 | 版本 v1.0_
