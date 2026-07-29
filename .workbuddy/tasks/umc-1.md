# umc-1 邮件中心：新增人员中台出站客户端

## 背景上下文
需求3：统一邮件中心（`D:\项目\统一邮件中心\server`，独立 Node/Express/Prisma/SQLite 仓库，端口 3210）的联系人当前存本地 `Contact` 表，需改为只读复用"人员中台"(localhost:8001)。本任务先建一个出站 HTTP 客户端调用中台 staff 列表接口，供 umc-2 使用。

## 精确改动范围
文件（邮件中心仓库）：新建 `src/services/masterService.ts`
- 用 Node 22 全局 `fetch` 调 `http://localhost:8001/...` 人员中台 staff 列表接口。
- 接口契约参考 PMWB 侧 `D:\项目\个人工作台系统\backend\master_service.py`（方法名/路径/鉴权头）。先读该文件确认接口 path、query、返回结构、是否需要 token。
- 实现：带超时（AbortController，建议 5s）、错误降级（中台不可用时抛出可控错误/返回空列表，不让邮件中心崩溃）。
- 可选：加简单内存缓存（30s TTL）避免每次请求打中台。
- 不引入重框架；如需可加轻量 axios，但优先原生 fetch。

## 可执行验收命令
- 单元/集成测试：中台可用时返回人员列表；中台宕机时降级不抛未捕获异常。
- 手动：`curl localhost:3210/<新增调试路由或测试>` 验证能拿到中台数据（可临时加一个调试接口，合版前移除或保留只读）。
- `npm run build`（tsc）无类型错误。

## 禁止项清单
- 不改人员中台（那是另一个服务）。
- 不写入中台。
- 不引入与现有栈冲突的重依赖。

## 前置依赖
人员中台(8001)运行且暴露 staff 列表接口（需先确认接口与鉴权；若中台未提供合适接口，回报阻塞）。

## 起点指引
1. 读 `D:\项目\个人工作台系统\backend\master_service.py` 了解契约。
2. 确认 8001 是否运行：`curl localhost:8001/` 或问 Vicky2号。
3. 新建 `src/services/masterService.ts`。
