# Coding Conventions

**Analysis Date:** 2026-05-22

## Scope

**Backend-only map:**
- Treat `backend/` as the implementation scope for these conventions.
- Use root guidance only where it directly governs backend validation, API contracts, Word COM constraints, or test placement: `AGENTS.md`, `README.md`.
- Do not use frontend tests as backend convention sources. Backend API shape changes still require frontend contract synchronization because `AGENTS.md` names `backend/api/`, `backend/models/`, `frontend/types/`, and `frontend/lib/api.ts` as shared API truth sources.

## Naming Patterns

**Files:**
- Use snake_case Python modules under backend packages, as in `backend/api/generate.py`, `backend/services/document_service.py`, `backend/config/tender_config.py`, and `backend/helper/word_helper/content_ops.py`.
- Use `test_*.py` for backend tests and place them under module-scoped directories such as `backend/tests/api/test_generate_api.py`, `backend/tests/services/test_document_service_initial_state.py`, and `backend/tests/nodes/test_gngk_fw_zc_update_word.py`.
- Name graph modules as `<type>_tender_graph.py` and classes as PascalCase `<Type>TenderGraph`, as in `backend/graphs/xjcg_tender_graph.py`, `backend/graphs/gngk_fw_zc_tender_graph.py`, and `backend/graphs/gjgk_tender_graph.py`.
- Put common Word nodes in `backend/nodes/common_word_nodes/` with generic names such as `backend/nodes/common_word_nodes/update_word.py`; put type-specific Word nodes in `backend/nodes/<type>_word_nodes/` with type prefixes such as `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py` and `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`.
- Put reusable Word business helpers in `backend/helper/word_helper/` with operation-oriented names such as `content_ops.py`, `paragraph_boundary_ops.py`, `protected_fields.py`, and `inline_style_ops.py`.
- Put low-level Word COM utilities in `backend/util/word_util/`, for example `backend/util/word_util/word_application_util.py`, `backend/util/word_util/anchor_utils.py`, and `backend/util/word_util/word_insert_text.py`.

**Functions:**
- Use snake_case for functions and route handlers, as in `create_generate_task()` and `get_generate_task()` in `backend/api/generate.py`, `list_tasks()` and `cancel_task()` in `backend/api/tasks.py`, and `load_skill_definitions()` in `backend/skills/loader.py`.
- Use the public node callable name as the stable graph contract, for example `update_word()` in `backend/nodes/common_word_nodes/update_word.py`, `gngk_fw_zc_update_word()` in `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, and `dispatch_tender_aware_update_word()` in `backend/nodes/skills_nodes/tender_aware_word_dispatch.py`.
- Prefix private helpers with `_` when they are module-internal implementation details, as in `_resolve_block4_insert_pos()` in `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py` and `_parse_skill_definition()` in `backend/skills/loader.py`.

**Variables:**
- Use snake_case for local variables and state keys such as `task_id`, `tender_type`, `prepared_doc_path`, and `style_writeback_result` in `backend/states/base_state.py` and `backend/services/document_service.py`.
- Use UPPER_SNAKE_CASE for module constants and registries such as `GRAPH_REGISTRY`, `REWRITE_STATE_KEYS`, `TASK_KIND_TO_LLM_NODE`, and `REWRITE_DEFAULT_ANCHORS` in `backend/services/document_service.py`.
- Use explicit marker/profile constants for Word protected-field contracts, such as `COMMON_TWO_FIELD_PROFILE_KEY`, `GNGK_THREE_FIELD_PROFILE_KEY`, and `PROTECTED_FIELD_PROFILE_OVERRIDES` in `backend/config/tender_config.py`.

**Types:**
- Use PascalCase for Pydantic models and enums such as `GenerateRequest`, `EditTaskRequest`, `GenerateResponse`, `FormType`, and `GenerationStyle` in `backend/models/generate.py`.
- Use PascalCase for graph state `TypedDict` classes such as `TenderGraphStateBase` in `backend/states/base_state.py`, `GngkTenderGraphState` in `backend/states/gngk_tender_state.py`, and `TaskSkillGraphState` exported from `backend/states/__init__.py`.
- Use frozen dataclasses for immutable configuration/prompt DTOs, as in `TenderAnchorConfig` and `ProtectedFieldProfile` in `backend/config/tender_config.py`, and `RenderedPrompt`, `GeneratePromptInput`, and `TaskSkillPromptInput` in `backend/prompts/types.py`.

## Code Style

**Formatting:**
- Match the existing Python style in `backend/`: module docstrings, `from __future__ import annotations` for newer modules, standard-library imports before third-party imports, then `backend.*` imports, as shown in `backend/config/tender_config.py`, `backend/prompts/types.py`, and `backend/skills/loader.py`.
- Prefer Python type hints on public functions and DTOs. Existing code uses `str | List[str]` in `backend/models/generate.py`, `Optional[...]` in `backend/config/settings.py`, and typed `dict[str, object]` test helpers in `backend/tests/services/test_document_service_initial_state.py`.
- Keep comments focused on operational contracts and non-obvious Word/graph behavior, as in `backend/helper/word_helper/protected_fields.py`, `backend/helper/word_helper/content_ops.py`, and `backend/graphs/base_graph.py`.

**Linting:**
- Not detected as a configured backend gate. There is no visible backend lint command in `README.md`; root validation guidance in `AGENTS.md` names `python -m pytest tests -v` as the backend minimum.
- Because no formatter/linter config is detected, preserve local style by matching nearby files in the same backend package, especially `backend/api/`, `backend/models/`, `backend/services/`, `backend/graphs/`, and `backend/helper/word_helper/`.

## Import Organization

**Order:**
1. Future annotations first, as in `backend/config/tender_config.py` and `backend/skills/types.py`.
2. Standard library imports such as `logging`, `datetime`, `pathlib`, `threading`, and `typing`, as in `backend/main.py`, `backend/api/tasks.py`, and `backend/services/document_service.py`.
3. Third-party imports such as FastAPI, Pydantic, LangGraph, and OpenAI-related clients, as in `backend/api/generate.py`, `backend/models/generate.py`, `backend/graphs/base_graph.py`, and `backend/services/chat_stream_service.py`.
4. Backend package imports using `backend.*`, as in `backend/api/tasks.py`, `backend/services/document_service.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, and `backend/prompts/generate_prompt.py`.

**Path Aliases:**
- Cross-package backend imports must use the `backend.*` package root. Root guidance explicitly requires this for API, service, task, graph, and node packages in `AGENTS.md`.
- `backend/main.py` adds the project root to `sys.path` so absolute `backend.*` imports resolve when running the app directly.
- `backend/tests/conftest.py` adds both the project root and backend root to `sys.path` so tests can import `backend.*` modules.
- Avoid new short imports such as `from util.word_util ...`; current exceptions exist in `backend/nodes/common_word_nodes/prepare_template.py` and `backend/nodes/common_word_nodes/generate_polished_text.py`, but new backend code should follow the `backend.*` pattern required by `AGENTS.md`.

## Error Handling

**Patterns:**
- API routes should raise `fastapi.HTTPException` with structured `detail` data containing `success`, `error.code`, `error.message`, and relevant identifiers. Use the task-not-found shape in `backend/api/tasks.py`, `backend/api/generate.py`, and `backend/api/stream.py` as the model.
- Request validation belongs in Pydantic models and validators. `EditTaskRequest` in `backend/models/generate.py` validates non-empty text, `fund_source_lx`, and `tender_lx` before service logic runs.
- Configuration and business-contract failures should fail fast with `ValueError`, as in `get_protected_field_profile()` in `backend/config/tender_config.py`, `split_polished_text_into_blocks()` in `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, and `validate_profile_required_protected_fields()` in `backend/helper/word_helper/protected_fields.py`.
- Operational Word/COM failures should raise `RuntimeError` with enough context for execution logs, as in `backend/util/word_util/word_application_util.py` and `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`.
- Graph cancellation should flow through `TaskCancelledException` and `_check_cancellation()` in `backend/graphs/base_graph.py`; nodes should not invent a parallel cancellation mechanism.
- Always close Word applications through the existing utility path after COM work. Current Word nodes import and call `create_word_application`, `open_document_with_retry`, and `close_word_application` from `backend/util/word_util/`, as shown in `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, and `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`.

## Logging

**Framework:** Python `logging`, plus project log utilities in `backend/util/log_util/`.

**Patterns:**
- Use `logger = logging.getLogger(__name__)` for API/service/module diagnostics, as in `backend/api/tasks.py`, `backend/api/stream.py`, `backend/services/user_routing_service.py`, and `backend/services/template_candidate_ranking_service.py`.
- Use `progress_log` for user-facing progress and high-level task status. It is queue-backed and file-backed in `backend/util/log_util/progress_log.py`, and is converted to SSE events by `backend/util/log_util/sse_log_handler.py`.
- Use execution/audit logging for task success and task-specific traces. Generate-success audit logic lives in `backend/util/log_util/execution_log.py`; edit/rewrite audit path handling is covered by `backend/util/log_util/skill_audit_log.py` and tests in `backend/tests/logging/test_task_audit_log_paths.py`.
- Initialize logging, progress listeners, execution listeners, SSE log handling, and log cleanup from application startup in `backend/main.py`.
- Keep user-facing progress concise. Detailed diagnostics belong in execution logs or debug logs, following the boundary in `AGENTS.md`, `backend/util/log_util/progress_log.py`, and `backend/util/log_util/execution_log.py`.

## Comments

**When to Comment:**
- Add comments for graph ordering, Word COM locks, protected-field parsing, prompt contracts, and fail-fast behavior. Existing examples live in `backend/graphs/base_graph.py`, `backend/helper/word_helper/protected_fields.py`, and `backend/prompts/comment_prompt.py`.
- Avoid historical planning comments in new code. Existing references such as requirement notes in `backend/graphs/xjcg_tender_graph.py` should not be copied into new modules unless they describe current behavior.

**JSDoc/TSDoc:**
- Not applicable for backend Python. Use Python docstrings for public API routes, services, graph classes, helper functions, and DTOs, as in `backend/api/stream.py`, `backend/services/document_service.py`, `backend/graphs/xjcg_tender_graph.py`, and `backend/models/common.py`.

## Function Design

**Size:** Keep API handlers thin and push orchestration to services. `backend/api/generate.py` delegates task creation to `backend/services/document_service.py`; `backend/api/tasks.py` delegates task state to `backend/services/task_service.py`.

**Parameters:** Pass explicit state/config objects through graph nodes. Node callables use `(state, config)` and return state updates in `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, and `backend/nodes/skills_nodes/tender_aware_word_dispatch.py`.

**Return Values:** Return typed Pydantic response models from API routes, such as `GenerateResponse` in `backend/api/generate.py` and `TaskResponse`/`TaskCancelResponse` in `backend/api/tasks.py`.

**Pure Logic:** Move COM-free parsing, matching, and insertion decision logic into helpers so it can be unit tested. Use `backend/helper/word_helper/protected_fields.py`, `backend/helper/word_helper/content_ops.py`, `backend/helper/word_helper/paragraph_boundary_ops.py`, and `backend/helper/word_helper/inline_style_ops.py` as the pattern.

## Module Design

**Exports:** Use package `__init__.py` files for public graph/node/state imports. Examples include `backend/graphs/__init__.py`, `backend/states/__init__.py`, `backend/nodes/common_word_nodes/__init__.py`, and `backend/util/word_util/__init__.py`.

**Barrel Files:** Barrel files exist for backend packages, but implementation should remain in dedicated modules such as `backend/services/document_service.py`, `backend/config/tender_config.py`, and `backend/helper/word_helper/content_ops.py`.

**Configuration:** Use `backend/config/settings.py` for runtime settings via Pydantic Settings. It reads backend environment configuration from `backend/.env`; never read, print, test, or document secret values from `backend/.env`.

**Prompt Layer:** Keep LLM prompt rendering in `backend/prompts/`. `backend/prompts/generate_prompt.py` routes generate prompt style, `backend/prompts/types.py` defines prompt input DTOs, and `backend/prompts/template_candidate_ranking_prompt.py` owns template-ranking prompt shape.

**Skill Runtime:** Keep task skill declarations under `backend/skills/*/SKILL.md`, parse declarations with `backend/skills/loader.py`, and represent workflows with immutable dataclasses from `backend/skills/types.py`.

## Graph And Node Conventions

**Standard graph pattern:**
- New standard generation graphs should subclass `StandardTenderWorkflowGraph` from `backend/graphs/base_graph.py`.
- Set `STATE_CLS` and class-level `NODE_*` callables like `XjcgTenderGraph` in `backend/graphs/xjcg_tender_graph.py`.
- Override only the type-specific node callables needed for a subtype, as `GngkFwZcTenderGraph` does in `backend/graphs/gngk_fw_zc_tender_graph.py`.
- Register new backend `form_type` values in `GRAPH_REGISTRY` through `_init_graph_registry()` in `backend/services/document_service.py`, and keep `FormType` in `backend/models/generate.py` synchronized.

**Shared trunk first:**
- Keep common workflow construction in `StandardTenderWorkflowGraph` and common nodes in `backend/nodes/common_word_nodes/`.
- Add type-specific nodes only when the business behavior differs, following `backend/nodes/gngk_word_nodes/gngk_fw_zc_delete_tender_param.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_get_replacements.py`, and `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`.
- Use `get_tender_type_family()` in `backend/config/tender_config.py` when behavior should collapse `gngk` variants to a shared family.

**Word COM boundary:**
- Do not call pywin32/COM from API routes, services, or arbitrary scripts. Word application lifecycle belongs behind utilities exported from `backend/util/word_util/__init__.py` and used by Word nodes such as `backend/nodes/common_word_nodes/update_word.py`.
- Graph execution and progress wrapping belong in `backend/graphs/base_graph.py`; new nodes should be added through `wrap_node_with_progress()` by graph/workflow builders rather than manually updating progress.
- Keep protected-field profiles, anchors, content modes, and target sizes in `backend/config/tender_config.py`; node code should call `get_anchor_target_sizes()`, `get_default_anchor_texts()`, and `get_protected_field_profile()`.

**Protected field contracts:**
- Normalize protected-field markers through `backend/helper/word_helper/protected_fields.py` before scanning or splitting text.
- Use strict protected-field matching from `match_protected_field_line()` and fail-fast validation from `validate_profile_required_protected_fields()` in `backend/helper/word_helper/protected_fields.py`.
- Preserve explicit blank lines in generated body text where helpers already support it, as tested by `backend/tests/nodes/test_gngk_fw_zc_update_word.py` and implemented in `backend/helper/word_helper/content_ops.py`.

---

*Convention analysis: 2026-05-22*
