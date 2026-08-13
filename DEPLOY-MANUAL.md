# PMWB 部署手册（面向协作者 / 新环境）

> 适用对象：需要从零在另一台机器拉取并跑起 **产品经理个人工作台 (PMWB)** 的开发者或协作者。  
> 适用场景：本地开发、演示部署。生产部署仅在文末给出要点提示。  
> 配套文档：根目录 `README.md`（功能/架构总览）、`docs/需求规格说明书.md`。



---

## 0. 一句话架构

PMWB 由 **3 个本地服务 + 2 个可选外部服务** 组成，全部跑在 localhost：

| 端口   | 服务                       | 是否必需  | 说明                                    |
| ---- | ------------------------ | ----- | ------------------------------------- |
| 3306 | MySQL                    | ✅ 必需  | 两个库：`yxtyg_db`（主）、`pmwb_master`（人员中台） |
| 8000 | 主后端（FastAPI）             | ✅ 必需  | `backend/`，统一前缀 `/api/v1`             |
| 8001 | 人员中台 Master（FastAPI 微服务） | ✅ 必需  | `services/master/`，组织/人员唯一数据源         |
| 5173 | 前端（Vite + Vue3）          | ✅ 必需  | `frontend/`，dev 模式内置 `/api` 代理到 8000  |
| 3210 | 统一邮件中心                   | ⚠️ 可选 | **独立外部服务，本仓库不含源码**；缺失时邮件发送降级（不中断业务）   |

> 浏览器插件 `extension/`（Chrome MV3）为可选增强，不影响主流程，本文不展开。

---

## 1. 环境要求

| 依赖      | 版本         | 说明           |
| ------- | ---------- | ------------ |
| Python  | 3.11+      | 主后端与人员中台均用   |
| Node.js | 18+        | 前端；建议 20 LTS |
| MySQL   | 5.7+ / 8.0 | 需支持 utf8mb4  |
| 包管理     | pip / npm  | —            |
| （可选）Git | 任意         | 拉取代码         |

---

## 2. 获取代码

```bash
git clone <你的仓库地址> pmwb
cd pmwb
```

> 仓库已通过 `.gitignore` 排除所有 `.env` 真实配置文件，**不会**包含任何数据库密码或 API Key。

---

## 3. 数据库准备（先建库，再迁移）

PMWB 用 Alembic 管理表结构，但 **Alembic 只建表、不建库**，需先手动建两个空库。

```sql
-- 用 root 或有权限账号登录 MySQL 后执行
CREATE DATABASE yxtyg_db      CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE pmwb_master   CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

- `yxtyg_db`：主后端业务库（含 `sent_emails` 等表，由迁移自动建表）。
- `pmwb_master`：人员中台独立库。

> 说明：本机历史环境曾导入 6000+ 条 `sent_emails` 需求催办数据，迁移只负责建表，**新环境表为空属正常**，需求模块可正常使用只是初始无数据。

---

## 4. 主后端（端口 8000）

### 4.1 安装依赖

```bash
cd backend

# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4.2 配置文件

复制模板并填写真实值：

```bash
cp .env.example .env      # Windows 用 copy .env.example .env
```

`.env` 必填项（缺失会启动报错）：

| 字段                                            | 说明                                                |
| --------------------------------------------- | ------------------------------------------------- |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_NAME` | 指向第 3 步建的 `yxtyg_db`                              |
| `DB_PASSWORD`                                 | **必填**，无默认值                                       |
| `SECRET_KEY`                                  | **必填**，随机长字符串（如 `openssl rand -hex 32` 生成）        |
| `MASTER_SERVICE_URL`                          | 人员中台地址，默认 `http://localhost:8001`                 |
| `EMAIL_CENTER_URL`                            | 邮件中心地址，默认 `http://localhost:3210`（无邮件中心可留默认，功能降级） |
| `OBSIDIAN_VAULT_PATH`                         | Obsidian 仓库路径，**可选**，留空则知识库联动不可用                  |
| `DEBUG`                                       | 生产/日常保持 `false`                                   |

### 4.3 执行数据库迁移

```bash
# 在 backend/ 目录下（venv 已激活）
alembic upgrade head
```

> 若修改过 SQLAlchemy 模型而未迁移，启动会报 `1054 Unknown column`，重跑上面命令即可。

### 4.4 启动

```bash
# 开发模式（热重载）
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 验证
curl http://127.0.0.1:8000/api/v1/health
# 预期返回 {"code":0,...}
# API 文档：http://127.0.0.1:8000/docs
```

---

## 5. 人员中台 Master（端口 8001）

独立 FastAPI 微服务，是组织/人员/联系方式的**唯一数据源**，前端选人、邮件收件人解析都依赖它。

### 5.1 安装依赖

```bash
cd services/master

# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5.2 配置文件

```bash
cp .env.example .env
```

填写 `MASTER_DB_*` 指向第 3 步建的 `pmwb_master` 库，`MASTER_DB_PASSWORD` 必填。

### 5.3 执行迁移

```bash
# 在 services/master/ 目录下（venv 已激活）
alembic upgrade head
```

### 5.4 启动

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

> 首次启动后，可在「人员中台」页面手动录入组织或导入数据；本仓库不含示例数据。

---

## 6. 前端（端口 5173）

### 6.1 安装依赖

```bash
cd frontend
npm install
```

### 6.2 启动

```bash
npm run dev          # 开发模式，默认 http://localhost:5173
```

前端 `vite.config.js` 已内置代理：`/api` → `http://127.0.0.1:8000`，因此**无需额外配置**即可联调主后端。

如需构建静态产物部署：

```bash
npm run build        # 产物在 frontend/dist/
npm run preview      # 本地预览构建结果
```

> 若后端不在本机 8000，请修改 `frontend/vite.config.js` 中 `server.proxy['/api'].target`，或部署时用 Nginx 反代。

---

## 7. 启动顺序与验证清单

推荐顺序（后两者依赖 MySQL 就绪）：

```
1. 启动 MySQL（3306）
2. 启动主后端（8000）
3. 启动人员中台（8001）
4. 启动前端（5173）
```

访问 `http://localhost:5173` 即进入系统。页面右上角若无报错、菜单可正常打开即为成功。

---

## 8. 可选能力说明（缺失不影响启动）

| 能力            | 依赖                               | 缺失后的表现                                        |
| ------------- | -------------------------------- | --------------------------------------------- |
| 邮件发送          | 统一邮件中心 (3210)                    | 邮件相关按钮调用失败仅记 `send_status=failed`，**不中断**其他功能 |
| 知识库联动         | `OBSIDIAN_VAULT_PATH` 指向有效 Vault | 知识沉淀/回链不可用，其余正常                               |
| Kimi 智能拆分用户故事 | `US_STORY_LLM_*` 配置且额度充足         | 用户故事生成策略中「Kimi 智能拆分」灰化，可改用「合并生成」（规则引擎，秒级）     |

---

## 9. 常见问题排查

| 现象                                      | 原因 / 解决                                        |
| --------------------------------------- | ---------------------------------------------- |
| 后端启动即报错 `DB_PASSWORD` / `SECRET_KEY` 缺失 | 未填 `.env` 必填项，回到 4.2 填写                        |
| 接口 500 且日志 `1054 Unknown column`        | 没跑 Alembic 迁移，回到 4.3 执行 `alembic upgrade head` |
| 前端白屏 / 接口 404                           | 后端未起，或 vite 代理目标端口不对（默认 8000）                  |
| 端口被占用                                   | 检查是否有旧进程占用 8000/8001/5173/3306，结束后再起           |
| 人员中台 8001 连不上                           | 确认 master 已启动且 `MASTER_SERVICE_URL` 配置正确       |
| Kimi 智能拆分不可点                            | 属正常降级（见第 8 节），非 bug                            |

---

## 10. 生产部署要点（简要）

本地开发用 `--reload` 即可；生产建议：

- 后端用 `gunicorn` / `uvicorn` 多 worker，关闭 `--reload`、`DEBUG=false`；
- 用 Nginx 反代 8000/8001，并把 `frontend/dist/` 作为静态站点托管，或将 `/api` 反代到后端；
- 数据库密码、API Key 一律走环境变量 / 密钥管理，绝不入库；
- 多个 `.env` 文件（主后端、master）分别配置，互不共用。

---

## 11. 对外分享前的隐私提示（重要）

本仓库为个人工作台项目，包含两类**不应随代码外传**的内容，分享前请确认：

1. **所有 `.env` 真实文件**——已被 `.gitignore` 排除，切勿 `git add -f` 强行加入。
2. **`.workbuddy/memory/`**——含个人工作日志、业务台账与真实姓名等隐私数据。当前 `.gitignore` 为支持多 AI 协作**放行**了该目录。若公开/分享给外部协作者，建议改为忽略：
   ```gitignore
   # 在 .gitignore 中取消对 memory 的放行
   .workbuddy/memory/
   ```
   保留 `.workbuddy/tasks/`（任务规范）与 `.workbuddy/reviews/`（审查记录）即可满足协作需要。

> 本手册不要求任何密钥即可完成部署；所有敏感信息均在 `.env` 模板中以 `<必填>` 占位。
