# Codebase Structure

**Analysis Date:** 2026-05-22

## Directory Layout

```text
TenderWord/
├── AGENTS.md                         # Repository operating guide with backend constraints
├── README.md                         # Backend setup and startup requirements
├── backend/
│   ├── main.py                       # FastAPI application entry point
│   ├── requirements.txt              # Backend Python dependencies
│   ├── api/                          # FastAPI routers
│   ├── config/                       # Settings and tender-type configuration
│   ├── core/                         # SSE core manager
│   ├── graphs/                       # LangGraph workflows
│   ├── helper/word_helper/           # Reusable Word business helpers
│   ├── models/                       # Pydantic API/event/task models
│   ├── nodes/                        # LangGraph node functions
│   ├── prompts/                      # Prompt renderers and parsers
│   ├── scripts/                      # Backend diagnostic scripts
│   ├── services/                     # Business orchestration services
│   ├── skills/                       # Task skill definitions and workflows
│   ├── states/                       # LangGraph TypedDict state contracts
│   ├── task/                         # Task queue runtime
│   ├── tests/                        # Backend pytest suite
│   └── util/                         # Common, logging, and Word utilities
```

## Directory Purposes

**Root Backend Guides:**
- Purpose: Keep backend setup and operating constraints visible to agents and developers.
- Contains: Repository guide at `AGENTS.md` and backend startup instructions at `README.md`.
- Key files: `AGENTS.md`, `README.md`.

**`backend/`:**
- Purpose: Python backend package for the FastAPI, LangGraph, task queue, SSE, LLM, and Word COM system.
- Contains: Package entry point `backend/main.py`, dependency manifest `backend/requirements.txt`, and subpackages under `backend/`.
- Key files: `backend/main.py`, `backend/requirements.txt`, `backend/__init__.py`.

**`backend/api/`:**
- Purpose: FastAPI route definitions.
- Contains: Thin routers for generate, edit, user stream, tasks, SSE stream, upload, download, tender lookup, conversation heartbeat, and template candidates.
- Key files: `backend/api/generate.py`, `backend/api/edit.py`, `backend/api/user.py`, `backend/api/tasks.py`, `backend/api/stream.py`, `backend/api/upload.py`, `backend/api/download.py`, `backend/api/tender.py`, `backend/api/conversations.py`, `backend/api/template_candidates.py`.

**`backend/config/`:**
- Purpose: Central backend settings and tender-type configuration.
- Contains: Pydantic Settings in `backend/config/settings.py` and tender anchors/protected-field profiles in `backend/config/tender_config.py`.
- Key files: `backend/config/settings.py`, `backend/config/tender_config.py`.

**`backend/core/`:**
- Purpose: Backend core infrastructure that does not belong to HTTP routes or graph nodes.
- Contains: SSE client/event manager and package exports.
- Key files: `backend/core/sse_manager.py`, `backend/core/__init__.py`.

**`backend/graphs/`:**
- Purpose: LangGraph workflow definitions and graph execution base classes.
- Contains: Shared graph runtime, standard tender workflow, concrete tender graphs, skill graph runtime, and user routing graph.
- Key files: `backend/graphs/base_graph.py`, `backend/graphs/xjcg_tender_graph.py`, `backend/graphs/gngk_hw_zc_tender_graph.py`, `backend/graphs/gngk_hw_cz_tender_graph.py`, `backend/graphs/gngk_fw_zc_tender_graph.py`, `backend/graphs/gngk_fw_cz_tender_graph.py`, `backend/graphs/gjgk_tender_graph.py`, `backend/graphs/skill_graph.py`, `backend/graphs/user_graph.py`, `backend/graphs/__init__.py`.

**`backend/helper/word_helper/`:**
- Purpose: Reusable Word business logic shared by nodes.
- Contains: Cleanup, content insertion, inline style writeback, paragraph boundary, protected field, range, semantic matching, and text parsing helpers.
- Key files: `backend/helper/word_helper/protected_fields.py`, `backend/helper/word_helper/content_ops.py`, `backend/helper/word_helper/paragraph_boundary_ops.py`, `backend/helper/word_helper/cleanup_ops.py`, `backend/helper/word_helper/inline_style_ops.py`, `backend/helper/word_helper/range_utils.py`, `backend/helper/word_helper/text_parsing.py`, `backend/helper/word_helper/semantic_matcher.py`.

**`backend/models/`:**
- Purpose: Pydantic models and enums for API requests, responses, task snapshots, and SSE events.
- Contains: Generate/edit models, common error models, task models, SSE models, tender models, upload models, and template candidate models.
- Key files: `backend/models/generate.py`, `backend/models/task.py`, `backend/models/sse.py`, `backend/models/tender.py`, `backend/models/template_candidates.py`, `backend/models/upload.py`, `backend/models/common.py`, `backend/models/__init__.py`.

**`backend/nodes/`:**
- Purpose: LangGraph node functions grouped by shared behavior, tender-specific behavior, and task-skill behavior.
- Contains: Shared Word nodes in `backend/nodes/common_word_nodes/`, tender-specific nodes in `backend/nodes/gngk_word_nodes/`, `backend/nodes/gjgk_word_nodes/`, `backend/nodes/xjcg_word_nodes/`, and rewrite/edit nodes in `backend/nodes/skills_nodes/`.
- Key files: `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/common_word_nodes/generate_polished_text.py`, `backend/nodes/common_word_nodes/delete_tender_param.py`, `backend/nodes/common_word_nodes/extract_tender_params.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/nodes/skills_nodes/edit_nodes.py`, `backend/nodes/skills_nodes/tender_aware_word_dispatch.py`.

**`backend/prompts/`:**
- Purpose: Central LLM prompt rendering and prompt-bound parsing.
- Contains: Generate prompt routing, template-vs-param prompts, comment prompt, routing prompt, skill prompt, template candidate ranking prompt, and prompt input/output types.
- Key files: `backend/prompts/generate_prompt.py`, `backend/prompts/generate_by_template_prompt.py`, `backend/prompts/generate_by_param_prompt.py`, `backend/prompts/comment_prompt.py`, `backend/prompts/routing_prompt.py`, `backend/prompts/skill_prompt.py`, `backend/prompts/template_candidate_ranking_prompt.py`, `backend/prompts/types.py`.

**`backend/scripts/`:**
- Purpose: Manual backend diagnostics.
- Contains: Word COM diagnostic script.
- Key files: `backend/scripts/diagnose_word.py`.

**`backend/services/`:**
- Purpose: Business orchestration layer.
- Contains: Document task orchestration, task API adapter, in-memory conversation state, user route/reply logic, chat streaming helpers, and template candidate ranking.
- Key files: `backend/services/document_service.py`, `backend/services/task_service.py`, `backend/services/conversation_service.py`, `backend/services/user_routing_service.py`, `backend/services/chat_stream_service.py`, `backend/services/template_candidate_ranking_service.py`, `backend/services/__init__.py`.

**`backend/skills/`:**
- Purpose: Task skill declarations and executable workflow scripts for rewrite/edit.
- Contains: Skill loader/registry/types plus skill folders with `SKILL.md` and workflow/runtime scripts.
- Key files: `backend/skills/loader.py`, `backend/skills/registry.py`, `backend/skills/types.py`, `backend/skills/rewrite/SKILL.md`, `backend/skills/rewrite/scripts/workflow.py`, `backend/skills/rewrite/scripts/runtime.py`, `backend/skills/edit/SKILL.md`, `backend/skills/edit/scripts/workflow.py`, `backend/skills/edit/scripts/runtime.py`.

**`backend/states/`:**
- Purpose: LangGraph state contracts.
- Contains: Shared tender state, type-specific tender states, task skill state, and user routing state.
- Key files: `backend/states/base_state.py`, `backend/states/xjcg_tender_state.py`, `backend/states/gngk_tender_state.py`, `backend/states/gjgk_tender_state.py`, `backend/states/skill_state.py`, `backend/states/user_state.py`, `backend/states/__init__.py`.

**`backend/task/`:**
- Purpose: Long-running task queue and progress runtime.
- Contains: Queue manager singleton, task dataclasses, task kind/status enums, progress tracking, fair-lock logic, cancellation, and heartbeat cleanup.
- Key files: `backend/task/task_queue_manager.py`, `backend/task/__init__.py`.

**`backend/tests/`:**
- Purpose: Backend pytest test suite grouped by module scope.
- Contains: API, config, graph, helper, logging, model, node, progress, prompt, service, skill, and utility tests.
- Key files: `backend/tests/api/test_generate_api.py`, `backend/tests/graphs/test_gngk_tender_graph.py`, `backend/tests/nodes/test_tender_aware_word_dispatch.py`, `backend/tests/services/test_document_service_initial_state.py`, `backend/tests/prompts/test_generate_prompt_routing.py`, `backend/tests/util/test_llm_stream_utils.py`, `backend/tests/conftest.py`.

**`backend/util/common_util/`:**
- Purpose: Common non-Word utilities for external HTTP, upload storage, LLM streaming, and tender number normalization.
- Contains: Tender data fetch, LLM streaming, template candidate fetch/download validation, upload persistence, and tender number normalization.
- Key files: `backend/util/common_util/fetch_tender_data.py`, `backend/util/common_util/llm_stream_utils.py`, `backend/util/common_util/template_candidates.py`, `backend/util/common_util/upload_storage.py`, `backend/util/common_util/tender_number.py`.

**`backend/util/log_util/`:**
- Purpose: Logging infrastructure for progress, execution detail, prompt output, skill audit, SSE log bridge, and log cleanup.
- Contains: Dedicated loggers and handlers.
- Key files: `backend/util/log_util/progress_log.py`, `backend/util/log_util/execution_log.py`, `backend/util/log_util/prompt_log.py`, `backend/util/log_util/skill_audit_log.py`, `backend/util/log_util/sse_log_handler.py`, `backend/util/log_util/log_cleanup.py`, `backend/util/log_util/daily_file_handler.py`.

**`backend/util/word_util/`:**
- Purpose: Low-level Word COM lifecycle, constants, document inspection, anchor lookup, extraction, insertion, and diagnostics.
- Contains: Word app creation/closing, COM manager, constants, anchor utilities, diagnostics, document inspector, extraction helpers, and insertion helpers.
- Key files: `backend/util/word_util/word_application_util.py`, `backend/util/word_util/word_com_manager.py`, `backend/util/word_util/anchor_utils.py`, `backend/util/word_util/word_constants.py`, `backend/util/word_util/word_insert_text.py`, `backend/util/word_util/word_diagnostics.py`, `backend/util/word_util/word_document_inspector.py`.

## Key File Locations

**Entry Points:**
- `backend/main.py`: FastAPI app factory, router registration, startup/shutdown events, health endpoints, and uvicorn script entry.
- `backend/api/generate.py`: Generate task creation and generate task status endpoint.
- `backend/api/edit.py`: Explicit edit task creation endpoint.
- `backend/api/user.py`: Unified user NDJSON stream endpoint for reply/rewrite routing.
- `backend/api/stream.py`: SSE endpoint for task event streaming and replay.
- `backend/api/tasks.py`: Task list/detail/cancel/heartbeat endpoints.

**Configuration:**
- `backend/config/settings.py`: Pydantic settings, backend `.env` loading location, CORS, LLM, upload, lock, logging, SSE, and task defaults.
- `backend/config/tender_config.py`: Tender anchors, target sizes, tender family, content update modes, and protected-field profiles.
- `backend/.env`: Environment configuration file is present; do not read or quote its contents.
- `backend/.env.example`: Backend environment setup template referenced by `README.md`.
- `backend/requirements.txt`: Backend Python dependency manifest.

**Core Logic:**
- `backend/services/document_service.py`: Main orchestration for generate/rewrite/edit graph tasks.
- `backend/task/task_queue_manager.py`: Task lifecycle, queue fairness, progress, cancellation, and heartbeat cleanup.
- `backend/core/sse_manager.py`: SSE client/event storage and stream formatting.
- `backend/graphs/base_graph.py`: Base graph runtime, standard tender workflow topology, progress wrappers, cancellation checks, fair lock, and file lock.
- `backend/graphs/skill_graph.py`: Generic graph builder for task skill workflows.
- `backend/graphs/user_graph.py`: User route/reply/rewrite dispatch graph.

**Tender Graphs:**
- `backend/graphs/xjcg_tender_graph.py`: XJCG graph node bindings.
- `backend/graphs/gngk_hw_zc_tender_graph.py`: GNGK goods/self-funded base graph node bindings.
- `backend/graphs/gngk_hw_cz_tender_graph.py`: GNGK goods/fiscal graph class inheriting the GNGK base graph.
- `backend/graphs/gngk_fw_zc_tender_graph.py`: GNGK service/self-funded graph overrides for delete/replacements/update nodes.
- `backend/graphs/gngk_fw_cz_tender_graph.py`: GNGK service/fiscal graph class inheriting the GNGK base graph.
- `backend/graphs/gjgk_tender_graph.py`: GJGK graph with custom word-operation and post-update step ordering.

**State Contracts:**
- `backend/states/base_state.py`: Shared `BaseState`, `CommentInstruction`, and `TenderGraphStateBase`.
- `backend/states/xjcg_tender_state.py`: XJCG graph state.
- `backend/states/gngk_tender_state.py`: GNGK graph state.
- `backend/states/gjgk_tender_state.py`: GJGK graph state.
- `backend/states/skill_state.py`: Rewrite/edit task skill state.
- `backend/states/user_state.py`: User route/reply graph state.

**Graph Nodes:**
- `backend/nodes/common_word_nodes/`: Shared generation nodes.
- `backend/nodes/gngk_word_nodes/`: GNGK-specific node wrappers and overrides.
- `backend/nodes/gjgk_word_nodes/`: GJGK-specific delete/replacement/update nodes.
- `backend/nodes/xjcg_word_nodes/`: XJCG-specific replacement node.
- `backend/nodes/skills_nodes/`: Rewrite/edit and tender-aware dispatch nodes.

**Word Logic:**
- `backend/helper/word_helper/`: Reusable business rules for protected fields, paragraph boundaries, content insertion, cleanup, and style writeback.
- `backend/util/word_util/`: Low-level COM lifecycle, constants, anchor lookup, insertion utilities, diagnostics, and document inspection.

**LLM And Prompts:**
- `backend/prompts/`: Prompt layer for generate/comment/routing/skill/template ranking.
- `backend/util/common_util/llm_stream_utils.py`: OpenAI-compatible streaming, timeout, provider config lookup, and LLM environment validation.
- `backend/services/user_routing_service.py`: Conversation-aware route/reply service.
- `backend/services/template_candidate_ranking_service.py`: AI ranking for tied template candidates.

**Task Skills:**
- `backend/skills/rewrite/SKILL.md`: Rewrite skill declaration and instructions.
- `backend/skills/rewrite/scripts/workflow.py`: Rewrite skill workflow definition.
- `backend/skills/edit/SKILL.md`: Edit skill declaration and instructions.
- `backend/skills/edit/scripts/workflow.py`: Edit skill workflow definition.
- `backend/skills/loader.py`: Skill frontmatter parser.
- `backend/skills/registry.py`: Skill registry and workflow loader.
- `backend/skills/types.py`: Skill definition and workflow dataclasses.

**Storage And External APIs:**
- `backend/util/common_util/upload_storage.py`: Upload persistence and filename safety.
- `backend/api/download.py`: Download path traversal guard and file response.
- `backend/util/common_util/fetch_tender_data.py`: External tender data fetch utility.
- `backend/util/common_util/template_candidates.py`: External template candidate fetch/download/select helper logic.

**Testing:**
- `backend/tests/api/`: API route tests.
- `backend/tests/graphs/`: Graph registration and topology tests.
- `backend/tests/nodes/`: Node behavior tests.
- `backend/tests/helper/`: Word helper tests.
- `backend/tests/services/`: Service tests.
- `backend/tests/prompts/`: Prompt rendering/parsing tests.
- `backend/tests/skills/`: Skill instruction/loader tests.
- `backend/tests/util/`: Utility tests.

## Naming Conventions

**Files:**
- Use snake_case Python module names, as in `backend/services/document_service.py`, `backend/task/task_queue_manager.py`, and `backend/util/common_util/llm_stream_utils.py`.
- Name API route files after resource or capability, as in `backend/api/generate.py`, `backend/api/tasks.py`, `backend/api/template_candidates.py`, and `backend/api/user.py`.
- Name tender graph modules `<type>_tender_graph.py`, as in `backend/graphs/xjcg_tender_graph.py`, `backend/graphs/gngk_fw_zc_tender_graph.py`, and `backend/graphs/gjgk_tender_graph.py`.
- Name tender state modules `<type>_tender_state.py`, as in `backend/states/xjcg_tender_state.py`, `backend/states/gngk_tender_state.py`, and `backend/states/gjgk_tender_state.py`.
- Name backend tests `test_*.py`, grouped under module-scope directories such as `backend/tests/graphs/test_gngk_tender_graph.py` and `backend/tests/services/test_document_service_initial_state.py`.

**Classes:**
- Use PascalCase for services, graphs, models, and state classes, as in `DocumentService` in `backend/services/document_service.py`, `GngkFwZcTenderGraph` in `backend/graphs/gngk_fw_zc_tender_graph.py`, `GenerateRequest` in `backend/models/generate.py`, and `TenderGraphStateBase` in `backend/states/base_state.py`.
- Tender graph class names mirror tender type identity, as in `XjcgTenderGraph`, `GngkHwZcTenderGraph`, `GngkFwZcTenderGraph`, and `GjgkTenderGraph` under `backend/graphs/`.
- Task skill workflow classes are not hand-written per skill; `SkillGraph.for_skill()` dynamically creates a class name from skill id in `backend/graphs/skill_graph.py`.

**Functions:**
- Use snake_case for route handlers, service methods, helper functions, and node functions, as in `create_generate_task()` in `backend/api/generate.py`, `create_task()` in `backend/services/document_service.py`, `get_default_anchor_texts()` in `backend/config/tender_config.py`, and `update_word()` in `backend/nodes/common_word_nodes/update_word.py`.
- Node function names match graph node names or type-prefixed variants, as in `delete_tender_param` in `backend/nodes/common_word_nodes/delete_tender_param.py`, `gngk_fw_zc_update_word` in `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, and `gjgk_update_word` in `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`.
- Singleton accessors use `get_*()` names, as in `get_document_service()` in `backend/services/document_service.py`, `get_task_queue()` in `backend/task/task_queue_manager.py`, and `get_skill_registry()` in `backend/skills/registry.py`.

**Constants And Enums:**
- Use uppercase constants for shared maps and runtime constants, as in `GRAPH_REGISTRY` and `REWRITE_STATE_KEYS` in `backend/services/document_service.py`, `NODE_DISPLAY_NAMES` in `backend/task/task_queue_manager.py`, and `ANCHOR_CONFIGS` in `backend/config/tender_config.py`.
- Use enum classes for API/runtime categorical values, as in `FormType`, `LLMModel`, `GenerationStyle`, and `StyleWritebackMode` in `backend/models/generate.py`, and `TaskStatus`/`TaskKind` in `backend/models/task.py`.

**Directories:**
- Group by backend layer first, not by tender type, using `backend/api/`, `backend/services/`, `backend/graphs/`, `backend/nodes/`, `backend/states/`, `backend/models/`, `backend/prompts/`, and `backend/tests/`.
- Put type-specific Word node behavior under `backend/nodes/<type>_word_nodes/`, as in `backend/nodes/gngk_word_nodes/` and `backend/nodes/gjgk_word_nodes/`.
- Put reusable Word business helpers under `backend/helper/word_helper/`; put low-level COM utilities under `backend/util/word_util/`.
- Put task skill declarations and workflow code under `backend/skills/<skill_id>/`, as in `backend/skills/rewrite/` and `backend/skills/edit/`.

## Where to Add New Code

**New Backend API Endpoint:**
- Primary code: add a router module under `backend/api/` or extend an existing router such as `backend/api/tasks.py`.
- Models: add request/response models under `backend/models/`.
- Service logic: put orchestration in `backend/services/`, following `backend/services/task_service.py` or `backend/services/template_candidate_ranking_service.py`.
- Registration: include the router in `create_application()` in `backend/main.py`.
- Tests: add API tests under `backend/tests/api/test_*.py`.

**New Generate Tender Type:**
- Request enum: add the backend form type in `FormType` in `backend/models/generate.py`.
- State: add or extend a state under `backend/states/`, inheriting from `TenderGraphStateBase` in `backend/states/base_state.py`.
- Graph: add a graph class under `backend/graphs/`, preferably subclassing `StandardTenderWorkflowGraph` from `backend/graphs/base_graph.py`.
- Registry: add the form type to `GRAPH_REGISTRY` in `_init_graph_registry()` in `backend/services/document_service.py` and export the class in `backend/graphs/__init__.py`.
- Config: add anchors, sizes, content update mode, tender family, and protected-field profile changes in `backend/config/tender_config.py`.
- Nodes: use shared nodes from `backend/nodes/common_word_nodes/`; add type-prefixed differences under `backend/nodes/<type>_word_nodes/` only when behavior differs.
- Tests: add graph registration/topology tests under `backend/tests/graphs/test_*.py`, node tests under `backend/tests/nodes/test_*.py`, config tests under `backend/tests/config/test_*.py`, and service initial-state tests under `backend/tests/services/test_*.py`.

**New Shared Graph Node:**
- Implementation: add the node function under `backend/nodes/common_word_nodes/` when it is usable by multiple tender types.
- Export: update `backend/nodes/common_word_nodes/__init__.py`.
- Graph wiring: add it through `StandardTenderWorkflowGraph` in `backend/graphs/base_graph.py` or through a graph override in `backend/graphs/<type>_tender_graph.py`.
- Progress: add the node name to `TRACKED_PROGRESS_NODES` in `backend/graphs/base_graph.py` and `NodeName`/`NODE_DISPLAY_NAMES` in `backend/task/task_queue_manager.py` when the node is user-visible progress.
- Tests: add focused tests under `backend/tests/nodes/test_*.py` and graph tests under `backend/tests/graphs/test_*.py` when topology changes.

**New Type-Specific Word Node:**
- Implementation: add a type-prefixed module under `backend/nodes/gngk_word_nodes/`, `backend/nodes/gjgk_word_nodes/`, `backend/nodes/xjcg_word_nodes/`, or a new `backend/nodes/<type>_word_nodes/`.
- Export: update that package `__init__.py`, following `backend/nodes/gngk_word_nodes/__init__.py`.
- Graph binding: override only the differing `NODE_*` class attribute in the graph, following `backend/graphs/gngk_fw_zc_tender_graph.py`.
- Shared logic: extract common business behavior to `backend/helper/word_helper/`; keep COM lifecycle calls in `backend/util/word_util/`.
- Tests: add node tests under `backend/tests/nodes/test_*.py`.

**New Word Business Helper:**
- Implementation: add it under `backend/helper/word_helper/`.
- Use when: the logic represents document business behavior such as protected field scanning, paragraph boundaries, markdown/table parsing, cleanup, or style writeback.
- Do not use for: raw COM app lifecycle, constants, or low-level Word API wrappers; those belong under `backend/util/word_util/`.
- Tests: add helper tests under `backend/tests/helper/test_*.py`.

**New Low-Level Word Utility:**
- Implementation: add it under `backend/util/word_util/`.
- Use when: the logic manages Word app lifecycle, COM locking/retry, constants, anchor lookup primitives, diagnostics, insertion primitives, or document inspection.
- Tests: add utility tests under `backend/tests/util/test_*.py` when the utility can be tested without Word COM, and document Windows+Word COM verification when it cannot.

**New Prompt Or LLM Contract:**
- Implementation: add prompt renderer or parser under `backend/prompts/`.
- Types: add prompt input/output dataclasses or parsers under `backend/prompts/types.py` when shared.
- Caller: call the renderer from a service or node, following `backend/nodes/common_word_nodes/generate_polished_text.py`, `backend/services/user_routing_service.py`, or `backend/services/template_candidate_ranking_service.py`.
- LLM streaming: use `stream_llm_completion()` from `backend/util/common_util/llm_stream_utils.py`.
- Tests: add prompt contract tests under `backend/tests/prompts/test_*.py`.

**New Task Skill:**
- Declaration: add `backend/skills/<skill_id>/SKILL.md` with the required frontmatter used by `backend/skills/loader.py`.
- Workflow: add `backend/skills/<skill_id>/scripts/workflow.py` returning `TaskSkillWorkflow` from `backend/skills/types.py`.
- Runtime helpers: add `backend/skills/<skill_id>/scripts/runtime.py` when workflow branching or node count estimation is needed.
- Nodes: add reusable skill nodes under `backend/nodes/skills_nodes/`.
- Graph: use `SkillGraph.for_skill()` from `backend/graphs/skill_graph.py`; wire task creation through `DocumentService` in `backend/services/document_service.py` when it is a queued document task.
- Tests: add skill tests under `backend/tests/skills/test_*.py`, node tests under `backend/tests/nodes/test_*.py`, and progress tests under `backend/tests/progress/test_*.py` when progress changes.

**New External HTTP Integration:**
- Settings: add configuration names and defaults in `backend/config/settings.py`, avoiding secrets in committed files.
- Utility: put HTTP fetch/normalization helpers under `backend/util/common_util/`.
- Service: put orchestration and AI ranking/processing under `backend/services/`.
- API: expose backend-owned endpoints under `backend/api/`.
- Tests: add utility tests under `backend/tests/util/test_*.py`, service tests under `backend/tests/services/test_*.py`, and API tests under `backend/tests/api/test_*.py`.

**New Logging Or SSE Event:**
- Event contract: update `backend/models/sse.py`.
- Manager behavior: update `backend/core/sse_manager.py`.
- Emission site: update `backend/services/document_service.py`, `backend/task/task_queue_manager.py`, or `backend/util/log_util/sse_log_handler.py`.
- API stream behavior: update `backend/api/stream.py` only when stream endpoint semantics change.
- Tests: add tests under `backend/tests/progress/`, `backend/tests/logging/`, or `backend/tests/api/` depending on the changed surface.

## Special Directories

**`backend/logs/`:**
- Purpose: Runtime backend logs managed by logging utilities and startup cleanup.
- Generated: Yes.
- Committed: Directory exists in the working tree; log file contents should not be treated as source contracts.
- Relevant code: `backend/main.py`, `backend/util/log_util/log_cleanup.py`, `backend/util/log_util/progress_log.py`, `backend/util/log_util/execution_log.py`.

**`backend/prompts_log/`:**
- Purpose: Runtime prompt or generation log output.
- Generated: Yes.
- Committed: Directory exists in the working tree; generated prompt logs should not be used as API contracts.
- Relevant code: `backend/util/log_util/prompt_log.py`, `backend/nodes/common_word_nodes/generate_polished_text.py`.

**`backend/test_doc/`:**
- Purpose: Local backend test documents.
- Generated: No for committed fixtures; may also contain local artifacts.
- Committed: Directory exists in the working tree.
- Relevant code: Word-related tests under `backend/tests/nodes/` and diagnostics under `backend/scripts/diagnose_word.py`.

**`backend/.venv/` and `backend/.venv-linux/`:**
- Purpose: Local Python virtual environments for Windows and Linux/WSL workflows.
- Generated: Yes.
- Committed: No.
- Relevant setup: `README.md`, `backend/requirements.txt`.

**`backend/.env`:**
- Purpose: Local backend environment configuration.
- Generated: Developer-created from setup.
- Committed: No.
- Handling: File existence only; do not read, quote, or copy contents.
- Relevant setup: `README.md`, `backend/config/settings.py`.

**`backend/.env.example`:**
- Purpose: Backend environment setup template.
- Generated: No.
- Committed: Yes.
- Relevant setup: `README.md`, `backend/config/settings.py`.

**`backend/__pycache__/` and nested `__pycache__/`:**
- Purpose: Python bytecode caches.
- Generated: Yes.
- Committed: No.
- Relevant directories: Caches appear under packages such as `backend/tests/`.

---

*Structure analysis: 2026-05-22*
