# PRD: 国内公开货物自筹字段替换修复

## Introduction

国内公开货物自筹生成链路当前在模板字段识别上存在口径漂移：采购人只覆盖部分标签，预算金额没有独立的 `investment` 旧值来源，项目联系人可能把电话等联系方式拼入姓名，同时还保留了不属于该类型的历史特殊字段。该修复要求在不新增招标类型、不改变正文全局替换机制、不依赖真实接口的前提下，让模拟模板数据可以稳定生成正确替换对。

## Goals

- 国内公开货物自筹模板中 `采购人：xxx` 与 `招标人：xxx` 均可提取为 `buyer_name` 旧值。
- 从 `预算金额：450 万元（人民币）` 中只提取数字 `450` 作为 `investment` 旧值，不从“最高限价”反向提取。
- `investment` 新值格式稳定：`140.0` 输出为 `140`，有效小数保留。
- `project_zbr_xbr` 支持 `项目联系人：xxx` 与 `联系人：xxx`，且不会把电话、传真、邮箱等联系方式拼入姓名。
- 国内公开货物自筹替换字段列表和替换结果不再包含 `project_content_v1`、`similar_project_performance_date`。

## User Stories

### US-001: 支持采购人/招标人双标签提取

**描述：** 作为生成招标文件的用户，我想让国内公开货物自筹模板中的 `采购人` 或 `招标人` 都能被识别，以便新采购人名称可以准确替换模板旧值。

**Acceptance Criteria：**
- [ ] 模拟模板含 `采购人：复旦大学附属中山医院` 时，提取出的 `buyer_name` 旧值为 `复旦大学附属中山医院`。
- [ ] 模拟模板含 `招标人：复旦大学附属中山医院` 时，提取出的 `buyer_name` 旧值为 `复旦大学附属中山医院`。
- [ ] 同一份模拟模板中只需命中一种标签即可生成 `buyer_name` 替换对。
- [ ] 不新增招标类型，不改变 `gngk_hw_zc_tender` 的 graph 注册关系。
- [ ] Typecheck 通过。
- [ ] 相关后端单测通过。

### US-002: 新增预算金额 investment 替换口径

**描述：** 作为生成招标文件的用户，我想让系统从预算金额行提取旧金额，并使用新的预算金额替换模板中的相同数字，以便预算金额和正文中相同金额保持一致。

**Acceptance Criteria：**
- [ ] 模拟模板含 `预算金额：450 万元（人民币）` 时，提取出的 `investment` 旧值为 `450`。
- [ ] 模拟模板只含 `最高限价：450 万元` 且无预算金额行时，不生成 `investment` 旧值。
- [ ] 当新值为 `140.0` 时，生成的替换对新值为 `140`。
- [ ] 当新值为 `140.50` 或 `140.05` 时，生成的替换对保留有效小数为 `140.5` 或 `140.05`。
- [ ] 替换对只提供旧数字到新数字，正文中所有相同旧数字继续由现有全局替换机制处理。
- [ ] Typecheck 通过。
- [ ] 相关后端单测通过。

### US-003: 修复项目联系人姓名提取边界

**描述：** 作为生成招标文件的用户，我想让项目联系人只提取姓名，不混入电话、传真或邮箱，以便联系人替换不会污染字段内容。

**Acceptance Criteria：**
- [ ] 模拟模板含 `项目联系人：史倩倩、刘宇昂` 后接 `电话：...` 时，提取出的 `project_zbr_xbr` 为 `史倩倩、刘宇昂`。
- [ ] 模拟模板含 `联系人：史倩倩、刘宇昂` 后接 `电 话：...` 时，提取出的 `project_zbr_xbr` 为 `史倩倩、刘宇昂`。
- [ ] `电话`、`电 话`、`传真`、`邮箱`、`电子邮箱` 等联系方式标签及其内容不会进入 `project_zbr_xbr`。
- [ ] 现有 `zbr_xbr_tel`、`zbr_pinyin` 可继续按既有口径提取，不因联系人姓名边界修复而回归。
- [ ] Typecheck 通过。
- [ ] 相关后端单测通过。

### US-004: 移除货物自筹错误特殊字段

**描述：** 作为维护国内公开货物自筹链路的开发者，我想移除不属于该类型的历史特殊字段，以便替换列表与业务字段边界一致。

**Acceptance Criteria：**
- [ ] `GNGK_HW_ZC_EXTRACTORS` 中不再包含 `project_content_v1` 和 `similar_project_performance_date`。
- [ ] `GNGK_HW_ZC_REPLACEMENT_FIELDS` 中不再包含 `project_content_v1` 和 `similar_project_performance_date`。
- [ ] 使用模拟数据生成替换结果时，`placeholder_mapping` 与 `replacements` 均不包含上述两个字段。
- [ ] 现有 `project_content` 共享替换口径保持不变。
- [ ] Typecheck 通过。
- [ ] 相关后端单测通过。

### US-005: 模拟数据闭环验证与知识包同步

**描述：** 作为后续接手的开发者，我想看到字段提取、替换结果和知识包边界都被验证，以便不依赖真实接口也能确认修复完成。

**Acceptance Criteria：**
- [ ] 后端模拟数据测试覆盖 `buyer_name`、`investment`、`project_zbr_xbr` 三类替换对。
- [ ] 后端模拟数据测试证明 `investment` 只从预算金额行提取，不从最高限价行提取。
- [ ] 后端测试证明错误特殊字段不在货物自筹替换字段列表或替换结果中。
- [ ] `asset/README.md` 与相关知识包更新国内公开货物自筹字段替换边界。
- [ ] 不调用真实接口，不依赖 Word 真实文档即可完成核心单元验证。
- [ ] Typecheck 通过。
- [ ] 相关后端单测通过。

## Functional Requirements

- FR-1: 系统必须在国内公开货物自筹替换链路中支持从 `采购人：xxx` 或 `招标人：xxx` 提取 `buyer_name` 旧值。
- FR-2: 系统必须新增 `investment` 字段作为预算金额替换字段，并将其纳入生成 state 与替换字段列表。
- FR-3: 系统必须只从 `预算金额` 标签所在行提取 `investment` 旧数字，不得从 `最高限价` 标签反向提取。
- FR-4: 系统必须将 `investment` 新值格式化为去除无效尾零的普通十进制字符串。
- FR-5: 系统必须让 `project_zbr_xbr` 同时支持 `项目联系人` 与 `联系人` 标签，并在联系方式标签前停止。
- FR-6: 系统必须从国内公开货物自筹提取器和替换字段列表中移除 `project_content_v1`、`similar_project_performance_date`。
- FR-7: 系统不得改变现有正文全局替换机制；旧数字到新数字的替换范围仍由现有 `replace_content` 链路决定。
- FR-8: 系统必须用模拟数据测试覆盖提取器、替换字段列表和生成替换对结果。
- FR-9: 系统必须同步更新相关长期知识包，记录新的字段边界与验证入口。

## Non-Goals

- 不新增新的招标类型、graph、前端大类或后端 `FormType`。
- 不把“最高限价”改造成独立字段。
- 不改变现有正文全局替换机制。
- 不要求真实接口、真实外部数据或真实 Word 文档参与验收。
- 不调整前端 UI 文案、URL 会话身份或模板候选链路。

## Technical Considerations

- 国内公开货物自筹 graph 当前通过 `GngkHwZcTenderGraph` 使用 `gngk_hw_zc_get_replacements`。
- `gngk_hw_cz` 当前也复用 `gngk_hw_zc_get_replacements`，实现时需避免无意改变财政货物行为，或用测试明确锁定共享 wrapper 的当前影响面。
- `run_get_replacements` 当前根据提取器返回的 `placeholder_mapping` 和字段列表生成 `(old_value, new_value)` 替换对；本需求应复用该机制。
- 若新增 `investment` 进入 `TenderData` / state，需要同步后端模型、服务初始 state、前端 API 类型和相关测试 fixture。

## Success Metrics

- 模拟数据能稳定生成 `buyer_name`、`investment`、`project_zbr_xbr` 三类替换对。
- 预算金额提取不误命中最高限价。
- 联系人姓名提取不包含电话、传真、邮箱等联系方式。
- 货物自筹替换字段列表中错误特殊字段为 0 个。
- 后端相关单测全部通过，且不依赖真实接口。

## Open Questions

- 无。
