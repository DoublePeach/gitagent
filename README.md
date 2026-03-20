# 发布管理中心（Release Management Center）

基于 **FastAPI + SQLAlchemy(2.x) + Alembic** 的发布管理后端，支持：

- 飞书（Lark）机器人接收群消息
- 使用 LLM 将自然语言解析为结构化“意图 + 参数”
- 驱动发布计划的创建/查询/取消，以及（可选）登记分支与触发执行
- 对接 GitLab / Zadig（当前为最小闭环能力）
- 提供管理员 REST API

## 技术栈

- Web：`fastapi` + `uvicorn`
- 数据库：`sqlalchemy`(async) + `aiomysql`
- 迁移：`alembic`（异步模式 env）
- 调度：`apscheduler`（基于 `ENABLE_SCHEDULER` 可配置启停）
- 飞书：`/api/v1/bot/feishu/events`（含 `encrypt` 解密）
- LLM：阿里云百炼（OpenAI 兼容接口模式；使用 `openai` SDK）

## 目录/入口（你可以从这里快速理解）

- `app/main.py`：应用入口，注册路由、全局异常处理、可选启动调度器
- `app/routers/`
  - `health.py`：`GET /health`
  - `admin_release.py`：管理员发布计划 API（前缀 `/api/v1/admin`）
  - `debug_llm.py`：LLM 意图解析调试（前缀 `/api/v1/debug`）
  - `bot_feishu.py`：飞书机器人事件回调（前缀 `/api/v1/bot`）
- `app/db/`：SQLAlchemy 基础、会话、模型与 Alembic 迁移
- `app/services/`：发布服务与 LLM 服务（业务逻辑入口）
- `app/integrations/`：GitLab / Zadig / 飞书 HTTP 客户端

## 本地运行指南

### 1. 准备 Python 与依赖

确保你的 Python 版本满足项目要求（建议使用你当前可用的版本）。

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. 配置环境变量

复制示例环境文件并填写：

```powershell
Copy-Item .env.example .env
```

重点需要配置：

- `DATABASE_URL`：MySQL 连接串
- `OPENAI_API_KEY` / `OPENAI_BASE_URL`：阿里云百炼（OpenAI 兼容接口）
- `GITLAB_URL` / `GITLAB_TOKEN`
- `LARK_APP_ID` / `LARK_APP_SECRET` / `LARK_VERIFICATION_TOKEN` / `LARK_ENCRYPT_KEY`

> `run.ps1` 会自动读取 `.env` 到当前 PowerShell 进程环境里。

### 3. 执行数据库迁移（Alembic）

```powershell
python -m alembic upgrade head
```

迁移会创建 `release_plans` / `release_items` 两张表。

### 4. 启动服务

```powershell
.\run.ps1
```

默认端口 `8000`；你也可以指定端口：

```powershell
.\run.ps1 -Port 8000
```

验证接口：

- 健康检查：`GET http://127.0.0.1:8000/health`
- API 文档（Swagger）：`http://127.0.1:8000/docs`

### 5. 快速验证 LLM 解析（可选）

调用 LLM 调试接口（Swagger 或直接用 HTTP）：

- `POST /api/v1/debug/llm/parse`

请求体示例：

```json
{
  "text": "今晚 6 点将 WMS 发送到生产环境",
  "context": { "chat_id": "oc_xxx", "user_open_id": "ou_xxx" }
}
```

## 飞书本地联调（可选）

### 1. 启动服务

先用 `.\run.ps1` 启动本地后端。

### 2. 用 ngrok 暴露公网回调
如果本地没有安装ngrok的话，需要去官网安装：https://dashboard.ngrok.com/get-started/setup/windows
可以选择把ngrok.exe复制到此项目的根目录下，方便调用启用。

```powershell
.\debug_feishu.ps1
```

脚本会输出你的 webhook URL，格式类似：

- `https://<your-ngrok-domain>/api/v1/bot/feishu/events`

然后在飞书开放平台里：

- 填写回调地址（Request URL）
- 订阅事件：`im.message.receive_v1`
- 保存后飞书会触发 `url_verification`（challenge）

## 管理员 API（用于创建/查询/取消发布计划）

路由前缀：`/api/v1/admin`

- `POST   /api/v1/admin/releases`：创建计划
- `GET    /api/v1/admin/releases`：列出计划（支持过滤/分页）
- `GET    /api/v1/admin/releases/{plan_id}`：获取详情
- `DELETE /api/v1/admin/releases/{plan_id}`：取消计划

## 调度器说明

调度器是否启动由环境变量 `ENABLE_SCHEDULER` 控制（默认 `false`）。

当启用时，服务会在启动时后台运行定时扫描并触发到期的发布计划执行。

