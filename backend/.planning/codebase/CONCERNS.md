# Codebase Concerns

**Analysis Date:** 2026-05-22

Scope: backend only. Root guidance from `AGENTS.md` and startup constraints from `README.md` are referenced only where they define backend constraints.

## Tech Debt

**Split tender-type registry and graph wiring:**
- Issue: Tender type identity is still maintained across separate registries and model/config sites instead of one backend metadata source.
- Files: `backend/models/generate.py`, `backend/services/document_service.py`, `backend/config/tender_config.py`, `backend/graphs/gngk_hw_zc_tender_graph.py`, `backend/graphs/gngk_hw_cz_tender_graph.py`, `backend/graphs/gngk_fw_zc_tender_graph.py`, `backend/graphs/gngk_fw_cz_tender_graph.py`, `AGENTS.md`
- Impact: Adding a backend tender type requires synchronized edits to `FormType`, `GRAPH_REGISTRY`, graph classes, anchor config, protected-field config, and state assembly. Missing one site breaks generate, rewrite state, task status, or Word insertion at runtime.
- Fix approach: Create a backend tender-type registry that owns `form_type`, runtime `tender_type`, graph class, state class, anchors, content mode, protected-field profile, and rewrite defaults. Keep `backend/models/generate.py` and `backend/services/document_service.py` generated or derived from that registry.

**Large Word writeback modules exceed maintainable size:**
- Issue: Word insertion and style writeback logic is concentrated in very large modules with duplicated control flow.
- Files: `backend/helper/word_helper/inline_style_ops.py`, `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`, `AGENTS.md`
- Impact: Small Word behavior changes can diverge between common, `gngk_fw_zc`, and `gjgk` paths. The highest-risk sections are protected-field splitting, editable-range recovery, cleanup, style writeback, comment writeback, and save/error handling.
- Fix approach: Continue extracting shared Word business behavior into `backend/helper/word_helper/`. Leave only anchor selection, type-specific block order, and state assembly in `backend/nodes/common_word_nodes/`, `backend/nodes/gngk_word_nodes/`, `backend/nodes/gjgk_word_nodes/`, and `backend/nodes/xjcg_word_nodes/`.

**Import path mutation and legacy short imports:**
- Issue: Multiple backend modules mutate `sys.path` to support direct script execution, and some still import through short package roots.
- Files: `backend/__init__.py`, `backend/main.py`, `backend/nodes/common_word_nodes/prepare_template.py`, `backend/nodes/common_word_nodes/generate_polished_text.py`, `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`, `backend/tests/conftest.py`
- Impact: Package import behavior depends on process cwd and execution style. This can mask missing `backend.*` absolute imports in tests while failing under uvicorn, scripts, WSL, or packaged execution.
- Fix approach: Keep runtime imports on `backend.*` only. Move direct-run diagnostics into `backend/scripts/` wrappers and remove `sys.path` mutation from node modules.

**Duplicated and dead code in graph lock implementation:**
- Issue: `CrossProcessFileLock` contains duplicate imports and two `acquire()` definitions; the first includes unreachable code that references `lock_file_path` outside its local scope.
- Files: `backend/graphs/base_graph.py`
- Impact: The effective lock is the second `acquire()` method, but dead code makes lock behavior harder to audit. This is high-risk because `AGENTS.md` makes `backend/graphs/base_graph.py` the owner of Word COM serialization, cancellation checks, and progress wrapping.
- Fix approach: Collapse `backend/graphs/base_graph.py` to one import block and one lock implementation. Add a focused lock unit test around timeout, release, and context-manager failure behavior.

**Task, SSE, and conversation state are process-local:**
- Issue: Task records, SSE events, callbacks, and rewrite conversation state live in in-memory singletons.
- Files: `backend/task/task_queue_manager.py`, `backend/core/sse_manager.py`, `backend/services/document_service.py`, `backend/services/conversation_service.py`
- Impact: Restarting the backend loses active tasks, task results, SSE replay buffers, and rewrite/edit history. Multiple uvicorn workers would have isolated queues and isolated conversation state.
- Fix approach: Keep single-process operation explicit in deployment guidance, or persist task/conversation metadata to a durable backend before enabling multiple workers or restart recovery.

**Dependency versions are lower-bound only:**
- Issue: Backend dependencies are specified with `>=` ranges rather than pinned versions or a lockfile.
- Files: `backend/requirements.txt`
- Impact: Fresh installs can receive newer FastAPI, LangGraph, OpenAI, pywin32, or Pydantic behavior without a planned upgrade. This is risky for Word COM automation, async streaming, and Pydantic response validation.
- Fix approach: Add a lock strategy for backend development and CI, or pin critical runtime dependencies with scheduled upgrade windows.

## Known Bugs

**Completed generate status can build an invalid `GenerateResponse`:**
- Symptoms: `GET /api/generate/{task_id}` assigns `task_info.result` directly to `GenerateResponse.output_file` when a task is completed. Document tasks store a dict payload, while `output_file` is typed as `Optional[str]`.
- Files: `backend/api/generate.py`, `backend/models/generate.py`, `backend/services/document_service.py`, `backend/task/task_queue_manager.py`
- Trigger: Complete a generate task through `backend/services/document_service.py`, then query `backend/api/generate.py` for that task after `Task.result` contains the full result payload dict.
- Workaround: Prefer `GET /api/tasks/{task_id}` until `backend/api/generate.py` extracts `result["output_file"]`, `result["file_name"]`, and related fields explicitly.

**Graph execution finalizes task state before service-level completion payload is built:**
- Symptoms: `backend/graphs/base_graph.py` calls `queue.complete_task()` inside the graph invocation `finally`, then `backend/services/document_service.py` calls `complete_task()` again after building the output payload and sending done events.
- Files: `backend/graphs/base_graph.py`, `backend/services/document_service.py`, `backend/task/task_queue_manager.py`
- Trigger: Any successful async graph task reaches the `finally` block in `invoke_with_timing_async()` before `DocumentService._run_graph()` builds the final result payload.
- Workaround: Treat `backend/services/document_service.py` as the completion owner. Move graph-level status updates to "running/progress only" or add an internal "graph returned" signal that does not finalize `Task.result`.

**SSE task cleanup exists but is not invoked:**
- Symptoms: `SSEManager.cleanup_task()` removes clients, events, and counters, but no backend caller invokes it.
- Files: `backend/core/sse_manager.py`, `backend/services/document_service.py`, `backend/task/task_queue_manager.py`
- Trigger: Tasks complete or fail and are later removed by `TaskQueueManager.cleanup_old_tasks()`, while `SSEManager._events` can retain per-task event history until process exit.
- Workaround: Call `sse_manager.cleanup_task(task_id)` after frontend replay TTL expires, or have `TaskQueueManager.cleanup_old_tasks()` schedule SSE cleanup on the bound loop.

**Readiness endpoint reports upload readiness without checking the filesystem:**
- Symptoms: `/health/ready` hardcodes `upload_dir_accessible=True`.
- Files: `backend/main.py`, `backend/config/settings.py`
- Trigger: `settings.UPLOAD_DIR` is missing, read-only, or points to an unavailable Windows path.
- Workaround: Check `Path(settings.UPLOAD_DIR).exists()`, create/write permissions, and free-space availability in `backend/main.py`.

## Security Considerations

**Task and file APIs have no authentication or ownership checks:**
- Risk: Any caller with backend network access can list tasks, query task results, cancel tasks, attach to SSE streams, upload files, request downloads under `UPLOAD_DIR`, create generate/edit tasks, and call user routing endpoints.
- Files: `backend/main.py`, `backend/api/tasks.py`, `backend/api/stream.py`, `backend/api/download.py`, `backend/api/upload.py`, `backend/api/generate.py`, `backend/api/edit.py`, `backend/api/user.py`, `backend/services/task_service.py`
- Current mitigation: CORS defaults are limited to localhost origins in `backend/config/settings.py`, but backend routes themselves do not enforce session ownership or authentication.
- Recommendations: Add a request-scoped session/user identity and enforce it in `backend/services/task_service.py`, `backend/api/stream.py`, and `backend/api/download.py`. `GET /api/tasks` should require an owner filter or privileged role.

**Download endpoint exposes any file under the upload directory by path:**
- Risk: `validate_file_path()` blocks traversal outside `settings.UPLOAD_DIR`, but a caller that knows or guesses an upload-directory path can download it.
- Files: `backend/api/download.py`, `backend/config/settings.py`, `backend/util/common_util/upload_storage.py`
- Current mitigation: Path traversal is blocked with `Path.resolve()` and `relative_to(upload_dir)`.
- Recommendations: Replace raw path downloads with task-bound or file-token downloads. Keep a server-side file registry that maps opaque IDs to paths and owner/session.

**Upload validation is extension-only and reads whole files into memory:**
- Risk: `save_upload_file()` reads the full upload into memory before validation/persistence; `persist_file_bytes()` trusts sanitized filename extension and does not inspect file signatures or scan content.
- Files: `backend/api/upload.py`, `backend/util/common_util/upload_storage.py`, `backend/config/settings.py`
- Current mitigation: Extension allowlist and max byte size are enforced in `backend/util/common_util/upload_storage.py`.
- Recommendations: Stream uploads to a temp file with size enforcement, verify content signatures for Word/PDF formats, and add malware scanning or quarantine for untrusted files.

**Template download proxy validates only the initial URL before following redirects:**
- Risk: `fetch_template_file()` validates the submitted URL host, then calls `requests.get()` with default redirect behavior. A whitelisted host can redirect to an unapproved host unless redirects are disabled or final URL is revalidated.
- Files: `backend/util/common_util/template_candidates.py`, `backend/api/template_candidates.py`, `backend/config/settings.py`
- Current mitigation: Initial scheme and hostname are validated against `TEMPLATE_CANDIDATE_ALLOWED_HOSTS`.
- Recommendations: Set `allow_redirects=False` or validate every redirect target. Enforce response size limits while streaming to disk.

**External tender and template APIs use plain HTTP defaults:**
- Risk: Tender data and template candidate requests default to non-TLS URLs.
- Files: `backend/config/settings.py`, `backend/util/common_util/fetch_tender_data.py`, `backend/util/common_util/template_candidates.py`
- Current mitigation: Not detected in code beyond network timeout.
- Recommendations: Prefer HTTPS endpoints when available, keep these services on trusted networks, and avoid logging sensitive external payload contents.

**Environment file boundary exists in backend:**
- Risk: `backend/.env` is present and `backend/config/settings.py` loads it. Values must never be printed or copied into planning docs.
- Files: `backend/.env`, `backend/.env.example`, `backend/config/settings.py`, `.gitignore`, `README.md`
- Current mitigation: `.gitignore` ignores `.env`, `.env.local`, `.env.*.local`, `.venv/`, `.venv-*`, and the `backend/logs` contents.
- Recommendations: Continue treating `backend/.env` as secret material. Document only variable names and existence, never values.

## Performance Bottlenecks

**The graph execution lock serializes the whole graph, not only Word COM sections:**
- Problem: `invoke_with_timing_async()` waits for queue turn and then holds the cross-process lock while `graph_instance.ainvoke()` runs.
- Files: `backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`, `AGENTS.md`
- Cause: The lock is the safety boundary for Word COM, but standard graphs also include LLM calls, extraction, replacement, comments, style writeback, and task bookkeeping.
- Improvement path: Split graph work into non-COM phases and COM phases, or introduce explicit Word operation locks inside Word nodes while preserving task ordering where required.

**Thread pool workers can be occupied by queued tasks waiting for a turn:**
- Problem: `DocumentService` submits every task to a 4-worker `ThreadPoolExecutor`, and each worker can block in `queue.wait_for_turn()` for up to 1200 seconds.
- Files: `backend/services/document_service.py`, `backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`, `backend/config/settings.py`
- Cause: Queue waiting happens inside worker execution rather than before worker submission.
- Improvement path: Use a single queue runner for Word-bound tasks or submit only the active task to the executor. Keep queued tasks as metadata until they are eligible to run.

**Template proxy and selection load remote files fully into memory:**
- Problem: `download_template_candidate()` returns `upstream_response.content`, and `select_template_candidate()` stores `template_content = upstream_response.content` before writing files.
- Files: `backend/api/template_candidates.py`, `backend/util/common_util/template_candidates.py`, `backend/util/common_util/upload_storage.py`
- Cause: `requests.Response.content` buffers the whole response.
- Improvement path: Stream remote content through a size-limited temp file and persist by chunks. Reuse `iter_response_content()` from `backend/util/common_util/template_candidates.py` instead of `.content`.

**SSE LLM snapshots can grow event memory quickly:**
- Problem: LLM output is sent as full `content_mode="snapshot"` events and `SSEManager` keeps up to 1000 events per task.
- Files: `backend/services/document_service.py`, `backend/core/sse_manager.py`, `backend/config/settings.py`
- Cause: `_LLMSnapshotRelay` emits full-content snapshots, while `_events` retains per-task histories for replay.
- Improvement path: Keep snapshot mode only for frontend replacement semantics, but store compact deltas or coalesce old LLM events in `SSEManager._events`.

## Fragile Areas

**Word COM lifecycle and cleanup:**
- Files: `backend/util/word_util/word_application_util.py`, `backend/util/word_util/word_com_manager.py`, `backend/graphs/base_graph.py`, `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`
- Why fragile: Windows COM automation depends on process threading, document locks, cleanup, retry timing, and global serialization. Nodes call `create_word_application()`, `open_document_with_retry()`, `unprotect_document()`, save, and close across several large modules.
- Safe modification: Keep all COM work inside Word utilities and Word nodes. Add tests for pure helper logic, and run Windows + Word COM integration checks for changes that touch `backend/util/word_util/`, `backend/nodes/common_word_nodes/`, `backend/nodes/gngk_word_nodes/`, `backend/nodes/gjgk_word_nodes/`, or `backend/nodes/xjcg_word_nodes/`.
- Test coverage: Helper-heavy logic has tests under `backend/tests/helper/` and `backend/tests/nodes/`, but real COM integration is not represented by automated pytest coverage.

**Comment and style writeback are shared task-contract fields:**
- Files: `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`, `backend/services/document_service.py`, `backend/tests/services/test_document_service_task_result.py`, `AGENTS.md`
- Why fragile: `comment_writeback_*` and `style_writeback_*` fields are produced by Word nodes, summarized by `DocumentService._build_task_result_payload()`, and forwarded through SSE done events. Missing one field can make the frontend believe a task succeeded while comments or styles were dropped.
- Safe modification: Any writeback change must update node state output, task result payload, SSE done payload, and tests together.
- Test coverage: Style payload coverage exists in `backend/tests/services/test_document_service_task_result.py`; route-level SSE done payload coverage is not detected.

**Protected-field parsing and paragraph boundary rules:**
- Files: `backend/config/tender_config.py`, `backend/helper/word_helper/protected_fields.py`, `backend/helper/word_helper/content_ops.py`, `backend/helper/word_helper/paragraph_boundary_ops.py`, `backend/helper/word_helper/text_parsing.py`, `backend/tests/nodes/test_protected_fields_strict_matching.py`
- Why fragile: The backend relies on strict Chinese-colon markers, field order, editable paragraph boundaries, and fail-fast behavior. Small parser changes can corrupt generated Word output.
- Safe modification: Keep profile selection in `backend/config/tender_config.py` and parsing helpers in `backend/helper/word_helper/`. Avoid reimplementing field scans inside nodes.
- Test coverage: Unit coverage exists for strict matching and helper behavior, but fixture coverage depends on fake Word objects instead of real `.doc/.docx` COM runs.

**GNGK subtype inheritance can hide missing specializations:**
- Files: `backend/graphs/gngk_hw_zc_tender_graph.py`, `backend/graphs/gngk_hw_cz_tender_graph.py`, `backend/graphs/gngk_fw_zc_tender_graph.py`, `backend/graphs/gngk_fw_cz_tender_graph.py`, `backend/nodes/gngk_word_nodes/__init__.py`, `backend/config/tender_config.py`
- Why fragile: `gngk_hw_cz` and `gngk_fw_cz` inherit the `gngk_hw_zc` workflow without overrides, while `gngk_fw_zc` overrides delete/replacement/update nodes. This is compact but makes subtype behavior easy to miss during new-type work.
- Safe modification: For every backend `gngk_*` change, explicitly review graph class inheritance, node overrides, anchor config, content mode, and protected-field profile.
- Test coverage: Registry and node route tests exist in `backend/tests/graphs/test_gngk_tender_graph.py`; end-to-end graph execution with realistic documents is not detected.

**Task heartbeat cancellation is aggressive:**
- Files: `backend/config/settings.py`, `backend/task/task_queue_manager.py`, `backend/api/tasks.py`, `backend/services/task_service.py`
- Why fragile: `TASK_HEARTBEAT_TIMEOUT` defaults to 15 seconds, and the cleanup thread cancels queued or running tasks when heartbeat age exceeds that threshold.
- Safe modification: Treat heartbeat behavior as a user-visible contract. Test browser reload, network hiccups, queued tasks, and long Word operations before changing timeout or heartbeat behavior.
- Test coverage: Task-kind preservation is tested in `backend/tests/services/test_task_service_task_kind.py`, but timeout cancellation behavior is not covered by route or integration tests.

## Scaling Limits

**Single-process task queue:**
- Current capacity: One active task is intended by `TaskQueueManager._current_task_id` and `CrossProcessFileLock`.
- Limit: Multiple backend processes or uvicorn workers do not share `_tasks`, `_queue`, callbacks, or conversation state.
- Scaling path: Use one backend worker for Word COM, or externalize queue state and route Word work to a dedicated single-consumer worker.

**Upload directory as shared local filesystem:**
- Current capacity: Files are persisted under `settings.UPLOAD_DIR`, defaulting to `D:/UploadFiles`.
- Limit: Local disk storage couples uploads, generated files, downloads, and template selections to one Windows machine.
- Scaling path: Add a file registry and retention policy before moving to shared storage. Do not expose raw filesystem paths in API contracts.

**SSE replay buffers are in memory:**
- Current capacity: `SSE_MAX_EVENTS_PER_TASK` defaults to 1000 events per task and `SSE_EVENT_TTL` is configured but cleanup is manual.
- Limit: Long LLM streams and many completed tasks increase memory usage.
- Scaling path: Coalesce old events, invoke `SSEManager.cleanup_task()`, or persist compact event state with TTL enforcement.

## Dependencies at Risk

**pywin32 / Microsoft Word COM:**
- Risk: Core document generation depends on Windows-only COM automation.
- Impact: Backend tests can run without COM for helper logic, but complete generate/rewrite/edit behavior requires Windows + Word.
- Migration plan: Keep COM-specific behavior isolated in `backend/util/word_util/`, `backend/nodes/common_word_nodes/`, `backend/nodes/gngk_word_nodes/`, `backend/nodes/gjgk_word_nodes/`, and `backend/nodes/xjcg_word_nodes/`. Use pure helper tests for business rules and explicit Windows COM smoke tests for integration.

**LangGraph API drift:**
- Risk: Graph construction uses `StateGraph`, list-based join edges, subgraph compilation, and async invocation while `backend/requirements.txt` allows any `langgraph>=0.2.0`.
- Impact: A fresh install can change graph compilation or execution semantics.
- Migration plan: Pin LangGraph in `backend/requirements.txt` or lock the environment, and keep graph-shape tests in `backend/tests/graphs/`.

**OpenAI-compatible SDK behavior:**
- Risk: LLM calls rely on `AsyncOpenAI.chat.completions.create(..., stream=True)` with provider-specific base URLs and extra params.
- Impact: SDK changes can alter timeout, streaming chunk shape, or error classes.
- Migration plan: Pin `openai` and keep `backend/tests/util/test_llm_stream_utils.py` focused on timeout, retry, and missing-env behavior.

## Missing Critical Features

**Backend route ownership model:**
- Problem: Task, stream, download, upload, generate, edit, and user routes lack a backend authorization/session ownership layer.
- Blocks: Safe multi-user deployment beyond a trusted local machine or tightly controlled intranet.

**Durable task and conversation recovery:**
- Problem: Active tasks and rewrite history are not durable across backend restart.
- Blocks: Reliable resume after process restart, multi-worker deployment, and auditable task history.

**File retention and cleanup policy for uploads/generated documents:**
- Problem: Uploads and generated outputs are persisted, but no backend retention job for `settings.UPLOAD_DIR` is detected.
- Blocks: Long-running production use where generated Word files accumulate on disk.

**Backend route-level contract tests for SSE/download/template APIs:**
- Problem: Tests cover many helper/node/service units, but no route-level tests are detected for `backend/api/stream.py`, `backend/api/download.py`, `backend/api/upload.py`, or `backend/api/template_candidates.py`.
- Blocks: Confident changes to task recovery, SSE replay, file download security, and template proxy behavior.

## Test Coverage Gaps

**SSE lifecycle and replay:**
- What's not tested: Connect, reconnect with `Last-Event-ID`, done/error stream termination, event deduplication, and cleanup.
- Files: `backend/api/stream.py`, `backend/core/sse_manager.py`
- Risk: Users can miss final task events, receive duplicate replay events, or leak event buffers.
- Priority: High

**Download path and file ownership:**
- What's not tested: Path traversal denial, download of unknown in-upload files, `download_name` behavior, and raw path exposure.
- Files: `backend/api/download.py`, `backend/util/common_util/upload_storage.py`
- Risk: Security regressions can expose files under `UPLOAD_DIR`.
- Priority: High

**Template candidate proxy and selection:**
- What's not tested: Host allowlist denial, redirect behavior, invalid year blocking, remote filename inference, partial slot failure, and large remote files.
- Files: `backend/api/template_candidates.py`, `backend/util/common_util/template_candidates.py`, `backend/services/template_candidate_ranking_service.py`
- Risk: SSRF, memory spikes, incorrect template selectability, or broken template popup behavior.
- Priority: High

**Task lifecycle race and completed generate status:**
- What's not tested: Final `Task.result` shape through `GET /api/generate/{task_id}`, double `complete_task()` behavior, cancellation after graph return, and heartbeat-timeout cancellation.
- Files: `backend/api/generate.py`, `backend/services/document_service.py`, `backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`, `backend/tests/api/test_generate_api.py`
- Risk: Completed tasks can return invalid responses or incomplete output metadata.
- Priority: High

**Upload streaming and validation:**
- What's not tested: Max-size enforcement without full memory buffering, extension spoofing, multiple-file partial failure details, and upload directory permission errors.
- Files: `backend/api/upload.py`, `backend/util/common_util/upload_storage.py`, `backend/main.py`
- Risk: Memory pressure and unsafe file ingestion.
- Priority: Medium

**Real Word COM integration smoke tests:**
- What's not tested: End-to-end Word automation on actual `.doc/.docx` files for generate, rewrite, edit, protected fields, style writeback, and comment writeback.
- Files: `backend/util/word_util/word_application_util.py`, `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`, `README.md`
- Risk: Fake-object unit tests can pass while real COM behavior fails on Windows Word.
- Priority: Medium

---

*Concerns audit: 2026-05-22*
