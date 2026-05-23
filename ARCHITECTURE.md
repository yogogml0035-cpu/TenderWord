# TenderWord 架构地图

**生成日期：** 2026-05-23

本文件是根级系统架构地图，描述 TenderWord 的系统边界、子系统职责和推荐理解路径。实现细节仍以代码为准；子系统内部事实以 `backend/.planning/codebase/` 和 `frontend/.planning/codebase/` 为准。

## 系统边界

TenderWord 是招标文档生成与修改系统，核心闭环是：

```text
浏览器 / Next.js 工作台
  -> FastAPI /api
  -> 任务队列 + SSE
  -> LangGraph tender 或 skill workflow
  -> Prompt Layer + LLM provider
  -> Word COM 文档操作
  -> 生成文件 / 任务结果 / 下载
```

系统的完整能力依赖 Windows + Word COM。前端可以在 WSL/Linux Node 环境运行，但后端 Word 自动化必须使用 Windows Python、pywin32 和本机 Word/WPS COM 能力。

## 子系统职责

### `frontend/`

`frontend/` 是 Next.js 16 + React 19 工作台。它负责：

- `/` 与 `/tender` 页面入口。
- 招标类型侧栏、表单面板、聊天和任务面板。
- 会话、草稿、历史、任务摘要与 SSE resume 元数据的 `sessionStorage` 持久化。
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

- `/api` 前缀下的生成、编辑、任务、SSE、用户流式、会话心跳、上传下载和模板候选接口。
- `DocumentService` 任务创建、graph 选择、初始 state 构造、任务提交和结果 payload。
- `TaskQueueManager` 串行化文档任务、跟踪进度、取消、心跳和清理。
- `SSEManager` 事件缓冲、客户端管理和重连重放。
- 标准 tender graph、rewrite/edit skill graph 和 user routing graph。
- Word COM 生命周期、共享 Word helper、类型特化节点和 Prompt Layer。
- 外部 LLM provider、招标详情接口和模板候选接口的后端代理。

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
  路由边界与工作台组合
frontend/components/chat/
  工作台面板、聊天、任务消息、侧栏
frontend/components/forms/
  招标表单、上传、模板候选弹窗
frontend/stores/
  持久化会话状态与临时 stream 状态
frontend/lib/
  API client、SSE wrapper、招标数据 helper
frontend/types/ 与 frontend/utils/
  API 契约、招标身份、URL 映射
```

核心原则：

- 组件不直接写裸 `fetch`，后端调用统一进 `frontend/lib/api.ts`。
- URL canonical 化统一走 `frontend/utils/tenderTypeMapper.ts` 和 store helpers。
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
  LangGraph tender、skill、user 工作流
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
- 后端跨包导入统一使用 `backend.*` 包绝对路径。

## 关键运行链路

### 生成

`POST /api/generate` 由前端表单提交，后端创建任务并通过 tender graph 执行文档生成。任务进度通过 SSE 回到前端，完成后前端展示下载入口。

关键入口：
- `frontend/components/chat/FormPanel.tsx`
- `frontend/lib/formDataConverter.ts`
- `backend/api/generate.py`
- `backend/services/document_service.py`
- `backend/graphs/base_graph.py`
- `backend/services/document_service.py`

### Rewrite / 聊天

`POST /api/user/stream` 返回 NDJSON。后端根据用户意图路由为普通回复或 rewrite task。rewrite task 进入同一任务队列和 SSE 进度链路。

关键入口：
- `frontend/components/chat/ChatPanel.tsx`
- `frontend/lib/api.ts`
- `backend/api/user.py`
- `backend/services/user_routing_service.py`
- `backend/graphs/user_graph.py`
- `backend/graphs/skill_graph.py`

### Edit

Edit 是显式 task 入口，只走 `POST /api/edit`。它复用任务队列、SSE、下载和会话结果机制，但请求模型、skill state 和 prompt surface 不应混回 user stream 判路链路。

关键入口：
- `frontend/components/chat/ChatPanel.tsx`
- `backend/api/edit.py`
- `backend/services/document_service.py`
- `backend/skills/edit/`

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
6. 相关 graph、node、helper、前端转换器和测试

## 维护建议

- 根级文档保留系统边界和阅读路径，不复制子项目内部实现细节。
- 子项目事实变化应先更新对应 `.planning/codebase/` 文档。
- 长期业务规则进入 `asset/`；影响多数未来需求的规则再上提到 `AGENTS.md`。
- 接口变化必须同步 `INTERFACES.md`、前后端类型和测试。
- 仅文档变更至少运行 `git diff --check` 和密钥模式扫描。
