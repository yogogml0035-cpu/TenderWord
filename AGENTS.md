# TenderWord 智能体操作指南

TenderWord 是招标文档生成、修改、补充批注和模板复用系统；前端是 Next.js 工作台，后端是 FastAPI + LangGraph + Word COM 任务执行端。

## 关键约定

- 代码是真源；根级文档只做导航和稳定规则沉淀。
- 前端包管理器是 npm；后端依赖以 `backend/requirements.txt` 为准。
- 完整 Word 生成验收必须回到 Windows Python、pywin32 和本机 Word/WPS COM 环境。
- 先看现有实现和同模块写法，再做最小必要改动；不要顺手重构、目录洗牌、批量改名或清理无关旧代码。
- 不回滚用户已有改动；不提交、不推送、不暂存，除非用户明确要求。
- `.env`、token、客户原文、私有路径和真实密钥不得进入文档、日志、测试夹具或最终回复。
- 验证是交付的一部分；能跑的检查必须跑，跑不了要说明原因和替代验证。

## 必守红线

- Word COM 写入只允许经过后端任务队列、graph 锁、取消检查和进度包装；不得在 API route、service、前端或随意脚本中直接操作 COM。
- 前端所有后端请求统一走 API client；组件不写裸 `fetch`，也不直接访问外部模板候选 URL。
- API shape、SSE、任务类型、招标类型、Prompt/LLM、Word helper、模板候选等跨层改动必须同步前后端模型、类型、客户端、测试和相关知识包。
- `generation_style`、`generation_mode`、`comment_generation_mode` 和 `style_writeback_mode` 是 generate-only 字段，不得进入 rewrite 请求模型、skill state 或 prompt surface。
- `gngk` 在前端只是一种 UI 类型；提交到后端时必须由共享 helper 按 `tender_lx + fund_lx + ifzgcg` 分派到具体 form type。

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
