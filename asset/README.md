# Asset Knowledge Pack Index

`asset/` 是 TenderWord 的长期知识沉淀入口。`AGENTS.md` 保存跨主题不变量，本目录保存 topic 级当前事实、同步面、验证入口和回归风险。

## 当前有效知识包

- `shared_runtime_word_skill_knowledge_pack.md`
  - 适用范围：generate / rewrite / edit 运行时、用户流式 rewrite 路由、Prompt Layer、task skill runtime、task skill 输出范围契约、Word COM、共享 Word helper、批注/样式回写、样式颜色门禁、任务结果与 SSE 透传。
- `tender_type_identity_session_knowledge_pack.md`
  - 适用范围：招标类型 identity、`form_type` / `tender_type` / family、`gngk` 子类型分派、anchor 默认值、graph/node 特化、canonical URL、当前页面会话与草稿恢复。
- `template_candidate_pipeline_knowledge_pack.md`
  - 适用范围：模板候选获取、同优先级 AI 重排、下载代理、文件落盘、上传槽位回填、模板弹窗缓存与刷新。

## 使用路由

- 改 Prompt Layer、task skill、generate / rewrite / edit runtime、Word COM、SSE、任务结果透传、批注/样式回写或 `backend/helper/word_helper/` 时，优先读取 `shared_runtime_word_skill_knowledge_pack.md`。
- 改招标类型 identity、`form_type` 分派、anchor config、graph/state/node/replacement 收敛、URL 判型、当前页面会话、`sessionStorage` 语义、聊天草稿与排队恢复时，优先读取 `tender_type_identity_session_knowledge_pack.md`。
- 改模板候选、AI 重排、下载代理、文件回填与模板弹窗时，优先读取 `template_candidate_pipeline_knowledge_pack.md`。

## 维护约定

- 优先更新已有主题包；只有出现新的长期边界且无法并入现有主题时才新建知识包。
- 知识包只写当前真实存在的代码路径、测试路径和可执行验证入口。
- 对尚未完全收敛的实现，允许记录“当前现实 + 目标方向”，但必须显式区分，不能把目标写成已落成事实。
- 被完全吸收的旧规则应删除，不保留 old/new 并行版本。
- 更新任一知识包时，应同步回看本索引、`AGENTS.md` 的知识包列表与回写路由。
