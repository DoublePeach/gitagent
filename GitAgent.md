# GitAgent项目设计文档（初版）

这个项目要做的是：把分散在 GitLab、Zadig 和各个系统同学脑子里的“发布流程”，收拢到一个统一、可配置、可追溯的“发布中台”，并且用飞书里的自然语言来驱动。

它的核心价值可以概括为三点：

1. **流程标准化 & 自动化**
   - 不同系统、不同环境（dev/uat/prod）的发布规则、分支规范、Zadig 工作流全部通过 Web 后台集中配置。
   - 从“创建发布计划 → 收集并预检测分支 → 定时合入 release → 合 prod → 触发部署 → 记录结果”的全链路自动编排，最大限度减少人工点错分支、错环境的操作风险。
2. **把复杂发布变成“在群里说句话”**
   - 开发、测试、业务只需在飞书群里 @大G 说自然语言（如“今晚 6 点发 WMS 到 prod”“帮我登记这个分支”），LLM 负责理解意图和参数，核心服务负责执行。
   - 对模糊和冲突场景自动追问澄清，大幅降低学习成本和沟通成本，让发布成为一种“对话能力”，而不是一套“少数人掌握的秘籍”。
3. **高可观测、高可追溯的发布资产**
   - 每一次发布都有结构化“发布计划 + 分支清单 + Git 提交 + Zadig 任务 + 状态变更记录”，可在 Web 后台和飞书中按系统、环境、时间随时查询。
   - 出问题可以快速定位“这次发了谁的什么分支，在什么阶段出的问题”，为回溯、审计和后续质量分析提供数据基础。

一句话总结：
 **这是一个用 LLM 做“发布大脑”、用配置化做“发布中台”的统一发布系统，把多系统多环境的上线流程，从人肉操作升级为“可配置、可编排、可追溯的对话式发布服务”。**

---

### 0. 文档目的

本设计文档描述“基于自然语言驱动的多系统多环境发布助手（大G）”的整体方案，包括：

- 系统目标与范围
- 整体架构与组件划分
- 核心功能与业务流程
- 数据模型（MySQL 8.0）
- 核心 API 设计（给飞书 Bot & Web 后台）
- 与 GitLab、Zadig 的集成方式
- LLM 使用方案 & Prompt 工程要求
- 非功能性要求与后续扩展规划

目标是让研发团队可以据此进行详细设计与开发排期。

---

### 1. 背景与目标

#### 1.1 背景

当前多个系统（以 WMS 为例）在 GitLab + Zadig 上进行发布，存在以下问题：

- 多系统、多环境发布流程分散，规则不统一。
- 每个系统命名规则、Zadig workflow 不同，人工操作容易出错。
- 发布计划、分支登记、冲突处理、发布记录查询等工作量大。
- 期望通过飞书群内简单自然语言交互，即可完成复杂的发布编排。

#### 1.2 目标

- 支持多个系统（每个系统一个 GitLab project & Zadig project），统一由“发布中台”调度。
- 支持同一系统同一天多次发布，通过“发布计划（plan）”精确区分。
- 支持 dev/uat/prod 等任意环境，每个环境配置独立 workflow / branch / deploy_mode。
- 支持完整的发布生命周期：
  - 创建发布计划、分支登记、预检测
  - 定时合入 release
  - 冲突终止策略
  - 合入 prod 并触发 Zadig 部署
- 完全自然语言交互，内部使用 LLM 作为“语义大脑”，通过结构化“内部指令集”驱动整个工作流。
- 提供 Web 后台进行配置管理与可视化运维。
- 为后续 BI 分析提供结构化发布记录数据。

---

### 2. 整体架构设计

#### 2.1 架构概览

组件：

1. **飞书 Bot 网关（Feishu Adapter）**
2. **LLM Service（语义解析服务）**
3. **Release Core Service（核心发布服务）**
4. **Web 管理后台（Admin UI）**
5. **GitLab 集成模块**
6. **Zadig 集成模块**
7. **MySQL 8.0 数据库**
8. **Scheduler（定时任务调度，可集成在 Core Service 内）**

数据流：

- 用户在飞书群 @大G 发送自然语言 → Bot → LLM → Core Service → 操作 DB + GitLab + Zadig → 通过 Bot 回写到飞书群。
- Web 管理后台通过 REST API 直接与 Core Service 交互，进行系统配置与计划管理。

![UML1-创建发布计划](D:\htt\pro\GitAgent\UML1-创建发布计划.png)

![UML2-到点合并分布分支&冲突终止](D:\htt\pro\GitAgent\UML2-到点合并分布分支&冲突终止.png)

![UML2-到点合并分布分支&冲突终止](D:\htt\pro\GitAgent\UML2-到点合并分布分支&冲突终止.png)

![UML4-飞书自然语言查询发布历史](D:\htt\pro\GitAgent\UML4-飞书自然语言查询发布历史.png)

#### 2.2 技术栈选型

1. **语言 & 运行环境**
语言：Python 3.13
包管理：pip
2. **Web & API 层**
Web 框架：FastAPI
ASGI 服务器：Uvicorn（开发） / Uvicorn + gunicorn（生产可选）
3. **数据 & 持久化**
数据库：MySQL 8+
ORM：SQLAlchemy 2.x（声明式）
迁移：Alembic
4. **任务调度 & 异步工作**
定时任务：APScheduler（应用内定时：扫描发布计划、触发合并与部署）
如后续有重型任务再考虑 Celery，但第一版先不用，避免复杂度。
5. **外部集成**
HTTP Client：httpx（异步）或  requests （同步，足够用）
用于：飞书、GitLab、Zadig 等 HTTP API 调用
6. **LLM & AI 层**
LLM 调用：OpenAI 官方 SDK（或兼容 SDK）
数据模型：Pydantic v2（FastAPI 默认）
模式：
首版：不使用 LangChain，用官方 SDK + Pydantic + function calling / JSON schema；
后续如果觉得 prompt/workflow 管理复杂，再轻度引入 LangChain 只封装 LLM 部分。
7. **其他工程配套**
配置管理：Pydantic Settings（从  .env  / 环境变量读取）
日志：内置  logging  + 简单 JSONFormatter（可选）
测试： pytest （后续再补）
关键原则：先保证“简单 + 好维护 + Cursor 易理解”，一切花活（LangChain、微服务拆分）都可以在后面版本加。

---

### 3. 功能设计

#### 3.1 系统配置管理（多系统、多环境）

- 每个系统对应一条 `system_config`：
  - GitLab 项目 ID、prod/dev/uat 目标分支。
  - release 分支命名模板（可包含 {system}/{env}/{date}/{time} 等占位符）。
  - Zadig 项目名、各环境 workflow 名。
  - 各环境 deploy_mode（auto/manual）。
  - 服务类型（single/microservice），以及默认服务列表（微服务场景）。

#### 3.2 发布计划管理

- 功能：
  - 创建计划（按 system/env/time）。
  - 支持同系统同日多次：使用 `plan_id = {system}-{env}-{date}-{seq}` 唯一标识。
  - 修改计划时间。
  - 取消计划。
  - 查询计划列表与详情。

- 状态机：
  - `collecting`：收集分支阶段。
  - `merging_to_release`：定时开始合到 release。
  - `waiting_confirm`：全部成功合入 release，等待执行 prod。
  - `waiting_execute`：准备执行 prod（可选状态，与 waiting_confirm 合并也行）。
  - `executing`：执行 release→prod + Zadig。
  - `success`：成功结束。
  - `failed`：失败（包含冲突终止、GitLab/Zadig 错误等）。
  - `cancelled`：被显式取消。

#### 3.3 分支登记与冲突策略

- 开发者通过自然语言登记自己的 feature 分支：
  - 注册/修改 `feature_branch` 与当前计划绑定。
  - 预检测阶段：
    - `feature_branch` vs release_branch 合并模拟；
    - 有冲突 → `status=conflict_precheck`，通知开发者；计划不终止，只是暂不包含此分支。
- 最终合入 release 时（schedule_time 到）：
  - 对所有 `pending` 分支依次真实合并；
  - 任何一个分支产生冲突 → 整个计划 `failed`，记录详细原因，@全体 通知冲突分支与文件；
  - 已预检测冲突的分支（`conflict_precheck`）可直接跳过或仍再尝试一次，策略可配置。

#### 3.4 发布到 prod & Zadig 集成

- 到 `execute_time` 或用户主动“立即执行”：
  - 再做一次 `release` vs `prod` 合并与冲突检查；
  - 合并成功，记录 prod commit；
  - 根据 deploy_mode：
    - 手动模式：核心服务主动调用 Zadig workflow API，触发部署；
    - 自动模式：仅记录合并结果，部署由 Zadig 自动处理（可监听状态）。
- 结果通知：
  - 成功：@全体，带上 plan_id、release 分支、commit、Zadig taskId。
  - 失败：@全体，附失败原因（GitLab 错误 / Zadig 错误 / 超时等）。

#### 3.5 发布记录与查询

- 每个 plan 完成后（success/failed），记录完整信息：
  - 系统、环境、release/target 分支。
  - schedule/execute/实际结束时间。
  - 参与的分支列表、状态（含冲突/剔除）。
  - Git prod 最终 commit id。
  - Zadig 项目/workflow/taskId、结果。
- 用户可在飞书通过自然语言查询：
  - 某系统最近 N 次发布。
  - 某日期范围内的 prod 发布情况。
- Web 后台可做更复杂的筛选和导出。

#### 3.6 LLM 驱动自然语言交互

- 内部指令集（Intent）：
  - `create_release_plan`
  - `update_release_plan_time`
  - `cancel_release_plan`
  - `register_branch`
  - `unregister_branch`
  - `query_release_plans`
  - `query_release_plan_detail`
  - `trigger_immediate_execute`
  - `query_release_history`
- LLM 负责：
  - 意图识别。
  - 参数抽取（system/env/time/plan_id/branch）。
  - 检测歧义，输出 `need_clarification=true` + 具体追问文案。
- 核心服务只接收结构化 JSON 指令（不直接接触用户自然语言）。

---

### 4. 数据库设计（MySQL 8.0）

#### 4.1 system_config

参考前一轮对话中给出的建表 SQL，可直接采用（略）。

关键字段：

- `system_name`（唯一）
- GitLab 配置：`gitlab_project_id`, `gitlab_prod_branch`, `gitlab_dev_branch`, `gitlab_uat_branch`
- `release_branch_template`
- Zadig 配置：`zadig_project`, `zadig_workflow_*`, `zadig_deploy_mode_*`
- 服务类型与默认服务列表。

#### 4.2 release_plan

字段要点：

- `plan_id`：主业务ID，唯一。
- `system_name`, `env`
- `release_branch`, `target_branch`
- `schedule_time`, `execute_time`
- `status`
- `created_by_feishu_id`, `created_by_name`
- `git_prod_commit_id`, `zadig_task_id`
- `failure_reason`, `extra_meta(JSON)`

#### 4.3 release_plan_branch

字段要点：

- `plan_id`, `system_name`
- `feishu_user_id`, `feishu_user_name`, `git_username`
- `feature_branch`
- `status`：pending / conflict_precheck / merged_to_release / conflict_final / skipped
- `conflict_detail`

> 视需要还可以引入日志表 `release_plan_log` 记录每一步状态变更与关键事件，方便审计与回溯。

---

### 5. 接口设计（概述）

本节仅概述，详细字段已在上一轮“API 设计”回答中给出，可以直接拷贝使用。

#### 5.1 飞书 Bot 对接 API（/api/bot）

- POST `/api/bot/commands/execute`：执行 LLM 解析后的内部指令。
  - Request: `{intent, params, context}`
  - Response: `{code, message, data:{reply_content, extra...}}`
- 所有具体业务（创建计划、登记分支等）都通过这一个入口完成。

#### 5.2 Web 后台 API（/api/admin）

- 系统配置：
  - GET `/api/admin/systems`：列表
  - GET `/api/admin/systems/{systemName}`：详情
  - POST `/api/admin/systems`：创建
  - PUT `/api/admin/systems/{systemName}`：更新
- 发布计划：
  - GET `/api/admin/plans`：列表
  - GET `/api/admin/plans/{planId}`：详情（含分支）
  - POST `/api/admin/plans/{planId}/cancel`：后台取消
  - POST `/api/admin/plans/{planId}/execute_now`：后台立即执行
- 发布历史：
  - GET `/api/admin/histories`：查询历史记录

#### 5.3 内部/调度 API（可选）（/api/internal）

- POST `/api/internal/plans/{planId}/merge_to_release`
- POST `/api/internal/plans/{planId}/merge_to_prod_and_deploy`

也可以完全不用 HTTP，直接在 Service 内部通过定时任务调用业务方法。

---

### 6. 与 GitLab 的集成

#### 6.1 功能需求

- 创建 release 分支（基于 prod/dev/uat 分支）。
- 分支合并预检测（dry-run 或 MR 检查）。
- 真正合并分支到 release / prod。
- 获取冲突详情（文件列表、diff 简要信息）。

#### 6.2 技术实现要点

- 使用 GitLab 官方 REST API 或本地 git 仓库操作：
  - Rest API:
    - 创建分支：`POST /projects/:id/repository/branches`
    - 创建 MR & 检查可否合并：`POST /projects/:id/merge_requests` + `GET /merge_requests/:iid`
    - 合并 MR：`PUT /merge_requests/:iid/merge`
  - 或者在独立 Runner 上使用 `git merge --no-commit --no-ff` 做 dry run。
- 需要考虑：
  - 鉴权：使用 project access token。
  - 超时与重试策略。
  - 冲突解析：仅提取前 N 个冲突文件用于消息展示，避免刷屏。

---

### 7. 与 Zadig 的集成

#### 7.1 功能需求

- 按系统 & env 触发指定 workflow。
- 指定要部署的服务列表（微服务/单服务）。
- 获取/监听任务状态（成功/失败/进行中）。

#### 7.2 技术实现要点

- 使用 Zadig 提供的 API：
  - URL、认证方式（token / header）。
  - 参数：project, workflow_name, environment, services[] 等。
- 触发后：
  - 立刻记录 task_id。
  - 轮询 Zadig 状态接口或配置 Zadig 回调到 Core Service。
- 失败时：
  - 将任务状态与错误信息写入 `failure_reason`。
  - 通知飞书群（@全体），给出 Zadig 任务链接。

---

### 8. LLM 使用方案 & Prompt 工程

#### 8.1 LLM 调用流程

1. 飞书 Bot 收到用户消息。
2. 组装调用 LLM 的请求：
   - system prompt（长）：定义角色、指令集、输出格式约束。
   - user prompt：用户原始消息 + 部分上下文（如系统列表、当前活跃计划等）。
3. LLM 返回 JSON：
   - `{intent, params, need_clarification, clarification_question}`。
4. 若 `need_clarification=true`：
   - Bot 不调用 Core Service，而是直接将 `clarification_question` 发送给用户。
5. 若不需要澄清：
   - Bot 调用 Core Service `/api/bot/commands/execute`。

#### 8.2 Prompt 要点

- 明确要求输出严格 JSON，不要出现自然语言。
- 列举所有 intent 及其必需参数。
- 明确写出“当无法确定 system/env/time/plan_id 时必须设置 need_clarification=true 并输出具体中文追问问题”。
- 可提供 few-shot 示例，例如：
  - “今天晚上六点 WMS 发到 prod” → create_release_plan
  - “帮我取消今天 WMS 的发布” → cancel_release_plan + 需要列出候选计划供用户选择
  - “我今天的分支是 feature_xxx” → register_branch

---

### 9. 非功能性要求

- 可用性：
  - 计划执行与调度逻辑必须可重复执行（幂等），防止因重试导致重复合并。
- 容错：
  - GitLab/Zadig 接口调用失败需要合理重试机制与降级处理。
- 审计：
  - 发布计划状态变更、手动干预（后台取消/立即执行）要有日志记录。
- 安全：
  - 内部 API 使用 token 校验；Web 后台需要账号体系或对接公司 IAM-SSO。（暂时先不做这个）
  - 飞书 Bot 只在指定群/白名单群中响应发布相关指令。
- 扩展性：
  - 后续可接入更多系统类型，甚至非 GitLab 源（如 GitHub）和非 Zadig 部署平台，只需扩展系统配置与集成模块。

---

