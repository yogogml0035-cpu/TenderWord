# 国内公开货物财政无保护字段模板生成 PRD

## 1. 介绍 / 概述

当前 TenderWord 已有“国内公开 + 货物 + 财政”类型，但后端 `GngkHwCzTenderGraph` 仍继承“国内公开 + 货物 + 自筹”的受保护字段写回流程。新的财政货物模板没有需要保留的加密或受保护字段，正文区域可以直接编辑，因此该类型首次生成时应改为锚点间整段清空并同页插入 AI 生成正文。

本需求只覆盖首次生成闭环，不覆盖 rewrite / edit 聊天修改链路。

## 2. 目标

- 让现有“国内公开 + 货物 + 财政”首次生成支持无保护字段模板。
- 保留现有前端入口、类型身份和默认模板优先生成模式。
- 在“第四章 招标需求”标题下方插入生成正文。
- 清空到“第五章 评标方法与程序”之前的旧正文，避免旧模板内容残留。
- 继续支持样式回填、任务状态、SSE 进度和下载结果。
- 不影响其它招标类型的生成行为。

## 3. User Stories

### US-001: 财政货物类型使用直替换生成流程

**描述：** 作为招标文件生成用户，我想在国内公开货物财政模式下使用无保护字段模板生成文件，以便不需要模板中存在 `交付日期`、`付款方式` 等受保护字段也能完成生成。

**Acceptance Criteria：**

- [ ] 当后端生成请求的 `form_type` 为 `gngk_hw_cz_tender` 时，首次生成流程不再使用 common 受保护字段 `delete_tender_param` / `update_word` 写回路径。
- [ ] `gngk_hw_cz_tender` 仍保留现有 `gngk_hw_zc_get_replacements` 替换字段提取能力和模板优先生成模式。
- [ ] `gngk_hw_cz_tender` 缺少 `交付日期：` 或 `付款方式：` 字段时，不因受保护字段 profile 校验失败而中断。
- [ ] `xjcg_tender`、`gngk_hw_zc_tender`、`gngk_fw_zc_tender`、`gngk_fw_cz_tender`、`gjgk_tender` 的既有节点路由保持不变。
- [ ] 相关后端 graph / config 单元测试通过。

### US-002: 招标需求正文按财政货物锚点同页清空并插入

**描述：** 作为招标文件生成用户，我想让系统保留第四章和第五章标题，只替换中间的招标需求正文，以便生成结果不会破坏后续章节。

**Acceptance Criteria：**

- [ ] 系统使用 `第四章  招标需求` / `第四章 招标需求` 的空格兼容文本作为前锚点，使用 `第五章  评标方法与程序` / `第五章 评标方法与程序` 的空格兼容文本作为后锚点。
- [ ] 锚点字号按宋体三号，即当前配置中的 `22.0` 匹配。
- [ ] 删除范围从“第四章 招标需求”标题之后开始，到“第五章 评标方法与程序”标题之前结束。
- [ ] 插入位置位于“第四章 招标需求”标题下方同页正文起点，而不是强制跳到下一页。
- [ ] 生成结果中“第五章 评标方法与程序”及其后续内容仍然存在且未被覆盖。
- [ ] 相关节点单元测试覆盖同页 content range 和空格兼容锚点。

### US-003: 样式回填与任务结果保持一致

**描述：** 作为招标文件生成用户，我想财政货物直替换生成后仍保留现有样式回填能力，以便生成文档和其它类型在格式体验上保持一致。

**Acceptance Criteria：**

- [ ] 财政货物直替换 update 节点插入正文后仍调用现有样式回填能力。
- [ ] 样式回填继续沿用现有安全门禁，黄色可编辑区域提示不作为正文高亮样式要求。
- [ ] update 节点继续把 `style_writeback_result` 和 `style_writeback_summary` 写回 state。
- [ ] 任务完成结果和 SSE done metadata 中继续包含已有样式回填摘要契约。
- [ ] 相关样式回填测试或 graph 流转测试通过。

### US-004: 首次生成闭环与知识沉淀

**描述：** 作为后续维护者，我想该需求的测试、知识包和验证说明同步更新，以便后续新增类似模板时能按一致边界扩展。

**Acceptance Criteria：**

- [ ] 新增或更新的后端测试覆盖 `gngk_hw_cz_tender` 的 direct replace 节点绑定、配置模式和默认锚点。
- [ ] 不新增前端大类；现有前端 `gngk` 货物财政到 `gngk_hw_cz_tender` 的分派保持不变。
- [ ] `asset/shared_runtime_word_skill_knowledge_pack.md` 更新财政货物 direct replace 与无受保护字段边界。
- [ ] `asset/tender_type_identity_session_knowledge_pack.md` 更新 `GngkHwCzTenderGraph` 当前 graph / node 分流事实。
- [ ] 如 `asset/README.md` 索引描述需要同步，已一并更新。
- [ ] 在可用环境中执行后端相关 pytest；若因 WSL / Word COM 环境限制不能跑真实 Word 集成，交付说明清楚列出阻塞原因和替代验证。

### US-005: 财政货物生成端到端验收

**描述：** 作为招标文件生成用户，我想使用指定测试用例完成一次财政货物文件生成，以便确认实际模板可以生成和下载。

**Acceptance Criteria：**

- [ ] 在 Windows + Word COM 环境中，使用 `C:\Users\0325\Desktop\投标文件测试用例\国内公开货物财政测试用例集\测试用例1\254226-小动物活体光声显微成像设备-招标文件-初稿1（审2）.doc` 作为模板。
- [ ] 使用同目录 `技术参数.docx` 作为参数文件。
- [ ] 通过国内公开“货物 + 财政”首次生成发起任务。
- [ ] 任务 SSE 正常推送进度并以完成状态结束。
- [ ] 下载生成结果后，第四章招标需求正文已替换为新内容，且第五章评标方法与程序仍存在。
- [ ] Typecheck passes。
- [ ] Tests pass。

## 4. Functional Requirements

- FR-1: 系统必须继续把前端国内公开“货物 + 财政”请求分派为后端 `gngk_hw_cz_tender`。
- FR-2: `gngk_hw_cz_tender` 首次生成必须使用直替换删除和直替换写回，不再依赖 common two-field 受保护字段。
- FR-3: `gngk_hw_cz` 的默认锚点必须保持为 `第四章  招标需求` 到 `第五章  评标方法与程序`。
- FR-4: 财政货物锚点匹配必须兼容章节标题中的空格差异。
- FR-5: 财政货物锚点字号必须继续按宋体三号 / 22.0 匹配。
- FR-6: 财政货物生成正文必须插入到前锚点标题下方同页正文区域。
- FR-7: 财政货物生成不能删除或覆盖后锚点及其后续章节。
- FR-8: 财政货物生成必须保留现有模板优先生成模式。
- FR-9: 财政货物生成必须继续支持现有样式回填及其任务结果摘要。
- FR-10: 本轮不得改变 rewrite / edit 分发行为。
- FR-11: 本轮不得新增前端类型、页面或独立表单。
- FR-12: 完成后必须同步相关测试与 `asset/` 知识包。

## 5. Non-Goals

- 不实现 rewrite / edit 对财政货物 direct replace 的支持。
- 不改变国内公开货物自筹和服务类型的受保护字段逻辑。
- 不改变国际公开现有生成行为。
- 不新增数据库、外部服务或新依赖。
- 不把 Word 限制编辑产生的黄色可编辑提示作为需要继承的正文样式。
- 不要求恢复模板原限制编辑状态。

## 6. Design Considerations

- 前端截图中的“国内公开 / 货物 / 财政”入口保持不变。
- 对用户可见的变化应体现在生成成功率和生成结果正文区域，不新增额外 UI。
- 下载结果里的章节结构是核心可见验收点：第四章标题保留、正文替换、第五章标题及后文保留。

## 7. Technical Considerations

- 当前 `backend/graphs/gngk_hw_cz_tender_graph.py` 只是继承 `GngkHwZcTenderGraph`，需要显式覆盖财政货物的 delete / update 节点。
- `backend/config/tender_config.py` 当前 `gngk_hw_cz` 锚点字号已经是 `22.0`，但 content update mode 仍随默认 `protected_fields`，需要与需求一致。
- `gjgk_delete_tender_param.py` 和 `gjgk_update_word.py` 是可参考的 direct replace 行为，但不能把 tender_type 硬写为 `gjgk` 后直接复用给 `gngk_hw_cz`，否则会使用错误锚点和字号。
- `anchor_utils` 已支持空格变体和 `normalize_space=True` 的锚点匹配。
- 样式回填、批注回写、任务结果透传属于共享任务契约，不能在新节点中丢失。
- 完整运行依赖 Windows + Word COM；WSL 中可优先跑纯 Python 单元测试。

## 8. Success Metrics

- 指定财政货物测试用例可以完成首次生成并下载。
- 指定模板不再因缺少受保护字段而失败。
- 生成结果第四章正文替换准确，后续第五章不受影响。
- 后端相关 pytest 通过。
- 知识包同步完成，后续维护者能从 `asset/` 读到新的财政货物 direct replace 边界。

## 9. Open Questions

- 无。
