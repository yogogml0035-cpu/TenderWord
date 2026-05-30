# 知识包索引

`asset/` 是 TenderWord 的长期知识沉淀入口。`AGENTS.md` 保存跨主题不变量，本目录保存 topic 级当前事实、同步面、验证入口和回归风险。

## 当前有效知识包

- `shared_runtime_word_skill_knowledge_pack.md`
  - 适用范围：generate / rewrite / edit / comment_supplement 运行时、初次生成 `generation_mode` 与 DeepAgents content_agent 自主调度、agent generate 后置 `comment_agent` 批注增强分支、补充批注 Graph 与 latest `rewrite_state` 更新、补充批注 direct `comment_agent` 生成/校验/写回、补充批注 mock E2E 入口、FilesystemBackend workspace 文件契约、agent_step 1-based 轮次与单入口广播、agent 热重载与输入摘要排障、智能体生成提示词中文化边界、审核 JSON 兜底与事实真源、招标详情 API 数据契约、用户流式 rewrite 路由、Prompt Layer、统一 `comment_prompt` 批注生成、comment_agent 两轮工具门禁、结构化过程卡与审计日志、LLM provider 默认模型与思考模式开关、generate prompt 路由模式契约、模板生成的参考符号零继承、硬换行与冒号挂载列表约束、task skill runtime、task skill 输出范围契约、按参数生成时的无源引导段删除与重编号约束、参考限权、参数表格 schema 真源、商务章去重删除、Word COM、共享 Word helper、批注/样式回写、样式颜色门禁、任务结果与 SSE / agent_step 透传。
- `tender_type_identity_session_knowledge_pack.md`
  - 适用范围：招标类型 identity、`form_type` / `tender_type` / family、`gngk` 子类型分派、anchor 默认值、`ifzgcg` 对货物财政 graph 分派的影响、graph/node/replacement 特化、国内公开货物自筹替换字段边界、canonical URL、当前页面会话、`generation_mode` 草稿字段、正文智能体结构化过程卡、智能体过程卡标题/空态/聚合、`comment_agent` 过程卡与草稿恢复。
- `template_candidate_pipeline_knowledge_pack.md`
  - 适用范围：模板候选获取、同优先级 AI 重排、下载代理、文件落盘、上传槽位回填、模板弹窗缓存与刷新。

## 使用路由

- 改招标详情 API 数据契约、Prompt Layer、task skill、generate / rewrite / edit / comment_supplement runtime、`generation_mode` 后端分流、DeepAgents content_agent、Word COM、SSE、任务结果透传、批注/样式回写或 `backend/helper/word_helper/` 时，优先读取 `shared_runtime_word_skill_knowledge_pack.md`。
- 改招标类型 identity、`form_type` 分派、anchor config、graph/state/node/replacement 收敛、URL 判型、当前页面会话、`sessionStorage` 语义、`generation_mode` 草稿、智能体过程卡、聊天草稿与排队恢复时，优先读取 `tender_type_identity_session_knowledge_pack.md`。
- 改模板候选、AI 重排、下载代理、文件回填与模板弹窗时，优先读取 `template_candidate_pipeline_knowledge_pack.md`。

## 维护约定

- 优先更新已有主题包；只有出现新的长期边界且无法并入现有主题时才新建知识包。
- 知识包只写当前真实存在的代码路径、测试路径和可执行验证入口。
- 对尚未完全收敛的实现，允许记录“当前现实 + 目标方向”，但必须显式区分，不能把目标写成已落成事实。
- 被完全吸收的旧规则应删除，不保留 old/new 并行版本。
- 更新任一知识包时，应同步回看本索引、`AGENTS.md` 的知识包列表与回写路由。
