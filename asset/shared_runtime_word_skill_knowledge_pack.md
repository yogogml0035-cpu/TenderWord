# 共享运行时、Word 与 Skill 边界知识包

## 背景与范围

本包适用于后端 generate / rewrite / edit 运行时、Prompt Layer、task skill runtime、Word COM、共享 Word helper、批注/样式回写、任务结果与 SSE 透传相关改动。

本包只记录当前仍存在的共享主干、稳定契约、验证入口和回归风险；实现细节以代码为准，不保留历史分叉、临时脚本或已删除文件名。

## 当前真源

- 任务创建与运行时装配：`backend/services/document_service.py`
- Graph 主干、锁、取消与进度包装：`backend/graphs/base_graph.py`、`backend/task/task_queue_manager.py`
- task skill runtime：`backend/graphs/skill_graph.py`、`backend/skills/`
- Prompt Layer：`backend/prompts/`
- Word 业务 helper：`backend/helper/word_helper/`
- SSE 与日志透传：`backend/core/sse_manager.py`、`backend/api/stream.py`、`backend/models/sse.py`、`backend/util/log_util/`

## 运行时分层

### Generate / Rewrite / Edit

- generate 任务通过 `DocumentService.create_task()` 进入 `GRAPH_REGISTRY`，按 `GenerateRequest.form_type` 选择具体 graph。
- rewrite 与 edit 走 `SkillGraph.for_skill(...)` 返回的 task graph；当前 task skill 注册以 `backend/skills/rewrite/SKILL.md`、`backend/skills/edit/SKILL.md` 为准。
- `POST /api/edit` 是显式 edit 入口；`/api/user/stream` 只负责普通聊天与 rewrite 路由，不承接显式 edit。
- `/api/user/stream` 在已有 rewrite history 且最新消息具备明确修改意图时，应优先走确定性 rewrite fast-path，再进入 rewrite task 创建；普通闲聊、能力询问和不确定语义仍走 LLM 路由/回复。前端构造 user stream `messages` 时必须过滤空内容气泡，避免历史空 AI 消息触发后端请求体验证失败。
- `generation_style` 是 generate-only 字段：`DocumentService._build_initial_state()` 可写入 generate state，edit / rewrite 初始 state 不得注入该字段。

### Skill 声明

- skill loader 与 registry 负责 fail-fast 校验 frontmatter、workflow 入口、返回类型和 `workflow.skill_id`。
- 修改 skill workflow、dispatch 路由或 audit log 时，必须同时检查 `backend/skills/`、`backend/graphs/skill_graph.py`、`backend/services/document_service.py` 和对应 tests。
- edit / rewrite 的 LLM 输出会作为当前文档内容或当前锚点区正文的完整替换载荷；skill instruction 必须明确“输出范围守恒”。分包名、章节名、锚点、`从……起` 等用户表述默认只定位修改范围，不能让模型把局部定位误解为只输出该局部，否则写回会丢失未修改分包或章节。

### Prompt Layer 与 LLM 流式

- `backend/` 内直接调用 LLM 的能力默认收敛到 `backend/prompts/`；Prompt Layer 只做纯渲染，不做日志、副作用、Word COM 或会话状态变更。
- generate prompt 路由当前由 `backend/prompts/generate_prompt.py` 分派到 template / param builder。
- template generate prompt 需要把编号拆成“层级语义”和“输出样式”两层处理：原材料只提供条款内容、物理顺序、父子层级和特殊符号，输出编号的层级形态、连接符与后缀标点应从参考内容对应章节抽取并顺排生成，避免把原材料里的括号、半括号、顿号、中文数字或混合编号外形直接带入最终文本。
- LLM 流式调用统一经 `backend/util/common_util/llm_stream_utils.py` 的 `stream_llm_completion()`，默认超时使用 `backend/config/settings.py` 的 `LLM_STREAM_TIMEOUT_SECONDS`。
- `generate_comments` 的批注 JSON 属于严格机器契约：节点必须先尝试本地提取数组、移除代码块包裹、修正常见尾逗号/非法反斜杠；仍失败时只允许再走一次 Prompt Layer 定义的 JSON 修复调用，然后再决定是否降级为空数组。原始批注输出与修复输出应继续落到 `backend/prompts_log/generate_log/` 便于排障。

## Word / Queue / Helper 边界

### 队列与串行执行

- Word COM 任务统一经过 `backend/task/task_queue_manager.py` 排队，不能绕开。
- Graph 节点必须复用 `backend/graphs/base_graph.py` 的锁、取消检查、进度包装和异常汇总。
- edit 当前会复制工作副本，再把 `origin_tender_path`、`prepared_doc_path`、`clean_draft_path` 指向副本；源文件不直接改写。

### Helper 分层

- `backend/helper/word_helper/` 是 Word 业务逻辑层，当前包含 range、protected fields、text parsing、content ops、paragraph boundary、cleanup、semantic matcher、inline style 等共享能力。
- `backend/util/word_util/` 只承担 COM 生命周期、底层 Word API、锚点解析、文档检查与底层插入工具。
- 节点文件只保留页码/锚点定位、Word 应用生命周期、日志、保存、state 装配和类型专属编排。
- 新 helper 落地后，调用方直接从 `backend.helper.word_helper.<module>` 导入；节点里的兼容别名只能短期过渡。

### 受保护字段

- 类型更新模式与受保护字段 profile 解析真源是 `backend/config/tender_config.py`。
- 当前 `content_update_mode` 只有 `protected_fields` 与 `direct_replace`。
- `xjcg`、`gngk_hw_zc`、`gngk_hw_cz`、`gngk_fw_cz` 使用 `common_two_field`；`gngk_fw_zc` 使用 `gngk_three_field`；`gjgk` 是 `direct_replace`，不支持受保护字段 profile。
- 受保护字段唯一真源是带中文冒号的 canonical marker；英文冒号兼容必须先规范化，再进入扫描、重绑或 AI 文本拆块。
- 字段识别必须严格匹配“可选编号前缀 + canonical marker + 值”的字段行；表格行、单元格文本或普通叙述句里的关键字命中不算有效字段。
- 关键字段缺失、格式非法或顺序非法时必须 fail-fast，不能部分写回后再靠 cleanup 兜底。

### 正文写回与段落边界

- 正文写回统一使用真实段落边界：`<br>`、字面量 `\n` / `\r\n` / `\r` 先归一化，再落成 Word `\r`。
- 不得用 `wdLineBreak`、`\v` 或手动换行兜底正文段落，避免多段正文被压成一段。
- 受保护字段后的正文写回顺序固定为：先复用现成可写段 -> 段内拆段 -> 向后扫描 -> fail-fast。
- 判断下一段是否可写时，不得把 Heading / `OutlineLevel` 当成锁；真正阻止写入的是 range 锁、字段锁、SDT 锁和文档保护。
- AI 输出中的显式空行属于正文语义；拆块阶段必须保留空字符串行，cleanup 默认不得无差别压平正文段。

## 批注、样式、日志与 SSE

### 批注与样式回写

- `backend/states/base_state.py` 是 `comment_writeback_*`、`style_writeback_*` state 字段真源。
- `common update_word`、`gjgk_update_word`、`gngk_fw_zc_update_word` 都要把批注和样式回写摘要写回 state。
- 当 `generated_comment_count > 0` 且最终成功写入数为 `0` 时，update 路径必须硬失败，错误文本包含“批注生成成功但写入失败”。
- 样式回填是 best-effort：低相似度、0 命中或片段跳过不硬失败；批注写回硬失败契约保持不变。
- `replace_content` 给首个正文 `project_name` 插入 `PROJECT_NAME_FIRST_HIT_COMMENT` 时，必须先按规范化后的批注文案做去重；只跳过“同文案”重复批注，其他文案批注不影响新增。Word 若把既有批注暴露成零宽或贴边锚点，也要视为同一落点参与判重。
- `DocumentService._build_task_result_payload()` 与 SSE `done` 事件必须继续透传 `style_writeback`。

### 生成文本基础格式与样式门禁

- 生成正文的基础插入格式必须先清洗为黑色普通字体，再允许后续样式回填叠加。
- `backend/helper/word_helper/content_ops.py` 的 `reset_generated_text_font_format()` 是生成文本 font-only 清洗真源；受保护字段值和生成编号前缀只能调用 font-only 清洗，不能顺手改段落布局。
- 字体颜色属于高风险可见样式，非默认/非自动颜色默认 fail-closed；只有强锚定、唯一、语义一致的局部片段，或短整段、目标原文完全一致且跨所有目标容器全局唯一的整容器片段，才允许写入颜色；整容器片段带下划线、高亮等伴随样式时，红色也必须通过同一全局唯一门禁。
- 行首编号前缀回填是独立窄路径；不得修改 `normalize_semantic_text()` 的全局“忽略编号”语义，也不得把编号样式扩散到正文。
- 普通短片段样式必须先通过 exact / 上下文 / 容器或表格结构硬门槛，再进入综合评分；位置分只能排序，不能救回高可见风险样式。

### 日志与 SSE 分工

- `progress_log` 只写用户可理解的进度和状态；排障堆栈、候选打分、淘汰原因、阈值与诊断 marker 留在 `execution_log` 或 debug log。
- `/api/stream/{task_id}` 是任务 SSE 主入口，支持 `Last-Event-ID` 断线续传。
- 用户态实时展示依赖 `log`、`llm`、`progress`、`done`、`error`。
- `frontend/hooks/useChatSSE.ts` 负责接收 done metadata；下载卡片是否展示摘要属于 UI 决策，不能影响任务结果透传契约。

## 关联测试与验证入口

- 运行时与任务结果：`backend/tests/services/test_document_service_initial_state.py`、`backend/tests/services/test_document_service_task_result.py`
- 用户流式 rewrite 路由：`backend/tests/services/test_user_routing_service.py`、`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`
- skill 与 edit/rewrite：`backend/tests/nodes/test_tender_aware_word_dispatch.py`、`backend/tests/nodes/test_edit_audit_logging.py`、`backend/tests/progress/test_edit_progress_tracking.py`
- Word helper：`backend/tests/helper/test_content_ops.py`、`backend/tests/helper/test_paragraph_boundary_ops.py`、`backend/tests/helper/test_inline_style_ops.py`
- 受保护字段与写回：`backend/tests/nodes/test_protected_fields_strict_matching.py`、`backend/tests/nodes/test_update_word_inline_style_writeback.py`
- Prompt / LLM stream：`backend/tests/prompts/test_generate_prompt_routing.py`、`backend/tests/util/test_llm_stream_utils.py`

## 回归风险

- 改 skill workflow、dispatch 或 task result 时，容易出现 generate/rewrite/edit 某一条链路漏同步。
- 改受保护字段规则时，必须同时检查 `tender_config.py`、`protected_fields.py`、三条 update 路径和严格匹配测试。
- 改样式回填或 SSE 结果结构时，必须同步检查后端 `DoneEventData`、任务结果 payload、`frontend/hooks/useChatSSE.ts` 和 chat store metadata。
- 任何新增 Word helper 都要先确认代码真实落地，再写入知识包；不要把目标设计提前写成已完成事实。
