# 共享运行时与 Word/Skill 边界知识包

## 背景与适用范围
- 适用于 `backend/` 内 generate / rewrite / edit 运行时、Prompt Layer、task skill runtime、Word COM、SSE、日志透传、批注回写、样式回填相关改动。
- 本知识包只保留当前仓库已落成的共享边界，不记录历史分叉实现、临时脚本或已删除 helper。

## 当前真源
- 任务创建与运行时装配：`backend/services/document_service.py`
- Graph 主干与 Word 执行约束：`backend/graphs/base_graph.py`、`backend/task/task_queue_manager.py`
- task skill runtime：`backend/graphs/skill_graph.py`、`backend/skills/loader.py`、`backend/skills/registry.py`、`backend/skills/edit/`、`backend/skills/rewrite/`
- Prompt Layer：`backend/prompts/`
- SSE 与事件模型：`backend/core/sse_manager.py`、`backend/api/stream.py`、`backend/models/sse.py`
- 共享 Word helper：`backend/helper/word_helper/`
- 用户态日志透传：`backend/util/log_util/progress_log.py`、`backend/util/log_util/sse_log_handler.py`

## 运行时主干

### Generate / Rewrite / Edit 的入口分层
- generate 任务通过 `DocumentService.create_task()` 进入 `GRAPH_REGISTRY`，按 `GenerateRequest.form_type` 选择具体 graph。
- rewrite 与 edit 都走 `SkillGraph.for_skill(...)` 返回的 task graph；当前仅注册了 `rewrite` 与 `edit` 两个 task skill。
- `POST /api/edit` 是显式 edit 唯一入口，对应 `backend/api/edit.py`。
- `/api/user/stream` 只负责普通聊天与 rewrite 路由，不承接显式 edit。
- `rewrite` 和 `edit` 的公开节点名保持稳定：
  - `rewrite`: `resolve_rewrite_target -> get_rewrite_comments? -> delete_section + rewrite_text -> update_word`
  - `edit`: `resolve_edit_target -> extract_edit_context -> delete_section + edit_text -> update_word`

### skill 声明与校验
- task skill 真源是 `backend/skills/edit/SKILL.md`、`backend/skills/rewrite/SKILL.md` 的 frontmatter 与正文，以及 `backend/skills/loader.py` / `backend/skills/registry.py` 的装载校验。
- 当前 loader 强校验的字段为：`name`、`description`、`executor_kind`、`dispatch_key`、`route_literal`、`workflow_entry`。
- registry 会继续校验：
  - `workflow_entry` 可解析到 skill 目录内真实模块
  - 入口函数存在
  - 返回值必须是 `TaskSkillWorkflow`
  - `workflow.skill_id` 必须与 skill 名一致

### generate-only 字段与 prompt 路由
- `generation_style` 只属于 generate 运行时。
- `DocumentService._build_initial_state()` 会把 `GenerateRequest.generation_style` 写入 generate graph state。
- `DocumentService._build_edit_graph_initial_state()` 与 `_build_skill_graph_initial_state()` 都不会注入 `generation_style`。
- Prompt 路由当前收口在：
  - `backend/prompts/generate_prompt.py`
  - `backend/prompts/generate_by_template_prompt.py`
  - `backend/prompts/generate_by_param_prompt.py`

### LLM 流式调用
- 统一流式调用入口是 `backend/util/common_util/llm_stream_utils.py` 的 `stream_llm_completion()`。
- 默认超时统一复用 `backend/config/settings.py` 的 `LLM_STREAM_TIMEOUT_SECONDS`。
- edit 的 prompt 审计与文本产物当前分别落在：
  - `backend/prompts_log/edit_log/` 的 JSON audit
  - `backend/prompts_log/generate_log/` 的 `prompt_edit_*` 双文本文件

## Word / Queue / Helper 边界

### 队列与串行执行
- Word COM 任务统一经过 `backend/task/task_queue_manager.py` 排队，不能绕开。
- Graph 节点执行统一挂在 `backend/graphs/base_graph.py` 的主干上，复用取消检查、进度包装、异常汇总和锁。
- edit 当前会先复制工作副本，再把 `origin_tender_path`、`prepared_doc_path`、`clean_draft_path` 都指向副本；源文件不直接改写。

### 共享 Word helper 的当前边界
- `backend/helper/word_helper/` 当前真实模块为：
  - `range_utils.py`
  - `protected_fields.py`
  - `text_parsing.py`
  - `content_ops.py`
  - `paragraph_boundary_ops.py`
  - `cleanup_ops.py`
  - `semantic_matcher.py`
  - `inline_style_ops.py`
- 当前仓库没有 keep-range 独立 helper 模块；知识沉淀不得再引用已删除的 keep-range 文件名。
- `backend/util/word_util/` 仍承担 COM 生命周期、底层 Word API、锚点解析、文档检查与底层插入工具；不要把业务层规则重新塞回 util 层。

### 受保护字段与更新模式
- 类型更新模式的真源是 `backend/config/tender_config.py`。
- 当前 `content_update_mode` 只有两类：
  - `protected_fields`
  - `direct_replace`
- 当前受保护字段 profile 解析结果为：
  - `xjcg`、`gngk_hw_zc`、`gngk_hw_cz`、`gngk_fw_cz` -> `common_two_field`
  - `gngk_fw_zc` -> `gngk_three_field`
  - `gjgk` -> `direct_replace`，调用 `get_protected_field_profile("gjgk")` 会直接报错
- 受保护字段识别与规范化当前统一收口在 `backend/helper/word_helper/protected_fields.py`，包括：
  - canonical marker 规范化
  - 严格字段行匹配
  - 文本预规范化
  - 收集、刷新、重定位与 fail-fast 校验

### skill runtime 的类型感知分发
- `backend/nodes/skills_nodes/tender_aware_word_dispatch.py` 当前只特判两类：
  - `gjgk`
  - `gngk_fw_zc`
- 其它运行态（包括 `xjcg`、`gngk_hw_*`、`gngk_fw_cz`）当前仍回退到 common `delete_tender_param` / `update_word`。
- 因此凡是修改某个类型在 rewrite / edit 中的 delete/update 路由，必须同时检查：
  - generate graph 的节点绑定
  - `tender_aware_word_dispatch.py` 的 skill runtime 分发

## 批注、样式、日志与 SSE 契约

### 批注与样式结果
- `backend/states/base_state.py` 仍是 `comment_writeback_*`、`style_writeback_*` 相关 state 字段的真源。
- generate 在 `extract_tender_params` 的最终锚点正文范围内提取 `inline_style_fragments`；样式抽取失败只记录并降级为空列表，不阻断正文生成。
- `common update_word`、`gjgk_update_word`、`gngk_fw_zc_update_word` 都会在最终写入边界内消费 `inline_style_fragments`，并把批注回写摘要和样式回填摘要写回 state。
- 当 `generated_comment_count > 0` 且最终成功写入数为 `0` 时，三条 update 路径都会硬失败，错误文本包含“批注生成成功但写入失败”。
- 样式回填属于 best-effort：低相似度、0 命中或片段跳过不会硬失败；批注写回硬失败契约保持不变。
- `DocumentService._build_task_result_payload()` 会把 `style_writeback` 摘要并入任务完成结果。
- `DoneEventData` 也保留 `style_writeback` 字段，SSE `done` 事件会继续透传。
- 行首编号前缀回填属于独立窄路径：`inline_style_ops.py` 会把只包含编号的红色/加粗等 run 提取为 `number_prefix` 片段，用编号后的正文做锚定，回填时只写目标行的可见编号前缀；若目标仍是 Word 自动编号且标签不在普通文本里，则写回目标段落 `ListFormat` 对应 list level 的 Font。
- 编号前缀回填不得修改 `normalize_semantic_text()` 的全局“忽略编号”语义；没有可见编号且没有可写自动编号标签时，应记录 `no_number_prefix_target` 并跳过，避免把编号样式扩散到正文；若编号前缀片段带删除线或斜体等高风险可见样式，应记录 `number_prefix_high_visible_style` 并跳过，避免把参考模板里的删除痕迹写到新章节编号。
- 普通 `partial_span` 不得给目标行首编号/列表前缀写样式；短片段样式必须先通过 exact / 上下文 / 容器或表格结构的硬门槛，再进入综合评分，位置分只能排序，不能把删除线、斜体等高可见风险样式救回到无关短文本。
- `normalized_text` 长度不超过 3 的普通短片段默认只接受非编号前缀的 exact 命中；表格短片段保留同单元格 exact 回填，但跨单元格短片段必须同时满足强结构与语义锚点。

### edit 的日志可见性
- `resolve_edit_target()` 当前固定写入：
  - `verbose_style_progress_logs = True`
  - `suppress_comment_progress_logs = True`
- 因此 edit 默认会输出更细的样式提取/回填日志，但会压制批注写入 summary 的用户态日志。
- 样式摘要仍会进入任务结果与 SSE `done`，只是下载卡片 UI 当前不直接渲染该摘要。
- generate 的样式提取用户态日志只保留 outcome-first 摘要（开始、完成片段数、失败已跳过），不输出片段全文、候选打分、阈值或淘汰原因；候选诊断继续留在 debug / execution log。

### SSE 与日志分工
- `/api/stream/{task_id}` 是任务 SSE 主入口，支持 `Last-Event-ID` 断线续传。
- `backend/util/log_util/sse_log_handler.py` 通过 `task_log_context` 将 `progress_log` 里的 INFO/WARNING/ERROR 推到 SSE `log` 事件。
- 用户态实时展示依赖：
  - `log`
  - `llm`
  - `progress`
  - `done`
  - `error`
- 当前前端在 `frontend/hooks/useChatSSE.ts` 里把 `style_writeback` 透传进 task download message metadata，但 `frontend/components/chat/TaskDownloadMessage.tsx` 只展示文件下载卡片，不展示样式摘要文本。

## 关键代码路径
- `backend/services/document_service.py`
- `backend/graphs/base_graph.py`
- `backend/graphs/skill_graph.py`
- `backend/skills/loader.py`
- `backend/skills/registry.py`
- `backend/skills/edit/SKILL.md`
- `backend/skills/edit/scripts/workflow.py`
- `backend/skills/rewrite/SKILL.md`
- `backend/skills/rewrite/scripts/workflow.py`
- `backend/nodes/skills_nodes/edit_nodes.py`
- `backend/nodes/skills_nodes/rewrite_nodes.py`
- `backend/nodes/skills_nodes/tender_aware_word_dispatch.py`
- `backend/nodes/common_word_nodes/update_word.py`
- `backend/nodes/common_word_nodes/comment_writeback.py`
- `backend/nodes/common_word_nodes/extract_tender_params.py`
- `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`
- `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`
- `backend/helper/word_helper/__init__.py`
- `backend/helper/word_helper/protected_fields.py`
- `backend/helper/word_helper/content_ops.py`
- `backend/helper/word_helper/paragraph_boundary_ops.py`
- `backend/helper/word_helper/cleanup_ops.py`
- `backend/helper/word_helper/inline_style_ops.py`
- `backend/core/sse_manager.py`
- `backend/api/stream.py`
- `backend/api/tasks.py`
- `backend/util/common_util/llm_stream_utils.py`
- `backend/util/log_util/prompt_log.py`
- `backend/util/log_util/skill_audit_log.py`

## 关联测试与验证路径
- `backend/tests/services/test_document_service_initial_state.py`
- `backend/tests/services/test_document_service_task_result.py`
- `backend/tests/nodes/test_tender_aware_word_dispatch.py`
- `backend/tests/nodes/test_edit_audit_logging.py`
- `backend/tests/logging/test_task_audit_log_paths.py`
- `backend/tests/progress/test_edit_progress_tracking.py`
- `backend/tests/nodes/test_edit_inline_style_context.py`
- `backend/tests/nodes/test_comment_writeback.py`
- `backend/tests/nodes/test_common_delete_tender_param.py`
- `backend/tests/nodes/test_common_update_word_split.py`
- `backend/tests/nodes/test_extract_tender_params_inline_style.py`
- `backend/tests/nodes/test_update_word_inline_style_writeback.py`
- `backend/tests/nodes/test_gngk_fw_zc_delete_tender_param.py`
- `backend/tests/nodes/test_gngk_fw_zc_update_word.py`
- `backend/tests/nodes/test_protected_fields_strict_matching.py`
- `backend/tests/nodes/test_word_insert_html_breaks.py`
- `backend/tests/helper/test_content_ops.py`
- `backend/tests/helper/test_paragraph_boundary_ops.py`
- `backend/tests/helper/test_inline_style_ops.py`
- `backend/tests/util/test_llm_stream_utils.py`
- `backend/tests/prompts/test_generate_prompt_routing.py`

## 回归风险与维护建议
- 修改 skill workflow、dispatch 路由或 task audit log 时，要同时检查 edit/rewrite 的运行时装配与对应测试，不要只改 `backend/skills/` 或只改 `document_service` 一侧。
- 修改受保护字段规则时，应同步检查 `tender_config.py`、`protected_fields.py`、三条 `update_word` 路径以及严格匹配测试。
- 修改样式回填或 SSE 结果结构时，应同步检查：
  - `backend/models/sse.py`
  - `backend/services/document_service.py`
  - `frontend/hooks/useChatSSE.ts`
  - `frontend/stores/chatStore.ts`
- 若未来新增共享 Word helper，先确认它在仓库里已经真实落地，再把它写入知识包；不要把设计意图提前写成事实。
