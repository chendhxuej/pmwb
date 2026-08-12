# umc-2 邮件中心：contacts 读路径改中台 + 禁用本地增改删

## 背景上下文
依赖 umc-1。把邮件中心联系人读路径从本地 `Contact` 表改为人员中台数据；禁用本地联系人增改删，不再单独维护一套人员数据。

## 精确改动范围
文件（邮件中心仓库）：
- `src/services/contacts.ts`：`listContacts` 改为调用 `masterService.getStaffList()` 并做字段映射（中台 staff → {name, email, department, tags?}；中台字段可能含 phone/position/org，按需映射，本地 Contact 仅 name/email/department/tags）。
- `createContact/updateContact/deleteContact` 及 `src/routes/contacts.ts` 对应 POST/PUT/DELETE 路由：改为只读或返回 403/提示"联系人由人员中台统一管理，不可在此编辑"。
- `contactsSeed.ts` 种子逻辑调整：不再写死默认联系人（或改为从中台拉取快照）。
- `Contact` 模型可保留作为本地只读快照（可选），但写路径关闭。
- 中台字段缺失（如 tags）时给默认值，不报错。

## 可执行验收命令
- `GET /contacts` 返回中台人员（字段映射正确）。
- `POST/PUT/DELETE /contacts` 被禁用或返回只读提示。
- 中台宕机时 `GET /contacts` 降级（空/缓存），不 500 崩溃。
- `tsc` 通过；邮件中心冒烟：通讯录页展示中台数据。

## 禁止项清单
- 不双写中台（只读）。
- 不保留可编辑 UI 的后端写能力。
- 不改发信逻辑（nodemailer/imap）。

## 依赖
umc-1。

## 起点指引
读 `prisma/schema.prisma`(Contact 模型) 与 `src/services/contacts.ts`、`src/routes/contacts.ts`。
