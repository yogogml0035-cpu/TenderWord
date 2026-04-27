# Asset Knowledge Pack Index

## 当前有效知识包
- `shared_runtime_boundary_knowledge_pack.md`
  - 适用范围：后端 generate / rewrite / edit 运行时、Prompt Layer、task skill runtime、Word COM、SSE、任务结果透传，以及 `backend/helper/word_helper/` 共享业务 helper（含 generate / edit 样式回填、短片段样式锚定边界）。
  - 当前真源：`backend/services/document_service.py`、`backend/graphs/base_graph.py`、`backend/graphs/skill_graph.py`、`backend/skills/`、`backend/core/sse_manager.py`、`backend/models/sse.py`、`backend/task/task_queue_manager.py`。
- `tender_type_extension_convergence_knowledge_pack.md`
  - 适用范围：招标类型 identity、前后端 `form_type` / `tender_type` 映射、`gngk` 子类型分派、anchor 默认值、graph/node 特化与收敛。
  - 当前真源：`backend/config/tender_config.py`、`backend/models/generate.py`、`backend/graphs/`、`backend/nodes/gngk_word_nodes/gngk_get_replacements.py`、`frontend/utils/tenderTypeMapper.ts`、`frontend/lib/formDataConverter.ts`、`frontend/components/chat/ChatPanel.tsx`。
- `frontend_conversation_scope_knowledge_pack.md`
  - 适用范围：前端当前页面会话范围、左侧栏展开/切换、URL 与会话双向同步、`chat_input` 与 `pending_*_prompt` 生命周期。
  - 当前真源：`frontend/stores/chatStore.ts`、`frontend/app/tender/page.tsx`、`frontend/components/chat/TenderTypeSidebar.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/ChatPanel.tsx`。
- `shared_template_extraction_knowledge_pack.md`
  - 适用范围：模板候选获取、同优先级 AI 重排、下载代理、文件落盘、上传槽位回填。
  - 当前真源：`backend/api/template_candidates.py`、`backend/services/template_candidate_ranking_service.py`、`backend/util/common_util/template_candidates.py`、`backend/util/common_util/upload_storage.py`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/lib/api.ts`。

## 使用路由
- 改 Prompt Layer、task skill、generate / rewrite / edit runtime、Word COM、SSE、任务结果透传或 `backend/helper/word_helper/` 时，优先读取 `shared_runtime_boundary_knowledge_pack.md`。
- 改招标类型 identity、`form_type` 分派、anchor config、graph/state/node/replacement 收敛时，优先读取 `tender_type_extension_convergence_knowledge_pack.md`。
- 改当前页面会话范围、左侧栏行为、URL 同步、聊天草稿与排队恢复时，优先读取 `frontend_conversation_scope_knowledge_pack.md`。
- 改模板候选、AI 重排、下载代理、文件回填与模板弹窗时，优先读取 `shared_template_extraction_knowledge_pack.md`。

## 维护约定
- 优先更新已有主题包；只有出现新的长期边界且无法并入现有主题时才新建知识包。
- 知识包只写当前真实存在的代码路径、测试路径和可执行验证入口。
- 对尚未完全收敛的实现，允许记录“当前现实 + 目标方向”，但必须显式区分，不能把目标写成已落成事实。
- 被完全吸收的旧规则应删除，不保留并行旧版。
- 更新任一知识包时，应同步回看本索引的适用范围与真源描述是否仍然准确。
