# 功能: 国内公开货物自筹字段替换修复

下面这份计划应尽可能完整，但在真正开始实现前，你仍然必须再次验证文档、代码库模式以及任务本身是否合理。

特别注意现有 utils、types、models 的命名，并确保从正确的文件中导入。

## 功能描述

修复国内公开货物自筹 `gngk_hw_zc_tender` 生成链路中的字段替换口径：采购人支持 `采购人/招标人` 双标签，预算金额新增 `investment` 字段并只从 `预算金额` 行提取旧数字，项目联系人支持 `项目联系人/联系人` 且不吞入联系方式，同时移除 `project_content_v1` 与 `similar_project_performance_date` 两个不属于该类型的历史特殊字段。

## 用户故事

作为一名招标文件生成用户，我想让国内公开货物自筹模板中的采购人、预算金额和项目联系人被正确识别和替换，以便生成文档时关键字段不会漏替换或错替换。

## 问题陈述

当前国内公开货物自筹替换链路复用了公开招标 common extractor，但字段边界与目标业务不一致：`buyer_name` 只按 `招标人` 模式识别，`investment` 不在 state/model/replacement 字段中，联系人姓名提取容易被联系方式污染，货物自筹 wrapper 还显式插入了 `project_content_v1` 与 `similar_project_performance_date` 历史特殊字段。

## 方案陈述

在不新增招标类型、不改变正文全局替换机制的前提下，沿用 `run_get_replacements` 的提取器 + replacement field spec 模式做局部修正：补齐 `investment` 数据契约与提取器，扩展公共采购人和联系人提取 helper，清理 `gngk_hw_zc_get_replacements` 中的错误特殊字段，并用纯模拟文本/伪 Word 文档测试锁定替换结果。

## 功能元数据

**功能类型**: 缺陷修复  
**预估复杂度**: 中  
**主要受影响系统**: 后端字段模型、DocumentService 初始 state、公开招标 replacement 节点、后端单测、前端 API 类型、asset 知识包  
**依赖项**: 无新增外部依赖

---

## 上下文参考

### 相关代码文件 重要：实现前你必须先阅读这些文件！

- `backend/nodes/gngk_word_nodes/gngk_hw_zc_get_replacements.py` (lines 24-155) - 当前货物自筹 wrapper 显式定义 `project_content_v1`、`similar_project_performance_date` 提取器和替换字段，是本次移除的核心位置。
- `backend/nodes/gngk_word_nodes/gngk_get_replacements.py` (lines 135-202) - 公开招标 common extractor 与 replacement field 构建器，`gngk_hw_zc` 复用这里的大部分字段。
- `backend/nodes/common_word_nodes/get_replacements_shared.py` (lines 303-339) - `extract_public_tender_buyer_name` 当前只围绕 `招标人` 搜索，需要兼容 `采购人`。
- `backend/nodes/common_word_nodes/get_replacements_shared.py` (lines 497-630) - `extract_public_tender_contact_fields` 当前处理联系人、电话、邮箱等字段，需要收紧 `project_zbr_xbr` 边界。
- `backend/nodes/common_word_nodes/get_replacements_shared.py` (lines 633-655) - common replacement 字段列表当前没有 `investment`。
- `backend/nodes/common_word_nodes/get_replacements_core.py` (lines 213-300) - 提取器执行与 replacement pair 生成真源；本需求应复用，不改正文全局替换机制。
- `backend/states/base_state.py` (lines 85-97) - 生成 state 的公共业务字段当前没有 `investment`。
- `backend/models/tender.py` (lines 57-101) - `TenderData` 当前没有 `investment`，需要补 optional 字段和 schema 示例。
- `backend/services/document_service.py` (lines 55-78, 740-759) - relevant state keys 与 generate 初始 state 当前没有 `investment`。
- `backend/util/common_util/fetch_tender_data.py` (lines 120-129) - 真实接口字段归一化当前未透传 `investment`，本需求虽然不依赖真实接口，但数据契约应保持一致。
- `frontend/types/api.ts` (lines 18-36) - 前端 `TenderData` 类型当前没有 `investment`。
- `backend/tests/nodes/test_gngk_replacements_extractors.py` (lines 115-180) - 现有公开招标字段提取测试和货物/服务字段边界测试，应在这里扩展或拆分新测试。
- `asset/README.md` - 知识包索引；字段替换边界更新时需要回看索引。
- `asset/tender_type_identity_session_knowledge_pack.md` (lines 102-118) - 记录 graph / replacement wrapper 当前事实。
- `asset/shared_runtime_word_skill_knowledge_pack.md` - 记录共享 Word / replacement / 验证入口相关长期边界。

### 需要创建的新文件

- 不需要新增业务源码文件。
- 如测试体量明显增大，可新增 `backend/tests/nodes/test_gngk_hw_zc_field_replacements.py`，文件名必须以 `test_` 开头。

### 相关文档 实现前你应该先阅读这些文档！

- `AGENTS.md` - 特别关注 Word COM、日志/SSE、前后端调用、知识包和测试命名约束。
- `asset/README.md` - 判断本次知识回写应落入哪个知识包。
- `asset/tender_type_identity_session_knowledge_pack.md` - 本次改动涉及 `gngk_hw_zc` replacement 字段边界。
- `asset/shared_runtime_word_skill_knowledge_pack.md` - 本次改动涉及共享 replacement 与 Word 运行时验证入口。

### 需要遵循的模式

**提取器模式：** 使用 `ExtractorSpec(name, enabled_if, extract_callable, output_field_names)` 注册字段提取，不在 `run_get_replacements` 里写类型专属分支。

**替换字段模式：** 使用 `ReplacementFieldSpec(field_name, skip_if_equal=True, fallback_fields=None)` 控制 replacement pair 生成；新增 `investment` 应和其它普通字段一样进入字段 spec。

**数据契约同步：** 生成 state 字段需要同步 `TenderData`、`TenderGraphStateBase`、`DocumentService` 初始 state、前端 `TenderData` 类型和测试 fixture。

**验证模式：** 核心逻辑用模拟文本测试提取器；替换 pair 用 monkeypatch/fake Word 文档或纯 helper 测试，不调用真实接口。

**知识包模式：** 只记录稳定字段边界、同步面、验证入口和回归风险，不记录一次性排障过程。

---

## 实现计划

### 阶段 1：补齐 investment 数据契约

**任务：**

- 在后端 `TenderData`、state、DocumentService 初始 state 和相关示例中补 `investment`。
- 在前端 `TenderData` 类型和 mock/test fixture 中补 optional `investment`，避免类型漂移。
- 在 `fetch_tender_data.py` 中透传 `investment`，但验收不依赖真实接口。

### 阶段 2：修复提取器和替换字段

**任务：**

- 扩展 `extract_public_tender_buyer_name`，支持 `采购人` 与 `招标人`。
- 新增 `extract_public_tender_investment` 或同等 helper，只从 `预算金额` 行提取数字。
- 新增金额格式化 helper，输出普通十进制字符串并去掉无效尾零。
- 收紧 `extract_public_tender_contact_fields` 中 `project_zbr_xbr` 的姓名截断边界。
- 清理 `GNGK_HW_ZC_EXTRACTORS` 和 `GNGK_HW_ZC_REPLACEMENT_FIELDS` 中两个错误特殊字段。

### 阶段 3：测试与知识包同步

**任务：**

- 用模拟文本覆盖采购人/招标人、预算金额/最高限价、项目联系人/联系人。
- 用伪 Word 文档或 monkeypatch 验证 `gngk_hw_zc_get_replacements` 输出替换对。
- 更新现有测试中关于 `project_content_v1` 与 `similar_project_performance_date` 的断言方向。
- 更新 `asset/README.md` 和对应知识包，记录国内公开货物自筹字段替换边界。

---

## 分步任务

重要：严格按顺序执行所有任务，从上到下。每个任务都必须是原子性的，并且可独立测试。

### UPDATE `backend/models/tender.py`

- **IMPLEMENT**: 给 `TenderData` 增加 `investment: str = Field(default="", description="预算金额")`，并更新 `model_config` 示例。
- **PATTERN**: 参考同文件 `buyer_name`、`service_fee` 字段写法。
- **GOTCHA**: 不把最高限价建成独立字段；`investment` 表示预算金额。
- **VALIDATE**: `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/models -v`

### UPDATE `backend/states/base_state.py`

- **IMPLEMENT**: 在公共业务字段中加入 `investment: str`，位置靠近 `project_content` / `buyer_name` 等基础字段。
- **PATTERN**: 保持 `TenderGraphStateBase` 只声明共享 state 字段，不写业务逻辑。
- **GOTCHA**: 不在 `GngkTenderGraphState` 中只做类型专属隐式字段，否则 replacement common core 无法统一读取。
- **VALIDATE**: `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/services/test_document_service_initial_state.py -v`

### UPDATE `backend/services/document_service.py`

- **IMPLEMENT**: 将 `investment` 加入 relevant state keys，并在 generate/edit 初始 state 装配中从 `tender_data` 安全读取。
- **PATTERN**: 参考 `buyer_name`、`service_fee` 的 `getattr(..., "")` 和 `.strip()` 处理。
- **GOTCHA**: `generation_style` 仍是 generate-only 字段，不要顺手改 rewrite/edit prompt surface。
- **VALIDATE**: `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/services/test_document_service_initial_state.py -v`

### UPDATE `frontend/types/api.ts` and frontend fixtures

- **IMPLEMENT**: 给前端 `TenderData` 增加可选 `investment?: string`，并更新受影响 mock/fixture。
- **PATTERN**: 参考 `ifdzpt2?: number`、`fund_source_lx?: number` 这类向后兼容字段。
- **GOTCHA**: 不改 UI 表单结构，除非测试发现现有表单数据类型必须显式包含该字段。
- **VALIDATE**: `cd frontend; npm run type-check`

### UPDATE `backend/util/common_util/fetch_tender_data.py`

- **IMPLEMENT**: 在接口返回数据归一化时透传 `investment`，缺失时为空字符串。
- **PATTERN**: 参考 `buyer_name`、`project_zbr_xbr` 的 `data.get(...)`。
- **GOTCHA**: 本需求不调用真实接口验收，但契约透传不能漏。
- **VALIDATE**: `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/util/test_fetch_tender_data.py -v`

### UPDATE `backend/nodes/common_word_nodes/get_replacements_shared.py`

- **IMPLEMENT**: 扩展 `extract_public_tender_buyer_name`，按 `采购人` 和 `招标人` 两类标签提取到下一业务标签前。
- **IMPLEMENT**: 新增预算金额提取 helper，只扫描包含 `预算金额` 标签的行，提取第一个数字并规范化旧值。
- **IMPLEMENT**: 新增新值格式化 helper，让 `140.0` -> `140`，有效小数保留。
- **IMPLEMENT**: 收紧 `extract_public_tender_contact_fields` 中 `project_zbr_xbr` 的 regex，支持 `项目联系人` / `联系人`，并在 `电话`、`电 话`、`传真`、`邮箱`、`电子邮箱` 等标签前停止。
- **PATTERN**: 继续使用纯函数 + `log_parts.append(...)` 的现有 extractor 风格。
- **GOTCHA**: 不在 helper 中调用 Word COM；不把 `最高限价` 当成 `investment` 来源。
- **VALIDATE**: `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/nodes/test_gngk_replacements_extractors.py -v`

### UPDATE `backend/nodes/common_word_nodes/get_replacements_shared.py`

- **IMPLEMENT**: 将 `investment` 加入 `COMMON_REPLACEMENT_FIELD_NAMES`，位置建议靠近 `project_content` 或 `buyer_name`。
- **PATTERN**: 所有普通公开招标 replacement fields 通过 `build_common_replacement_fields()` 生成。
- **GOTCHA**: 如果只想影响 `gngk_hw_zc`，不要把 `investment` 放进所有公开招标 common fields；可改为只在 `gngk_hw_zc_get_replacements.py` 注入字段。实施前按代码影响面选择并用测试锁定。
- **VALIDATE**: `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/nodes/test_gngk_replacements_extractors.py -v`

### UPDATE `backend/nodes/gngk_word_nodes/gngk_hw_zc_get_replacements.py`

- **IMPLEMENT**: 移除 `extract_project_content_v1`、`extract_similar_project_performance_date` 及其 `ExtractorSpec` / `ReplacementFieldSpec` 注册；保留 `gngk_hw_zc_get_replacements` 真名。
- **PATTERN**: 向 `gngk_fw_zc_get_replacements.py` 靠拢，保持 wrapper 薄封装。
- **GOTCHA**: `GngkHwCzTenderGraph` 当前复用该 replacement wrapper；如果财政货物仍需历史特殊字段，必须先拆出财政 wrapper，不要让静态字段表无意影响两个类型。
- **VALIDATE**: `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/graphs/test_gngk_tender_graph.py backend/tests/nodes/test_gngk_replacements_extractors.py -v`

### UPDATE `backend/tests/nodes/test_gngk_replacements_extractors.py`

- **IMPLEMENT**: 增加采购人/招标人双标签测试、预算金额/最高限价负例测试、项目联系人/联系人截断测试。
- **IMPLEMENT**: 将历史断言从“货物自筹包含 `project_content_v1` / `similar_project_performance_date`”改为“不包含”。
- **IMPLEMENT**: 增加模拟替换结果测试，断言 `replacements` 包含 `buyer_name`、`investment`、`project_zbr_xbr` 对应 pair。
- **PATTERN**: 复用现有 `SCREENSHOT_SHAPED_DOC` 和直接调用 extractor 的测试风格；需要完整 replacement pair 时 monkeypatch Word COM 读取。
- **GOTCHA**: 不使用真实接口；不依赖真实 Word 文件。
- **VALIDATE**: `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/nodes/test_gngk_replacements_extractors.py -v`

### UPDATE `asset/README.md` and knowledge pack

- **IMPLEMENT**: 在相关知识包中记录 `gngk_hw_zc` 字段替换边界：`buyer_name` 双标签、`investment` 预算金额来源、`project_zbr_xbr` 联系方式截断、两个历史特殊字段移除。
- **PATTERN**: `asset/README.md` 只更新索引/适用范围；稳定规则写进 `asset/tender_type_identity_session_knowledge_pack.md` 或 `asset/shared_runtime_word_skill_knowledge_pack.md`。
- **GOTCHA**: 不记录临时样本文档路径、一次性排障过程或尚未验证的猜测。
- **VALIDATE**: 人工校对引用路径均真实存在。

---

## 测试策略

### 单元测试

- 直接测试 `extract_public_tender_buyer_name` 的 `采购人` / `招标人` 输入。
- 直接测试预算金额 helper：预算金额正例、最高限价负例、无效数字负例、尾零格式化。
- 直接测试 `extract_public_tender_contact_fields`：`项目联系人`、`联系人`、`电话`、`电 话`、`传真`、`邮箱` 截断。
- 测试 `GNGK_HW_ZC_EXTRACTORS` 和 `GNGK_HW_ZC_REPLACEMENT_FIELDS` 的字段列表。

### 集成测试

- 使用 mock 文档内容驱动 `gngk_hw_zc_get_replacements`，验证 `placeholder_mapping` 与 `replacements`。
- 覆盖 `DocumentService._build_initial_state()` 是否写入 `investment`。
- 覆盖 `fetch_tender_data()` 对 `investment` 的透传。

### 边界情况

- 模板只有 `最高限价` 没有 `预算金额`。
- `预算金额：140.0 万元`、`预算金额：140.50 万元`。
- `项目联系人：史倩倩、刘宇昂` 下一行是 `电话`、`电 话`、`传真`、`邮箱`。
- `采购人` 或 `招标人` 后面跟 `招标代理机构`、`采购代理机构` 或换行。
- `project_content_v1` 与 `similar_project_performance_date` 即使出现在 state 中也不生成货物自筹替换对。

---

## 验证命令

执行所有命令，确保零回归与功能 100% 正确。

### 级别 1：语法与风格

```powershell
backend\.venv\Scripts\python.exe -m compileall backend\nodes\common_word_nodes backend\nodes\gngk_word_nodes backend\models backend\services
```

### 级别 2：后端单元测试

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/nodes/test_gngk_replacements_extractors.py -v
backend\.venv\Scripts\python.exe -m pytest backend/tests/services/test_document_service_initial_state.py backend/tests/util/test_fetch_tender_data.py -v
backend\.venv\Scripts\python.exe -m pytest backend/tests/graphs/test_gngk_tender_graph.py -v
```

### 级别 3：前端类型验证

```powershell
cd frontend
npm run type-check
```

### 级别 4：全量回归建议

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests -v
cd frontend
npm run lint
npm run test
```

### 级别 5：手动验证

- 用模拟 state 和模拟模板文本验证 `replacements` 至少包含：
  - `("复旦大学附属中山医院", "<新采购人>")`
  - `("450", "140")`
  - `("史倩倩、刘宇昂", "<新联系人>")`
- 验证 `project_content_v1`、`similar_project_performance_date` 不在字段列表、`placeholder_mapping` 或 `replacements` 中。

---

## 验收标准

- [ ] 功能实现了所有指定需求。
- [ ] `buyer_name` 可从 `采购人` 或 `招标人` 提取。
- [ ] `investment` 只从 `预算金额` 行提取旧数字，不从 `最高限价` 提取。
- [ ] `investment` 新值格式去除无效尾零并保留有效小数。
- [ ] `project_zbr_xbr` 不包含电话、传真、邮箱等联系方式。
- [ ] `project_content_v1` 与 `similar_project_performance_date` 不再出现在国内公开货物自筹替换字段列表或替换结果。
- [ ] 不新增招标类型，不改变正文全局替换机制。
- [ ] 模拟数据测试通过，不依赖真实接口。
- [ ] 相关知识包已更新。

---

## 完成检查清单

- [ ] 所有任务均已按顺序完成。
- [ ] 每个任务的验证都已立即通过。
- [ ] 所有验证命令都已成功执行。
- [ ] 无 lint 或类型检查错误。
- [ ] 验收标准全部满足。
- [ ] 已完成代码质量与可维护性审查。
- [ ] 交付说明包含经验回写说明。

---

## 备注

一次实现成功信心分数：8/10。主要风险是 `gngk_hw_cz` 当前复用 `gngk_hw_zc_get_replacements`，清理货物自筹字段时必须明确共享 wrapper 的实际影响面，并用测试锁住不想改变的类型行为。
