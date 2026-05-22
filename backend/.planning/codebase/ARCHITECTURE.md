<!-- refreshed: 2026-05-22 -->
# Architecture

**Analysis Date:** 2026-05-22

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend API                       │
│                    `backend/main.py`                         │
├──────────────────┬──────────────────┬───────────────────────┤
│ Generate/Edit    │ Task/SSE          │ Support APIs           │
│ `backend/api/`   │ `backend/api/`    │ `backend/api/`         │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                    │
         ▼                  ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                           │
│ `backend/services/document_service.py`                       │
│ `backend/services/task_service.py`                           │
│ `backend/services/conversation_service.py`                   │
│ `backend/services/user_routing_service.py`                   │
│ `backend/services/template_candidate_ranking_service.py`     │
└────────┬──────────────────┬─────────────────────┬────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Task Queue + SSE + LangGraph Runtime                         │
│ `backend/task/task_queue_manager.py`                         │
│ `backend/core/sse_manager.py`                                │
│ `backend/graphs/base_graph.py`                               │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ Tender Graphs, Skill Graphs, Nodes, Helpers, Prompts          │
│ `backend/graphs/` `backend/nodes/` `backend/states/`          │
│ `backend/helper/word_helper/` `backend/util/word_util/`       │
│ `backend/prompts/` `backend/skills/`                          │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ Word files, upload storage, external tender/template APIs     │
│ `backend/util/common_util/upload_storage.py`                  │
│ `backend/util/common_util/fetch_tender_data.py`               │
│ `backend/util/common_util/template_candidates.py`             │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app | Creates the backend app, registers `/api` routers, configures CORS, starts log listeners, binds the SSE event loop, and exposes health endpoints. | `backend/main.py` |
| Generate API | Accepts document generation requests and returns a queued task response. | `backend/api/generate.py` |
| Edit API | Accepts explicit edit requests and creates edit tasks through the shared document task pipeline. | `backend/api/edit.py` |
| User stream API | Provides the NDJSON chat entry that routes ordinary replies or rewrite task creation. | `backend/api/user.py` |
| Task API | Exposes task list, task detail, cancellation, and heartbeat operations. | `backend/api/tasks.py` |
| SSE API | Streams task events and supports `Last-Event-ID` replay for a task. | `backend/api/stream.py` |
| Upload/download APIs | Persist uploaded files under the configured upload directory and download only files under that directory. | `backend/api/upload.py`, `backend/api/download.py` |
| Tender data API | Fetches external tender metadata and normalizes it into backend models. | `backend/api/tender.py`, `backend/util/common_util/fetch_tender_data.py` |
| Template candidate API | Proxies template candidate list/download/select operations and applies backend-side ranking and storage rules. | `backend/api/template_candidates.py`, `backend/services/template_candidate_ranking_service.py`, `backend/util/common_util/template_candidates.py` |
| Document service | Owns graph registry initialization, task allocation, initial state assembly, graph submission, result payloads, conversation rewrite snapshots, and done/error SSE emission. | `backend/services/document_service.py` |
| Task service | Converts the internal task queue model into API response models. | `backend/services/task_service.py` |
| Conversation service | Stores in-memory conversation heartbeat and rewrite/edit history snapshots. | `backend/services/conversation_service.py` |
| Task queue manager | Serializes document tasks, tracks progress, handles cancellation, and cancels heartbeat-stale tasks. | `backend/task/task_queue_manager.py` |
| SSE manager | Stores per-task events, manages SSE clients, formats events, and replays missed events. | `backend/core/sse_manager.py` |
| Base graph runtime | Provides LangGraph base classes, progress wrappers, cancellation checks, fair execution, and cross-process file locking. | `backend/graphs/base_graph.py` |
| Tender graphs | Bind tender-specific state classes and node implementations to the shared standard tender workflow. | `backend/graphs/xjcg_tender_graph.py`, `backend/graphs/gngk_hw_zc_tender_graph.py`, `backend/graphs/gngk_fw_zc_tender_graph.py`, `backend/graphs/gjgk_tender_graph.py` |
| Skill graph runtime | Builds rewrite/edit task workflows from skill metadata and workflow declarations. | `backend/graphs/skill_graph.py`, `backend/skills/registry.py`, `backend/skills/loader.py`, `backend/skills/types.py` |
| State contracts | Define LangGraph state dictionaries for shared tender graphs, task skills, and user routing. | `backend/states/base_state.py`, `backend/states/skill_state.py`, `backend/states/user_state.py` |
| Word nodes | Execute graph node work for shared and tender-specific Word operations. | `backend/nodes/common_word_nodes/`, `backend/nodes/gngk_word_nodes/`, `backend/nodes/gjgk_word_nodes/`, `backend/nodes/xjcg_word_nodes/`, `backend/nodes/skills_nodes/` |
| Word helpers and utilities | Keep reusable Word business operations separate from COM lifecycle and low-level constants. | `backend/helper/word_helper/`, `backend/util/word_util/` |
| Prompt layer | Renders LLM prompts and parses prompt-bound outputs. | `backend/prompts/` |
| Settings | Loads backend configuration from `backend/.env` via Pydantic Settings and exposes defaults. | `backend/config/settings.py` |
| Tender configuration | Centralizes tender anchors, content update modes, protected-field profiles, and tender family routing. | `backend/config/tender_config.py` |

## Pattern Overview

**Overall:** Layered FastAPI service with queued LangGraph workflows and Word COM serialization.

**Key Characteristics:**
- API routers in `backend/api/` are thin entry points that call services such as `backend/services/document_service.py`, `backend/services/task_service.py`, and `backend/services/template_candidate_ranking_service.py`.
- Pydantic request/response contracts live in `backend/models/`, with task and SSE models in `backend/models/task.py` and `backend/models/sse.py`.
- Long-running document work is represented as tasks in `backend/task/task_queue_manager.py` and executed through graph classes in `backend/graphs/`.
- Tender generation graphs share `StandardTenderWorkflowGraph` from `backend/graphs/base_graph.py` and specialize by binding node callables in graph classes such as `backend/graphs/gngk_fw_zc_tender_graph.py`.
- Rewrite/edit workflows are task skills loaded from `backend/skills/*/SKILL.md` and converted to `TaskSkillWorkflow` objects in `backend/skills/*/scripts/workflow.py`.
- Word COM work is guarded by queue fairness in `backend/task/task_queue_manager.py`, graph/file locking in `backend/graphs/base_graph.py`, and COM-level locking in `backend/util/word_util/word_com_manager.py`.

## Layers

**HTTP API Layer:**
- Purpose: Expose backend-facing REST, SSE, and NDJSON endpoints.
- Location: `backend/api/`
- Contains: FastAPI `APIRouter` modules such as `backend/api/generate.py`, `backend/api/edit.py`, `backend/api/tasks.py`, `backend/api/stream.py`, `backend/api/user.py`, `backend/api/template_candidates.py`, `backend/api/upload.py`, `backend/api/download.py`, and `backend/api/tender.py`.
- Depends on: Pydantic models in `backend/models/` and service modules in `backend/services/`.
- Used by: The FastAPI app registration in `backend/main.py`.

**Model Layer:**
- Purpose: Define API and runtime contracts with Pydantic models and enums.
- Location: `backend/models/`
- Contains: Generate/edit models in `backend/models/generate.py`, task models in `backend/models/task.py`, SSE models in `backend/models/sse.py`, tender models in `backend/models/tender.py`, upload models in `backend/models/upload.py`, and template candidate models in `backend/models/template_candidates.py`.
- Depends on: Pydantic and standard Python types.
- Used by: API routers in `backend/api/`, services in `backend/services/`, and SSE manager code in `backend/core/sse_manager.py`.

**Service Layer:**
- Purpose: Coordinate business workflows between APIs, graphs, task queue, conversation memory, LLM routing, and template ranking.
- Location: `backend/services/`
- Contains: `DocumentService` in `backend/services/document_service.py`, `TaskService` in `backend/services/task_service.py`, `ConversationService` in `backend/services/conversation_service.py`, `UserRoutingService` in `backend/services/user_routing_service.py`, and `TemplateCandidateRankingService` in `backend/services/template_candidate_ranking_service.py`.
- Depends on: Models in `backend/models/`, graph classes in `backend/graphs/`, task queue in `backend/task/task_queue_manager.py`, prompts in `backend/prompts/`, and utilities in `backend/util/`.
- Used by: API routers in `backend/api/` and graph routing code in `backend/graphs/user_graph.py`.

**Task Runtime Layer:**
- Purpose: Track task lifecycle, queue order, progress, cancellation, heartbeats, and task API snapshots.
- Location: `backend/task/task_queue_manager.py`
- Contains: `TaskQueueManager`, internal `Task`, `TaskProgress`, `TaskStatus`, `TaskKind`, `NodeName`, and display-name mappings.
- Depends on: Settings in `backend/config/settings.py`, progress logging in `backend/util/log_util/progress_log.py`, and SSE scheduling through `backend/core/sse_manager.py`.
- Used by: `DocumentService` in `backend/services/document_service.py`, `TaskService` in `backend/services/task_service.py`, and graph progress wrappers in `backend/graphs/base_graph.py`.

**SSE Layer:**
- Purpose: Broadcast task events, retain event history, support reconnection replay, and format SSE frames.
- Location: `backend/core/sse_manager.py`, `backend/api/stream.py`, `backend/util/log_util/sse_log_handler.py`
- Contains: `SSEManager`, `SSEClient`, `/api/stream/{task_id}`, `/api/stream/{task_id}/status`, and a logging handler that routes task-context logs into SSE.
- Depends on: SSE models in `backend/models/sse.py` and settings in `backend/config/settings.py`.
- Used by: `backend/main.py`, `backend/services/document_service.py`, `backend/task/task_queue_manager.py`, and `backend/util/log_util/sse_log_handler.py`.

**Graph Layer:**
- Purpose: Define executable LangGraph workflows for generation, rewrite/edit skills, and user routing.
- Location: `backend/graphs/`
- Contains: `BaseGraph` and `StandardTenderWorkflowGraph` in `backend/graphs/base_graph.py`, tender graphs in `backend/graphs/*_tender_graph.py`, skill graph runtime in `backend/graphs/skill_graph.py`, and user routing graph in `backend/graphs/user_graph.py`.
- Depends on: State classes in `backend/states/`, node modules in `backend/nodes/`, task queue in `backend/task/task_queue_manager.py`, and LangGraph.
- Used by: `DocumentService` in `backend/services/document_service.py` and user stream routing in `backend/api/user.py`.

**State Layer:**
- Purpose: Document the shared graph state surface and type-specific extensions for LangGraph nodes.
- Location: `backend/states/`
- Contains: Shared `TenderGraphStateBase` in `backend/states/base_state.py`, tender states in `backend/states/xjcg_tender_state.py`, `backend/states/gngk_tender_state.py`, `backend/states/gjgk_tender_state.py`, task skill state in `backend/states/skill_state.py`, and user route state in `backend/states/user_state.py`.
- Depends on: Python `TypedDict` and shared type definitions.
- Used by: Graph classes in `backend/graphs/` and node functions in `backend/nodes/`.

**Node Layer:**
- Purpose: Implement graph node callables for Word preparation, parameter extraction, replacement, LLM generation, comment handling, section deletion, rewrite/edit, and Word update.
- Location: `backend/nodes/`
- Contains: Shared nodes in `backend/nodes/common_word_nodes/`, tender-specific nodes in `backend/nodes/gngk_word_nodes/`, `backend/nodes/gjgk_word_nodes/`, `backend/nodes/xjcg_word_nodes/`, and skill nodes in `backend/nodes/skills_nodes/`.
- Depends on: State contracts in `backend/states/`, Word helpers in `backend/helper/word_helper/`, Word utilities in `backend/util/word_util/`, prompts in `backend/prompts/`, and LLM utilities in `backend/util/common_util/llm_stream_utils.py`.
- Used by: Graph classes in `backend/graphs/` and skill workflow declarations in `backend/skills/*/scripts/workflow.py`.

**Word Helper Layer:**
- Purpose: Hold reusable Word business logic that is above low-level COM calls and below graph-node orchestration.
- Location: `backend/helper/word_helper/`
- Contains: Protected field logic in `backend/helper/word_helper/protected_fields.py`, content insertion helpers in `backend/helper/word_helper/content_ops.py`, paragraph boundary helpers in `backend/helper/word_helper/paragraph_boundary_ops.py`, cleanup helpers in `backend/helper/word_helper/cleanup_ops.py`, style helpers in `backend/helper/word_helper/inline_style_ops.py`, and range helpers in `backend/helper/word_helper/range_utils.py`.
- Depends on: Tender config in `backend/config/tender_config.py` and low-level Word constants/utilities in `backend/util/word_util/`.
- Used by: Word nodes such as `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, and `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`.

**Utility Layer:**
- Purpose: Provide low-level Word COM lifecycle, external HTTP utilities, upload storage, LLM streaming, logging, and diagnostics.
- Location: `backend/util/`
- Contains: Word COM utilities in `backend/util/word_util/`, common HTTP/storage/LLM utilities in `backend/util/common_util/`, and logging utilities in `backend/util/log_util/`.
- Depends on: Settings in `backend/config/settings.py`, pywin32 on Windows through `backend/util/word_util/word_application_util.py`, and OpenAI-compatible streaming through `backend/util/common_util/llm_stream_utils.py`.
- Used by: APIs, services, nodes, and scripts under `backend/`.

**Prompt And Skill Layer:**
- Purpose: Keep LLM prompt rendering and task-skill workflow definitions centralized.
- Location: `backend/prompts/`, `backend/skills/`
- Contains: Prompt renderers such as `backend/prompts/generate_prompt.py`, `backend/prompts/comment_prompt.py`, `backend/prompts/routing_prompt.py`, `backend/prompts/template_candidate_ranking_prompt.py`, plus skill definitions and workflow scripts in `backend/skills/rewrite/` and `backend/skills/edit/`.
- Depends on: Prompt input/output types in `backend/prompts/types.py`, skill types in `backend/skills/types.py`, and LLM utilities in `backend/util/common_util/llm_stream_utils.py`.
- Used by: Generation nodes in `backend/nodes/common_word_nodes/generate_polished_text.py`, user routing in `backend/services/user_routing_service.py`, template ranking in `backend/services/template_candidate_ranking_service.py`, and skill graph runtime in `backend/graphs/skill_graph.py`.

## Data Flow

### Primary Generate Request Path

1. Client submits `POST /api/generate`; `create_generate_task()` validates `GenerateRequest` and calls `get_document_service().create_task(request)` in `backend/api/generate.py`.
2. `DocumentService.create_task()` maps `GenerateRequest.form_type` to `GRAPH_REGISTRY`, builds the initial graph state, and selects the LLM node name in `backend/services/document_service.py`.
3. `DocumentService._build_initial_state()` normalizes `tender_type`, `conversation_id`, tender data, file paths, default anchors, `generation_style`, and `style_writeback_mode` in `backend/services/document_service.py`, using anchor defaults from `backend/config/tender_config.py`.
4. `DocumentService._submit_graph_task()` adds the task to `TaskQueueManager`, submits `_run_graph()` to a `ThreadPoolExecutor`, and returns queue position metadata in `backend/services/document_service.py`.
5. `_run_graph()` instantiates the selected graph, estimates node count, compiles the graph, creates a per-task event loop, and calls `_invoke_graph_async()` in `backend/services/document_service.py`.
6. `_invoke_graph_async()` builds LangGraph config with task id, model provider, LLM snapshot callbacks, audit log paths, and stdout/stderr writers, then calls `invoke_with_timing_async()` from `backend/graphs/base_graph.py`.
7. `invoke_with_timing_async()` waits for the task's fair queue turn, acquires the cross-process file lock, marks the task running, registers the running async context, invokes LangGraph, and completes the task queue entry in `backend/graphs/base_graph.py` and `backend/task/task_queue_manager.py`.
8. `StandardTenderWorkflowGraph.build_graph()` executes the shared generation topology: `prepare_template`, optional `get_comments`/`copy_comments`, `extract_tender_params`, `word_operations_subgraph`, `generate_polished_text`, optional `generate_comments`, `update_word`, and optional post-update steps in `backend/graphs/base_graph.py`.
9. Tender graph classes supply the node bindings: `XjcgTenderGraph` in `backend/graphs/xjcg_tender_graph.py`, `GngkHwZcTenderGraph` in `backend/graphs/gngk_hw_zc_tender_graph.py`, `GngkFwZcTenderGraph` in `backend/graphs/gngk_fw_zc_tender_graph.py`, and `GjgkTenderGraph` in `backend/graphs/gjgk_tender_graph.py`.
10. On success, `DocumentService._build_task_result_payload()` builds the output metadata, conversation service stores rewrite state when `conversation_id` exists, task queue stores result, and `SSEManager.send_done_threadsafe()` emits the `done` event in `backend/services/document_service.py`.
11. On failure, `DocumentService._run_graph()` pushes an `ErrorEventData`, sends an SSE `error` event, cleans failed rewrite/edit temp output when applicable, and marks the task failed in `backend/services/document_service.py`.

### Task Status And Cancellation Flow

1. Client reads `GET /api/tasks/{task_id}` or `GET /api/generate/{task_id}`; API routers call `TaskService.get_task()` in `backend/api/tasks.py` and `backend/api/generate.py`.
2. `TaskService` converts the internal `TaskQueueManager.Task` into `TaskInfo`, including status, queue position, waiting count, progress snapshot, and current running task progress for queued tasks in `backend/services/task_service.py`.
3. Client cancels with `DELETE /api/tasks/{task_id}`; `TaskService.cancel_task()` calls `TaskQueueManager.cancel_task()` in `backend/services/task_service.py`.
4. `TaskQueueManager.cancel_task()` removes queued tasks or requests cancellation on the registered running async task and marks the task cancelled in `backend/task/task_queue_manager.py`.
5. Graph nodes are wrapped by `wrap_node_with_progress()`, which checks cancellation before and after each node and raises `TaskCancelledException` from `backend/graphs/base_graph.py`.
6. Task heartbeat uses `POST /api/tasks/{task_id}/heartbeat`; stale queued/running tasks are cancelled by the background cleanup loop in `backend/task/task_queue_manager.py`.

### SSE Event Flow

1. Client connects to `GET /api/stream/{task_id}`; the router first verifies the task exists via `TaskService` in `backend/api/stream.py`.
2. The router parses `Last-Event-ID` from header or `lastEventId` query parameter and starts `SSEManager.event_stream()` in `backend/api/stream.py`.
3. `SSEManager.event_stream()` registers an `SSEClient`, emits a connection log event, replays missed events from per-task storage, sends heartbeat events on timeout, and ends on `done` or `error` in `backend/core/sse_manager.py`.
4. Progress events are emitted by `TaskQueueManager.set_total_nodes()` and `TaskQueueManager.update_progress()` through `SSEManager.send_progress_threadsafe()` in `backend/task/task_queue_manager.py`.
5. LLM snapshot events are throttled by `_LLMSnapshotRelay` and emitted through `SSEManager.send_llm_output_threadsafe()` in `backend/services/document_service.py`.
6. User-readable progress logs are bridged into SSE by `SSELogHandler` within `task_log_context()` in `backend/util/log_util/sse_log_handler.py`.
7. Final `done` and `error` events are emitted by `DocumentService._run_graph()` through `SSEManager.send_done_threadsafe()` and `SSEManager.send_error_threadsafe()` in `backend/services/document_service.py`.

### Rewrite Flow

1. Client sends `POST /api/user/stream`; `stream_user_message()` normalizes messages and constructs `UserGraph` in `backend/api/user.py`.
2. `UserGraph.route_or_reply()` calls `UserRoutingService.stream_route_or_reply()` and emits NDJSON `route`, `chunk`, `done`, or `error` events through a stream writer in `backend/graphs/user_graph.py`.
3. `UserRoutingService` uses deterministic rewrite keyword routing when conversation rewrite history exists, otherwise renders the routing prompt and calls the shared LLM streaming utility in `backend/services/user_routing_service.py`.
4. If route is rewrite, `UserGraph.rewrite_dispatch()` calls `DocumentService.create_rewrite_task()` and emits NDJSON `task_accepted` with task id and queue metadata in `backend/graphs/user_graph.py`.
5. `DocumentService.create_rewrite_task()` validates conversation rewrite history from `ConversationService`, builds skill graph state, and submits the `rewrite` skill graph class in `backend/services/document_service.py`.
6. `SkillGraph` loads the rewrite workflow from `backend/skills/rewrite/scripts/workflow.py`; that workflow executes `resolve_rewrite_target`, optional `get_rewrite_comments`, `delete_section`, `rewrite_text`, and `update_word` through `backend/graphs/skill_graph.py`.
7. Tender-aware delete/update dispatch selects `gjgk`, `gngk_fw_zc`, or shared handlers in `backend/nodes/skills_nodes/tender_aware_word_dispatch.py`.

### Edit Flow

1. Client submits `POST /api/edit`; `create_edit_task()` calls `DocumentService.create_edit_task()` in `backend/api/edit.py`.
2. `DocumentService.create_edit_task()` validates conversation id, edit prompt, target Word path or latest conversation document, creates an edit audit log, builds edit graph initial state, and submits the `edit` skill graph in `backend/services/document_service.py`.
3. `SkillGraph` loads the edit workflow from `backend/skills/edit/scripts/workflow.py`; the workflow executes `resolve_edit_target`, `extract_edit_context`, `delete_section`, `edit_text`, and `update_word` through `backend/graphs/skill_graph.py`.
4. Edit tasks share the same task queue, progress, cancellation, SSE, download, and conversation snapshot mechanisms as generate/rewrite through `backend/services/document_service.py` and `backend/task/task_queue_manager.py`.

### Template Candidate Flow

1. `GET /api/template-candidates` calls `fetch_template_candidates()` and then `TemplateCandidateRankingService.rank_candidates()` in `backend/api/template_candidates.py`.
2. Candidate fetch and normalization use the external template candidate URL from settings, validate JSON array shape, normalize year/selectability, and apply blocked reasons in `backend/util/common_util/template_candidates.py`.
3. Tied-priority candidate groups can be AI-ranked by `TemplateCandidateRankingService._rank_group_by_ai()` using prompt rendering and `stream_llm_completion()` in `backend/services/template_candidate_ranking_service.py`.
4. `GET /api/template-candidates/download` validates the remote file URL against allowed hosts and proxies the file response in `backend/api/template_candidates.py` and `backend/util/common_util/template_candidates.py`.
5. `POST /api/template-candidates/select` rejects invalid/old years, downloads the selected template file, persists it twice into upload storage, and returns selected file slots in `backend/api/template_candidates.py` and `backend/util/common_util/upload_storage.py`.

### Upload, Download, And External Tender Data Flow

1. Upload endpoints read `UploadFile` bytes and call `persist_file_bytes()` for sanitization, extension validation, size validation, unique naming, and disk persistence in `backend/api/upload.py` and `backend/util/common_util/upload_storage.py`.
2. Download endpoint validates that the requested file resolves under `settings.UPLOAD_DIR` before returning `FileResponse` in `backend/api/download.py`.
3. Tender data endpoint calls `fetch_tender_data()` and maps the response into `TenderData` and `TenderType` models in `backend/api/tender.py`.

**State Management:**
- Task runtime state is in-memory and process-local in `TaskQueueManager` at `backend/task/task_queue_manager.py`.
- SSE event replay buffers are in-memory and process-local in `SSEManager` at `backend/core/sse_manager.py`.
- Conversation rewrite/edit state is in-memory and process-local in `ConversationService` at `backend/services/conversation_service.py`.
- LangGraph execution state is a `TypedDict` contract under `backend/states/`, with shared tender fields in `backend/states/base_state.py` and task skill extensions in `backend/states/skill_state.py`.
- Uploaded and generated files are persisted to the configured upload directory through `backend/util/common_util/upload_storage.py` and downloaded through `backend/api/download.py`.

## Key Abstractions

**`GenerateRequest` / `EditTaskRequest`:**
- Purpose: Backend API input contracts for generation and explicit edit tasks.
- Examples: `backend/models/generate.py`, `backend/api/generate.py`, `backend/api/edit.py`
- Pattern: Pydantic models with typed enums for `FormType`, `LLMModel`, `GenerationStyle`, and `StyleWritebackMode`.

**`FormType` To `GRAPH_REGISTRY`:**
- Purpose: Map backend form type strings to graph classes.
- Examples: `backend/models/generate.py`, `backend/services/document_service.py`, `backend/graphs/__init__.py`
- Pattern: Enum values such as `xjcg_tender`, `gngk_hw_zc_tender`, `gngk_fw_zc_tender`, and `gjgk_tender` resolve to graph classes through delayed registry initialization.

**`TenderGraphStateBase`:**
- Purpose: Shared graph state contract for tender generation and task-skill writeback.
- Examples: `backend/states/base_state.py`, `backend/states/gngk_tender_state.py`, `backend/states/gjgk_tender_state.py`
- Pattern: `TypedDict(total=False)` base plus explicit per-type extensions.

**`BaseGraph`:**
- Purpose: Common graph compile/invoke surface with locking and progress support.
- Examples: `backend/graphs/base_graph.py`, `backend/graphs/xjcg_tender_graph.py`
- Pattern: Subclasses implement `build_graph()` and `get_state_class()`, then call `compile()`, `invoke()`, or `ainvoke()`.

**`StandardTenderWorkflowGraph`:**
- Purpose: Shared generation workflow topology for tender document creation.
- Examples: `backend/graphs/base_graph.py`, `backend/graphs/xjcg_tender_graph.py`, `backend/graphs/gngk_hw_zc_tender_graph.py`, `backend/graphs/gjgk_tender_graph.py`
- Pattern: Graph subclasses bind node callables as class attributes and override `get_word_operation_steps()` or `get_post_update_steps()` only for real workflow differences.

**`TaskQueueManager`:**
- Purpose: Queue, serialize, cancel, and track long-running graph tasks.
- Examples: `backend/task/task_queue_manager.py`, `backend/services/task_service.py`, `backend/graphs/base_graph.py`
- Pattern: Process-level singleton returned by `get_task_queue()`.

**`SSEManager`:**
- Purpose: Manage per-task SSE clients, event buffers, replay, and cross-thread event scheduling.
- Examples: `backend/core/sse_manager.py`, `backend/api/stream.py`, `backend/services/document_service.py`
- Pattern: Process-level singleton `sse_manager` with `send_*_threadsafe()` methods for background graph threads.

**`TaskSkillWorkflow`:**
- Purpose: Declare executable rewrite/edit workflows from skill metadata.
- Examples: `backend/skills/types.py`, `backend/skills/rewrite/scripts/workflow.py`, `backend/skills/edit/scripts/workflow.py`
- Pattern: Skill folders contain `SKILL.md` frontmatter plus `scripts/workflow.py` returning a `TaskSkillWorkflow`.

**Prompt Rendering:**
- Purpose: Separate prompt construction and prompt-bound parsing from service/node side effects.
- Examples: `backend/prompts/generate_prompt.py`, `backend/prompts/comment_prompt.py`, `backend/prompts/routing_prompt.py`, `backend/prompts/template_candidate_ranking_prompt.py`
- Pattern: Services and nodes collect data, call prompt renderers, then call `stream_llm_completion()` from `backend/util/common_util/llm_stream_utils.py`.

**Tender Configuration:**
- Purpose: Store anchor texts, font sizes, content update modes, protected-field profiles, and tender family mapping.
- Examples: `backend/config/tender_config.py`, `backend/services/document_service.py`, `backend/nodes/common_word_nodes/update_word.py`
- Pattern: Node logic asks config helpers such as `get_default_anchor_texts()`, `get_anchor_target_sizes()`, `get_tender_type_family()`, and `get_protected_field_profile()`.

## Entry Points

**Backend process:**
- Location: `backend/main.py`
- Triggers: `python main.py`, `uvicorn backend.main:app`, or root startup scripts documented in `README.md`.
- Responsibilities: Register routers with `/api`, configure CORS, initialize logging/SSE listeners, expose health endpoints, and run uvicorn when executed as a script.

**Generate task:**
- Location: `backend/api/generate.py`
- Triggers: `POST /api/generate`
- Responsibilities: Validate `GenerateRequest`, call `DocumentService.create_task()`, and return `GenerateResponse` with task id and queue metadata.

**Edit task:**
- Location: `backend/api/edit.py`
- Triggers: `POST /api/edit`
- Responsibilities: Validate `EditTaskRequest`, call `DocumentService.create_edit_task()`, and return the shared task response.

**User route stream:**
- Location: `backend/api/user.py`
- Triggers: `POST /api/user/stream`
- Responsibilities: Normalize chat messages, run `UserGraph`, and return NDJSON route/reply/task events.

**Task status and control:**
- Location: `backend/api/tasks.py`
- Triggers: `GET /api/tasks`, `GET /api/tasks/{task_id}`, `DELETE /api/tasks/{task_id}`, `POST /api/tasks/{task_id}/heartbeat`
- Responsibilities: Expose task snapshots, cancellation, and page heartbeat.

**Task SSE stream:**
- Location: `backend/api/stream.py`
- Triggers: `GET /api/stream/{task_id}`, `GET /api/stream/{task_id}/status`
- Responsibilities: Validate task existence, stream SSE events, support replay, and report client count.

**Upload/download:**
- Location: `backend/api/upload.py`, `backend/api/download.py`
- Triggers: `POST /api/upload`, `POST /api/upload/multiple`, `GET /api/download/{file_path:path}`
- Responsibilities: Persist uploads and serve generated/uploaded files with path-safety checks.

**Tender lookup:**
- Location: `backend/api/tender.py`
- Triggers: `GET /api/tender/{tender_no}`
- Responsibilities: Fetch and normalize external tender data.

**Template candidates:**
- Location: `backend/api/template_candidates.py`
- Triggers: `GET /api/template-candidates`, `GET /api/template-candidates/download`, `POST /api/template-candidates/select`
- Responsibilities: Proxy, rank, download, and store template candidate files.

**Word diagnostics:**
- Location: `backend/scripts/diagnose_word.py`
- Triggers: Manual backend diagnostic command.
- Responsibilities: Diagnose Word COM availability through utilities under `backend/util/word_util/`.

## Architectural Constraints

- **Runtime platform:** Complete backend document generation requires Windows Python with Microsoft Word COM support; this is reflected by `pywin32>=306; platform_system == "Windows"` in `backend/requirements.txt`, Word setup instructions in `README.md`, and COM utilities in `backend/util/word_util/word_application_util.py`.
- **Threading:** FastAPI runs on the main event loop in `backend/main.py`; document graphs run in a `ThreadPoolExecutor` in `backend/services/document_service.py`; each graph worker creates a per-task asyncio event loop in `backend/services/document_service.py`; SSE events are scheduled back to the main loop through `SSEManager.bind_loop()` and `send_*_threadsafe()` in `backend/core/sse_manager.py`.
- **Word serialization:** Long-running graph execution must pass through fair queue ordering in `backend/task/task_queue_manager.py`, cross-process file locking in `backend/graphs/base_graph.py`, and COM-level locking in `backend/util/word_util/word_com_manager.py`.
- **Global state:** Process-level singletons exist for task queue in `backend/task/task_queue_manager.py`, document service in `backend/services/document_service.py`, task service in `backend/services/task_service.py`, conversation service in `backend/services/conversation_service.py`, SSE manager in `backend/core/sse_manager.py`, and skill registry in `backend/skills/registry.py`.
- **Persistence limits:** Task state, SSE event buffers, and conversation rewrite history are process-local memory stores in `backend/task/task_queue_manager.py`, `backend/core/sse_manager.py`, and `backend/services/conversation_service.py`; uploaded/generated files are persisted through `backend/util/common_util/upload_storage.py`.
- **API prefix:** Backend routers are registered under `/api` in `backend/main.py`; health and root endpoints are outside `/api` in `backend/main.py`.
- **Configuration:** Settings are loaded through Pydantic Settings from `backend/config/settings.py`; `backend/.env` exists as environment configuration and must not be quoted; `backend/.env.example` is the setup template referenced by `README.md`.
- **Import style:** Backend package imports should use `backend.*`; this is the dominant pattern across `backend/api/`, `backend/services/`, and `backend/graphs/`. Short imports such as `from util.word_util` exist in some node modules and should not be copied.
- **Circular imports:** No circular dependency chain is documented in the backend source scan; delayed imports are used in `backend/graphs/base_graph.py`, `backend/services/document_service.py`, and `backend/task/task_queue_manager.py` where task queue/SSE/graph code would otherwise be tightly coupled.

## Anti-Patterns

### Bypassing The Task Queue For Word Work

**What happens:** A route, service, script, or node opens Word and mutates a document outside the `DocumentService` + `TaskQueueManager` + `BaseGraph` execution path.
**Why it's wrong:** It bypasses the fair queue in `backend/task/task_queue_manager.py`, the file lock in `backend/graphs/base_graph.py`, and COM lock/retry behavior in `backend/util/word_util/word_com_manager.py`.
**Do this instead:** Submit document generation, rewrite, or edit work through `DocumentService` in `backend/services/document_service.py`; place reusable Word logic under `backend/helper/word_helper/` or low-level COM utilities under `backend/util/word_util/`.

### Copying A Whole Tender Graph For Small Differences

**What happens:** A new tender type duplicates `backend/graphs/xjcg_tender_graph.py`, `backend/graphs/gngk_hw_zc_tender_graph.py`, or `backend/graphs/gjgk_tender_graph.py` and edits string constants.
**Why it's wrong:** The shared topology already lives in `StandardTenderWorkflowGraph` in `backend/graphs/base_graph.py`, and tender-specific graph classes are supposed to bind only the nodes that differ.
**Do this instead:** Add or override only the necessary node callables in a graph class under `backend/graphs/`, following `backend/graphs/gngk_fw_zc_tender_graph.py` for service-specific node overrides and `backend/graphs/gjgk_tender_graph.py` for workflow-step overrides.

### Adding Type Rules Inside Nodes Instead Of Tender Config

**What happens:** A node hardcodes anchor texts, font sizes, protected-field profiles, or tender family logic.
**Why it's wrong:** Anchors, content modes, family routing, and protected-field profiles are centralized in `backend/config/tender_config.py`.
**Do this instead:** Add type-level config to `backend/config/tender_config.py` and call helpers such as `get_default_anchor_texts()`, `get_anchor_target_sizes()`, `get_content_update_mode()`, `get_tender_type_family()`, and `get_protected_field_profile()`.

### Duplicating Word Business Helpers In Nodes

**What happens:** Type-specific nodes reimplement protected-field scanning, paragraph-boundary logic, content insertion, cleanup, or inline style writeback.
**Why it's wrong:** The shared business layer already exists in `backend/helper/word_helper/`, while low-level COM lifecycle belongs in `backend/util/word_util/`.
**Do this instead:** Move reusable Word business behavior to modules such as `backend/helper/word_helper/protected_fields.py`, `backend/helper/word_helper/content_ops.py`, and `backend/helper/word_helper/paragraph_boundary_ops.py`; keep node modules such as `backend/nodes/common_word_nodes/update_word.py` focused on orchestration.

### Scattering Prompt Construction Outside The Prompt Layer

**What happens:** Services or nodes build long LLM prompts inline instead of calling prompt renderers.
**Why it's wrong:** Generate, comment, route, skill, and template-ranking prompt contracts are centralized in `backend/prompts/` and tested under `backend/tests/prompts/`.
**Do this instead:** Add or change prompt renderers in `backend/prompts/`, then call them from nodes/services such as `backend/nodes/common_word_nodes/generate_polished_text.py`, `backend/services/user_routing_service.py`, or `backend/services/template_candidate_ranking_service.py`.

### Copying Short Import Compatibility Patterns

**What happens:** New backend files import from `util.*` or mutate `sys.path` for normal package imports.
**Why it's wrong:** Backend code is packaged around `backend.*` imports, and root path injection is only a compatibility measure in `backend/main.py`, `backend/__init__.py`, and several node modules.
**Do this instead:** Use absolute `backend.*` imports as shown in `backend/services/document_service.py`, `backend/graphs/gngk_hw_zc_tender_graph.py`, and `backend/api/stream.py`.

## Error Handling

**Strategy:** API validation errors return structured `HTTPException` payloads, graph execution errors become task failure state plus SSE `error` events, and Word/LLM helpers fail fast when required configuration or document contracts are missing.

**Patterns:**
- API not-found/conflict cases use structured error payloads with codes such as `TASK_NOT_FOUND`, `TASK_CANNOT_CANCEL`, and template-specific codes in `backend/api/tasks.py`, `backend/api/generate.py`, and `backend/api/template_candidates.py`.
- Unhandled request exceptions are caught by the global exception handler in `backend/main.py` and returned as HTTP 500 without exposing stack details to the client.
- Graph cancellation raises `TaskCancelledException` from `backend/graphs/base_graph.py`, and `DocumentService._run_graph()` converts it into a non-fatal SSE error in `backend/services/document_service.py`.
- LLM configuration and stream timeout errors are centralized in `backend/util/common_util/llm_stream_utils.py` and surfaced through user routing or node execution paths in `backend/services/user_routing_service.py` and `backend/nodes/common_word_nodes/generate_polished_text.py`.
- Upload and download safety errors are raised near storage/path boundaries in `backend/util/common_util/upload_storage.py` and `backend/api/download.py`.
- Protected-field contract violations fail fast through helper functions in `backend/helper/word_helper/protected_fields.py`.

## Cross-Cutting Concerns

**Logging:** `backend/main.py` configures JSON stdout logging and starts progress/execution log listeners; `backend/util/log_util/progress_log.py`, `backend/util/log_util/execution_log.py`, `backend/util/log_util/prompt_log.py`, and `backend/util/log_util/skill_audit_log.py` split user progress, execution detail, prompt logging, and skill audit logs.

**SSE Logging:** `backend/util/log_util/sse_log_handler.py` uses `task_log_context()` to forward task-scoped INFO/WARNING/ERROR progress logs through `backend/core/sse_manager.py`.

**Validation:** Pydantic models validate API payloads in `backend/models/`; tender-specific config and protected-field contracts are validated by `backend/config/tender_config.py` and `backend/helper/word_helper/protected_fields.py`.

**Authentication:** Not detected in backend route modules; the API routers in `backend/api/` do not depend on auth middleware or auth dependencies.

**External Services:** LLM calls use OpenAI-compatible streaming through `backend/util/common_util/llm_stream_utils.py`; tender data and template candidates use HTTP utilities in `backend/util/common_util/fetch_tender_data.py` and `backend/util/common_util/template_candidates.py`.

**File Safety:** Upload persistence sanitizes filenames and validates extension/size in `backend/util/common_util/upload_storage.py`; downloads are restricted to `settings.UPLOAD_DIR` in `backend/api/download.py`; template candidate downloads validate allowed hosts in `backend/util/common_util/template_candidates.py`.

**Testing Hooks:** Backend tests are grouped by layer under `backend/tests/`, including graph tests in `backend/tests/graphs/`, node tests in `backend/tests/nodes/`, service tests in `backend/tests/services/`, API tests in `backend/tests/api/`, helper tests in `backend/tests/helper/`, and prompt tests in `backend/tests/prompts/`.

---

*Architecture analysis: 2026-05-22*
