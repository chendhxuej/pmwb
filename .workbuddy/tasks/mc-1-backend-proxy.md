# Task: mc-1 - 后端代理层（配置 + MailCenterProxyClient + 全量 CRUD 路由）

## 基本信息
- **分支**: feature/mc-1-backend-proxy
- **级别**: S2
- **预估**: 3 文件，约 250 行
- **依赖**: 无

## 目标
在 PMWB 后端建立统一邮件中心（localhost:3210）的代理层，使前端无需跨端口调用，统一通过 `/api/v1/mail-center/*` 访问邮件中心全部功能。

## 改动范围
| 类型 | 文件路径 | 说明 |
|------|----------|------|
| 修改 | backend/core/config.py | 新增 `EMAIL_CENTER_API_KEY` 配置项 |
| 修改 | backend/utils/email.py | 新增 `MailCenterProxyClient` 通用代理类 |
| 修改 | backend/routers/mail_center.py | 重写，新增 25 条 CRUD 代理路由 + 合并日志端点 |
| 修改 | backend/.env | 新增 `EMAIL_CENTER_API_KEY=` |

## 技术要求
- 邮件中心 API 基础路径：`http://localhost:3210`
- API Key 通过 `x-api-key` 头传递（可选，邮件中心不强制验证）
- 所有代理请求使用 `httpx.Client`，超时 10s
- 代理路由统一返回格式：`success(data=...)` 或 `error(...)`
- 合并日志端点需同时查询邮件中心 SendLog 和 PMWB email_records 表，按时间倒序归并分页

## 路由清单

### 健康检查
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /mail-center/health | 邮件中心健康检查 |

### 邮件账号
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /mail-center/accounts | 列表 |
| POST | /mail-center/accounts | 新增 |
| PUT | /mail-center/accounts/{id} | 修改 |
| DELETE | /mail-center/accounts/{id} | 删除 |
| POST | /mail-center/accounts/{id}/test | 测试连接 |
| PUT | /mail-center/accounts/{id}/set-default | 设为默认 |

### 通讯录
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /mail-center/contacts | 列表（支持 search） |
| POST | /mail-center/contacts | 新增 |
| PUT | /mail-center/contacts/{id} | 修改 |
| DELETE | /mail-center/contacts/{id} | 删除 |

### 联系人分组
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /mail-center/contact-groups | 列表 |
| POST | /mail-center/contact-groups | 新增 |
| PUT | /mail-center/contact-groups/{id} | 修改 |
| DELETE | /mail-center/contact-groups/{id} | 删除 |

### 邮件模板
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /mail-center/templates | 列表 |
| POST | /mail-center/templates | 新增 |
| PUT | /mail-center/templates/{id} | 修改 |
| DELETE | /mail-center/templates/{id} | 删除 |
| POST | /mail-center/templates/{id}/render | 渲染预览 |

### 发送日志（⚠️ 注意路由顺序）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /mail-center/logs/merged | 合并日志（邮件中心 + PMWB email_records） |
| GET | /mail-center/logs | 邮件中心日志列表 |
| GET | /mail-center/logs/{log_id} | 日志详情 |

### 发送邮件
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /mail-center/send | 发送邮件（代理转发） |

## 完成标准 (DoD)
- [x] router 模块可正常导入（25 条路由）
- [ ] `/api/v1/mail-center/health` 返回 200
- [ ] `/api/v1/mail-center/accounts` 代理返回账号列表
- [ ] `/api/v1/mail-center/logs/merged` 返回合并日志（不报 422）
- [ ] 邮件中心不可达时返回 502 友好错误，不抛异常
- [ ] pytest 通过

## 已知问题
- `/logs/merged` 路由必须放在 `/logs/{log_id}` 前面，否则 FastAPI 会将 `merged` 匹配为 `log_id`
- `get_db` 导入路径为 `db.session`（SQLAlchemy Session）

## 提交方式
1. 在 feature/mc-1-backend-proxy 分支上开发
2. 自测通过后 commit
3. 将 TASKS.md 中 mc-1 状态改为 🟡待审查
