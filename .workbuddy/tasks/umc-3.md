# umc-3 邮件中心前端：通讯录只读展示

## 背景上下文
依赖 umc-2。邮件中心管理前端（`public/admin.js`）通讯录页改为只读展示中台人员，隐藏新增/编辑/删除按钮，并标注"数据来自人员中台"。

## 精确改动范围
文件（邮件中心仓库）：`public/admin.js`
- `loadContacts()`/`renderContacts()`：展示中台返回数据（umc-2 已改后端，前端基本不动，仅确认渲染字段映射）。
- `openContactModal()` / `deleteContact()`：隐藏或禁用新增/编辑/删除入口；表单改为只读展示。
- 页面加提示："联系人由人员中台统一管理，不可在此编辑"。
- 路由 `src/routes/contactGroups.ts` 对应 UI 如涉及也改为只读。

## 可执行验收命令
- 通讯录页只读展示中台人员，无编辑入口。
- 浏览器冒烟：打开 3210 通讯录，数据来自中台，无新增/删除按钮。
- 中台宕机时页面友好提示而非报错白屏。

## 禁止项清单
- 不实现本地联系人写 UI。
- 不改发信流程。

## 依赖
umc-2。

## 起点指引
读 `public/admin.js` 通讯录相关函数（loadContacts/renderContacts/openContactModal/deleteContact，约 264-360 行）。
