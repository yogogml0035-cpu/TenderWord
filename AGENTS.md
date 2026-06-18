# TenderWord 智能体操作指南

TenderWord 是招标文档生成、修改、补充批注和模板复用系统；前端是 Next.js 工作台，后端是 FastAPI + LangGraph + Word COM 任务执行端。

## 关键约定

- 代码是真源；根级文档只做导航和稳定规则沉淀。
- 按任务先看下方详细文档，再进入对应子项目事实文档和知识包；不要只凭根级摘要改跨层逻辑。
- 长期文档说明性正文默认使用简体中文；代码标识符、文件路径、命令、配置键和 API 名称保留原文。
- 前端包管理器是 npm；后端依赖以 `backend/requirements.txt` 为准。
- 完整 Word 生成验收必须回到 Windows Python、pywin32 和本机 Word/WPS COM 环境。
- 先看现有实现和同模块写法，再做最小必要改动；不要顺手重构、目录洗牌、批量改名或清理无关旧代码。
- 不回滚用户已有改动；不提交、不推送、不暂存，除非用户明确要求。
- `.env`、token不得进入文档、日志、测试夹具或最终回复。
- 验证是交付的一部分；能跑的检查必须跑，跑不了要说明原因和替代验证。

## 必守红线

- Word COM 写入只允许经过后端任务队列、graph 锁、取消检查和进度包装；不得在 API route、service、前端或随意脚本中直接操作 COM。
- 前端所有后端请求统一走 API client；组件不写裸 `fetch`，也不直接访问外部模板候选 URL。
- API shape、SSE、任务类型、招标类型、Prompt/LLM、Word helper、模板候选等跨层改动必须同步前后端模型、类型、客户端、测试和相关知识包。
- `generation_style`、`generation_mode`、`comment_generation_mode` 和 `style_writeback_mode` 是 generate-only 字段，不得进入 rewrite 请求模型、skill state 或 prompt surface。
- `gngk` 在前端只是一种 UI 类型；提交到后端时必须由共享 helper 按 `tender_lx + fund_lx + ifzgcg` 分派到具体 form type。
- 上传文件 rewrite 前端使用 `rewrite_source` 文件类型，后端 task skill state 用 `rewrite_source="uploaded_file"` 标记来源；不要恢复旧 edit 入口或把上传修改做成第二套任务链路。
- rewrite 任务由显式 `RewriteSkillGraph` 承载；不要恢复 `SkillGraph.for_skill + TaskSkillWorkflow` 元数据驱动框架。
- content agent 生成正文必须原样保留技术参数里的 `[[TABLE:<id>]]` 结构化表占位符；占位符校验集中在后端生成智能体工具层，不得改写为 Markdown/手绘表格或省略。
- Agent run 只负责任务创建前置流；审计日志和摘要工具只暴露 scrub 后白名单信息，不记录或返回完整客户原文、真实密钥、私有路径、traceback 或下载路径。

## 验证与维护

- 文档型变更至少运行 `git diff --check`，并扫描本轮改动文档中的密钥/token 模式；仅文档变更不需要跑代码测试或 E2E。
- 前端代码改动至少运行 lint、type-check 和相关测试；后端代码改动至少运行 pytest；Word COM 闭环需要 Windows + Word/WPS COM。
- 改动影响长期边界时，同步刷新对应 `.planning/codebase/`、`coding_maps/`、`docs/` 或 `asset/` 知识包。

## 详细文档

- [后端架构与约定](docs/backend.md)
- [前端架构与约定](docs/frontend.md)
- [接口与运行时契约](docs/interfaces-runtime.md)
- [知识回写与验证门槛](docs/knowledge-validation.md)

## 系统地图

- [架构地图](ARCHITECTURE.md)
- [接口边界](INTERFACES.md)
- [系统地图](coding_maps/SYSTEM_MAP.md)
- [长期知识包索引](asset/README.md)
- 子项目事实文档：`backend/.planning/codebase/`、`frontend/.planning/codebase/`
