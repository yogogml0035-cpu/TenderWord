# TenderWord 架构地图

**生成日期：** 2026-06-04

本文件是根级系统架构地图，描述 TenderWord 的系统边界、子系统职责和推荐理解路径。实现细节仍以代码为准；子系统内部事实以 `backend/.planning/codebase/` 和 `frontend/.planning/codebase/` 为准。

## 系统边界

TenderWord 是招标文档生成与修改系统，核心闭环是：

```text
浏览器 / Next.js 工作台
  -> FastAPI /api
  -> 任务队列 + SSE
  -> LangGraph tender / skill / comment_supplement workflow
  -> Prompt Layer + LLM provider / DeepAgents content_agent / LangChain comment_agent
  -> Word COM 文档操作
  -> 生成文件 / 任务结果 / 下载
```

系统的完整能力依赖 Windows + Word COM。前端可以在 WSL/Linux Node 环境运行，但后端 Word 自动化必须使用 Windows Python、pywin32 和本机 Word/WPS COM 能力。

## 子系统职责

### `frontend/`

`frontend/` 是 Next.js 16 + React 19 工作台。它负责：

- `/` 根路径重定向与 `/tender` 工作台入口。
- 招标类型侧栏、表单面板、聊天和任务面板。
- 会话、草稿、历史、任务摘要与 SSE resume 元数据的 `sessionStorage` 持久化。
- 初次生成 `generation_mode`、`comment_generation_mode` 草稿，高级设置控件和智能体 `agent-step` 过程卡展示。
- 初次生成下载卡上的补充批注动作和 `comment_agent` 过程卡展示。
- 前端 `TenderType`、URL canonical 化、`gngk` 子类型身份匹配。
- 通过 `frontend/lib/api.ts` 调用后端 JSON、上传、下载、NDJSON 和 SSE helper。
- 模板候选弹窗、候选选择、后端文件回填和下载链接展示。

事实入口：
- `frontend/.planning/codebase/ARCHITECTURE.md`
- `frontend/.planning/codebase/STRUCTURE.md`
- `frontend/.planning/codebase/INTEGRATIONS.md`
- `frontend/.planning/codebase/CONVENTIONS.md`
- `frontend/.planning/codebase/TESTING.md`

### `backend/`

`backend/` 是 FastAPI + LangGraph + Word COM 后端。它负责：

- `/api` 前缀下的生成、重写、补充批注、任务、SSE、任务上下文助手 agent run、会话心跳、上传下载和模板候选接口。
- `DocumentService` 任务创建、graph 选择、初始 state 构造、任务提交和结果 payload。
- `TaskQueueManager` 串行化文档任务、跟踪进度、取消、心跳和清理。
- `SSEManager` 事件缓冲、客户端管理和重连重放。
- 标准 tender graph、rewrite task skill graph、任务上下文助手 `task_context_assistant` 和 `generation_mode=agent` 的 content agent 分支。
- agent generate 与补充批注共用的 `comment_agent` 批注生成、锚点校验、写回统计和过程事件。
- Word COM 生命周期、共享 Word helper、类型特化节点和 Prompt Layer。
- 外部 LLM provider、招标详情接口和模板候选接口的后端代理。
- `content_verify_agent` 的审核契约只保留真实需修复的问题；无问题或无需修改的审核项会在后端折叠为 `[]`，避免把空 findings 传播到 workspace audit 或前端过程卡。

事实入口：
- `backend/.planning/codebase/ARCHITECTURE.md`
- `backend/.planning/codebase/STRUCTURE.md`
- `backend/.planning/codebase/INTEGRATIONS.md`
- `backend/.planning/codebase/CONVENTIONS.md`
- `backend/.planning/codebase/TESTING.md`

### `asset/`

`asset/` 是长期知识包目录。它不替代代码真源，但沉淀跨多轮需求会复用的同步面、边界和回归风险。

当前有效主题：
- `asset/shared_runtime_word_skill_knowledge_pack.md`
- `asset/tender_type_identity_session_knowledge_pack.md`
- `asset/template_candidate_pipeline_knowledge_pack.md`

### 根级文档

- `AGENTS.md`：仓库级执行规则、阅读顺序和维护红线。
- `ARCHITECTURE.md`：系统边界和子系统职责。
- `INTERFACES.md`：前后端接口、状态、事件和外部集成边界。
- `coding_maps/SYSTEM_MAP.md`：跨子项目系统地图和按任务阅读指南。
- `README.md`：首次安装和启动导航。

## 架构分层

### 前端分层

```text
frontend/app/
  根路径重定向、工作台路由边界与页面组合
frontend/components/chat/
  工作台面板、聊天、任务消息、侧栏
frontend/components/forms/
  招标表单、上传、模板候选弹窗
frontend/stores/
  持久化会话状态、agent-step 过程卡与临时 stream 状态
frontend/lib/
  API client、SSE wrapper、招标数据 helper、gngk form type helper
frontend/types/ 与 frontend/utils/
  API 契约、招标身份、URL 映射
```

核心原则：

- 组件不直接写裸 `fetch`，后端调用统一进 `frontend/lib/api.ts`。
- URL canonical 化统一走 `frontend/utils/tenderTypeMapper.ts` 和 store helpers。
- `gngk` 后端 `form_type` 分派统一走 `frontend/lib/gngkFormType.ts`。
- 会话语义继续使用 `sessionStorage`。
- `TenderFormShared` 初始化优先级是 `draft > URL > default`。

### 后端分层

```text
backend/api/
  FastAPI 路由
backend/models/
  Pydantic API 与运行时契约
backend/services/
  任务创建、路由、会话、排序编排
backend/task/
  队列、进度、取消、心跳
backend/core/
  SSE 管理与跨线程基础设施
backend/graphs/
  LangGraph tender、skill 与 comment_supplement 工作流
backend/agents/generation/
  初次生成 content_agent 主/子智能体与工作区
backend/agents/comments/
  comment_agent 批注候选生成、锚点校验、工具门禁与审计工作区
backend/states/
  Typed graph state 契约
backend/nodes/
  graph 节点 callable
backend/helper/word_helper/
  可复用 Word 业务逻辑
backend/util/
  底层 Word COM、HTTP、存储、日志、LLM 工具
backend/prompts/ 与 backend/skills/
  Prompt Layer 与 task skill 运行时
```

核心原则：

- API router 保持薄入口，业务编排放 service / graph / node / helper。
- Word COM 是稀缺临界资源，新增能力不得绕开队列、graph 锁、取消检查和进度包装。
- Prompt Layer 只做纯渲染和契约相关逻辑，不承载副作用。
- `generation_mode` 分流保留在标准生成 graph 主干，类型 graph 不复制智能体分支。
- 后端跨包导入统一使用 `backend.*` 包绝对路径。

## 关键运行链路

### 生成

`POST /api/generate` 由前端表单提交，生成文件契约是 `file_paths.template` 加 `file_paths.tender_params`。后端创建任务并通过 tender graph 执行文档生成：`generation_mode=workflow` 走旧 `generate_polished_text`，`generation_mode=agent` 走 `content_agent`；`comment_generation_mode` 决定是否生成或补写 AI 批注。任务进度通过 SSE 回到前端，智能体过程通过 `agent_step` 展示，完成后前端展示下载入口。

关键入口：
- `frontend/components/chat/FormPanel.tsx`
- `frontend/lib/formDataConverter.ts`
- `frontend/lib/gngkFormType.ts`
- `backend/api/generate.py`
- `backend/services/document_service.py`
- `backend/graphs/base_graph.py`
- `backend/nodes/common_word_nodes/content_agent_generate.py`
- `backend/agents/generation/`
- `backend/services/document_service.py`

### 任务上下文助手 / Rewrite

`POST /api/agent/runs/stream` 是右侧聊天唯一流式入口。它返回 NDJSON agent run 事件，由任务上下文助手结合 `selected_skills`、受控 `context_snapshot` 和确定性 guard，决定是返回 `needs_input` 追问，还是通过受控 tool 创建 rewrite task。上传 Word 文件后的修改也统一归入 rewrite：必须有用户重写指令、当前页面 `form_type`、完整锚点、标的类型和资金性质；招标数据快照只是可选上下文。缺条件时只返回 `needs_input`。`task_accepted` 后，agent run 即结束；后续排队、Word COM 执行、SSE、取消和下载继续沿用现有任务主链路。

关键入口：
- `frontend/components/chat/ChatPanel.tsx`
- `frontend/lib/api.ts`
- `backend/api/agent.py`
- `backend/services/agent_run_service.py`
- `backend/agents/task_context_assistant/`
- `backend/services/document_service.py`
- `backend/skills/rewrite/`

### 补充批注

补充批注是独立 task 入口，只走 `POST /api/comment-supplement`。前端从初次生成下载卡触发，后端校验 latest `rewrite_state` 和当前下载文件后，执行 `CommentSupplementGraph`：复制当前文档副本、通过 `backend/agents/comments/` 的 `comment_agent` 生成/校验/写回批注，再更新会话 latest `rewrite_state.prepared_doc_path` 和新的下载结果。

关键入口：
- `frontend/components/chat/TaskDownloadMessage.tsx`
- `frontend/components/chat/ChatPanel.tsx`
- `frontend/lib/api.ts`
- `backend/api/comment_supplement.py`
- `backend/services/document_service.py`
- `backend/graphs/comment_supplement_graph.py`
- `backend/nodes/common_word_nodes/comment_agent.py`
- `backend/agents/comments/`

### 模板候选

模板候选由后端代理外部列表、AI 重排、下载和落盘，前端只通过项目内 API helper 交互。

关键入口：
- `frontend/components/forms/TemplateCandidateDialog.tsx`
- `frontend/components/forms/TenderFormShared.tsx`
- `backend/api/template_candidates.py`
- `backend/util/common_util/template_candidates.py`
- `backend/services/template_candidate_ranking_service.py`

## 推荐理解路径

### 第一次接手

1. `AGENTS.md`
2. `README.md`
3. `coding_maps/SYSTEM_MAP.md`
4. `INTERFACES.md`
5. 相关子项目 `.planning/codebase/ARCHITECTURE.md`

### 改后端

1. `AGENTS.md`
2. `backend/.planning/codebase/ARCHITECTURE.md`
3. `backend/.planning/codebase/STRUCTURE.md`
4. `backend/.planning/codebase/CONVENTIONS.md`
5. `backend/.planning/codebase/TESTING.md`
6. 相关 `asset/*.md`

### 改前端

1. `AGENTS.md`
2. `frontend/.planning/codebase/ARCHITECTURE.md`
3. `frontend/.planning/codebase/STRUCTURE.md`
4. `frontend/.planning/codebase/CONVENTIONS.md`
5. `frontend/.planning/codebase/TESTING.md`

### 改跨端接口

1. `INTERFACES.md`
2. `backend/api/`
3. `backend/models/`
4. `frontend/lib/api.ts`
5. `frontend/types/api.ts`
6. 相关前后端测试

### 改 Word 运行时或招标类型

1. `AGENTS.md`
2. `backend/.planning/codebase/ARCHITECTURE.md`
3. `backend/.planning/codebase/CONVENTIONS.md`
4. `asset/shared_runtime_word_skill_knowledge_pack.md`
5. `asset/tender_type_identity_session_knowledge_pack.md`
6. 相关 graph、node、helper、前端转换器、`gngkFormType` 和测试

## 维护建议

- 根级文档保留系统边界和阅读路径，不复制子项目内部实现细节。
- 子项目事实变化应先更新对应 `.planning/codebase/` 文档。
- 长期业务规则进入 `asset/`；影响多数未来需求的规则再上提到 `AGENTS.md`。
- 接口变化必须同步 `INTERFACES.md`、前后端类型和测试；新增任务类型还要同步任务状态、SSE、下载卡和会话结果语义。
- 仅文档变更至少运行 `git diff --check` 和密钥模式扫描。
