# PRD: 模板文件与批注生成链路收敛

## 1. 介绍 / 概述

当前 TenderWord 的初次生成链路仍同时存在“模板文件 / 清洁稿 / 送审稿”多套概念，批注生成又依赖送审稿中提取的批注、删除线、非黑字计划。该需求将全类型生成入口收敛到“模板文件 + 技术参数文件”两类必填输入，并将批注生成统一到 `comment_prompt.py` 与 `comment_agent`，减少跨前后端字段分叉和旧送审稿分支带来的维护成本。

## 2. 目标

- 所有初次生成类型只接受 `file_paths.template` 和 `file_paths.tender_params`。
- 前端表单只展示“模板文件（必填）”和“技术参数文件（必填）”，提交错误提示明确。
- 后端 state、模板复制、模板正文提取全部以 `template_path` 为真源。
- 标准生成 graph 删除送审稿批注提取与复制分支。
- `workflow` 生成由 `generate_comments` 基于 `polished_text` 生成批注候选。
- `agent` 生成由 `comment_agent` 自主生成、校验、写回批注，不进入 `generate_comments`。
- 模板候选选择接口和前端弹窗统一为单文件回填。
- 长期知识包、测试和回归搜索同步完成。

## 3. 用户故事

### US-001: 前端表单统一为模板文件上传

**描述：** 作为生成任务用户，我想只看到“模板文件”和“技术参数文件”两个必填上传入口，以便不用理解送审稿、清洁稿等历史概念。

**验收标准：**
- [ ] `TenderFormShared` 文件上传区只渲染“模板文件（必填）”和“技术参数文件（必填）”。
- [ ] 页面不再出现“送审稿文件（可选）”“清洁稿和送审稿至少要上传一个文件”“模板文件（可选）”等旧文案。
- [ ] 未上传模板文件点击提交时阻止提交，并展示“请上传模板文件”。
- [ ] 未上传技术参数文件点击提交时阻止提交，并展示“请上传至少一个技术参数文件”。
- [ ] 表单 draft 中 `files` 只保留 `template` 和 `tender_params`。
- [ ] 使用 Playwright 打开 `/tender`，在 mock 后端数据下确认上传区只出现两个必填上传位，缺少模板文件时显示“请上传模板文件”，页面无 console error。
- [ ] `npm run lint`、`npm run type-check` 和相关 Jest 表单测试通过。

### US-002: 前端生成请求收敛为 template payload

**描述：** 作为开发者，我想让所有前端生成请求只发送 `file_paths.template` 与 `file_paths.tender_params`，以便后端不再兼容旧上传槽位。

**验收标准：**
- [ ] `frontend/types/api.ts` 中 `FileType` 支持 `template`，不再包含 `origin_tender`、`clean_draft`。
- [ ] `FilesConfig` 类型收敛为 `{ template: string; tender_params: string[] }`。
- [ ] `convertXjcgFormToApiRequest`、`convertGngkFormToApiRequest`、`convertGjgkFormToApiRequest` 输出的 `file_paths` 只包含 `template` 和 `tender_params`。
- [ ] `ChatPanel` 的编辑文件上传不再复用 `origin_tender` 上传类型；如编辑链路仍需文件分类，应使用与 generate 解耦的明确类型。
- [ ] `frontend/__tests__/unit/lib/test_form_data_converter.test.ts` 覆盖三类表单的 payload，断言不含 `origin_tender` 和 `clean_draft`。
- [ ] `npm run type-check` 和相关 API client 测试通过。

### US-003: 后端生成接口和初始 state 使用 template_path

**描述：** 作为后端生成链路维护者，我想让 `GenerateRequest` 与 graph 初始 state 只使用模板文件路径，以便生成入口字段和运行态字段一致。

**验收标准：**
- [ ] `GenerateRequest.file_paths` 接受且要求 `{ template: string, tender_params: string[] }`。
- [ ] 缺少 `template` 时，后端生成任务创建返回明确错误，不进入 graph。
- [ ] `DocumentService._build_initial_state()` 只写入 `template_path` 和 `tender_param_paths`，不写入 `origin_tender_path`、`clean_draft_path`、`source_origin_tender_path`。
- [ ] `prepare_template` 只从 `template_path` 复制工作副本，错误信息不再提及清洁稿或送审稿。
- [ ] `extract_tender_params` 从 `template_path` 提取模板参考正文，从 `tender_param_paths` 提取技术参数正文。
- [ ] `backend/tests/services/test_document_service_initial_state.py` 和相关节点测试覆盖缺少模板、模板存在、多技术参数文件三种路径。
- [ ] `python -m pytest tests/services/test_document_service_initial_state.py tests/nodes/test_extract_tender_params_inline_style.py -v` 通过。

### US-004: 标准生成 graph 删除送审稿批注分支

**描述：** 作为 graph 维护者，我想移除 `get_comments` 和 `copy_comments` 分支，以便标准生成图的批注链路只由生成后的正文驱动。

**验收标准：**
- [ ] `StandardTenderWorkflowGraph` 不再注册 `get_comments`、`copy_comments`、`comments_ready` 或基于送审稿路径的条件分支。
- [ ] `workflow` 分支执行顺序为 `prepare_template -> extract_tender_params -> word_operations_subgraph + generate_polished_text -> generate_comments -> update_word`。
- [ ] `agent` 分支执行顺序为 `prepare_template -> extract_tender_params -> word_operations_subgraph + content_agent -> update_word -> comment_agent`。
- [ ] `content_agent` 分支不进入 `generate_comments`。
- [ ] `estimate_total_nodes()` 的节点数不再随模板文件是否存在而变化，只随 `generation_mode` 和类型特化步骤变化。
- [ ] `backend/tests/graphs/test_generation_mode_branching.py`、`test_generation_mode_workflow.py` 和各类型 `test_*_generation_mode_agent.py` 覆盖新拓扑。
- [ ] 相关 graph 测试通过。

### US-005: generate_comments 统一基于 comment_prompt.py

**描述：** 作为批注生成维护者，我想让 `generate_comments` 只基于 `polished_text` 调用通用批注 prompt，以便不再依赖送审稿提取出的历史计划。

**验收标准：**
- [ ] `CommentPromptInput` 只保留 `tender_type` 和 `polished_text` 等当前正文必要输入。
- [ ] `comment_prompt.py` 用户 prompt 不再包含 `comment_plan_detail`、`strikethrough_plan`、`non_black_font_plan`。
- [ ] `generate_comments` 不读取批注计划字段，只传入 `polished_text` 调用 `render_comment_prompt`。
- [ ] JSON 数组解析、修复和 `polished_comments` 输出契约保持不变。
- [ ] `backend/tests/nodes/test_generate_comments.py` 和 prompt 测试覆盖“无计划字段也能生成 / 空数组可解析 / 锚点必须来自正文”。
- [ ] 相关 prompt 和节点测试通过。

### US-006: comment_agent 复用同一批注 prompt 自主生成批注

**描述：** 作为 agent 生成链路维护者，我想让 `comment_agent` 在 agent generate 和 comment_supplement 中使用同一批注 prompt 自主生成批注，以便三条批注入口规则一致。

**验收标准：**
- [ ] `comment_agent` 在 `generation_mode=agent` 的 generate 任务且无 `polished_comments` 时允许自主生成批注。
- [ ] `comment_supplement` 继续允许无候选时由 `comment_agent` 自主生成批注。
- [ ] `comment_agent` 自主生成批注时复用 `comment_prompt.py` 的渲染结果，不再导入 `comment_no_reference_prompt.py`。
- [ ] 删除 `comment_no_reference_prompt.py` 及其 `backend/prompts/__init__.py` 导出。
- [ ] `backend/tests/agents/test_comment_agent.py`、`backend/tests/nodes/test_comment_agent_writeback_node.py` 覆盖 agent generate 和 comment_supplement 的无候选自主生成。
- [ ] 相关 agent、节点、SSE 过程卡测试通过。

### US-007: 模板候选选择改为单文件回填

**描述：** 作为表单用户，我想从模板候选弹窗选择一个模板后只回填模板文件，以便选择行为和生成表单一致。

**验收标准：**
- [ ] `backend/models/template_candidates.py` 的选择结果改为 `selected_file` 单文件字段。
- [ ] `backend/api/template_candidates.py` 选择候选时只下载并保存一次推荐模板文件。
- [ ] 选择失败时整体失败，不再返回 `failed_slots` 或 `partial_success`。
- [ ] `frontend/types/api.ts` 与 `frontend/lib/api.ts` 同步单文件响应类型。
- [ ] `TemplateCandidateDialog` 文案改为“选择后回填模板文件”。
- [ ] `TenderFormShared` 选择模板后只设置 `template` 上传位。
- [ ] 后端 API 测试、前端 API client 测试和弹窗表单测试覆盖成功与整体失败。

### US-008: 清理旧送审稿契约和知识包

**描述：** 作为长期维护者，我想删除旧字段、旧节点和旧知识包描述，以便后续开发不会继续沿用历史分叉。

**验收标准：**
- [ ] 删除或停用 `backend/nodes/common_word_nodes/get_comments.py`、`copy_comments.py` 的标准生成引用；如文件完全无引用则删除。
- [ ] 清理 state、store、SSE 结果过滤和测试中的 `comment_plan_detail`、`strikethrough_plan`、`non_black_font_plan`、`copy_comments_*`。
- [ ] 更新 `asset/shared_runtime_word_skill_knowledge_pack.md`、`asset/tender_type_identity_session_knowledge_pack.md`、`asset/template_candidate_pipeline_knowledge_pack.md` 和 `asset/README.md`。
- [ ] `rg "送审稿|origin_tender|clean_draft|comment_plan_detail|strikethrough_plan|non_black_font_plan|copy_comments"` 只剩必要历史说明或已更新文案。
- [ ] 文档中引用的代码路径、测试路径和命令真实存在。

### US-009: 全链路回归验证

**描述：** 作为交付负责人，我想通过单元、集成和 mock E2E 证明模板文件与批注链路收敛没有破坏生成、候选回填和补充批注流程。

**验收标准：**
- [ ] 后端相关 graph、service、node、prompt、API 测试通过。
- [ ] 前端 `npm run lint`、`npm run type-check` 和相关 Jest 测试通过。
- [ ] `frontend/e2e/test_generation_mode_agent.spec.ts` 覆盖 agent generate 的 `content_agent -> update_word -> comment_agent` 过程卡。
- [ ] 模板候选和补充批注的 mock E2E 根据单文件回填和统一批注 prompt 同步更新并通过。
- [ ] Windows + Word COM 环境下可执行一次手工或自动化生成冒烟：上传模板文件和技术参数文件后生成任务完成并可下载。

## 4. 功能需求

- FR-1: 前端生成表单必须只暴露“模板文件（必填）”和“技术参数文件（必填）”两个上传入口。
- FR-2: 未上传模板文件时，前端必须阻止提交并显示“请上传模板文件”。
- FR-3: 未上传技术参数文件时，前端必须阻止提交并显示“请上传至少一个技术参数文件”。
- FR-4: 前端 draft 文件结构必须只包含 `template` 和 `tender_params`。
- FR-5: 前端生成请求必须只发送 `file_paths.template` 和 `file_paths.tender_params`。
- FR-6: 后端 `GenerateRequest.file_paths` 必须只接受模板文件和技术参数文件路径。
- FR-7: 后端初始 state 必须只写入 `template_path` 和 `tender_param_paths`。
- FR-8: `prepare_template` 必须只从 `template_path` 复制工作副本到 `prepared_doc_path`。
- FR-9: `extract_tender_params` 必须从 `template_path` 提取模板参考正文，并从 `tender_param_paths` 提取技术参数正文。
- FR-10: 标准生成 graph 必须删除 `get_comments` 和 `copy_comments` 分支。
- FR-11: `workflow` 生成必须在 `generate_polished_text` 后进入 `generate_comments`，再进入 `update_word`。
- FR-12: `agent` 生成必须在 `content_agent` 后进入 `update_word`，再进入 `comment_agent`。
- FR-13: `agent` 生成不得进入 `generate_comments`。
- FR-14: `generate_comments` 必须只基于 `polished_text` 和 `comment_prompt.py` 生成 JSON 批注候选。
- FR-15: `comment_agent` 在 agent generate 和 comment_supplement 中必须复用 `comment_prompt.py` 自主生成批注候选。
- FR-16: `comment_no_reference_prompt.py` 及其导出、测试引用必须删除。
- FR-17: 模板候选选择 API 必须只返回一个 `selected_file`。
- FR-18: 模板候选选择失败必须整体失败，不得返回 partial success。
- FR-19: 模板文件自带 Word 批注不得被主动提取、复制或清空。
- FR-20: 三个知识包和 `asset/README.md` 必须同步更新。

## 5. 非目标

- 不保留旧 API 字段、旧会话草稿或旧请求兼容。
- 不新增新的招标类型或新的 graph 家族。
- 不主动清理模板文件已有 Word 批注。
- 不改变 rewrite / edit / comment_supplement 的入口 URL。
- 不引入新的 LLM provider、Word COM 生命周期方案或任务队列方案。

## 6. 设计考虑

- 前端表单应复用现有 `FileUploader` 和 `TenderFormShared` 布局，不重新设计页面结构。
- 模板候选弹窗只调整文案和回填目标，保留现有候选列表、下载链接、不可选择年份提示和缓存刷新行为。
- UI 文案必须避免继续暴露“送审稿 / 清洁稿 / 发售稿回填到两个槽位”等旧概念。

## 7. 技术考虑

- 当前前端 `gngk` 到后端四套 `form_type` 的分派仍以 `frontend/lib/gngkFormType.ts` 为真源，本需求不改变分派规则。
- 当前 `generation_mode` 只影响初次 generate，本需求保持该边界。
- Graph 改动影响所有 `StandardTenderWorkflowGraph` 子类，需要同步 `xjcg`、`gngk_*`、`gjgk` 的节点绑定和测试。
- Word COM 仍必须走 `BaseGraph` 的锁、取消检查和进度包装。
- 模板候选下载代理必须继续受白名单主机约束。
- 批注写回仍应遵守已有“正文已成功写入并可下载时，批注写回可降级为 warning”的任务结果契约。

## 8. 成功指标

- 用户创建生成任务时，上传区概念从三个历史槽位减少为两个必填槽位。
- `rg` 回归搜索不再显示生成链路旧字段的活跃引用。
- `workflow` 和 `agent` 两种生成模式的 graph 测试能明确区分批注路径。
- 模板候选选择失败不再出现部分成功状态。
- 后端相关测试和前端相关测试全部通过。

## 9. 待确认问题

- 无。当前需求明确不保留旧字段兼容。
