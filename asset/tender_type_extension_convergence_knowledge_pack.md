# 招标类型扩展与收敛知识包

## 背景与适用范围
- 适用于新增招标类型，或修改 `xjcg` / `gngk` / `gjgk` 的 identity、URL 判型、`form_type` 分派、anchor 默认值、graph/state/node 特化与前端表单注册。
- 本知识包记录当前代码已经落成的类型边界，以及仍未完全收敛但必须同步维护的现实，不把目标结构误写成现状。

## 当前真源
- 后端类型与运行态：`backend/models/generate.py`、`backend/config/tender_config.py`、`backend/services/document_service.py`
- graph / node 绑定：`backend/graphs/`、`backend/nodes/`
- 前端 URL 判型与 canonical URL：`frontend/utils/tenderTypeMapper.ts`
- 前端表单到后端请求转换：`frontend/lib/formDataConverter.ts`
- edit 任务表单类型分派：`frontend/components/chat/ChatPanel.tsx`
- 表单注册与展示名：`frontend/components/chat/tenderFormRegistry.ts`
- 前端锚点默认值与 `gngk` 模式缓存：`frontend/components/forms/tenderFormConfig.ts`、`frontend/components/forms/TenderFormShared.tsx`

## 当前真实类型矩阵

### 前端类型
- `xjcg`
- `gngk`
- `gjgk`

### 后端 `FormType`
- `xjcg_tender`
- `gngk_hw_zc_tender`
- `gngk_hw_cz_tender`
- `gngk_fw_zc_tender`
- `gngk_fw_cz_tender`
- `gjgk_tender`

### 运行态 `tender_type`
- `DocumentService` 当前通过 `request.form_type.value.replace("_tender", "")` 生成运行态：
  - `xjcg`
  - `gngk_hw_zc`
  - `gngk_hw_cz`
  - `gngk_fw_zc`
  - `gngk_fw_cz`
  - `gjgk`
- 运行态 family 收敛真源是 `backend/config/tender_config.py` 的 `get_tender_type_family()`：
  - 所有 `gngk_*` 运行态归并为 family `gngk`
  - 其它类型保持自身名称

## URL 判型与会话 identity

### 前端判型
- `frontend/utils/tenderTypeMapper.ts` 当前只用 `purchase_method` 判定前端 `TenderType`：
  - `5 -> xjcg`
  - `2 -> gngk`
  - `0 -> gjgk`
- `tender_lx` / `fund_lx` 当前不参与前端判型，只参与 `gngk` 的会话 identity、URL canonical 化与后端 `form_type` 分派。

### canonical URL 当前规则
- `buildCanonicalSearchParams()` 当前输出：
  - `xjcg`: `tender_lx=0&purchase_method=5&fund_lx=0`
  - `gngk`: `purchase_method=2`，并保留 `tender_lx` / `fund_lx`
  - `gjgk`: `tender_lx=0&purchase_method=0&fund_lx=1`
- `gjgk` 当前 canonical URL 不保留输入里的任意 `tender_lx` / `fund_lx` 变体。

### gngk 会话 identity
- `frontend/stores/chatStore.ts` 的 `findGngkConversationByIdentity()` 以四维精确匹配：
  - `tenderType = gngk`
  - `tenderno`
  - `tender_lx`
  - `fund_lx`
- 若有多条完全同身份会话，URL 进入时复用 `updatedAt` 最新的一条。
- `frontend/app/tender/page.tsx` 的深链 dedup key 也会把 `tender_lx` / `fund_lx` 带上，避免不同 `gngk` 子类型共用同一 URL 命中结果。

## 后端 anchor / graph / node 当前现实

### anchor 默认值
- `backend/config/tender_config.py` 当前 anchor config 为：
  - `xjcg`: `第三章  采购需求` -> `第四章  响应文件有关格式`
  - `gngk_hw_zc`: `第三章 招标内容及要求` -> `第四章 投标文件有关格式`
  - `gngk_hw_cz`: `第四章  招标需求` -> `第五章  评标方法与程序`
  - `gngk_fw_zc`: `第三章 招标内容及要求` -> `第四章 合同条款`
  - `gngk_fw_cz`: `第三章 招标内容及要求` -> `第四章 合同条款`
  - `gjgk`: `技术规格及要求` -> `附件1：投标文件封面（格式）`
- `generate` 与 `edit` 默认锚点直接读取 `get_default_anchor_texts()`。
- `rewrite` 当前还保留 `DocumentService.REWRITE_DEFAULT_ANCHORS` 作为快照回退，内容必须与 `tender_config.py` 保持同步。

### graph 绑定
- `XjcgTenderGraph`：共享 common word 节点，仅 replacement 使用 `xjcg_get_replacements`
- `GngkHwZcTenderGraph`：共享 common delete / update，replacement 使用 `gngk_hw_zc_get_replacements`
- `GngkHwCzTenderGraph`：当前直接继承 `GngkHwZcTenderGraph`
- `GngkFwZcTenderGraph`：当前覆盖三处服务特化节点
  - `gngk_fw_zc_delete_tender_param`
  - `gngk_fw_zc_get_replacements`
  - `gngk_fw_zc_update_word`
- `GngkFwCzTenderGraph`：当前直接继承 `GngkHwZcTenderGraph`，没有额外覆盖
- `GjgkTenderGraph`：沿用 `StandardTenderWorkflowGraph`，但替换为 `gjgk_*` 专属 delete / replacements / update，并保留 post-update hook
- 六类 generate graph 当前都通过共享 `extract_tender_params` 从模板正文范围提取 `inline_style_fragments`；后续按三条 update 分流回填样式并保留 `style_writeback_*`：
  - `xjcg`、`gngk_hw_zc`、`gngk_hw_cz`、`gngk_fw_cz` -> common `update_word`
  - `gngk_fw_zc` -> `gngk_fw_zc_update_word`
  - `gjgk` -> `gjgk_update_word`

### skill runtime 分发现实
- `backend/nodes/skills_nodes/tender_aware_word_dispatch.py` 当前只 special-case：
  - `gjgk`
  - `gngk_fw_zc`
- 这意味着 `gngk_fw_cz` 当前在 rewrite / edit 运行时仍回落到 common delete / update。
- 如果未来要把 `gngk_fw_cz` 与 `gngk_fw_zc` 一起走服务专用路径，必须同时修改：
  - graph 绑定
  - `tender_aware_word_dispatch.py`
  - 相关测试

### replacement 与受保护字段 profile
- 公开招标 family 的共享 replacement 逻辑收敛在 `backend/nodes/gngk_word_nodes/gngk_get_replacements.py`。
- `gngk_get_replacements.py` 只提供公共 extractor / replacement field 构建器，不作为 graph 节点兼容别名。
- 公开招标 family 的 graph wrapper 当前真名是：
  - `gngk_hw_zc_get_replacements`
  - `gngk_fw_zc_get_replacements`
- `gngk_hw_zc_get_replacements` 只保留货物自筹差异：`project_content_v1`、`similar_project_performance_date`。
- `gngk_fw_zc_get_replacements` 只保留服务自筹差异：整行提取 `project_content`，包含项目名称、数量和项目预算括号。
- 受保护字段 profile 当前为：
  - `xjcg`、`gngk_hw_zc`、`gngk_hw_cz`、`gngk_fw_cz` -> `common_two_field`
  - `gngk_fw_zc` -> `gngk_three_field`
  - `gjgk` -> `direct_replace`，不允许走受保护字段 profile

## 前端表单与锚点缓存现实

### `gngk` 表单到后端 `form_type`
- `frontend/lib/formDataConverter.ts` 与 `frontend/components/chat/ChatPanel.tsx` 当前都按同一规则计算 `gngk` 的 `form_type`：
  - `tender_lx=0, fund_lx=0 -> gngk_hw_zc_tender`
  - `tender_lx=0, fund_lx=1 -> gngk_hw_cz_tender`
  - `tender_lx=1, fund_lx=0 -> gngk_fw_zc_tender`
  - `tender_lx=1, fund_lx=1 -> gngk_fw_cz_tender`
- 任一处改动都必须双向同步并补测试。

### `TenderFormShared` 的当前 `gngk` 模式缓存
- `frontend/components/forms/tenderFormConfig.ts` 只提供每个大类的基础默认锚点。
- `gngk` 的真实运行时默认值与模式缓存逻辑在 `TenderFormShared.tsx`：
  - 货物模式按 `fund_lx` 维护两套 `gngk_insertion_configs`
  - 服务模式跨 `fund_lx` 共享一套 `gngk_service_insertion_config`
  - 服务模式默认锚点：`第三章 招标内容及要求` -> `第四章 合同条款`
  - 财政货物默认锚点：`第四章  招标需求` -> `第五章  评标方法与程序`
  - 其余货物默认锚点回退到 `tenderFormConfig.ts` 的 `gngk` 基础值
- 首次从旧草稿切到服务模式时，如果还没有 `gngk_service_insertion_config`，当前代码允许用旧 `draft.insertion_config` 作为一次性兼容回退。

### `generation_style` 的前端默认值
- `TenderFormShared` 当前把 `generation_style` 作为表单态保存：
  - `tender_lx = 0` 默认 `template`
  - `tender_lx = 1` 默认 `param`
- 这只是前端 generate 表单默认值；后端仍只在 generate runtime 使用该字段。

## 新增或修改类型时的同步清单
- 后端至少检查：
  - `backend/models/generate.py`
  - `backend/config/tender_config.py`
  - `backend/services/document_service.py`
  - `backend/graphs/`
  - `backend/states/`
  - `backend/nodes/`
- 前端至少检查：
  - `frontend/types/api.ts`
  - `frontend/utils/tenderTypeMapper.ts`
  - `frontend/lib/formDataConverter.ts`
  - `frontend/components/chat/ChatPanel.tsx`
  - `frontend/components/chat/tenderFormRegistry.ts`
  - `frontend/components/forms/tenderFormConfig.ts`
  - `frontend/components/forms/TenderFormShared.tsx`
  - `frontend/stores/chatStore.ts`
- 若类型会影响 skill runtime，还必须同步检查 `backend/nodes/skills_nodes/tender_aware_word_dispatch.py`。
- 改完类型边界后，必须同步更新本知识包和 `asset/README.md`。

## 关联测试与验证路径
- `backend/tests/graphs/test_gngk_tender_graph.py`
- `backend/tests/nodes/test_extract_tender_params_inline_style.py`
- `backend/tests/nodes/test_update_word_inline_style_writeback.py`
- `backend/tests/graphs/test_gjgk_tender_graph.py`
- `backend/tests/config/test_tender_config_protected_fields.py`
- `backend/tests/services/test_document_service_initial_state.py`
- `backend/tests/nodes/test_tender_aware_word_dispatch.py`
- `backend/tests/nodes/test_gjgk_replacements_extractors.py`
- `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`
- `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`
- `frontend/__tests__/unit/components/chat/test_tender_form_registry.test.tsx`
- `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`
- `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`
- `frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`
- `frontend/e2e/test_url_conversation.spec.ts`

## 回归风险与维护建议
- 当前项目的类型元数据仍分散在前后端多个位置；新增类型不能只改一侧。
- `tender_config.py` 与 `DocumentService.REWRITE_DEFAULT_ANCHORS` 当前存在双份默认锚点语义；只改其中一处会造成 rewrite 与 generate / edit 默认值漂移。
- `gngk_fw_cz` 当前并没有像 `gngk_fw_zc` 那样在 skill runtime 上专门分发；如果后续业务希望两者保持一致，必须显式改代码与测试，不能在知识包里默认它已经完成。
