# 知识回写与验证门槛

本文件保存文档维护、知识包回写、验证和交付规则。

## 阅读顺序

- 第一次接手：先读 `AGENTS.md`、`README.md`、`coding_maps/SYSTEM_MAP.md`、`INTERFACES.md`，再读相关子项目 `.planning/codebase/`。
- 改后端：先读 `docs/backend.md` 和 `backend/.planning/codebase/`，再读相关 `asset/*.md`。
- 改前端：先读 `docs/frontend.md` 和 `frontend/.planning/codebase/`，再读相关 `asset/*.md`。
- 改跨端接口：先读 `docs/interfaces-runtime.md`、`INTERFACES.md`、后端模型/API、前端类型/API client 和相关测试。

## 知识包回写

- 改 Prompt Layer、task skill、generate/rewrite/comment_supplement runtime、`generation_mode`/`comment_generation_mode`、content/comment agent、`annotate_corrections` 编号隔离、Word COM（含特殊字形 token / 自动编号抽取 / Find 上限）、任务结果、SSE、批注/样式写回或 Word helper：更新共享运行时知识包。
- 改招标类型 identity、`form_type` 分派、anchor、graph/state/node/replacement、URL、会话、`sessionStorage`、生成草稿字段、过程卡或排队恢复：更新类型身份与会话知识包。
- 改 agent run 审计日志、公共摘要工具、上传文件 rewrite 来源标记、`selected_skills` 一次性语义或上传文件 rewrite 上下文：同时检查共享运行时知识包和类型身份与会话知识包。
- 改模板候选、AI 重排、下载代理、文件回填或模板弹窗：更新模板候选知识包。
- 大范围改动后若 `.planning/codebase/` 或系统地图明显过期，先刷新对应子项目事实地图，再更新系统地图。
- `[[TABLE:<id>]]` 现在是内部写回入口语义；若涉及占位符、写回解析、`content_verify_agent` 或 `content_sanitizer`，优先同步共享运行时知识包中的对应条目，再回看接口和事实地图。
- 知识包只写当前仍成立的边界、同步面、验证入口和回归风险；不保存单次排障时间线。

## 验证门槛

- 文档型变更至少运行 `git diff --check`，并扫描本轮改动文档中的密钥/token 模式；仅文档变更不需要跑代码测试或 E2E。
- 长期文档说明性正文必须保持简体中文；代码标识符、文件路径、命令、配置键和 API 名称保留原文。
- 前端改动至少运行 `npm run lint`、`npm run type-check` 和相关 `npm run test`。
- 后端改动至少运行 `python -m pytest tests -v`。
- Word COM 真实闭环需要 Windows + Word COM，WSL 只能作为无 COM 替代验证。
- API shape、SSE、任务类型、招标类型、Prompt/LLM、Word helper、模板候选等跨层改动必须同步前后端类型、客户端、服务端模型、相关测试和知识包。
- 新增测试文件必须以 `test_` 开头，并放入既有测试归档层级。

## 交付说明

最终回复写清：

- 改了什么。
- 影响哪些层。
- 跑了哪些验证。
- 未跑项及原因。
- 剩余风险与最短回滚方式。
- 若本轮属于完整需求或修复，说明是否发现可迁移经验，以及对应 `asset/` 知识包是否已更新；没有沉淀也要说明原因。
