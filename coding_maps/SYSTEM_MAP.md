# TenderWord System Map

**Generated:** 2026-05-22

本文件是仓库级系统地图，帮助后续开发先判断“该看哪里、跨层怎么协作、哪些边界不能破坏”。它不替代代码真源、不替代根级 `AGENTS.md` 的执行红线，也不替代 `backend/.planning/codebase/` 和 `frontend/.planning/codebase/` 的子系统事实文档。

## 系统目的与仓库形态

TenderWord 是前后端分离的招标文档生成、修改和模板复用系统。完整运行依赖 Windows + Word COM：前端负责会话、表单、任务进度和文件交互，后端负责 API、任务队列、LangGraph 工作流、LLM 调用、模板候选代理和 Word 文件生成。

仓库当前主要由两个可独立理解但必须同步维护的子项目组成：

| 子项目 | 职责 | 事实文档 |
| --- | --- | --- |
| `backend/` | FastAPI API、任务队列、SSE、LangGraph、Prompt Layer、Word COM、模板候选代理、上传与下载。 | `backend/.planning/codebase/` |
| `frontend/` | Next.js 工作台、招标类型表单、会话与 URL 身份、任务 SSE 展示、模板候选弹窗、上传下载交互。 | `frontend/.planning/codebase/` |

长期业务规则和跨主题回归风险沉淀在 `asset/`，当前索引是 `asset/README.md`。启动和首次安装入口保留在 `README.md`。

## 跨子项目调用链

### 生成任务主链路

1. 用户进入 `/tender`，`frontend/app/tender/page.tsx` 解析 URL 参数并恢复或创建会话。
2. 表单由 `frontend/components/forms/TenderFormShared.tsx` 收集招标数据、上传文件、模板候选和插入锚点。
3. `frontend/components/chat/FormPanel.tsx` 通过 `frontend/components/chat/tenderFormRegistry.ts` 选择转换器。
4. `frontend/lib/formDataConverter.ts` 把前端 `TenderType` 和 `gngk` 子类型参数转换为后端 `GenerateRequest.form_type`。
5. `frontend/lib/api.ts` 调用 `POST /api/generate`。
6. `backend/api/generate.py` 校验请求并交给 `backend/services/document_service.py`。
7. `DocumentService` 选择 `GRAPH_REGISTRY` 中的 graph，构造初始 state，并提交到 `backend/task/task_queue_manager.py`。
8. `backend/graphs/base_graph.py` 执行共享 LangGraph 工作流，类型 graph 绑定具体 node。
9. Word 业务逻辑通过 `backend/helper/word_helper/` 和 `backend/util/word_util/` 执行，LLM prompt 通过 `backend/prompts/` 渲染。
10. 后端完成任务后写入任务结果并推送 `done` / `error` SSE，前端通过 `frontend/hooks/useChatSSE.ts` 写入聊天任务消息和下载入口。

### 任务状态、SSE 与下载

- 前端任务创建、查询、取消、心跳、下载统一通过 `frontend/lib/api.ts`。
- 后端任务生命周期在 `backend/task/task_queue_manager.py`，API 展示在 `backend/api/tasks.py` 和 `backend/services/task_service.py`。
- SSE 后端入口是 `backend/api/stream.py`，事件缓冲和重放在 `backend/core/sse_manager.py`，进度日志桥接在 `backend/util/log_util/sse_log_handler.py`。
- 前端 SSE runtime 是 `frontend/lib/sse.ts`，任务事件到 UI 的映射是 `frontend/hooks/useChatSSE.ts`。
- 下载由 `backend/api/download.py` 和上传存储 helper 保护，前端使用 `downloadFile()` / `getDownloadUrl()`。

### 普通聊天、rewrite 与 edit

- 普通聊天和 rewrite 路由前端从 `frontend/components/chat/ChatPanel.tsx` 发起，通过 `frontend/lib/api.ts` 调用 `POST /api/user/stream`。
- 后端 `backend/api/user.py` 返回 NDJSON，路由和 prompt 相关逻辑收敛在 `backend/services/user_routing_service.py`、`backend/graphs/user_graph.py` 和 `backend/prompts/`。
- rewrite / edit 是 task skill runtime，声明和 workflow 在 `backend/skills/rewrite/`、`backend/skills/edit/`，执行图在 `backend/graphs/skill_graph.py`。
- edit 只走 `POST /api/edit`，前端入口在 `frontend/components/chat/ChatPanel.tsx`，后端入口在 `backend/api/edit.py`。

### 模板候选链路

- 前端只调用项目内 `/api/template-candidates*` helper：`fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()`。
- 模板候选 UI 在 `frontend/components/forms/TemplateCandidateDialog.tsx`，表单回填在 `frontend/components/forms/TenderFormShared.tsx`。
- 后端代理、下载、选择、落盘在 `backend/api/template_candidates.py` 和 `backend/util/common_util/template_candidates.py`。
- AI 重排在 `backend/services/template_candidate_ranking_service.py`，prompt 在 `backend/prompts/template_candidate_ranking_prompt.py`。
- 外部下载链接必须继续受后端白名单约束，前端不得绕过后端直接请求外部模板文件。

## 接口边界

| 边界 | 前端入口 | 后端入口 | 同步要求 |
| --- | --- | --- | --- |
| API client | `frontend/lib/api.ts` | `backend/api/` | API 形状变化时同步 `frontend/types/api.ts`、后端 `backend/models/` 和相关测试。 |
| 招标类型身份 | `frontend/types/index.ts`, `frontend/utils/tenderTypeMapper.ts`, `frontend/lib/formDataConverter.ts` | `backend/models/generate.py`, `backend/config/tender_config.py`, `backend/services/document_service.py` | 新增或修改类型必须同步前端 UI 类型、后端 `form_type`、URL、graph/state/node、anchor 和测试。 |
| 会话和 URL | `frontend/stores/chatStore.ts`, `frontend/utils/tenderTypeMapper.ts` | `backend/api/conversations.py`, `backend/services/conversation_service.py` | 地址栏、会话身份、任务恢复和后端心跳需保持一致。 |
| 任务与 SSE | `frontend/hooks/useChatSSE.ts`, `frontend/lib/sse.ts`, `frontend/stores/*` | `backend/api/stream.py`, `backend/core/sse_manager.py`, `backend/task/task_queue_manager.py` | 新增 SSE 事件必须同步后端模型、前端类型、解析和测试。 |
| Word 运行时 | 无前端直接入口 | `backend/graphs/`, `backend/nodes/`, `backend/helper/word_helper/`, `backend/util/word_util/` | 前端不得触碰 COM；后端新增 graph/node/tool 不得绕过队列、锁、取消检查和进度包装。 |
| Prompt / LLM | 无前端直接入口 | `backend/prompts/`, `backend/util/common_util/llm_stream_utils.py` | prompt 渲染、超时、解析和结构校验要集中维护。 |
| 模板候选 | `frontend/components/forms/TemplateCandidateDialog.tsx`, `frontend/lib/api.ts` | `backend/api/template_candidates.py` | 前端不得直接调用外部候选接口或外部文件 URL。 |

## 状态、存储与运行时

- 前端会话、草稿、任务摘要和历史状态使用 `sessionStorage`，主要由 `frontend/stores/chatStore.ts`、`frontend/stores/historyStore.ts` 和 `frontend/stores/chatTaskSessionStore.ts` 持久化。
- 前端活跃 SSE 文本、日志、进度和当前节点是内存态，位于 `frontend/stores/chatStreamStore.ts`。
- 后端任务、会话和 SSE 事件当前是内存态；上传、下载、生成文档、prompt log 和运行日志是本地文件。
- 后端没有已确认的外部数据库；外部集成主要是 LLM provider、招标详情接口、模板候选接口和 Word COM。
- 本地完整运行的关键环境是 Windows + Word COM；WSL 场景下前端可在 Linux Node 运行，后端仍需要 Windows Python 和 Word COM。

## 按任务分类的阅读指南

### 后端 API、任务或 graph 修改

先读：
- `AGENTS.md`
- `backend/.planning/codebase/ARCHITECTURE.md`
- `backend/.planning/codebase/STRUCTURE.md`
- `backend/.planning/codebase/INTEGRATIONS.md`
- `backend/.planning/codebase/CONVENTIONS.md`

再按任务读取：
- 任务与队列：`backend/task/task_queue_manager.py`、`backend/services/document_service.py`
- SSE：`backend/core/sse_manager.py`、`backend/api/stream.py`
- Prompt / skill：`backend/prompts/`、`backend/skills/`
- Word 业务：`asset/shared_runtime_word_skill_knowledge_pack.md`

### 前端表单、会话、URL 或任务展示修改

先读：
- `AGENTS.md`
- `frontend/.planning/codebase/ARCHITECTURE.md`
- `frontend/.planning/codebase/STRUCTURE.md`
- `frontend/.planning/codebase/CONVENTIONS.md`
- `frontend/.planning/codebase/TESTING.md`

再按任务读取：
- 类型身份与会话：`asset/tender_type_identity_session_knowledge_pack.md`
- API client：`frontend/lib/api.ts`
- URL 映射：`frontend/utils/tenderTypeMapper.ts`
- 表单：`frontend/components/forms/TenderFormShared.tsx`
- 聊天任务：`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/FormPanel.tsx`

### 跨系统接口修改

必须同时读：
- `INTERFACES.md`
- `backend/models/`
- `backend/api/`
- `frontend/types/api.ts`
- `frontend/lib/api.ts`
- 相关前后端测试

接口变更不能只改一侧。

### 模板候选修改

先读：
- `asset/template_candidate_pipeline_knowledge_pack.md`
- `backend/.planning/codebase/INTEGRATIONS.md`
- `frontend/.planning/codebase/INTEGRATIONS.md`

重点同步：
- `backend/api/template_candidates.py`
- `backend/util/common_util/template_candidates.py`
- `backend/services/template_candidate_ranking_service.py`
- `frontend/lib/api.ts`
- `frontend/components/forms/TemplateCandidateDialog.tsx`
- `frontend/components/forms/TenderFormShared.tsx`

### 视觉或 UX 修改

先读：
- `frontend/.planning/codebase/ARCHITECTURE.md`
- `frontend/.planning/codebase/CONVENTIONS.md`
- `frontend/.planning/codebase/TESTING.md`

涉及真实浏览器交互、页面跳转、会话恢复、模板弹窗或任务进度展示时，最终回归入口应是 `frontend/e2e/test_*.spec.ts` 和 `npm run test:e2e`。

## 集成风险检查清单

- API 形状变化是否同步了后端模型、前端类型、API client 和测试。
- `gngk` 的 `tender_lx + fund_lx` 是否同时同步 `frontend/lib/formDataConverter.ts` 和 `frontend/components/chat/ChatPanel.tsx`。
- 新增或修改 SSE 事件是否同步后端事件模型、前端事件 union、`useChatSSE` 和测试。
- Word COM 相关改动是否仍然经过任务队列、graph 锁、取消检查和进度包装。
- Prompt 或 LLM 流式改动是否复用 `LLM_STREAM_TIMEOUT_SECONDS`，并保留 prompt layer 边界。
- 模板候选改动是否仍由后端代理外部列表、文件下载和白名单校验。
- 前端 running task 恢复是否先查任务状态，避免直接连接已不存在的 SSE。
- 文档引用的路径、命令、端口和目录是否仍真实存在。

## 验证入口

- 后端常规验证：在 `backend/` 运行 `python -m pytest tests -v`。
- 前端常规验证：在 `frontend/` 运行 `npm run lint`、`npm run type-check`、相关 `npm run test`。
- 前端 E2E：在 `frontend/` 运行 `npm run test:e2e`。
- 文档型变更：根目录运行 `git diff --check`，并扫描文档中的密钥/token 模式。

本次系统地图是文档层产物；具体功能验证仍以受影响代码路径的测试要求为准。

## 源文档索引

- `AGENTS.md`
- `README.md`
- `backend/.planning/codebase/ARCHITECTURE.md`
- `backend/.planning/codebase/INTEGRATIONS.md`
- `backend/.planning/codebase/STRUCTURE.md`
- `backend/.planning/codebase/TESTING.md`
- `backend/.planning/codebase/CONVENTIONS.md`
- `backend/.planning/codebase/CONCERNS.md`
- `backend/.planning/codebase/STACK.md`
- `frontend/.planning/codebase/ARCHITECTURE.md`
- `frontend/.planning/codebase/INTEGRATIONS.md`
- `frontend/.planning/codebase/STRUCTURE.md`
- `frontend/.planning/codebase/TESTING.md`
- `frontend/.planning/codebase/CONVENTIONS.md`
- `frontend/.planning/codebase/CONCERNS.md`
- `frontend/.planning/codebase/STACK.md`
- `asset/README.md`
- `asset/shared_runtime_word_skill_knowledge_pack.md`
- `asset/template_candidate_pipeline_knowledge_pack.md`
- `asset/tender_type_identity_session_knowledge_pack.md`
