# 后端风险事实地图

**分析日期：** 2026-05-31

**范围：** `backend/` 当前技术债、脆弱点、安全边界和测试缺口。

## 技术债

**Graph/锁实现存在历史重复片段：**
- 文件：`backend/graphs/base_graph.py`
- 风险：同一模块中存在重复导入和部分重复实现痕迹，排查锁、超时或取消时容易读错分支。
- 安全修改：重构前先补锁/取消/进度行为测试；不要在功能需求中顺手整理。

**部分依赖声明与代码使用需要复核：**
- 文件：`backend/requirements.txt`、`backend/util/common_util/fetch_tender_data.py`、`backend/util/common_util/template_candidates.py`
- 风险：代码中使用 `requests`，但依赖清单当前未显式列出。
- 安全修改：如要调整依赖，先确认 Windows 启动脚本和现有环境是否隐式安装，再统一修依赖与 README。

**进程内存态限制明显：**
- 文件：`backend/task/task_queue_manager.py`、`backend/core/sse_manager.py`、`backend/services/conversation_service.py`
- 风险：服务重启会丢失任务状态、SSE buffer 和会话快照。
- 安全修改：前端已把后端重启收敛成本地中断态；后端若引入持久化，要同步接口和恢复语义。

**智能体生成分支增加了文件工作区与事件链路：**
- 文件：`backend/agents/generation/`、`backend/nodes/common_word_nodes/content_agent_generate.py`、`backend/core/sse_manager.py`
- 风险：如果子 agent 绕过统一 callback 直发 SSE，或运行中快照写入错误存储，会造成重复过程卡、断线重放异常或浏览器持久化膨胀。
- 安全修改：智能体步骤统一走 `agent_step_callback` -> `SSEManager.send_agent_step()`；运行日志只记录摘要，完整输入与中间产物留在 content agent 工作区。

**补充批注依赖 latest 会话快照：**
- 文件：`backend/api/comment_supplement.py`、`backend/services/document_service.py`、`backend/graphs/comment_supplement_graph.py`
- 风险：如果 source file 不是 latest `rewrite_state.prepared_doc_path`，或会话缺少 `polished_text`，补充批注会基于过期正文写回。
- 安全修改：创建任务前继续校验 latest `rewrite_state`、当前文件存在且路径匹配；成功后必须把新副本写回 latest `rewrite_state`，避免后续 rewrite/edit 回退到旧文件。

## 已知脆弱区

**Word COM 是全局临界资源：**
- 文件：`backend/task/task_queue_manager.py`、`backend/graphs/base_graph.py`、`backend/util/word_util/word_com_manager.py`
- 风险：绕开任一层锁都会导致并发打开、写入冲突或 Word 残留进程。
- 安全修改：新增 Word 能力必须走队列、graph 锁、取消检查和进度包装。

**GNGK 子类型继承与覆写边界容易被漏看：**
- 文件：`backend/graphs/gngk_hw_zc_tender_graph.py`、`backend/graphs/gngk_hw_cz_tender_graph.py`、`backend/graphs/gngk_fw_zc_tender_graph.py`、`backend/graphs/gngk_fw_cz_tender_graph.py`
- 当前事实：`gngk_hw_cz` 继承货物自筹主干但覆写 direct-replace delete/update；`gngk_fw_zc` 覆写服务专属 delete/replacement/update；`gngk_fw_cz` 当前仍继承共享主干。
- 安全修改：任何 `gngk_*` 改动都要复核 graph 继承、node 覆写、anchor config、content mode、protected-field profile 和前端分派。
- 覆盖入口：`backend/tests/graphs/test_gngk_tender_graph.py`、`backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`。

**受保护字段契约必须保持严格：**
- 文件：`backend/config/tender_config.py`、`backend/helper/word_helper/protected_fields.py`
- 风险：模糊匹配会把表格、叙述句或普通关键词误识别为字段，导致写回边界错误。
- 安全修改：字段 marker 先规范化为中文冒号 canonical marker，再做严格字段行匹配；缺失、乱序或非法时 fail-fast。

**Direct-replace 与 protected-fields 不能混用：**
- 文件：`backend/config/tender_config.py`、`backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py`
- 风险：direct-replace 类型如果误走 protected profile，会要求不存在的“交付日期/付款方式”等字段并阻断生成。
- 安全修改：content mode 由 `TenderAnchorConfig` 显式声明，`get_protected_field_profile()` 对 direct-replace 类型抛错。

**Prompt 文案也是测试合同：**
- 文件：`backend/prompts/generate_by_template_prompt.py`、`backend/tests/prompts/test_generate_prompt_routing.py`
- 风险：只改提示语示例也可能破坏字面量断言。
- 安全修改：prompt 文案变化同步复核 prompt 测试。

**generation mode 不得影响 rewrite/edit：**
- 文件：`backend/models/generate.py`、`backend/services/document_service.py`、`backend/states/base_state.py`
- 风险：把 `generation_mode` 混入 rewrite/edit 会让显式修改链路误触初次生成智能体分支。
- 安全修改：`generation_mode` 只进入 generate request 和 generate initial state；rewrite/edit 请求模型、skill state 和 prompt surface 不接收该字段。

## 安全关注

- `.env`、真实 LLM key、token、客户原文和私有文件路径不得写入日志或文档。
- 模板候选下载必须保留主机白名单，避免下载代理变成 SSRF 入口。
- 下载接口必须继续限制在 `settings.UPLOAD_DIR` 下。
- `progress_log` 不写堆栈和敏感参数；排障细节进入 `execution_log`。

## 性能与扩展限制

- Word COM 任务被设计为串行执行，吞吐量天然有限。
- LLM streaming、Word 写回和文件 IO 是长耗时路径。
- SSE、任务和会话为进程内存态，横向扩展前需要重新设计持久化和事件分发。
- 模板候选 AI 重排会增加外部 LLM 延迟，应限制在同优先级候选组内。

## 缺失或未确认能力

- 未确认稳定登录、权限和多用户隔离。
- 未确认外部数据库、Redis、对象存储或队列服务。
- 未确认 CI 环境能执行 Windows + Word COM 真实集成。
- 未确认稳定部署平台或生产运行拓扑。

## 测试缺口

- 真实 Word `.doc/.docx` 端到端测试仍依赖 Windows + Word COM 环境。
- 部分 Word helper 测试使用 fake 对象，不能完全替代真实 COM 边界。
- 跨前后端完整链路需要前端 Playwright 或真实运行环境验证。
- 模板候选外部接口和 LLM 重排应保持 mock 覆盖，避免测试依赖外部服务状态。

## 回归风险检查

- 改 `FormType` 或 graph registry：同步前端 union、`gngkFormType`、converter、ChatPanel edit 调用点、graph 测试。
- 改 SSE event：同步后端模型、发送方、前端类型、`useChatSSE` 和测试。
- 改 Word helper：同步相关节点测试和 `asset/shared_runtime_word_skill_knowledge_pack.md`。
- 改 `generation_mode`、`content_agent` 或 `agent_step`：同步 generation mode graph 测试、agent 运行时测试、SSE manager 测试、前端事件解析测试和相关知识包。
- 改类型 identity / URL：同步 `asset/tender_type_identity_session_knowledge_pack.md`。
- 改模板候选：同步 `asset/template_candidate_pipeline_knowledge_pack.md`。

---

*后端风险审计：2026-05-31*
