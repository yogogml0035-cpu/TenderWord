# 功能: 模板文件与批注生成链路收敛

下面这份计划应尽可能完整，但在真正开始实现前，仍然必须再次验证文档、代码库模式以及任务本身是否合理。

特别注意现有 utils、types、models 的命名，并确保从正确的文件中导入。

## 功能描述

将 TenderWord 初次生成链路从“模板文件 / 清洁稿 / 送审稿 / 技术参数文件”收敛为“模板文件 / 技术参数文件”。生成接口只接受 `file_paths.template` 和 `file_paths.tender_params`，后端 state 只以 `template_path` 表示模板源文件。批注生成不再依赖送审稿里提取的批注、删除线、非黑字计划，而统一由 `comment_prompt.py` 基于 `polished_text` 生成。`workflow` 走 `generate_comments`，`agent` 走后置 `comment_agent` 自主生成、校验、写回。模板候选选择也改为单文件回填。

## 用户故事

作为一名招标文件生成用户，我想只上传模板文件和技术参数文件，以便生成流程不再要求我理解送审稿、清洁稿等历史概念。

作为一名维护开发者，我想统一批注 prompt 和 graph 拓扑，以便新增招标类型或修改批注逻辑时只维护一个批注生成契约。

## 问题陈述

当前代码中存在多套历史概念：

- 前端类型和表单仍声明 `origin_tender`、`clean_draft`、`tender_params` 三类文件。
- 后端 `DocumentService._build_initial_state()` 同时写入 `origin_tender_path`、`source_origin_tender_path`、`clean_draft_path` 和 `template_path`。
- `prepare_template` 与 `extract_tender_params` 优先读取 `clean_draft_path` 或 `origin_tender_path`。
- `StandardTenderWorkflowGraph` 根据 `origin_tender_path` 启动 `get_comments`、`copy_comments`、`generate_comments` 条件分支。
- `comment_prompt.py` 仍要求批注计划、删除线计划、非黑字计划；`comment_agent` 另有 `comment_no_reference_prompt.py`。
- 模板候选选择 API 下载一次内容后保存到两个上传槽位，并返回 partial success。

这些分叉会放大新增类型、维护 prompt、调试批注失败和前端测试的成本。

## 方案陈述

采用一次性破坏性收敛，不保留旧字段兼容：

- 前端文件模型、draft、上传类型、converter 全部改成 `template` + `tender_params`。
- 后端请求模型和初始 state 只接收并写入 `template_path` + `tender_param_paths`。
- Word 节点按 `template_path` 准备工作副本，并从 `template_path` 提取模板参考正文。
- 标准生成 graph 删除送审稿提取分支；`workflow` 固定进入 `generate_comments`，`agent` 固定跳过 `generate_comments` 并在 `update_word` 后进入 `comment_agent`。
- `comment_prompt.py` 成为唯一批注生成 prompt；`comment_no_reference_prompt.py` 删除。
- 模板候选选择返回 `selected_file`，失败整体失败。
- 同步更新测试和 `asset/` 知识包。

## 功能元数据

**功能类型**: 重构 / 增强  
**预估复杂度**: 高  
**主要受影响系统**: 前端表单、前端 API 类型、会话 draft、后端生成 API、DocumentService、LangGraph、Word 节点、Prompt Layer、comment_agent、模板候选 API、知识包  
**依赖项**: 无新增外部依赖；继续依赖 Next.js、Jest、Playwright、FastAPI、LangGraph、pywin32、pytest

---

## 上下文参考

### 相关代码文件 重要：实现前必须先阅读这些文件

- `frontend/components/forms/TenderFormShared.tsx` (lines 49-64) - 当前表单数据仍有 `origin_tender`、`clean_draft`、`tender_params`。
- `frontend/components/forms/TenderFormShared.tsx` (lines 81-90) - 当前上传文案仍把模板文件设为可选，并说明回退到送审稿。
- `frontend/components/forms/TenderFormShared.tsx` (lines 670-678) - 当前本地 state 分别维护 `originFile` 和 `cleanDraftFile`。
- `frontend/components/forms/TenderFormShared.tsx` (lines 903-923) - 当前 draft 同步会写入 `origin_tender` 和 `clean_draft`。
- `frontend/components/forms/TenderFormShared.tsx` (lines 1538-1554) - 当前提交校验仍要求“清洁稿和送审稿至少要上传一个文件”。
- `frontend/components/forms/TenderFormShared.tsx` (lines 1570-1588) - 当前 submit formData 仍包含两个旧文件槽位。
- `frontend/components/forms/TenderFormShared.tsx` (lines 1722-1765) - 当前 UI 渲染两个 Word 模板类上传位和一个技术参数上传位。
- `frontend/components/forms/TemplateCandidateDialog.tsx` (lines 91-94) - 当前弹窗文案说明会回填发售稿和送审稿。
- `frontend/components/forms/TemplateCandidateDialog.tsx` (lines 231-242) - 当前候选下载链接仍使用“送审稿”命名。
- `frontend/types/api.ts` (lines 95-135) - 当前模板选择响应和 `FilesConfig` 仍使用 `selected_files`、`origin_tender`、`clean_draft`。
- `frontend/lib/formDataConverter.ts` (lines 57-69) - 当前 `buildFilesConfig` 会输出 `origin_tender` 和 `clean_draft`。
- `frontend/lib/formDataConverter.ts` (lines 112-132, 188-214, 220-242) - 三类表单 converter 都调用旧文件构造函数。
- `frontend/lib/api.ts` (lines 540-560) - 模板候选获取和选择仍走统一 API client，应同步响应类型。
- `frontend/lib/api.ts` (lines 576-587) - 上传 API 依赖 `FileType`，新增 `template` 类型后要同步。
- `frontend/components/chat/ChatPanel.tsx` (lines 332-350) - 编辑文件上传当前复用 `origin_tender` 类型，需与 generate 文件类型解耦。
- `frontend/stores/chatStore.ts` (lines 144-148) - 会话 draft 文件结构仍含 `origin_tender` 和 `clean_draft`。
- `frontend/stores/chatStore.ts` (lines 174-178) - store 仍过滤旧批注计划字段。
- `frontend/stores/chatStore.ts` (lines 301-320) - draft 合并和规范化仍处理两个旧文件槽位。
- `backend/models/generate.py` (lines 69-96) - `GenerateRequest.file_paths` 当前是宽泛 dict，说明里已有 template/params，但未强约束。
- `backend/services/document_service.py` (lines 931-1039) - 当前 `_build_initial_state()` 同时写入旧路径和 `template_path`。
- `backend/states/base_state.py` (lines 41-83) - 共享 state 仍包含旧模板路径、批注计划、复制批注结果字段。
- `backend/nodes/common_word_nodes/prepare_template.py` (lines 23-39) - 当前模板复制从 `clean_draft_path or origin_tender_path` 取源。
- `backend/nodes/common_word_nodes/extract_tender_params.py` (lines 50-86) - 当前模板正文提取从清洁稿或送审稿取源。
- `backend/nodes/common_word_nodes/extract_tender_params.py` (lines 259-307) - 当前输出仍写入旧“原始内容”字段，并附加技术参数内容。
- `backend/graphs/base_graph.py` (lines 513-538) - 当前节点数量估算随 `origin_tender_path` 决定批注分支。
- `backend/graphs/base_graph.py` (lines 540-646) - 当前标准生成图注册 `get_comments`、`copy_comments`、`comments_ready` 和双生成节点后的条件批注分支。
- `backend/graphs/base_graph.py` (lines 648-671) - 当前 `agent` 模式在 `update_word` 后进入 `comment_agent` 的后置分支可复用。
- `backend/graphs/xjcg_tender_graph.py` (lines 64-110) - 子类节点绑定仍导入并注册 `get_comments`、`copy_comments`、`generate_comments`。
- `backend/task/task_queue_manager.py` (lines 38-77) - 进度节点枚举和显示名仍包含“提取送审稿批注”“复制送审稿批注”。
- `backend/nodes/common_word_nodes/generate_comments.py` (lines 214-269) - 当前 `generate_comments` 读取三类旧计划字段并传给 prompt。
- `backend/prompts/comment_prompt.py` (lines 119-150, 188-210) - 当前用户 prompt 仍渲染批注计划、删除线计划、非黑字计划。
- `backend/prompts/comment_no_reference_prompt.py` (lines 1-80) - 当前无参考批注 prompt 是独立文件，需求要求删除。
- `backend/nodes/common_word_nodes/comment_agent.py` (lines 14-15, 203-321) - 当前节点导入 `comment_no_reference_prompt`，并只允许 `comment_supplement` 无候选时生成批注。
- `backend/agents/comments/comment_agent.py` (lines 34-103, 611-651) - comment_agent runner 已支持 `allow_comment_generation` 和生成模式 system prompt，可改为接收统一 prompt 指令。
- `backend/models/template_candidates.py` (lines 82-107) - 当前选择结果模型是双槽位、失败槽位和 partial success。
- `backend/api/template_candidates.py` (lines 221-299) - 当前选择 API 下载一次推荐模板后保存两份，并允许部分成功。

### 需要创建的新文件

- 一般不需要创建业务新文件。
- 如选择为 `GenerateRequest.file_paths` 建立显式模型，可在 `backend/models/generate.py` 中新增 `GenerateFilePaths` 类，不单独建文件。
- 如新增 prompt 测试，可创建 `backend/tests/prompts/test_comment_prompt.py` 或扩展现有 `backend/tests/nodes/test_generate_comments.py`，文件名必须以 `test_` 开头。

### 相关文档 实现前应该先阅读

- `AGENTS.md` - Word COM、SSE、Prompt Layer、测试命名、知识包回写红线。
- `asset/shared_runtime_word_skill_knowledge_pack.md` - Prompt Layer、批注/样式写回、Word COM、comment_agent 与任务结果/SSE 契约。
- `asset/tender_type_identity_session_knowledge_pack.md` - 类型 identity、graph/state/node 收敛、会话 draft 和 generation mode 草稿。
- `asset/template_candidate_pipeline_knowledge_pack.md` - 模板候选、下载代理、文件回填和弹窗链路。
- `backend/.planning/codebase/TESTING.md` - 后端测试命令与测试组织。
- `frontend/.planning/codebase/TESTING.md` - 前端 Jest、Playwright 和 mock 测试组织。

### 需要遵循的模式

**前端 API 模式：** 所有请求必须经 `frontend/lib/api.ts`，类型来自 `frontend/types/api.ts`。组件不得直接裸 `fetch`。

**前端表单模式：** `TenderFormShared` 是共享上传、draft、校验、submit 的核心；`gngk` 后端 form type 分派继续通过 `frontend/lib/gngkFormType.ts`。

**后端导入模式：** 后端跨包导入使用 `backend.*` 包绝对路径。当前 `prepare_template.py` 中 `from util.word_util` 是历史写法，触达时应顺手改为 `backend.util.word_util`。

**Graph 模式：** 标准生成图集中在 `StandardTenderWorkflowGraph`；各类型 graph 只绑定节点 callable，不复制拓扑。

**Prompt Layer 模式：** Prompt 纯渲染，不做日志、SSE、Word COM 或状态副作用。调用侧收集业务数据后调用 builder。

**Word COM 模式：** 所有 Word 操作必须走现有 graph 节点包装、锁、取消检查、进度追踪；不得在 API、service 或前端新增 COM 调用。

**测试模式：** 后端测试放 `backend/tests/<scope>/test_*.py`，前端单测放 `frontend/__tests__/unit/<scope>/test_*.test.ts(x)`，E2E 放 `frontend/e2e/test_*.spec.ts`。

---

## 实现计划

### 阶段 1：模板字段闭环

先完成前端和后端输入字段收敛，让生成任务的初始 state、模板复制和模板正文提取只依赖 `template_path`。

**任务：**

- 更新前端文件类型、draft、上传 UI、表单校验和 converter。
- 更新 `GenerateRequest.file_paths` 显式模型。
- 更新 `DocumentService._build_initial_state()`、`prepare_template`、`extract_tender_params`。
- 更新相关前后端单元测试。

### 阶段 2：Graph 删除送审稿分支

移除 `get_comments`、`copy_comments` 和送审稿条件分支，固定 workflow/agent 两条批注路径。

**任务：**

- 修改 `StandardTenderWorkflowGraph.build_graph()` 与 `estimate_total_nodes()`。
- 清理各类型 graph 的旧节点绑定和 imports。
- 清理任务进度节点显示名。
- 更新 graph 路由测试。

### 阶段 3：批注 prompt 与 agent 闭环

将 `comment_prompt.py` 改为唯一批注生成 prompt，`generate_comments` 与 `comment_agent` 共用它。

**任务：**

- 简化 `CommentPromptInput` 和 `comment_prompt.py`。
- 修改 `generate_comments` 输入。
- 修改 `comment_agent_writeback` 的 `allow_comment_generation` 判断和 prompt 指令来源。
- 删除 `comment_no_reference_prompt.py` 及导出引用。
- 更新 prompt、agent、节点、SSE 过程卡相关测试。

### 阶段 4：模板候选单文件回填

后端选择 API 改成单文件成功或整体失败，前端弹窗只回填模板文件。

**任务：**

- 更新后端 Pydantic model 和 API 实现。
- 更新前端 API 类型、弹窗文案和 `TenderFormShared` 回填逻辑。
- 更新 API client、表单和 E2E mock 数据。

### 阶段 5：清理、知识包与完整验证

删除旧字段、旧测试、旧文案和旧知识包描述，并跑完整相关验证。

**任务：**

- 用 `rg` 清理旧关键词。
- 更新三个知识包和 `asset/README.md`。
- 跑后端、前端、E2E 相关测试。
- 在 Windows + Word COM 环境做生成冒烟验证。

---

## 分步任务

重要：严格按顺序执行所有任务，从上到下。每个任务都必须是原子性的，并且可独立测试。

### UPDATE frontend/types/api.ts

- **IMPLEMENT**: 将 `TemplateSelectResponse` 改为单文件结构，例如 `{ selected_file: TemplateSelectedFile }`；删除 `TemplateSelectedFiles`、`TemplateSelectFailure`、`failed_slots`、`partial_success`。
- **IMPLEMENT**: 将 `FileType` 改为包含 `template`、`params`、必要的 edit 专用类型；删除 generate 使用的 `origin_tender`、`clean_draft`。
- **IMPLEMENT**: 将 `FilesConfig` 改为 `{ template: string; tender_params: string[] }`。
- **PATTERN**: `frontend/types/api.ts:95-135` 当前集中定义上传、模板选择和生成文件类型。
- **GOTCHA**: 如果 edit 上传仍需要文件类型，不要复用 generate 的 `template` 语义，需用单独明确类型或不传 file_type。
- **VALIDATE**: `cd frontend; npm run type-check`

### UPDATE frontend/components/forms/TenderFormShared.tsx

- **IMPLEMENT**: 将 `BaseTenderFormData.files` 改为 `{ template?: UploadedFile; tender_params: UploadedFile[] }`。
- **IMPLEMENT**: 用单个 `templateFile` state 取代 `originFile` 和 `cleanDraftFile`。
- **IMPLEMENT**: `syncDraftFiles` 只写 `template` 和 `tender_params`。
- **IMPLEMENT**: 提交校验改为 `if (!templateFile) setError('请上传模板文件')`。
- **IMPLEMENT**: 上传区只渲染一个 label 为“模板文件（必填）”的 Word 上传位，`fileType="template"`。
- **IMPLEMENT**: 提交 formData 只包含 `template` 和 `tender_params`。
- **IMPLEMENT**: 模板候选选择成功后只回填 `templateFile`。
- **PATTERN**: `frontend/components/forms/TenderFormShared.tsx:1538-1554` 是当前 submit 校验入口；`1722-1765` 是当前上传 UI。
- **GOTCHA**: 不要改变 `TenderFormShared` 的初始化优先级 `draft > URL > default`。
- **VALIDATE**: `cd frontend; npm test -- --runInBand __tests__/unit/components/forms/test_tender_form_shared.test.tsx`

### UPDATE frontend/lib/formDataConverter.ts

- **IMPLEMENT**: 将 `buildFilesConfig` 参数改为 `template` 和 `tenderParams`。
- **IMPLEMENT**: 三类 converter 输出 `file_paths: { template: template.file_path, tender_params: [...] }`。
- **IMPLEMENT**: 删除注释示例中的 `origin_tender_path`、`clean_draft_path`。
- **PATTERN**: `frontend/lib/formDataConverter.ts:112-242` 覆盖 xjcg、gngk、gjgk 三类请求。
- **GOTCHA**: `gngk` 的 `form_type` 分派继续调用 `resolveGngkFormType`，不得顺手改类型 identity。
- **VALIDATE**: `cd frontend; npm test -- --runInBand __tests__/unit/lib/test_form_data_converter.test.ts`

### UPDATE frontend/stores/chatStore.ts and frontend/components/chat/ChatPanel.tsx

- **IMPLEMENT**: draft `files` 结构删除 `origin_tender`、`clean_draft`，改为 `template`。
- **IMPLEMENT**: draft merge 和 normalize 逻辑只保留 `template` 与 `tender_params`。
- **IMPLEMENT**: 删除 `REWRITE_STATE_DETAIL_METADATA_KEYS` 中已经不存在的送审稿计划字段，或确认这些字段仅属于 rewrite 历史且仍有真实来源；本需求目标是清理活跃生成链路引用。
- **IMPLEMENT**: `ChatPanel` 的 edit 文件上传不再调用 `uploadFile(file, 'origin_tender')`。
- **PATTERN**: `frontend/stores/chatStore.ts:301-320` 是 draft 文件规范化入口；`frontend/components/chat/ChatPanel.tsx:341` 是 edit 上传旧类型使用点。
- **GOTCHA**: 不要破坏 `pending_rewrite_prompt`、`pending_edit_prompt` 的恢复语义。
- **VALIDATE**: `cd frontend; npm test -- --runInBand __tests__/unit/stores __tests__/unit/components/chat`

### UPDATE frontend/components/forms/TemplateCandidateDialog.tsx and frontend/lib/api.ts

- **IMPLEMENT**: 弹窗文案改为“从ERP模板库中选择适合模板，选择后回填模板文件。”。
- **IMPLEMENT**: 候选下载展示名称改为“模板文件”或项目名模板，不再拼接“送审稿”。
- **IMPLEMENT**: `selectTemplateCandidate` 返回单文件响应类型。
- **PATTERN**: `frontend/components/forms/TemplateCandidateDialog.tsx:91-94` 是提示文案；`frontend/lib/api.ts:540-560` 是 API client。
- **GOTCHA**: 下载代理 URL 仍必须通过 `getTemplateCandidateDownloadUrl`，不要绕过后端代理。
- **VALIDATE**: `cd frontend; npm test -- --runInBand __tests__/unit/lib/test_api.test.ts __tests__/unit/components/forms/test_tender_form_shared.test.tsx`

### UPDATE backend/models/generate.py

- **IMPLEMENT**: 新增显式 `GenerateFilePaths` Pydantic 模型，字段为 `template: str` 和 `tender_params: List[str]`。
- **IMPLEMENT**: `template` 必须非空；`tender_params` 至少一个非空路径。
- **IMPLEMENT**: `GenerateRequest.file_paths` 类型改为 `GenerateFilePaths`。
- **PATTERN**: `backend/models/generate.py:69-96` 是当前请求模型入口。
- **GOTCHA**: 如果后续代码仍以 dict 访问，需同步改为属性访问或 `model_dump()`，避免运行时错误。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/api tests/models -v`

### UPDATE backend/services/document_service.py

- **IMPLEMENT**: `_build_initial_state()` 从 `request.file_paths.template` 写入 `state["template_path"]`。
- **IMPLEMENT**: 从 `request.file_paths.tender_params` 写入 `state["tender_param_paths"]`。
- **REMOVE**: 删除生成链路中的 `origin_tender_path`、`source_origin_tender_path`、`clean_draft_path` 写入。
- **PATTERN**: `backend/services/document_service.py:1010-1038` 是当前旧字段写入位置。
- **GOTCHA**: rewrite/edit/comment_supplement 可能仍有独立 state 字段，清理时只删除初次 generate 旧字段；如果字段名跨链路共用，必须同步相关测试。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/services/test_document_service_initial_state.py -v`

### UPDATE backend/states/base_state.py and related state types

- **IMPLEMENT**: 在 `TenderGraphStateBase` 中用 `template_path` 表示源模板文件。
- **IMPLEMENT**: 将模板参考正文输出字段统一命名为 `template_reference_text` 或项目内最终选定的等价名称，避免继续使用 `origin_tender_params`。
- **REMOVE**: 删除 `origin_tender_path`、`clean_draft_path`、`comment_plan_detail`、`strikethrough_plan`、`non_black_font_plan`、`copy_comments_*` 等初次生成旧契约。
- **PATTERN**: `backend/states/base_state.py:41-83` 是共享 state 字段真源。
- **GOTCHA**: 如果改名 `origin_tender_params`，必须同步 `backend/prompts/types.py`、`generate_by_template_prompt.py`、`generate_by_param_prompt.py`、`backend/agents/generation/*` 和相关测试。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/prompts tests/agents/test_generation_content_agent.py -v`

### UPDATE backend/nodes/common_word_nodes/prepare_template.py

- **IMPLEMENT**: 只读取 `state.get("template_path")`。
- **IMPLEMENT**: 错误信息改为“请上传模板文件”或后端等价明确描述。
- **IMPLEMENT**: 顺手将 `from util.word_util` 改为 `from backend.util.word_util`。
- **PATTERN**: `backend/nodes/common_word_nodes/prepare_template.py:30-39` 是旧源路径选择逻辑。
- **GOTCHA**: 继续保留工作副本命名、重试删除和 Word 资源清理逻辑。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/nodes -k prepare_template -v`

### UPDATE backend/nodes/common_word_nodes/extract_tender_params.py

- **IMPLEMENT**: 只读取 `template_path` 作为模板参考正文提取源。
- **IMPLEMENT**: 输出字段改为模板参考正文新命名；技术参数继续输出 `tender_params`。
- **IMPLEMENT**: 用户态进度文案改为“开始提取模板参考正文”和“开始提取技术参数文件”。
- **PATTERN**: `backend/nodes/common_word_nodes/extract_tender_params.py:73-86` 是旧源路径选择逻辑；`271-300` 是多技术参数文件拼接逻辑。
- **GOTCHA**: 当前节点会打开 Word 提取锚点范围，仍必须通过现有 Word COM 生命周期工具。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/nodes/test_extract_tender_params_inline_style.py -v`

### UPDATE backend/graphs/base_graph.py

- **IMPLEMENT**: `estimate_total_nodes()` 不再检查 `origin_tender_path`；workflow 固定包含 `generate_comments`，agent 固定包含 `comment_agent`。
- **IMPLEMENT**: `build_graph()` 删除 `get_comments`、`copy_comments`、`comments_ready` 注册和条件边。
- **IMPLEMENT**: `NODE_GENERATE_POLISHED_TEXT -> generate_comments -> comments_branch_done/update_word`。
- **IMPLEMENT**: `NODE_CONTENT_AGENT -> comments_branch_done/update_word`，不得进入 `generate_comments`。
- **IMPLEMENT**: `update_word -> comment_agent` 仅 agent 模式保留。
- **PATTERN**: `backend/graphs/base_graph.py:579-646` 是当前拓扑集中点。
- **GOTCHA**: `word_operations_subgraph` 和生成节点之间已有并发汇合屏障，修改边时必须保持 `update_word` 等待正文、Word 操作、批注准备都完成。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/graphs/test_generation_mode_branching.py tests/graphs/test_generation_mode_workflow.py -v`

### UPDATE backend/graphs/*_tender_graph.py

- **IMPLEMENT**: 删除各类型 graph 对 `get_comments`、`copy_comments` 的 imports 和 `NODE_GET_COMMENTS`、`NODE_COPY_COMMENTS` 绑定。
- **IMPLEMENT**: 保留 `NODE_GENERATE_COMMENTS` 供 workflow 使用，保留 `NODE_COMMENT_AGENT` 默认绑定供 agent 使用。
- **PATTERN**: `backend/graphs/xjcg_tender_graph.py:64-110` 是典型子类绑定；`gngk_hw_zc_tender_graph.py`、`gjgk_tender_graph.py` 同样需要同步。
- **GOTCHA**: 不要复制拓扑到子类；拓扑仍由 `StandardTenderWorkflowGraph` 统一控制。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/graphs -v`

### UPDATE backend/task/task_queue_manager.py

- **IMPLEMENT**: 删除 `GET_COMMENTS`、`COPY_COMMENTS` 节点枚举或至少从生成流程显示名中移除。
- **IMPLEMENT**: 更新 `PREPARE_TEMPLATE`、`EXTRACT_TENDER_PARAMS` 显示文案，避免“原始模板 / 原始采购需求”含混或旧送审稿含义。
- **PATTERN**: `backend/task/task_queue_manager.py:38-77` 是节点枚举和用户态显示名。
- **GOTCHA**: 如果历史任务状态仍可能包含旧节点名，不需要为旧会话兼容；需求明确不保留旧会话兼容。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/progress tests/services -v`

### UPDATE backend/prompts/types.py and backend/prompts/comment_prompt.py

- **IMPLEMENT**: `CommentPromptInput` 只保留 `tender_type`、`polished_text`。
- **IMPLEMENT**: `COMMENT_USER_PROMPT` 删除批注计划、删除线计划、非黑字计划输入块。
- **IMPLEMENT**: 系统 prompt 中删除“历史参考逻辑优先匹配”这类依赖旧计划的语义，保留三维合规、公平、严谨审核逻辑和 JSON 输出契约。
- **IMPLEMENT**: `render_comment_prompt()` 只格式化 `polished_text`。
- **PATTERN**: `backend/prompts/comment_prompt.py:119-150` 是用户 prompt；`188-210` 是渲染入口。
- **GOTCHA**: `get_tender_type_family()` 仍是招标类型 family 真源，不能绕过。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/prompts tests/nodes/test_generate_comments.py -v`

### UPDATE backend/nodes/common_word_nodes/generate_comments.py

- **IMPLEMENT**: 删除读取 `comment_plan_detail`、`strikethrough_plan`、`non_black_font_plan`。
- **IMPLEMENT**: 调用 `render_comment_prompt(CommentPromptInput(tender_type=..., polished_text=...))`。
- **IMPLEMENT**: 保留 JSON 提取、修复、`polished_comments`、`generated_comment_count` 和 prompt log 输出。
- **PATTERN**: `backend/nodes/common_word_nodes/generate_comments.py:250-269` 是旧 prompt input 构造。
- **GOTCHA**: 不要把完整批注 LLM 输出推到用户态 SSE；当前 `_push_stream_update` 禁止外传，应保持。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/nodes/test_generate_comments.py -v`

### UPDATE backend/nodes/common_word_nodes/comment_agent.py

- **IMPLEMENT**: 删除 `render_comment_no_reference_prompt` 和 `CommentNoReferencePromptInput` 导入。
- **IMPLEMENT**: `allow_comment_generation` 改为 `(task_kind == "comment_supplement" or generation_mode == "agent") and not comments`。
- **IMPLEMENT**: 自主生成批注时使用 `render_comment_prompt(CommentPromptInput(tender_type=tender_type, polished_text=...))` 的 system + user prompt 作为 `comment_generation_instruction`。
- **PATTERN**: `backend/nodes/common_word_nodes/comment_agent.py:203-321` 是当前自主生成和 agent 调用入口。
- **GOTCHA**: `comment_agent` 写回失败仍应降级 warning，不得因批注失败让正文成功的生成任务整体失败。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/nodes/test_comment_agent_writeback_node.py tests/agents/test_comment_agent.py -v`

### DELETE backend/prompts/comment_no_reference_prompt.py and exports

- **REMOVE**: 删除 `backend/prompts/comment_no_reference_prompt.py`。
- **REMOVE**: 删除 `backend/prompts/__init__.py` 中 `COMMENT_NO_REFERENCE_*`、`CommentNoReferencePromptInput` 和 `render_comment_no_reference_prompt` 导出。
- **REMOVE**: 删除或改写所有测试引用。
- **PATTERN**: `backend/prompts/__init__.py:3-14` 当前导出两个批注 prompt。
- **GOTCHA**: 删除后运行 `rg "comment_no_reference|CommentNoReference"` 确保无引用。
- **VALIDATE**: `rg "comment_no_reference|CommentNoReference" backend frontend`

### UPDATE backend/models/template_candidates.py and backend/api/template_candidates.py

- **IMPLEMENT**: 将选择响应模型改为 `TemplateSelectData(selected_file: TemplateSelectedFile)` 或等价单文件结构。
- **IMPLEMENT**: 删除 `TemplateSelectedFiles`、`TemplateSelectFailure`、`failed_slots`、`partial_success`。
- **IMPLEMENT**: `select_template_candidate()` 只下载 `candidate.shener` 一次并持久化一次。
- **IMPLEMENT**: 缺少链接、下载失败、保存失败都整体抛出 `TEMPLATE_SELECT_FAILED`。
- **PATTERN**: `backend/api/template_candidates.py:221-299` 是当前双槽位保存和 partial success 逻辑。
- **GOTCHA**: 保留 `derive_template_blocked_reason()` 对 `year < 2025` 和非法年份的阻断语义。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/api -k template_candidate -v`

### UPDATE frontend tests and mocks

- **IMPLEMENT**: 更新 `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx` 中上传位、校验错误、模板候选单文件回填断言。
- **IMPLEMENT**: 更新 `frontend/__tests__/unit/lib/test_api.test.ts` 中模板候选选择响应 fixture。
- **IMPLEMENT**: 更新 `frontend/__tests__/unit/lib/test_form_data_converter.test.ts` 中 payload 断言。
- **IMPLEMENT**: 更新 `frontend/e2e/test_generation_mode_agent.spec.ts` 和 `frontend/e2e/test_comment_supplement.spec.ts` 的 mock 请求 / 响应。
- **GOTCHA**: Playwright locator 使用 role、accessible name 或 `data-testid`，不要使用宽泛 `getByText()` 断言重复文案。
- **VALIDATE**: `cd frontend; npm test -- --runInBand __tests__/unit/lib/test_api.test.ts __tests__/unit/lib/test_form_data_converter.test.ts __tests__/unit/components/forms/test_tender_form_shared.test.tsx`

### UPDATE backend tests

- **IMPLEMENT**: 更新 `backend/tests/services/test_document_service_initial_state.py`，断言 state 只含 `template_path` 和 `tender_param_paths`。
- **IMPLEMENT**: 更新 `backend/tests/graphs/test_generation_mode_branching.py`，断言 workflow 进入 `generate_comments`，agent 跳过 `generate_comments` 并进入 `comment_agent`。
- **IMPLEMENT**: 更新各类型 `test_*_generation_mode_agent.py`，移除 `origin_tender_path` fixture。
- **IMPLEMENT**: 更新 `backend/tests/nodes/test_generate_comments.py`，断言 prompt input 不含旧计划字段。
- **IMPLEMENT**: 更新 `backend/tests/agents/test_comment_agent.py` 和 `backend/tests/nodes/test_comment_agent_writeback_node.py`，覆盖 agent generate 无候选自主生成。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests/graphs tests/services/test_document_service_initial_state.py tests/nodes/test_generate_comments.py tests/nodes/test_comment_agent_writeback_node.py tests/agents/test_comment_agent.py -v`

### UPDATE asset knowledge packs

- **IMPLEMENT**: 更新 `asset/shared_runtime_word_skill_knowledge_pack.md`，写明统一批注 prompt、workflow/agent/comment_supplement 批注链路、删除无参考 prompt 和送审稿计划契约。
- **IMPLEMENT**: 更新 `asset/tender_type_identity_session_knowledge_pack.md`，写明全类型生成输入只使用模板文件和技术参数文件、draft 文件结构改为 `template`。
- **IMPLEMENT**: 更新 `asset/template_candidate_pipeline_knowledge_pack.md`，写明模板候选选择单文件回填和整体失败。
- **IMPLEMENT**: 更新 `asset/README.md` 的适用范围描述。
- **VALIDATE**: `rg "送审稿|origin_tender|clean_draft|comment_plan_detail|strikethrough_plan|non_black_font_plan|copy_comments" asset`

### RUN final regression search

- **IMPLEMENT**: 执行旧关键词搜索，逐条判断是否为必要历史说明。
- **VALIDATE**: `rg "送审稿|origin_tender|clean_draft|comment_plan_detail|strikethrough_plan|non_black_font_plan|copy_comments" frontend backend asset tasks/template-comment-generation-convergence`

---

## 测试策略

### 单元测试

- 前端表单：`frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx` 覆盖上传位、必填校验、draft、模板候选回填。
- 前端 converter：`frontend/__tests__/unit/lib/test_form_data_converter.test.ts` 覆盖 xjcg、gngk、gjgk payload。
- 前端 API：`frontend/__tests__/unit/lib/test_api.test.ts` 覆盖模板候选单文件响应。
- 后端 service：`backend/tests/services/test_document_service_initial_state.py` 覆盖 `template_path` 初始 state。
- 后端 graph：`backend/tests/graphs/` 覆盖 workflow/agent 拓扑。
- 后端 prompt/node：`backend/tests/nodes/test_generate_comments.py` 和 prompt 测试覆盖统一 prompt。
- 后端 agent：`backend/tests/agents/test_comment_agent.py`、`backend/tests/nodes/test_comment_agent_writeback_node.py` 覆盖无候选自主生成和写回降级。
- 后端模板候选 API：新增或更新 `backend/tests/api/test_template_candidates.py`。

### 集成测试

- 后端 graph + service 组合测试确认生成任务进入预期节点顺序。
- 前端表单 + API mock 测试确认提交 payload 与模板候选回填一致。
- SSE / agent_step 测试确认 agent generate 后置 `comment_agent` 过程卡仍渲染，workflow generate 不渲染 `comment_agent` 过程卡。

### 边界情况

- 未上传模板文件。
- 未上传技术参数文件。
- 技术参数文件列表包含空路径或不存在路径。
- 模板候选年份小于 2025。
- 模板候选缺少推荐模板链接。
- 模板候选下载成功但保存失败。
- `workflow` 下 `generate_comments` 返回空数组。
- `agent` 下 `comment_agent` 无候选但可自主生成。
- `comment_agent` 写回失败时正文生成任务仍可完成并记录 warning。
- 模板文件自带 Word 批注不主动提取、不复制、不清空。

---

## 验证命令

执行所有命令，确保零回归与功能正确。

### 级别 1：语法与风格

```powershell
cd frontend
npm run lint
npm run type-check
```

```powershell
git diff --check
```

### 级别 2：前端单元测试

```powershell
cd frontend
npm test -- --runInBand __tests__/unit/lib/test_form_data_converter.test.ts __tests__/unit/lib/test_api.test.ts __tests__/unit/components/forms/test_tender_form_shared.test.tsx
```

### 级别 3：后端单元与 graph 测试

```powershell
cd backend
.\\.venv\\Scripts\\python.exe -m pytest tests/services/test_document_service_initial_state.py tests/graphs tests/nodes/test_generate_comments.py tests/nodes/test_comment_agent_writeback_node.py tests/agents/test_comment_agent.py -v
```

### 级别 4：E2E / mock 流程

```powershell
cd frontend
npm run test:e2e
```

### 级别 5：完整回归

```powershell
cd backend
.\\.venv\\Scripts\\python.exe -m pytest tests -v
```

```powershell
cd frontend
npm run test
```

### 级别 6：旧契约搜索

```powershell
rg "送审稿|origin_tender|clean_draft|comment_plan_detail|strikethrough_plan|non_black_font_plan|copy_comments" frontend backend asset
```

### 级别 7：Windows + Word COM 冒烟

在 Windows + Word COM 可用环境中启动后端和前端，使用模板文件 + 技术参数文件创建一次 `xjcg`、至少一个 `gngk` 子类型和 `gjgk` 的生成任务，确认任务完成、SSE 终态正常、下载入口可用。

---

## 验收标准

- [ ] 功能实现了所有指定需求。
- [ ] 前端生成 payload 只包含 `file_paths.template` 和 `file_paths.tender_params`。
- [ ] 后端生成初始 state 只包含模板源路径和技术参数路径。
- [ ] 标准生成图无 `get_comments` 和 `copy_comments` 分支。
- [ ] `workflow` 调用 `generate_comments`，`agent` 跳过 `generate_comments` 并调用 `comment_agent`。
- [ ] `comment_prompt.py` 是唯一批注生成 prompt 真源。
- [ ] `comment_no_reference_prompt.py` 已删除且无引用。
- [ ] 模板候选选择返回单文件，失败整体失败。
- [ ] 三个知识包和索引已更新。
- [ ] 相关后端、前端、E2E 验证通过。
- [ ] 旧关键词搜索只剩必要历史说明或已更新文案。

---

## 完成检查清单

- [ ] 所有任务均已按顺序完成。
- [ ] 每个任务的验证都已立即通过。
- [ ] 所有验证命令都已成功执行。
- [ ] 完整测试套件通过。
- [ ] 无 lint 或类型检查错误。
- [ ] 手动 Windows + Word COM 冒烟确认功能可用。
- [ ] 验收标准全部满足。
- [ ] 已完成代码质量与可维护性审查。

---

## 备注

- 本需求明确不保留旧会话、旧 API 字段或旧请求兼容，因此不需要写兼容 shim。
- 改动面较大，建议按阶段提交和验证，但不要让中间阶段长时间停留在新旧字段并存状态。
- 首次执行成功信心分数：7/10。主要风险在 state 字段改名影响 Prompt Layer、content_agent、rewrite/edit 旁路引用，以及 graph 并发汇合边修改后的节点顺序测试。
