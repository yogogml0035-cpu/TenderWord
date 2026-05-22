# TenderWord Interfaces

**Generated:** 2026-05-22

本文件记录 TenderWord 当前已确认的系统级接口边界。具体模型和行为以 `backend/api/`、`backend/models/`、`frontend/types/api.ts` 和 `frontend/lib/api.ts` 为准。

## 已确认接口边界

### API 前缀与前端调用入口

- 后端真实 API 前缀是 `/api`，FastAPI router 注册在 `backend/main.py`。
- 前端所有后端调用统一经由 `frontend/lib/api.ts`。
- JSON 请求走 `request<T>()` / `api.get/post/put/delete` 封装。
- 流式、上传和下载使用 `frontend/lib/api.ts` 内的专用 helper。
- 前端基础 URL 由 `frontend/lib/apiBaseUrl.ts` 解析，Next rewrites 在 `frontend/next.config.ts`。

### Generate Task

| 项 | 当前边界 |
| --- | --- |
| Frontend caller | `frontend/components/chat/FormPanel.tsx` |
| Request conversion | `frontend/lib/formDataConverter.ts` |
| API client | `createGenerateTask()` in `frontend/lib/api.ts` |
| Backend route | `POST /api/generate` in `backend/api/generate.py` |
| Backend model | `GenerateRequest` / `FormType` in `backend/models/generate.py` |
| Backend service | `backend/services/document_service.py` |
| Runtime | `backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py` |

同步要求：
- `GenerateRequest.form_type` 变化必须同步 `frontend/types/api.ts`、`frontend/lib/formDataConverter.ts` 和 `backend/models/generate.py`。
- `gngk` 的后端分派依赖 `tender_lx + fund_lx`，不能只改前端或只改后端。

### Task Status, Cancel, Heartbeat

| 项 | 当前边界 |
| --- | --- |
| API client | `getTaskStatus()`, `getTaskList()`, `cancelTask()`, `sendTaskHeartbeat()` in `frontend/lib/api.ts` |
| Backend route | `backend/api/tasks.py` |
| Backend service | `backend/services/task_service.py` |
| Queue source | `backend/task/task_queue_manager.py` |
| Frontend polling | `frontend/hooks/useCurrentConversationTaskStatus.ts` |
| Frontend heartbeat | `frontend/hooks/useTaskHeartbeat.ts` |

同步要求：
- 任务状态字段变化必须同步 `backend/models/task.py`、`frontend/types/api.ts`、store task summary 和任务 UI。
- 从 `sessionStorage` 恢复 running task 前，前端必须先查任务状态；404 / `TASK_NOT_FOUND` 收敛成本地中断态。

### Task SSE

| 项 | 当前边界 |
| --- | --- |
| Backend route | `GET /api/stream/{task_id}` in `backend/api/stream.py` |
| Backend manager | `backend/core/sse_manager.py` |
| Log bridge | `backend/util/log_util/sse_log_handler.py` |
| Frontend URL helper | `getTaskStreamUrl()` in `frontend/lib/api.ts` |
| Frontend runtime | `frontend/lib/sse.ts` |
| Frontend mapping | `frontend/hooks/useChatSSE.ts` |
| Frontend types | `frontend/types/api.ts` |

已确认前端事件类型包括 `connected`、`log`、`llm`、`progress`、`status`、`error`、`done`、`heartbeat`。

同步要求：
- 新增 SSE 事件类型必须同步后端模型、事件发送、前端 union 类型、`useChatSSE` 解析和测试。
- 任务失败必须最终表现为 `error` 或 `done`，不能让 SSE 静默中断。
- `comment_writeback_*` 和 `style_writeback_*` 摘要属于任务结果契约，不得在 state、任务结果或 `done` 事件中丢失。

### User Stream, Chat, Rewrite

| 项 | 当前边界 |
| --- | --- |
| Frontend caller | `frontend/components/chat/ChatPanel.tsx` |
| API client | `streamUserMessage()` / `streamNdjson()` in `frontend/lib/api.ts` |
| Backend route | `POST /api/user/stream` in `backend/api/user.py` |
| Routing service | `backend/services/user_routing_service.py` |
| Routing graph | `backend/graphs/user_graph.py` |
| Skill runtime | `backend/graphs/skill_graph.py`, `backend/skills/rewrite/` |

同步要求：
- NDJSON event shape 变化必须同步 `frontend/types/api.ts` 和 `ChatPanel`。
- rewrite 可创建任务，但 edit 不应重新并入 `/api/user/stream` 的模型判路链路。
- `generation_style` 是 generate-only 字段，不得透传进 rewrite / edit 请求模型、skill state 或 prompt surface。

### Edit Task

| 项 | 当前边界 |
| --- | --- |
| Frontend caller | `frontend/components/chat/ChatPanel.tsx` |
| Upload helper | `uploadFile()` in `frontend/lib/api.ts` |
| API client | `createEditTask()` in `frontend/lib/api.ts` |
| Backend route | `POST /api/edit` in `backend/api/edit.py` |
| Backend service | `DocumentService.create_edit_task()` |
| Skill runtime | `backend/skills/edit/`, `backend/graphs/skill_graph.py` |

同步要求：
- Edit 是显式入口，只走 `POST /api/edit`。
- edit request / response 变化必须同步 `frontend/types/api.ts`、`frontend/lib/api.ts` 和后端模型。

### Tender Data Lookup

| 项 | 当前边界 |
| --- | --- |
| Frontend caller | `frontend/lib/tenderFetch.ts`, `frontend/app/tender/page.tsx`, `frontend/components/forms/TenderFormShared.tsx` |
| API client | `fetchTenderDataWithType()` / `fetchTenderData()` in `frontend/lib/api.ts` |
| Backend route | `GET /api/tender/{tender_no}` in `backend/api/tender.py` |
| Backend utility | `backend/util/common_util/fetch_tender_data.py` |
| External setting | `TENDER_DATA_API_URL` in `backend/config/settings.py` |

同步要求：
- 前端 URL 驱动查数要把必要 URL 参数写入 draft，再由表单初始化读取。
- 外部接口细节不应泄露到前端组件。

### Upload And Download

| 项 | 当前边界 |
| --- | --- |
| Upload client | `uploadFile()`, `uploadFiles()` in `frontend/lib/api.ts` |
| Upload UI | `frontend/components/forms/FileUploader.tsx`, edit upload in `ChatPanel` |
| Upload route | `backend/api/upload.py` |
| Download client | `downloadFile()`, `getDownloadUrl()` in `frontend/lib/api.ts` |
| Download route | `backend/api/download.py` |
| Storage helper | `backend/util/common_util/upload_storage.py` |

同步要求：
- 前端不直接访问本地文件系统或云存储。
- 后端下载路径必须继续受存储 helper 和路径安全规则约束。

### Template Candidates

| 项 | 当前边界 |
| --- | --- |
| Frontend callers | `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx` |
| API client | `fetchTemplateCandidates()`, `selectTemplateCandidate()`, `getTemplateCandidateDownloadUrl()` in `frontend/lib/api.ts` |
| Backend route | `backend/api/template_candidates.py` |
| Backend utility | `backend/util/common_util/template_candidates.py` |
| Ranking service | `backend/services/template_candidate_ranking_service.py` |
| Prompt | `backend/prompts/template_candidate_ranking_prompt.py` |
| External settings | `TEMPLATE_CANDIDATE_API_URL`, `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` |

同步要求：
- 前端只调用项目内 `/api/template-candidates*`。
- 外部列表请求、下载代理、落盘和文件名清洗统一由后端处理。
- AI 排序契约只返回后端生成的 `row_index` 列表，不能要求前端用项目名称反查候选。
- `year < 2025` 或非法年份的模板不可选择，只允许下载参考。

### Conversation Heartbeat

| 项 | 当前边界 |
| --- | --- |
| Frontend caller | `frontend/app/tender/page.tsx` |
| API client | `sendConversationHeartbeat()` in `frontend/lib/api.ts` |
| Backend route | `backend/api/conversations.py` |
| Backend service | `backend/services/conversation_service.py` |

同步要求：
- 浏览器地址栏必须始终反映当前会话身份。
- 后端实例变化时，前端需要收敛本地 running task 状态，避免旧快照误连。

## 类型身份接口

当前有三层身份：

- 前端 UI 类型：`xjcg`、`gngk`、`gjgk`，定义在 `frontend/types/index.ts`。
- 后端 `FormType`：`xjcg_tender`、`gngk_hw_zc_tender`、`gngk_hw_cz_tender`、`gngk_fw_zc_tender`、`gngk_fw_cz_tender`、`gjgk_tender`，定义在 `backend/models/generate.py`。
- 运行态 `tender_type` / family：后端 graph、prompt、replacement 和公共节点会用 family 收敛公开招标差异。

关键同步点：

- `frontend/lib/formDataConverter.ts`
- `frontend/components/chat/ChatPanel.tsx`
- `frontend/utils/tenderTypeMapper.ts`
- `frontend/components/chat/tenderFormRegistry.ts`
- `backend/models/generate.py`
- `backend/config/tender_config.py`
- `backend/services/document_service.py`
- `backend/graphs/`
- `backend/states/`

新增招标类型或修改 `gngk` 子类型分派时，必须同步上述两端映射和测试。

## 外部集成边界

### LLM Providers

后端通过 OpenAI-compatible streaming client 调用 DeepSeek、Doubao / Volcengine ARK 和 Qwen / DashScope。调用封装集中在 `backend/util/common_util/llm_stream_utils.py` 和相关服务。

关键设置位于 `backend/config/settings.py`，包括 provider key、base URL、model、`LLM_STREAM_TIMEOUT_SECONDS` 和模板候选重排 provider。

### Word COM

Word COM 只存在于后端：

- 低层 COM 生命周期：`backend/util/word_util/`
- 业务 helper：`backend/helper/word_helper/`
- graph node：`backend/nodes/`
- graph 锁和进度包装：`backend/graphs/base_graph.py`
- 任务队列：`backend/task/task_queue_manager.py`

新增 Word 能力不得在 API route、service、前端或随意脚本中直接写 pywin32 / COM 调用。

### External Tender And Template APIs

- 招标详情：`TENDER_DATA_API_URL` -> `backend/util/common_util/fetch_tender_data.py`。
- 模板候选：`TEMPLATE_CANDIDATE_API_URL` -> `backend/util/common_util/template_candidates.py`。
- 模板下载：必须经过 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 和 `validate_template_download_url()`。

## 未证实或当前不存在的接口

- 当前源文档未确认稳定登录、用户认证或权限接口。
- 当前源文档未确认外部数据库、Redis、队列服务或对象存储。
- 当前源文档未确认第三方入站 webhook。
- 当前源文档未确认部署平台或 CI workflow 文件。

这些能力若后续新增，需要先建立代码真源，再同步本文件和对应 `.planning/codebase/` 文档。

## 排查建议

- 接口返回异常：先看 `frontend/lib/api.ts` 的 `ApiError` 包装，再看对应 `backend/api/` route 和 `backend/models/`。
- SSE 卡住：先区分任务是否还存在、队列是否运行、后端是否发出 `error` / `done`，再看 `backend/core/sse_manager.py` 和 `frontend/hooks/useChatSSE.ts`。
- `gngk` 类型不对：同时检查 URL 参数、draft、`formDataConverter`、`ChatPanel` edit form type、后端 `FormType` 和 `GRAPH_REGISTRY`。
- 模板候选不可选：检查 `year`、blocked reason、后端归一化、AI row_index 重排和前端选择按钮状态。
- Word 写回异常：先看任务队列、graph 锁、protected fields、paragraph boundary helper，再看类型专属 node。
