# 功能: 国内公开货物财政无保护字段模板生成

下面这份计划应尽可能完整，但在真正开始实现前，你仍然必须再次验证文档、代码库模式以及任务本身是否合理。

特别注意现有 graph、node、config、tests 的命名，并确保从正确的 `backend.*` 包路径导入。

## 功能描述

让现有“国内公开 + 货物 + 财政”首次生成链路支持无保护字段模板：保留前后章节锚点，清空“第四章 招标需求”到“第五章 评标方法与程序”之间的旧正文，并在第四章标题下方同页插入 AI 生成正文。默认仍为模板优先生成，继续支持样式回填、任务状态、SSE 完成和下载结果。本轮不扩展 rewrite / edit。

## 用户故事

作为一名招标文件生成用户，  
我想要在国内公开货物财政模式下使用无保护字段模板完成首次生成，  
以便即使模板中没有 `交付日期`、`付款方式` 等受保护字段，也能生成并下载正确的招标文件。

## 问题陈述

当前 `GngkHwCzTenderGraph` 继承 `GngkHwZcTenderGraph`，因此仍使用 common `delete_tender_param` / `update_word` 的受保护字段流程。该流程要求 common two-field profile，并会围绕 `交付日期：`、`付款方式：` 做保留和写回。用户给出的财政货物模板正文区可以直接编辑，没有需要保留的受保护字段；继续走 common 流程会产生错误边界和失败风险。

## 方案陈述

将 `gngk_hw_cz` 配置为 direct replace 类型，并为 `gngk_hw_cz_tender_graph.py` 显式绑定财政货物专用 direct replace delete / update 节点。节点行为参考 `gjgk_delete_tender_param.py` 和 `gjgk_update_word.py` 的整段清空、同页插入、样式回填和保存路径，但 tender_type、锚点、字号和 state 类型保持 `gngk_hw_cz` / `GngkTenderGraphState`。继续复用 `gngk_hw_zc_get_replacements`，不新增前端类型，不改 rewrite / edit 分发。

## 功能元数据

**功能类型**: 增强 / 缺陷修复  
**预估复杂度**: 中  
**主要受影响系统**: 后端 graph、Word node、tender config、后端测试、asset 知识包  
**依赖项**: 现有 FastAPI / LangGraph / Word COM / pytest；不新增依赖

---

## 上下文参考

### 相关代码文件

- `backend/graphs/gngk_hw_cz_tender_graph.py` (lines 1-11) - 当前财政货物 graph 只继承货物自筹，是本次要显式覆盖节点的入口。
- `backend/graphs/gngk_hw_zc_tender_graph.py` (lines 25-39) - 货物自筹 graph 的共享主干和当前 inherited 节点绑定；财政货物仍应复用其 replacement wrapper。
- `backend/graphs/gjgk_tender_graph.py` (lines 25-48) - direct replace graph 模式：delete / replacement 在 word operation steps，update 后再 post-update replace_content。
- `backend/config/tender_config.py` (lines 12-26, 90-95, 114-120, 173-180) - content start mode、content update mode、财政货物锚点和字号配置真源。
- `backend/util/word_util/anchor_utils.py` (lines 29-46, 257-307, 337-420) - 锚点空格变体、双字号查找和 content range 解析；财政货物同页插入需要使用 same-page start mode。
- `backend/nodes/gjgk_word_nodes/gjgk_delete_tender_param.py` (lines 48-201) - 可参考的 direct replace 删除节点，但不能硬复用 `tender_type = "gjgk"`。
- `backend/nodes/gjgk_word_nodes/gjgk_update_word.py` (lines 111-146, 602-760) - 可参考的同页 direct replace 插入、Markdown 表格解析、样式回填路径。
- `backend/nodes/gngk_word_nodes/__init__.py` (lines 1-38) - gngk 专属节点 re-export 位置；新增财政货物专属节点后需要导出。
- `backend/services/document_service.py` (lines 80-90, 187-209, 713-782) - graph registry、rewrite 默认锚点和 generate 初始 state 构造。不要扩大到 rewrite / edit。
- `frontend/lib/formDataConverter.ts` (lines 70-76) - 前端 generate 已将国内公开货物财政映射到 `gngk_hw_cz_tender`，本轮应保持不变。
- `frontend/components/chat/ChatPanel.tsx` (lines 100-108) - edit form_type 分派存在但本轮不改 rewrite / edit。
- `frontend/components/forms/TenderFormShared.tsx` (lines 97-103) - 前端财政货物默认锚点已是第四章到第五章；本轮不改 UI。
- `asset/shared_runtime_word_skill_knowledge_pack.md` (lines 68-105) - 受保护字段、direct replace、样式回填和 SSE 结果契约知识包。
- `asset/tender_type_identity_session_knowledge_pack.md` (lines 86-117) - 当前类型锚点和 graph/node 分流事实，需要更新财政货物 direct replace 现实。
- `backend/tests/graphs/test_gngk_tender_graph.py` (lines 28-60) - graph 节点绑定和 registry 路由测试，需要更新 expected update 并补 delete 断言。
- `backend/tests/config/test_tender_config_protected_fields.py` (lines 8-29) - 当前断言 `gngk_hw_cz` 使用 common two-field，需要改为 direct replace 不支持 profile。
- `backend/tests/services/test_document_service_initial_state.py` (lines 116-210) - 默认锚点测试，预计保持通过。

### 需要创建的新文件

- `backend/nodes/gngk_word_nodes/gngk_hw_cz_delete_tender_param.py` - 财政货物 direct replace 删除节点。
- `backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py` - 财政货物 direct replace 同页写回节点，保留样式回填摘要。
- `backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py` - 财政货物节点的纯逻辑/猴补丁测试，覆盖同页 range、direct replace mode、样式摘要回写。

### 需要更新的文件

- `backend/config/tender_config.py`
- `backend/graphs/gngk_hw_cz_tender_graph.py`
- `backend/nodes/gngk_word_nodes/__init__.py`
- `backend/tests/graphs/test_gngk_tender_graph.py`
- `backend/tests/config/test_tender_config_protected_fields.py`
- `asset/shared_runtime_word_skill_knowledge_pack.md`
- `asset/tender_type_identity_session_knowledge_pack.md`
- `asset/README.md`（如索引描述需要同步）

### 相关文档

- `AGENTS.md` - 仓库级执行规则，尤其是 Word COM、gngk 类型身份、知识包和测试命名约束。
- `ARCHITECTURE.md` - 系统边界和 generate 主链路。
- `INTERFACES.md` - `GenerateRequest.form_type`、任务 SSE、类型身份接口。
- `backend/.planning/codebase/ARCHITECTURE.md` - 后端 graph / node / helper 分层。
- `backend/.planning/codebase/CONVENTIONS.md` - 后端导入、命名、测试放置和 Word COM 约定。

### 需要遵循的模式

**Graph 命名与绑定：**

- 新 graph 仍继承 `GngkHwZcTenderGraph`，但财政货物应像 `GngkFwZcTenderGraph` 一样只覆盖差异节点。
- node callable 使用类型前缀：`gngk_hw_cz_delete_tender_param`、`gngk_hw_cz_update_word`。

**配置真源：**

- 锚点、字号、content update mode 必须从 `backend/config/tender_config.py` 读取。
- `gngk_hw_cz` 前锚点保持 `第四章  招标需求`，后锚点保持 `第五章  评标方法与程序`，字号保持 `22.0`。
- `anchor_utils` 已支持空格变体和 normalize space，不要在节点里手写另一套锚点模糊匹配。

**Word COM 边界：**

- 节点可以执行 Word 操作，但必须使用 `create_word_application`、`open_document_with_retry`、`save_document_with_retry`、`close_word_application`。
- 不要在 API route、service 或前端写 COM 调用。
- 不绕过 graph 队列、锁、取消检查和进度包装。

**样式回填：**

- 直接参考 `gjgk_update_word` 的 `apply_inline_style_fragments` 与 `summarize_style_writeback_result` 调用方式。
- 生成正文基础插入格式应是干净黑色正文，再由安全样式回填叠加。
- 黄色可编辑区域提示不应被当成必须继承的高亮。

**范围控制：**

- 本轮只改 generate graph 路径。
- 不改 `backend/nodes/skills_nodes/tender_aware_word_dispatch.py`，避免 rewrite / edit 范围扩张。

---

## 实现计划

### 阶段 1：配置 direct replace 边界

将 `gngk_hw_cz` 的 content update mode 从默认 `protected_fields` 调整为 `direct_replace`，并通过测试固定其不支持受保护字段 profile。

### 阶段 2：财政货物 direct replace 节点

新增 `gngk_hw_cz_delete_tender_param` 和 `gngk_hw_cz_update_word`。实现时以 `gjgk` 节点为参考，但所有 tender_type、节点名、日志名、state 类型和锚点配置都使用 `gngk_hw_cz`。

### 阶段 3：graph 接入

更新 `GngkHwCzTenderGraph`，保留 `gngk_hw_zc_get_replacements`，覆盖 delete / update 节点。确认 registry 和标准 graph 工作流仍保留 extract -> delete -> replacement -> replace_content -> generate -> update 的首次生成闭环。

### 阶段 4：测试与知识包

更新 graph / config 测试，新增节点单元测试，更新 `asset/` 知识包。最后执行后端相关测试；真实 Word COM 验收需在 Windows 环境执行。

---

## 分步任务

### UPDATE `backend/config/tender_config.py`

- **IMPLEMENT**: 给 `ANCHOR_CONFIGS["gngk_hw_cz"]` 显式设置 `content_start_mode=CONTENT_START_MODE_SAME_PAGE_AFTER_ANCHOR` 和 `content_update_mode=CONTENT_UPDATE_MODE_DIRECT_REPLACE`。
- **PATTERN**: `gjgk` 配置已经在 `backend/config/tender_config.py:114-120` 同时设置 same-page 和 direct-replace。
- **GOTCHA**: 不要改 `gngk_cz` 或 `gngk_fw_cz`，除非代码事实证明它们也应变更；用户本轮只确认 `gngk_hw_cz`。
- **VALIDATE**: `cd backend && TMPDIR=/tmp python -m pytest tests/config/test_tender_config_protected_fields.py -v`

### CREATE `backend/nodes/gngk_word_nodes/gngk_hw_cz_delete_tender_param.py`

- **IMPLEMENT**: 基于 `gjgk_delete_tender_param.py` 创建财政货物删除节点：
  - public callable 名称为 `gngk_hw_cz_delete_tender_param`。
  - `NODE_NAME = "gngk_hw_cz_delete_tender_param"`。
  - `tender_type` 从 state 读取，默认 `gngk_hw_cz`，但只允许 direct_replace mode；错误消息指向财政货物节点。
  - 使用 `get_anchor_target_sizes(tender_type)`，即 `22.0 / 22.0`。
  - 使用 `find_anchor_range(... prefer_before="last", prefer_after="first")`。
  - 使用 `resolve_anchor_content_range(... tender_type=tender_type, allow_empty=True)`，依赖配置中的 same-page start mode。
  - 删除 `range_start` 到 `range_end`，保存并关闭 Word。
- **PATTERN**: `backend/nodes/gjgk_word_nodes/gjgk_delete_tender_param.py:48-201`。
- **IMPORTS**: 使用 `backend.*` 绝对导入。
- **GOTCHA**: 不要硬写 `tender_type = "gjgk"`；否则会使用国际公开锚点和字号。
- **VALIDATE**: `cd backend && TMPDIR=/tmp python -m pytest tests/nodes/test_gngk_hw_cz_direct_replace_word.py -v`

### CREATE `backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py`

- **IMPLEMENT**: 基于 `gjgk_update_word.py` 创建财政货物同页写回节点：
  - public callable 名称为 `gngk_hw_cz_update_word`。
  - `NODE_NAME = "gngk_hw_cz_update_word"`。
  - 使用 `GngkTenderGraphState` 或 `TenderGraphStateBase` 类型，返回同类 state dict。
  - 读取 `prepared_doc_path`、`polished_text`、`insertion_before_text`、`insertion_after_text`、`tender_type`。
  - 定位前后锚点后解析 same-page content range。
  - 清理旧正文残留后，在 `range_start` 附近寻找可编辑同页插入点。
  - 按 `gjgk_update_word` 的 `_build_insert_items` 逻辑处理普通文本、空行和 Markdown 表格。
  - 插入正文后执行 `apply_inline_style_fragments` 和 `summarize_style_writeback_result`，把 `style_writeback_result` 与 `style_writeback_summary` 写回 state。
  - 保留批注写回硬失败契约，如直接复制 gjgk 路径，需保持 `write_polished_comments` 结果字段不丢失。
- **PATTERN**: `backend/nodes/gjgk_word_nodes/gjgk_update_word.py:111-146`、`backend/nodes/gjgk_word_nodes/gjgk_update_word.py:602-760`。
- **IMPORTS**: 从 `backend.helper.word_helper.*` 和 `backend.util.word_util.*` 绝对导入。
- **GOTCHA**: 黄色可编辑区域提示不是正文高亮，样式回填应由现有安全门禁决定是否应用。
- **GOTCHA**: 不要使用 common `split_polished_text_into_blocks()`，因为它要求交付日期和付款方式字段。
- **VALIDATE**: `cd backend && TMPDIR=/tmp python -m pytest tests/nodes/test_gngk_hw_cz_direct_replace_word.py tests/nodes/test_update_word_inline_style_writeback.py -v`

### UPDATE `backend/nodes/gngk_word_nodes/__init__.py`

- **IMPLEMENT**: re-export `gngk_hw_cz_delete_tender_param` 和 `gngk_hw_cz_update_word`，并加入 `__all__`。
- **PATTERN**: 当前 gngk 目录已 re-export `gngk_fw_zc_*` 和 `gngk_hw_zc_get_replacements`。
- **GOTCHA**: 不要新增无类型前缀的 generic callable。
- **VALIDATE**: `cd backend && TMPDIR=/tmp python -m pytest tests/graphs/test_gngk_tender_graph.py -v`

### UPDATE `backend/graphs/gngk_hw_cz_tender_graph.py`

- **IMPLEMENT**: 显式覆盖财政货物节点：
  - `NODE_DELETE_TENDER_PARAM = gngk_hw_cz_delete_tender_param`
  - `NODE_GET_REPLACEMENTS = gngk_hw_zc_get_replacements`
  - `NODE_UPDATE_WORD = gngk_hw_cz_update_word`
  - 必要时覆盖 `get_word_operation_steps()` / `get_post_update_steps()` 以保持 direct replace 流程和 `gjgk` 一致；如果标准 workflow 已能按 delete -> replacements -> replace_content -> generate -> update 正确执行，则不额外覆盖。
- **PATTERN**: `backend/graphs/gngk_fw_zc_tender_graph.py` 的差异节点覆盖；`backend/graphs/gjgk_tender_graph.py` 的 direct replace step 顺序。
- **GOTCHA**: 保留 `STATE_CLS = GngkTenderGraphState` 的继承，不要切到 `GjgkTenderGraphState`。
- **VALIDATE**: `cd backend && TMPDIR=/tmp python -m pytest tests/graphs/test_gngk_tender_graph.py -v`

### UPDATE `backend/tests/config/test_tender_config_protected_fields.py`

- **IMPLEMENT**:
  - 从 common two-field 参数列表移除 `gngk_hw_cz`。
  - 增加断言 `get_protected_field_profile("gngk_hw_cz")` 抛出 direct_replace 不支持 profile。
  - 保留 `gngk_hw_zc`、`gngk_fw_cz`、`gngk_fw_zc` 现有断言。
- **PATTERN**: 现有 `gjgk` direct_replace rejection 测试。
- **VALIDATE**: `cd backend && TMPDIR=/tmp python -m pytest tests/config/test_tender_config_protected_fields.py -v`

### UPDATE `backend/tests/graphs/test_gngk_tender_graph.py`

- **IMPLEMENT**:
  - import 新财政货物 delete / update 节点。
  - 增加 `test_gngk_hw_cz_graph_overrides_direct_replace_word_nodes`。
  - 将 registry 参数表里 `gngk_hw_cz_tender` 的 expected update 从 common `update_word` 改为 `gngk_hw_cz_update_word`。
  - 可增加 expected delete 断言，确保 graph 不再继承 common delete。
- **PATTERN**: `test_gngk_fw_zc_graph_overrides_service_specific_word_nodes`。
- **VALIDATE**: `cd backend && TMPDIR=/tmp python -m pytest tests/graphs/test_gngk_tender_graph.py -v`

### CREATE `backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`

- **IMPLEMENT**: 用猴补丁覆盖 Word COM 依赖，测试节点关键可观察行为：
  - `gngk_hw_cz_delete_tender_param` 使用 `tender_type="gngk_hw_cz"` 调 `get_anchor_target_sizes` 和 `resolve_anchor_content_range`。
  - delete 节点在 range 合法时调用 `doc.Range(range_start, range_end).Delete()`。
  - update 节点不调用 common protected-field split；给定 `polished_text` 不含 `交付日期` / `付款方式` 也能进入插入流程。
  - update 节点返回 `style_writeback_result` 和 `style_writeback_summary`。
  - 可直接测试小 helper：财政货物 content range 以 `CONTENT_START_MODE_SAME_PAGE_AFTER_ANCHOR` 从 before anchor 后开始，而非下一页。
- **PATTERN**: `backend/tests/nodes/test_comment_writeback.py` 和 `backend/tests/nodes/test_update_word_inline_style_writeback.py` 中 monkeypatch Word 节点依赖的方式。
- **GOTCHA**: 新测试文件名必须以 `test_` 开头，并放在 `backend/tests/nodes/`。
- **VALIDATE**: `cd backend && TMPDIR=/tmp python -m pytest tests/nodes/test_gngk_hw_cz_direct_replace_word.py -v`

### UPDATE `asset/shared_runtime_word_skill_knowledge_pack.md`

- **IMPLEMENT**:
  - 将受保护字段现实从“`gngk_hw_cz` 使用 common_two_field”改为“`gngk_hw_cz` 是 direct_replace，不支持 protected field profile”。
  - 增加财政货物 direct replace 说明：首次生成清空第四章到第五章之间正文，同页插入，样式回填继续走安全门禁。
  - 保持 rewrite / edit 不在本轮范围的说明，避免后续误读。
- **VALIDATE**: `git diff --check`

### UPDATE `asset/tender_type_identity_session_knowledge_pack.md`

- **IMPLEMENT**:
  - 更新 Graph 与运行时分流：`GngkHwCzTenderGraph` 不再仅继承 `GngkHwZcTenderGraph` 的 common delete/update，而是覆盖 direct replace delete/update，replacement 仍用 `gngk_hw_zc_get_replacements`。
  - 保持前端 gngk 货物财政分派规则和默认锚点不变。
- **VALIDATE**: `git diff --check`

### UPDATE `asset/README.md`

- **IMPLEMENT**: 如共享运行时知识包或类型身份知识包的适用范围描述需要反映财政货物 direct replace，更新索引摘要；如果当前摘要已足够，无需强行改动。
- **VALIDATE**: `git diff --check`

### RUN focused backend validation

- **IMPLEMENT**: 在 WSL 中设置 Linux 临时目录并运行相关测试。
- **VALIDATE**:
  - `cd backend && TMPDIR=/tmp python -m pytest tests/config/test_tender_config_protected_fields.py tests/graphs/test_gngk_tender_graph.py tests/nodes/test_gngk_hw_cz_direct_replace_word.py -v`
  - 如果改动触碰样式回填：`cd backend && TMPDIR=/tmp python -m pytest tests/nodes/test_update_word_inline_style_writeback.py tests/nodes/test_comment_writeback.py -v`

### RUN full / environment validation

- **IMPLEMENT**:
  - 若 Linux backend env 可用，运行 `cd backend && TMPDIR=/tmp python -m pytest tests -v`。
  - 若当前在 WSL 且缺少 Windows Word COM，记录真实 Word 集成未执行原因。
  - 在 Windows + Word COM 环境中使用用户指定测试用例执行一次真实生成。
- **VALIDATE**:
  - Windows 手动验收：用 `254226-小动物活体光声显微成像设备-招标文件-初稿1（审2）.doc` 作模板、`技术参数.docx` 作参数，国内公开选择“货物 + 财政”，确认 SSE 完成和下载文件第四章/第五章边界正确。

---

## 测试策略

### 单元测试

- `backend/tests/config/test_tender_config_protected_fields.py`: 固定 `gngk_hw_cz` direct_replace 后不支持 protected profile。
- `backend/tests/graphs/test_gngk_tender_graph.py`: 固定 `GngkHwCzTenderGraph` 节点绑定和 registry route。
- `backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`: 用 fake doc / monkeypatch 测财政货物 direct replace 节点，不依赖真实 Word COM。

### 集成测试

- 后端 focused pytest 覆盖 graph registry、配置和节点行为。
- 真实文件生成需要 Windows + Word COM，用用户指定模板和参数做手动集成验收。

### 边界情况

- 前后锚点文本包含不同数量空格：`第四章  招标需求` / `第四章 招标需求`，`第五章  评标方法与程序` / `第五章 评标方法与程序`。
- 模板中没有 `交付日期：` 或 `付款方式：`。
- 第五章标题紧跟正文后，删除范围不能跨过后锚点。
- 插入正文含 Markdown 表格、空行和普通编号行。
- 样式片段无法安全匹配时应 best-effort 跳过，不硬失败；批注写回硬失败契约保持。

---

## 验证命令

执行所有命令，确保零回归与功能正确。

### 级别 1：语法与风格

```bash
git diff --check
```

### 级别 2：单元测试

```bash
cd backend && TMPDIR=/tmp python -m pytest tests/config/test_tender_config_protected_fields.py tests/graphs/test_gngk_tender_graph.py tests/nodes/test_gngk_hw_cz_direct_replace_word.py -v
```

### 级别 3：相关回归测试

```bash
cd backend && TMPDIR=/tmp python -m pytest tests/nodes/test_update_word_inline_style_writeback.py tests/nodes/test_comment_writeback.py tests/services/test_document_service_initial_state.py -v
```

### 级别 4：完整后端测试

```bash
cd backend && TMPDIR=/tmp python -m pytest tests -v
```

### 级别 5：手动验证

在 Windows + Word COM 环境中：

1. 启动后端和前端。
2. 打开 TenderWord 国内公开页面。
3. 选择“货物 + 财政”。
4. 模板选择 `C:\Users\0325\Desktop\投标文件测试用例\国内公开货物财政测试用例集\测试用例1\254226-小动物活体光声显微成像设备-招标文件-初稿1（审2）.doc`。
5. 参数选择同目录 `技术参数.docx`。
6. 发起首次生成。
7. 确认 SSE 正常完成并出现下载入口。
8. 下载文件，确认“第四章 招标需求”下方正文已替换，“第五章 评标方法与程序”及后续内容仍存在。

---

## 验收标准

- [ ] `gngk_hw_cz_tender` 首次生成不再依赖 common two-field protected profile。
- [ ] `GngkHwCzTenderGraph` 显式绑定财政货物 direct replace delete / update 节点。
- [ ] 财政货物删除和插入范围保留前后章节锚点。
- [ ] 插入位置为“第四章 招标需求”标题下方同页正文区域。
- [ ] 样式回填摘要继续写回 state 和任务结果。
- [ ] 其它招标类型 graph 节点绑定无回归。
- [ ] 相关 pytest 通过。
- [ ] `asset/` 知识包同步更新。
- [ ] 真实 Windows + Word COM 验收完成，或交付说明明确未执行原因。

---

## 完成检查清单

- [ ] 所有任务均已按顺序完成。
- [ ] 每个任务的验证都已立即通过。
- [ ] 所有验证命令都已成功执行或说明阻塞原因。
- [ ] 后端相关测试通过。
- [ ] 无 lint / diff whitespace 错误。
- [ ] 手动测试确认功能可用。
- [ ] 验收标准全部满足。
- [ ] 经验回写到 `asset/`。

---

## 备注

- 本轮用户明确确认：只做首次生成闭环，不做 rewrite / edit。
- 本轮用户明确确认：默认生成模式仍为模板优先。
- 本轮用户明确确认：整段清空，只保留“第四章 招标需求”和“第五章 评标方法与程序”两个章节锚点。
- 本轮用户明确确认：插入位置在“第四章 招标需求”标题下方同页，参考 `gjgk_update_word.py`。
- 本轮用户明确确认：样式回填继续支持并沿用安全门禁。

**信心分数**: 8/10。主要风险在于 Word COM 节点复制/抽取时需处理真实文档中表格、段落边界和锁定范围的细节；通过 fake 单测加 Windows 真实样例验收可以把风险降到可接受范围。
