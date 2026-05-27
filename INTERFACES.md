# TenderWord 接口边界

**生成日期：** 2026-05-27

本文件记录 TenderWord 当前已确认的系统级接口边界。具体模型和行为以 `backend/api/`、`backend/models/`、`frontend/types/api.ts` 和 `frontend/lib/api.ts` 为准。

## 已确认接口边界

### API 前缀与前端调用入口

- 后端真实 API 前缀是 `/api`，FastAPI router 注册在 `backend/main.py`。
- 前端所有后端调用统一经由 `frontend/lib/api.ts`。
- JSON 请求走 `request<T>()` / `api.get/post/put/delete` 封装。
- 流式、上传和下载使用 `frontend/lib/api.ts` 内的专用 helper。
- 前端基础 URL 由 `frontend/lib/apiBaseUrl.ts` 解析，Next rewrites 在 `frontend/next.config.ts`。

### 生成任务

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/components/chat/FormPanel.tsx` |
| 请求转换 | `frontend/lib/formDataConverter.ts` |
| API client | `frontend/lib/api.ts` 中的 `createGenerateTask()` |
| 后端路由 | `backend/api/generate.py` 中的 `POST /api/generate` |
| 后端模型 | `backend/models/generate.py` 中的 `GenerateRequest` / `FormType` |
| 后端 service | `backend/services/document_service.py` |
| 运行时 | `backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py` |

同步要求：
- `GenerateRequest.form_type` 变化必须同步 `frontend/types/api.ts`、`frontend/lib/formDataConverter.ts` 和 `backend/models/generate.py`；`gngk` 分派变化还必须同步 `frontend/lib/gngkFormType.ts`。
- `gngk` 的后端分派依赖 `tender_lx + fund_lx + ifzgcg`，共享真源是 `frontend/lib/gngkFormType.ts`；generate 由 `formDataConverter.ts` 调用该 helper，edit 由 `ChatPanel.tsx` 调用该 helper，不能绕开 helper 单独改调用点。

### 任务状态、取消与心跳

| 项 | 当前边界 |
| --- | --- |
| API client | `frontend/lib/api.ts` 中的 `getTaskStatus()`, `getTaskList()`, `cancelTask()`, `sendTaskHeartbeat()` |
| 后端路由 | `backend/api/tasks.py` |
| 后端 service | `backend/services/task_service.py` |
| 队列真源 | `backend/task/task_queue_manager.py` |
| 前端轮询 | `frontend/hooks/useCurrentConversationTaskStatus.ts` |
| 前端心跳 | `frontend/hooks/useTaskHeartbeat.ts` |

同步要求：
- 任务状态字段变化必须同步 `backend/models/task.py`、`frontend/types/api.ts`、store task summary 和任务 UI。
- 从 `sessionStorage` 恢复 running task 前，前端必须先查任务状态；404 / `TASK_NOT_FOUND` 收敛成本地中断态。

### 任务 SSE

| 项 | 当前边界 |
| --- | --- |
| 后端路由 | `backend/api/stream.py` 中的 `GET /api/stream/{task_id}` |
| 后端 manager | `backend/core/sse_manager.py` |
| 日志桥接 | `backend/util/log_util/sse_log_handler.py` |
| 前端 URL helper | `frontend/lib/api.ts` 中的 `getTaskStreamUrl()` |
| 前端 runtime | `frontend/lib/sse.ts` |
| 前端映射 | `frontend/hooks/useChatSSE.ts` |
| 前端类型 | `frontend/types/api.ts` |

已确认前端事件类型包括 `connected`、`log`、`llm`、`progress`、`status`、`error`、`done`、`heartbeat`。

同步要求：
- 新增 SSE 事件类型必须同步后端模型、事件发送、前端 union 类型、`useChatSSE` 解析和测试。
- 任务失败必须最终表现为 `error` 或 `done`，不能让 SSE 静默中断。
- `comment_writeback_*` 和 `style_writeback_*` 摘要属于任务结果契约，不得在 state、任务结果或 `done` 事件中丢失。

### 用户流式、聊天与 Rewrite

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/components/chat/ChatPanel.tsx` |
| API client | `frontend/lib/api.ts` 中的 `streamUserMessage()` / `streamNdjson()` |
| 后端路由 | `backend/api/user.py` 中的 `POST /api/user/stream` |
| 路由 service | `backend/services/user_routing_service.py` |
| 路由 graph | `backend/graphs/user_graph.py` |
| Skill runtime | `backend/graphs/skill_graph.py`, `backend/skills/rewrite/` |

同步要求：
- NDJSON event shape 变化必须同步 `frontend/types/api.ts` 和 `ChatPanel`。
- rewrite 可创建任务，但 edit 不应重新并入 `/api/user/stream` 的模型判路链路。
- `generation_style` 是 generate-only 字段，不得透传进 rewrite / edit 请求模型、skill state 或 prompt surface。

### Edit 任务

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/components/chat/ChatPanel.tsx` |
| 上传 helper | `frontend/lib/api.ts` 中的 `uploadFile()` |
| API client | `frontend/lib/api.ts` 中的 `createEditTask()` |
| 后端路由 | `backend/api/edit.py` 中的 `POST /api/edit` |
| 后端 service | `DocumentService.create_edit_task()` |
| Skill runtime | `backend/skills/edit/`, `backend/graphs/skill_graph.py` |

同步要求：
- Edit 是显式入口，只走 `POST /api/edit`。
- edit request / response 变化必须同步 `frontend/types/api.ts`、`frontend/lib/api.ts` 和后端模型。

### 招标详情查询

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/lib/tenderFetch.ts`, `frontend/app/tender/page.tsx`, `frontend/components/forms/TenderFormShared.tsx` |
| API client | `frontend/lib/api.ts` 中的 `fetchTenderDataWithType()` / `fetchTenderData()` |
| 后端路由 | `backend/api/tender.py` 中的 `GET /api/tender/{tender_no}` |
| 后端工具 | `backend/util/common_util/fetch_tender_data.py` |
| 外部配置 | `backend/config/settings.py` 中的 `TENDER_DATA_API_URL` |

同步要求：
- 前端 URL 驱动查数要把必要 URL 参数写入 draft，再由表单初始化读取。
- 外部接口细节不应泄露到前端组件。

### 上传与下载

| 项 | 当前边界 |
| --- | --- |
| 上传 client | `frontend/lib/api.ts` 中的 `uploadFile()`, `uploadFiles()` |
| 上传 UI | `frontend/components/forms/FileUploader.tsx`, `ChatPanel` 中的 edit upload |
| 上传路由 | `backend/api/upload.py` |
| 下载 client | `frontend/lib/api.ts` 中的 `downloadFile()`, `getDownloadUrl()` |
| 下载路由 | `backend/api/download.py` |
| 存储 helper | `backend/util/common_util/upload_storage.py` |

同步要求：
- 前端不直接访问本地文件系统或云存储。
- 后端下载路径必须继续受存储 helper 和路径安全规则约束。

### 模板候选

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx` |
| API client | `frontend/lib/api.ts` 中的 `fetchTemplateCandidates()`, `selectTemplateCandidate()`, `getTemplateCandidateDownloadUrl()` |
| 后端路由 | `backend/api/template_candidates.py` |
| 后端工具 | `backend/util/common_util/template_candidates.py` |
| 排序 service | `backend/services/template_candidate_ranking_service.py` |
| Prompt | `backend/prompts/template_candidate_ranking_prompt.py` |
| 外部配置 | `TEMPLATE_CANDIDATE_API_URL`, `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` |

同步要求：
- 前端只调用项目内 `/api/template-candidates*`。
- 外部列表请求、下载代理、落盘和文件名清洗统一由后端处理。
- AI 排序契约只返回后端生成的 `row_index` 列表，不能要求前端用项目名称反查候选。
- `year < 2025` 或非法年份的模板不可选择，只允许下载参考。

### 会话心跳

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/app/tender/page.tsx` |
| API client | `frontend/lib/api.ts` 中的 `sendConversationHeartbeat()` |
| 后端路由 | `backend/api/conversations.py` |
| 后端 service | `backend/services/conversation_service.py` |

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
- `frontend/lib/gngkFormType.ts`
- `frontend/components/chat/ChatPanel.tsx`
- `frontend/utils/tenderTypeMapper.ts`
- `frontend/components/chat/tenderFormRegistry.ts`
- `backend/models/generate.py`
- `backend/config/tender_config.py`
- `backend/services/document_service.py`
- `backend/graphs/`
- `backend/states/`

新增招标类型或修改 `gngk` 子类型分派时，必须同步上述两端映射和测试。

当前 `gngk_hw_cz_tender` 是 direct-replace 首次生成类型：后端 `GngkHwCzTenderGraph` 显式绑定财政货物 delete/update 节点，锚点和 content mode 真源位于 `backend/config/tender_config.py`。这不改变前端仍以单一 `gngk` UI 类型承载公开招标的现实。

## 外部集成边界

### LLM 服务商

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

### 外部招标详情与模板 API

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
- `gngk` 类型不对：同时检查 URL 参数、draft、`gngkFormType`、`formDataConverter`、`ChatPanel` edit 调用点、后端 `FormType` 和 `GRAPH_REGISTRY`。
- 模板候选不可选：检查 `year`、blocked reason、后端归一化、AI row_index 重排和前端选择按钮状态。
- Word 写回异常：先看任务队列、graph 锁、protected fields、paragraph boundary helper，再看类型专属 node。
