# AI 批注 bad case 风险模式级知识库 v2

## 来源与目标

- 来源主文件：`comments_prompt_plans_summary.md`。
- 参考文件：`comments_bad_case_knowledge_essence.md`。
- 原始信号：批注计划、删除线计划、非黑色字体计划。
- 目标：把实际业务 bad case 提炼成可用于向量召回、关键词召回和 prompt 注入的“风险模式级”知识，而不是保存项目级原文。
- 使用边界：本文件只服务 AI 批注生成，不直接驱动删除线、字体颜色或 Word 写回动作。

## 入库筛选口径

保留：

- 能迁移到不同招标项目的合规、公平、严谨性或可验收性风险。
- 能从原文片段和人工批注中归纳出稳定触发特征的模式。
- 能转译成明确批注动作的模式：`建议提示`、`建议删除`、`建议新增或明确`。
- 批注计划、删除线计划、非黑色字体计划中反复出现，或虽出现较少但业务含义稳定的模式。

剔除：

- 只有“同上”“请确认”“？”等无独立业务判断的记录。
- 只有 `★`、`▲`、`≥`、`≤`、`等`、`至少` 等孤立短词，且无法扩展到完整风险分句的记录。
- 只能服务某个具体设备、具体品牌、具体型号或单次排版错误的记录。
- 完整客户原文、联系人、电话、真实项目路径和过长上下文。

## 字段说明

- `bad_case_id`：风险模式唯一编号。
- `risk_layer`：`general_tender` 表示通用招标风险，`medical_device` 表示医疗设备采购高频风险。
- `risk_type`：风险大类。
- `risk_pattern`：可直接召回的一条子模式。
- `comment_action`：建议采用的批注动作。
- `evidence_strength`：`high`、`medium`、`low`，表示该模式在来源数据中的证据强度。
- `source_signals`：观察到该模式的来源信号。
- `trigger_signals`：识别和召回该模式的组合触发特征。
- `keywords_for_retrieval`：关键词召回词。
- `typical_source_pattern`：去项目化后的典型原文形态。
- `bad_case_core`：坏案例的本质问题。
- `recommended_comment_policy`：推荐批注口径。
- `non_retain_reason`：不建议原样保留该原文的原因。
- `applicability_boundary`：适用边界，避免 AI 过度批注。
- `anchor_policy`：建议选择的 `reference_text` 锚点范围。
- `basis_hint`：业务依据提示，非强制法规条文。

---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_001
risk_layer: general_tender
risk_type: 参数指纹
risk_pattern: 异常精确小数或非整数指标
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 指标出现明显精细小数、非常规重量、尺寸、转速、频率或角度。
  - 原文同时缺少行业依据、允差或测试条件。
  - 人工意见常表现为“是否需要那么精确”“能否取整”。
keywords_for_retrieval: [参数指纹, 小数精度, 精确数值, 取整, 允差, 排他性参数]
typical_source_pattern:
  - 某部件重量要求为精确到个位或小数位的上限。
  - 某器械直径、长度、转速使用异常精确数值。
bad_case_core: 过细数值可能形成特定产品的参数指纹，降低竞争充分性。
recommended_comment_policy:
  - 建议提示：该数值精度较高，请确认是否为项目必要需求；如无充分依据，建议改为合理区间、取整值或补充允差范围。
non_retain_reason: 原样保留容易把单一产品参数固化为准入门槛。
applicability_boundary:
  - 若该精度来自强制标准、临床安全要求或明确验收依据，可保留并补充依据。
anchor_policy: 锚点取包含指标名称和精确数值的完整分句，不只取数字。
basis_hint: 采购需求应客观、明确且不过度限制竞争。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_002
risk_layer: general_tender
risk_type: 参数指纹
risk_pattern: 多个固定档位或枚举值组合形成指纹
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 原文写“至少包含”后列出多个固定档位、固定模式或固定数值。
  - 枚举值排列像产品说明书参数。
  - 同一条同时出现多个精确范围或档位。
keywords_for_retrieval: [至少包含, 固定档位, 枚举值, 参数组合, 产品说明书, 指向性]
typical_source_pattern:
  - 某压力或流速调节“至少包含 A、B、C 三档”。
  - 某设备模式“至少包含模式一、模式二、模式三”等固定组合。
bad_case_core: 单个数值未必排他，但多个固定档位组合容易变成特定产品指纹。
recommended_comment_policy:
  - 建议提示：该处列举多个固定档位或模式，可能指向特定产品；建议改为连续可调范围、最低性能要求或开放式功能描述。
non_retain_reason: 固定枚举组合会把“满足功能”误写成“必须同款配置”。
applicability_boundary:
  - 若枚举项是行业统一分类或强制标准列项，可保留并写明标准来源。
anchor_policy: 锚点取“至少包含”及其后的完整列举片段。
basis_hint: 参数应表达实际性能需求，而非复制特定产品配置。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_003
risk_layer: general_tender
risk_type: 参数边界
risk_pattern: 范围覆盖与单点阈值混用
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 非黑色字体计划]
trigger_signals:
  - 原文写“范围不小于 A-B”“至少包含 A-B”“覆盖 A-B”等。
  - 人工意见关注“是大于某值，还是至少包含某范围”。
keywords_for_retrieval: [范围覆盖, 至少包含, 不小于, 测量范围, 显示范围, 阈值]
typical_source_pattern:
  - 测量范围写为“不小于 0-X”。
  - 显示范围写为“至少包含 A-B”，但不清楚是否允许更宽范围。
bad_case_core: 范围覆盖和单点阈值是不同业务含义，混用会导致验收判断错误。
recommended_comment_policy:
  - 建议提示：请明确该处是要求范围至少覆盖指定区间，还是要求某一指标达到指定阈值；建议改为“范围至少覆盖 A-B”或明确上下限。
non_retain_reason: 原样保留会让临界值和超范围响应是否合格不清楚。
applicability_boundary:
  - 对仪器测量范围、显示范围、调节范围特别适用。
anchor_policy: 锚点取完整范围表达，不只取上下限数字。
basis_hint: 验收指标应能直接判断供应商响应是否合格。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_004
risk_layer: general_tender
risk_type: 参数边界
risk_pattern: 大于/小于与大于等于/小于等于口径不清
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 非黑色字体计划]
trigger_signals:
  - 出现 `>`、`<`、`＞`、`＜`、`不大于`、`不小于`、`不少于`。
  - 人工意见为“是否包含”“是否含该数值”。
keywords_for_retrieval: [是否包含, 临界值, 大于, 小于, 不小于, 不大于, 边界符号]
typical_source_pattern:
  - 数量要求写“>N 个”。
  - 时间、尺寸或性能指标写“<X”但未说明是否含 X。
bad_case_core: 边界符号会直接影响临界响应是否合格，必须明确含不含。
recommended_comment_policy:
  - 建议提示：该处边界符号会影响临界值是否合格，请确认是否包含该数值；建议统一使用 `≥/≤` 或写明“含/不含”。
non_retain_reason: 原样保留可能导致评审和验收争议。
applicability_boundary:
  - 若上下文已明确“含/不含”，不重复批注。
anchor_policy: 锚点取指标名称加边界表达。
basis_hint: 采购指标边界应清晰可判定。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_005
risk_layer: general_tender
risk_type: 参数边界
risk_pattern: 允差范围缺失或只给固定值
comment_action: 建议新增或明确
evidence_strength: medium
source_signals: [批注计划]
trigger_signals:
  - 关键尺寸、角度、频率、温度、压力只给固定值。
  - 人工意见出现“有允差”“是否加允差”“只能这个范围吗”。
keywords_for_retrieval: [允差, 固定值, 公差, 范围值, 验收误差]
typical_source_pattern:
  - 某角度写为固定值但未说明允许误差。
  - 某频率或温度写为单点值。
bad_case_core: 固定值缺少允差会把正常产品差异排除在外，也不利于验收。
recommended_comment_policy:
  - 建议新增或明确：请确认该固定值是否允许合理允差；如允许，建议补充范围或公差。
non_retain_reason: 单点值容易造成不必要排他和验收僵化。
applicability_boundary:
  - 对必须精确控制的安全指标，应保留并说明依据。
anchor_policy: 锚点取固定值所在完整指标句。
basis_hint: 技术指标应兼顾必要性和可验收性。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_006
risk_layer: general_tender
risk_type: 表述可验收性
risk_pattern: 主观形容词作为技术指标
comment_action: 建议删除
evidence_strength: high
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 出现“精准”“快速”“智能”“先进”“成熟”“稳定”“高效”“优质”等主观词。
  - 缺少量化阈值、测试方法或验收标准。
keywords_for_retrieval: [主观表述, 无法量化, 精准, 快速, 智能, 先进, 高效, 稳定]
typical_source_pattern:
  - 某功能描述为“精准控制”“快速响应”“智能分析”。
  - 某系统描述为“稳定可靠、操作简单”。
bad_case_core: 主观词无法客观验收，容易让 AI 误以为是有效技术指标。
recommended_comment_policy:
  - 建议删除：该表述偏主观，无法作为明确验收指标；如确需保留，建议改为可检测的数值、标准或测试条件。
non_retain_reason: 原样保留不能支持公平评审和验收。
applicability_boundary:
  - 若只是章节引导语且不作为响应指标，可不批注或弱提示。
anchor_policy: 锚点取包含主观词的完整分句。
basis_hint: 采购需求应可量化、可验证。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_007
risk_layer: general_tender
risk_type: 表述可验收性
risk_pattern: 产品宣传或说明书介绍混入参数
comment_action: 建议删除
evidence_strength: high
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 原文像产品卖点、功能原理、应用效果介绍。
  - 人工意见出现“产品说明类描述建议删除”“像产品宣传用语”。
keywords_for_retrieval: [产品说明, 宣传用语, 功能原理, 卖点, 参数冗余]
typical_source_pattern:
  - 参数中大段描述设备原理、优势或用户体验。
  - 技术要求中出现“便于用户自行开展”“提升效率”等效果性介绍。
bad_case_core: 采购参数应表达需求和验收标准，不应复制产品宣传材料。
recommended_comment_policy:
  - 建议删除：该内容偏产品宣传或说明性文字，建议保留可验收的核心性能要求，其余删除或改为客观指标。
non_retain_reason: 宣传性文字会稀释核心需求，也可能指向特定产品文案。
applicability_boundary:
  - 对必要的用途说明，可保留在项目背景或用途段，不应作为硬参数。
anchor_policy: 锚点取宣传性描述所在完整句或段内最小连续片段。
basis_hint: 技术条款应围绕必要功能和验收指标。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_008
risk_layer: general_tender
risk_type: 表述可验收性
risk_pattern: 只写功能原理但无验收指标
comment_action: 建议新增或明确
evidence_strength: medium
source_signals: [批注计划]
trigger_signals:
  - 原文解释设备如何工作，但没有性能阈值或验收方法。
  - 人工意见出现“功能原理不建议在参数详细阐述”“建议客观参数表示”。
keywords_for_retrieval: [功能原理, 验收指标, 客观参数, 工作原理, 技术路线]
typical_source_pattern:
  - 某条详细描述传感器、泵送、算法或联动原理。
  - 只有技术路线，没有输出能力、精度或响应要求。
bad_case_core: 原理描述不能替代采购需求，且技术路线可能排除其他等效实现。
recommended_comment_policy:
  - 建议提示：该处偏功能原理描述，建议改为需实现的功能效果、性能指标或验收方法，避免限定单一技术路线。
non_retain_reason: 原样保留可能把实现方式当成准入条件。
applicability_boundary:
  - 若项目确需指定技术路线，应补充必要性依据。
anchor_policy: 锚点取限定技术路线或原理的最小完整分句。
basis_hint: 采购需求宜描述结果和性能，谨慎限定实现路径。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_009
risk_layer: general_tender
risk_type: 表述可验收性
risk_pattern: 行业术语或专有名词缺少定义
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划]
trigger_signals:
  - 出现专业缩写、英文缩写、厂商化技术名或特殊结构名。
  - 人工意见出现“行业通用术语？”“专业术语？”“如何定义？”。
keywords_for_retrieval: [专业术语, 行业通用, 英文缩写, 专有名词, 技术名称, 参数含义]
typical_source_pattern:
  - 某功能写为“多段式”“磁吸式”“短时增压”等特殊术语。
  - 原文出现英文缩写但没有中文定义。
bad_case_core: 术语可能是行业通用，也可能是厂商专有，缺定义会造成排他或不可验收。
recommended_comment_policy:
  - 建议提示：该术语请确认是否为行业通用表述；如非通用，建议改为功能性、性能性描述，并补充中文定义或验收方式。
non_retain_reason: 未解释的专有术语容易让评审对象不清。
applicability_boundary:
  - 对国家标准或行业标准已明确定义的术语，可保留并引用标准。
anchor_policy: 锚点取术语所在完整短句，不只取缩写。
basis_hint: 参数名称和术语应让供应商可理解、可响应。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_010
risk_layer: general_tender
risk_type: 表述可验收性
risk_pattern: 英文描述或型号化表达未中文化
comment_action: 建议新增或明确
evidence_strength: medium
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 原文大段使用英文功能名、英文模块名或英文接口名。
  - 人工意见出现“建议使用中文描述”“建议中文或删除”。
keywords_for_retrieval: [英文描述, 中文描述, 缩写解释, 型号化表达, 技术名]
typical_source_pattern:
  - 参数中直接写英文功能名称或软件模块名称。
  - 配置清单中出现无解释英文代号。
bad_case_core: 招标需求应便于所有供应商理解，英文或代号化表达需有中文含义。
recommended_comment_policy:
  - 建议新增或明确：请补充中文名称、功能含义和验收口径；若为品牌或型号代号，建议删除或泛化。
non_retain_reason: 原样保留会增加理解偏差，甚至隐藏品牌型号指向。
applicability_boundary:
  - 通用接口标准名可保留英文，但宜补充中文说明。
anchor_policy: 锚点取英文术语及其所属指标分句。
basis_hint: 招标文件表述应清晰、完整、可响应。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_011
risk_layer: general_tender
risk_type: 品牌型号指向
risk_pattern: 明示品牌名或品牌组合
comment_action: 建议删除
evidence_strength: high
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 原文直接列出品牌名、品牌组合或“某品牌等”。
  - 人工意见出现“不建议显示品牌”“改为市场主流品牌”。
keywords_for_retrieval: [品牌, 品牌名, 市场主流品牌, 指向性, 兼容品牌]
typical_source_pattern:
  - 接口或配件要求可连接品牌A/品牌B。
  - 技术要求列举特定品牌作为可兼容对象。
bad_case_core: 明示品牌会削弱采购需求中立性，可能限制竞争。
recommended_comment_policy:
  - 建议删除：该处出现具体品牌，可能存在指向性；建议改为“兼容市场主流品牌/满足同等功能”或客观兼容指标。
non_retain_reason: 原样保留容易让供应商理解为限定或偏向特定品牌。
applicability_boundary:
  - 若用于说明已有系统兼容需求，应写明兼容场景，并避免限定唯一品牌。
anchor_policy: 锚点取包含品牌及兼容要求的完整分句。
basis_hint: 采购需求应保持品牌中立。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_012
risk_layer: general_tender
risk_type: 品牌型号指向
risk_pattern: 型号代码或产品系列号进入需求
comment_action: 建议删除
evidence_strength: high
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 配置、参数或标题中出现具体型号、系列号、代号。
  - 人工意见出现“删除型号”“是否为品牌型号”。
keywords_for_retrieval: [型号, 系列号, 产品代号, 设备型号, 指向性]
typical_source_pattern:
  - 配置清单写“某设备型号 X 系列”。
  - 参数条款中出现非标准型号代码。
bad_case_core: 型号是比品牌更强的指向性信号，通常不应进入中立采购需求。
recommended_comment_policy:
  - 建议删除：该处疑似具体型号或产品代号，建议改为功能、规格、性能或兼容要求。
non_retain_reason: 型号化表达可能直接锁定单一产品。
applicability_boundary:
  - 旧系统扩容或原厂配套采购需另有合规依据，不宜在通用参数中直接写型号。
anchor_policy: 锚点取型号所在完整配置行。
basis_hint: 技术需求应避免指定特定产品型号。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_013
risk_layer: general_tender
risk_type: 品牌型号指向
risk_pattern: “本公司生产”或供应商自指表述残留
comment_action: 建议删除
evidence_strength: medium
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 原文出现“本公司生产”“我公司”“本品牌专用”等供应商口吻。
  - 句式像从供应商材料复制。
keywords_for_retrieval: [本公司生产, 我公司, 供应商口吻, 厂商文案, 自指表述]
typical_source_pattern:
  - 要求与“本公司生产”的耗材或配件配套使用。
  - 参数中出现“我公司独有技术”。
bad_case_core: 供应商自指表述说明原文可能来自厂商材料，具有明显不中立风险。
recommended_comment_policy:
  - 建议删除：该处存在供应商自指或厂商文案残留，建议删除并改为中立、客观的功能或兼容要求。
non_retain_reason: 原样保留会直接破坏招标文件身份和公平性。
applicability_boundary:
  - 无明确单一来源采购依据时应删除。
anchor_policy: 锚点取包含自指词的完整分句。
basis_hint: 招标文件不应保留供应商宣传口吻。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_014
risk_layer: general_tender
risk_type: 品牌型号指向
risk_pattern: 原厂授权、原厂承诺或原厂培训作为硬要求
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 出现“原厂授权”“原厂承诺函”“原厂培训资质”“原厂工程师”。
  - 与核心产品、售后或人员能力混合。
keywords_for_retrieval: [原厂授权, 原厂承诺函, 原厂培训, 原厂工程师, 厂家限制]
typical_source_pattern:
  - 投标人需提供原厂售后承诺函。
  - 维修人员需具备原厂培训资质。
bad_case_core: 原厂要求可能排除合法代理商或第三方服务商，应确认必要性和范围。
recommended_comment_policy:
  - 建议提示：该处要求原厂授权/承诺/培训，可能提高准入门槛；请确认是否仅针对核心产品且确有必要，或改为制造商/授权机构/同等能力证明。
non_retain_reason: 原样保留可能形成厂家限制。
applicability_boundary:
  - 对依法需制造商支持的核心设备，可保留但应限定范围和替代证明路径。
anchor_policy: 锚点取原厂要求所在完整条款。
basis_hint: 证明要求应与项目履约能力直接相关。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_015
risk_layer: general_tender
risk_type: 品牌型号指向
risk_pattern: 同品牌、非 OEM 或特定生产关系限制
comment_action: 建议删除
evidence_strength: medium
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 出现“同品牌”“非 OEM”“同一厂家生产”“原装”等。
  - 不是为了接口兼容或安全责任的必要说明。
keywords_for_retrieval: [同品牌, 非OEM, 同一厂家, 原装, 生产关系, 指向性]
typical_source_pattern:
  - 主机与附件要求同品牌。
  - 某部件要求非 OEM 或原装生产。
bad_case_core: 生产关系限制通常比性能要求更排他，容易排除同等兼容产品。
recommended_comment_policy:
  - 建议删除：该处限定同品牌/非 OEM/原装关系，建议改为兼容性、安全性或性能要求。
non_retain_reason: 原样保留会把产品来源关系作为准入条件。
applicability_boundary:
  - 若涉及安全责任或注册证配套范围，应写明法规或注册依据。
anchor_policy: 锚点取包含生产关系限制的完整分句。
basis_hint: 采购需求应优先描述功能和质量，不宜限制来源关系。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_016
risk_layer: general_tender
risk_type: 国外认证标准
risk_pattern: 国外认证作为硬性条件
comment_action: 建议删除
evidence_strength: high
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 出现 CE、FDA、国外认证、国外注册或境外准入。
  - 国内注册证或法定证明已可覆盖。
keywords_for_retrieval: [CE, FDA, 国外认证, 境外认证, 注册证, 国内要求]
typical_source_pattern:
  - 设备要求同时具有国内注册和国外认证。
  - 技术参数单独要求 FDA 或 CE。
bad_case_core: 非必要国外认证容易形成不合理限制，尤其在已有国内法定准入要求时。
recommended_comment_policy:
  - 建议删除：国外认证不宜作为采购需求硬性条件；建议改为适用的国内注册、国家标准或行业标准要求。
non_retain_reason: 原样保留可能排除符合国内准入但无国外认证的产品。
applicability_boundary:
  - 若项目确有境外使用或国际认证必要性，应单独说明依据。
anchor_policy: 锚点取国外认证所在完整分句。
basis_hint: 证明条件应与本项目实际履约和国内准入要求匹配。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_017
risk_layer: general_tender
risk_type: 国外认证标准
risk_pattern: 国外标准与国内标准并列但无必要性
comment_action: 建议删除
evidence_strength: high
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 出现 ASTM、IEC、EN、UL 等国外标准。
  - 同条已有国家标准、行业标准或国内强制标准。
keywords_for_retrieval: [国外标准, ASTM, IEC, EN, 国内标准, 强制标准]
typical_source_pattern:
  - 材料或器械要求符合国外标准或国内标准。
  - 检测要求列出国外标准但未说明适用性。
bad_case_core: 国内采购通常应优先采用适用的国家或行业标准，国外标准需证明必要性。
recommended_comment_policy:
  - 建议删除：该处国外标准不建议作为硬性要求，建议调整为适用的国内标准或法定要求。
non_retain_reason: 原样保留可能形成对部分供应商的不合理限制。
applicability_boundary:
  - 若国内无对应标准且国外标准确为行业通用参考，可作为参考性说明而非硬门槛。
anchor_policy: 锚点取标准号和适用对象所在分句。
basis_hint: 标准引用应现行有效、适用且不过度限制竞争。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_018
risk_layer: general_tender
risk_type: 国外认证标准
risk_pattern: ISO 或管理体系认证设为关键技术硬指标
comment_action: 建议提示
evidence_strength: medium
source_signals: [批注计划]
trigger_signals:
  - ISO、质量管理体系、环境管理体系等被设为星号或关键参数。
  - 人工意见出现“是否放入打分”“设置星号不建议”。
keywords_for_retrieval: [ISO, 管理体系认证, 星号, 评分项, 技术指标]
typical_source_pattern:
  - 技术条款要求投标人或厂家具有某管理体系认证。
  - 管理体系认证被设为否决项。
bad_case_core: 管理体系认证通常不等同于产品性能，作为硬技术条件需谨慎。
recommended_comment_policy:
  - 建议提示：请确认该管理体系认证是否与本项目履约直接相关；不建议作为星号技术硬指标，必要时可考虑放入评分或删除。
non_retain_reason: 原样保留可能把企业资质当成产品技术参数。
applicability_boundary:
  - 若采购文件评分规则明确要求，可按评分项口径处理。
anchor_policy: 锚点取认证名称和指标等级所在条款。
basis_hint: 资格、评分和技术参数应分层设置。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_019
risk_layer: general_tender
risk_type: 指标等级
risk_pattern: 星号条款过多或设置在章节大点
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 非黑色字体计划]
trigger_signals:
  - 大量 `★` 条款集中出现。
  - `★` 标在章节标题、大点或整段综合描述上。
keywords_for_retrieval: [星号过多, 否决项, 大点星号, 关键指标, 竞争充分性]
typical_source_pattern:
  - 技术要求中多条连续星号。
  - 星号标在“技术要求”“售后服务”等章节标题或大段落。
bad_case_core: 星号是否定性门槛，过多或过大范围会放大否决风险。
recommended_comment_policy:
  - 建议提示：本项目星号条款较多或标注范围过大，请确认是否均为实质性必要要求；建议只保留关键、可证明、竞争充分的否决指标。
non_retain_reason: 原样保留可能导致有效供应商不足或评审争议。
applicability_boundary:
  - 对安全、法规准入等确需否决的要求可保留。
anchor_policy: 锚点取星号所在具体条款，避免只锚章节标题。
basis_hint: 否决项应必要、明确、可证明。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_020
risk_layer: general_tender
risk_type: 指标等级
risk_pattern: 询价项目出现三角号或打分项
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 非黑色字体计划]
trigger_signals:
  - 询价、最低价成交场景中出现 `▲`、打分项、评分项。
  - 人工意见出现“询价没有三角指标”“询价要么星号要么一般指标”。
keywords_for_retrieval: [询价, 三角号, 打分项, 最低价成交, 评审办法, ▲]
typical_source_pattern:
  - 询价项目技术参数中标注 `▲`。
  - 最低价成交项目仍设置加分指标。
bad_case_core: 采购方式与指标符号体系不匹配，会造成评审规则混乱。
recommended_comment_policy:
  - 建议提示：请确认采购方式和评审办法；询价项目通常不宜设置 `▲` 打分项，建议调整为 `★` 否决项或一般指标。
non_retain_reason: 原样保留会让评审办法和参数标识不一致。
applicability_boundary:
  - 若项目实际采用综合评分，应以评审办法为准。
anchor_policy: 锚点取带 `▲` 的完整条款。
basis_hint: 指标符号应与采购方式和评审办法一致。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_021
risk_layer: general_tender
risk_type: 指标等级
risk_pattern: 星号条款缺少支撑材料或否决后果提示
comment_action: 建议新增或明确
evidence_strength: high
source_signals: [批注计划, 非黑色字体计划]
trigger_signals:
  - `★` 条款未说明证明材料、响应方式或无效响应后果。
  - 人工意见出现“星号条款为否决条款”“需要支撑材料”。
keywords_for_retrieval: [星号条款, 支撑材料, 否决项, 无效响应, 证明文件]
typical_source_pattern:
  - 技术参数标 `★` 但没有任何证明要求。
  - 章节说明缺少星号条款的统一响应要求。
bad_case_core: 星号条款直接影响响应有效性，应同步明确证明和后果。
recommended_comment_policy:
  - 建议新增或明确：星号条款为否决条款，请明确需提供的证明材料、响应方式以及未满足时的处理后果。
non_retain_reason: 原样保留会导致评审依据不足。
applicability_boundary:
  - 若招标文件前文已有统一星号说明，可不重复批注具体条款。
anchor_policy: 锚点取 `★` 条款或星号统一说明所在分句。
basis_hint: 否决项应有清晰证明路径。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_022
risk_layer: general_tender
risk_type: 证明材料
risk_pattern: 普通参数机械要求证明材料
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 普通参数后要求说明书、检测报告、照片、制造商盖章。
  - 人工意见出现“一般参数提供证明无意义”“是否加星号，否则删除”。
keywords_for_retrieval: [普通参数, 证明材料, 检测报告, 说明书, 制造商盖章, 指标等级]
typical_source_pattern:
  - 一般技术参数括号要求提供检测报告。
  - 非关键条款要求每项均提供证明材料。
bad_case_core: 普通参数索证过重会增加响应负担，也会和指标等级不匹配。
recommended_comment_policy:
  - 建议提示：请确认该普通参数是否确需证明材料；如为关键指标可调整指标等级并明确证明方式，否则建议删除过重索证要求。
non_retain_reason: 原样保留会扩大材料审查范围并增加争议。
applicability_boundary:
  - 对安全、法规、核心性能参数可保留证明要求。
anchor_policy: 锚点取参数和括号内证明要求的完整片段。
basis_hint: 证明要求应与指标重要性匹配。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_023
risk_layer: general_tender
risk_type: 证明材料
risk_pattern: 证明方式过窄或只接受单一材料
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 只接受原厂承诺函、制造商盖章、指定报告或指定证书。
  - 人工意见建议承诺函、原厂承诺函、偏离表多选。
keywords_for_retrieval: [证明方式, 单一材料, 原厂承诺函, 偏离表, 承诺函, 替代证明]
typical_source_pattern:
  - 星号条款只要求原厂承诺函。
  - 技术要求只接受制造商盖章证明。
bad_case_core: 证明路径过窄可能排除具备履约能力但材料形式不同的供应商。
recommended_comment_policy:
  - 建议提示：证明材料口径建议提供可替代路径，例如承诺函、原厂承诺函、偏离表响应或有效证明文件，避免限定单一材料形式。
non_retain_reason: 原样保留可能形成不合理材料门槛。
applicability_boundary:
  - 法规明确要求特定证书时可保留。
anchor_policy: 锚点取“提供某材料”的完整后缀或条款。
basis_hint: 证明材料应能证明实质能力，不宜无必要限定形式。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_024
risk_layer: general_tender
risk_type: 证明材料
risk_pattern: 检测/检验/校准机构资质口径不清
comment_action: 建议新增或明确
evidence_strength: high
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 出现检测机构、检验机构、第三方报告、CMA、校准报告等。
  - 机构类型、资质标志或报告适用范围不清。
keywords_for_retrieval: [检测机构, 检验机构, CMA, 第三方报告, 校准报告, 资质口径]
typical_source_pattern:
  - 要求“权威机构报告”但未定义机构资质。
  - 同一文件混用检测报告、检验报告、校准报告。
bad_case_core: 证明机构口径不清会影响供应商准备材料和评审判断。
recommended_comment_policy:
  - 建议新增或明确：请统一证明机构类型和资质要求，例如是否要求国家认可、CMA 标志或第三方检测/校准机构报告。
non_retain_reason: 原样保留会造成证明材料可接受性不明确。
applicability_boundary:
  - 若前文已有统一证明材料规则，可锚定前文统一确认。
anchor_policy: 锚点取机构要求和证明材料名称所在完整分句。
basis_hint: 材料要求应清楚说明出具主体和适用范围。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_025
risk_layer: general_tender
risk_type: 证明材料
risk_pattern: 专利证书或独占性证书作为证明要求
comment_action: 建议删除
evidence_strength: medium
source_signals: [批注计划]
trigger_signals:
  - 要求提供专利证书、独有技术证书或排他性知识产权证明。
  - 人工意见出现“专利证书具有排他性，建议调整为证明材料即可”。
keywords_for_retrieval: [专利证书, 独有技术, 排他性, 证明材料, 知识产权]
typical_source_pattern:
  - 某功能要求提供专利证书证明。
  - 技术条款将专利作为满足条件。
bad_case_core: 专利证书天然具有排他性，不宜作为通用采购指标证明。
recommended_comment_policy:
  - 建议删除：专利证书具有排他性，建议改为提供能证明功能或性能满足的材料即可。
non_retain_reason: 原样保留可能直接指向专利持有人。
applicability_boundary:
  - 科研服务或专利采购等特殊项目不按此通用规则处理。
anchor_policy: 锚点取专利证明要求所在完整分句。
basis_hint: 证明材料不应变相限定知识产权归属。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_026
risk_layer: general_tender
risk_type: 配置与采购范围
risk_pattern: 配置清单缺数量、单位或规格
comment_action: 建议新增或明确
evidence_strength: high
source_signals: [批注计划, 非黑色字体计划]
trigger_signals:
  - 配置要求只有名称或标题，缺数量、单位、规格。
  - 人工意见出现“请补充数量、单位”“建议明确配置”。
keywords_for_retrieval: [配置清单, 数量, 单位, 规格, 采购范围, 配置要求]
typical_source_pattern:
  - 配置章节只写“配置要求”或列名称无数量。
  - 项目数量写“壹套/壹批”但未拆明细。
bad_case_core: 配置不明确会影响报价、供货和验收。
recommended_comment_policy:
  - 建议新增或明确：请补充配置明细的数量、单位、规格及是否纳入本次采购范围。
non_retain_reason: 原样保留会导致供应商报价口径不一致。
applicability_boundary:
  - 总包类项目可允许上位数量，但关键交付物仍应明确。
anchor_policy: 锚点优先取缺失数量单位的具体配置行。
basis_hint: 采购范围应清楚可报价、可验收。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_027
risk_layer: general_tender
risk_type: 配置与采购范围
risk_pattern: 核心产品与厂家授权范围不清
comment_action: 建议提示
evidence_strength: medium
source_signals: [批注计划]
trigger_signals:
  - 项目为一批设备或多项产品，但授权要求未说明适用对象。
  - 人工意见出现“是否设置核心产品，仅核心产品提供厂家授权”。
keywords_for_retrieval: [核心产品, 厂家授权, 壹批, 多产品, 授权范围]
typical_source_pattern:
  - 设备名称及数量为多个设备/一批。
  - 要求所有产品均提供厂家授权。
bad_case_core: 多产品项目中授权范围过宽会显著提高投标门槛。
recommended_comment_policy:
  - 建议提示：请确认是否需要设置核心产品，并限定厂家授权或制造商证明仅适用于核心产品，避免扩大授权范围。
non_retain_reason: 原样保留可能对非核心配件设置不必要门槛。
applicability_boundary:
  - 对单一核心设备采购，可直接按核心产品处理。
anchor_policy: 锚点取项目数量和授权要求相关分句。
basis_hint: 授权要求应与核心采购对象匹配。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_028
risk_layer: general_tender
risk_type: 配置与采购范围
risk_pattern: 备件、软件升级或服务藏在售后段落
comment_action: 建议新增或明确
evidence_strength: high
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 售后段落出现维修备件、软件升级、备用设备、附件交付。
  - 人工意见出现“是否放入配置要求内”“或者供应商自述”。
keywords_for_retrieval: [备件, 软件升级, 售后段落, 配置要求, 交付物, 报价范围]
typical_source_pattern:
  - 售后服务中要求提供若干备件。
  - 维护条款中写软件终身升级。
bad_case_core: 交付物、报价范围和售后承诺混在一起，会造成响应边界不清。
recommended_comment_policy:
  - 建议提示：请确认该内容是本次采购交付物、售后承诺还是供应商自述；如为交付物，建议纳入配置清单和报价范围。
non_retain_reason: 原样保留会让供应商难以判断是否必须供货。
applicability_boundary:
  - 纯服务承诺可留在售后，但应明确不作为额外交付物。
anchor_policy: 锚点取包含备件、软件升级或备用设备的完整句。
basis_hint: 交付内容和售后承诺应分层表达。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_029
risk_layer: general_tender
risk_type: 付款交付
risk_pattern: 付款期限与资金来源或中小企业规则不匹配
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划]
trigger_signals:
  - 出现财政资金、自筹资金、中小企业、60 天、90 天、3 个月。
  - 人工意见出现“财政资金 60 天”“中小企业 60 天？”。
keywords_for_retrieval: [付款方式, 财政资金, 自筹资金, 中小企业, 60天, 90天, 3个月]
typical_source_pattern:
  - 验收后 90 日或 3 个月内付款。
  - 财政资金或中小企业项目未匹配付款期限口径。
bad_case_core: 付款期限受资金来源和项目属性影响，不能机械套用模板。
recommended_comment_policy:
  - 建议提示：请结合资金来源和中小企业支付要求确认付款期限，避免财政资金、自筹资金和中小企业付款口径混用。
non_retain_reason: 原样保留可能与项目支付规则不一致。
applicability_boundary:
  - 具体期限应由业务员结合项目事实确认，AI 不直接断言违法。
anchor_policy: 锚点取完整付款条款。
basis_hint: 付款条款应与资金来源、采购方式和合同履行节点一致。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_030
risk_layer: general_tender
risk_type: 付款交付
risk_pattern: 付款起算点和触发条件不清
comment_action: 建议新增或明确
evidence_strength: high
source_signals: [批注计划]
trigger_signals:
  - 出现货到、安装调试、验收合格、正常使用、收到发票等多个触发点。
  - 起算点未明确，或多个条件顺序不清。
keywords_for_retrieval: [付款节点, 起算点, 验收合格, 收到发票, 正常使用, 触发条件]
typical_source_pattern:
  - “安装调试验收合格正常使用后付款”。
  - “收到发票后若干日内支付”但未说明验收节点。
bad_case_core: 多个付款触发条件叠加会影响付款期限计算和合同执行。
recommended_comment_policy:
  - 建议新增或明确：请明确付款起算点、触发条件及条件之间的先后关系，例如以验收合格、收到发票或其他节点为准。
non_retain_reason: 原样保留会导致付款期限计算争议。
applicability_boundary:
  - 若合同模板已有统一付款定义，可提醒与模板保持一致。
anchor_policy: 锚点取包含付款触发条件的完整分句。
basis_hint: 合同付款条款应明确起算点和履行条件。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_031
risk_layer: general_tender
risk_type: 付款交付
risk_pattern: 交付日期缺起算点或自然日/工作日口径
comment_action: 建议新增或明确
evidence_strength: medium
source_signals: [批注计划]
trigger_signals:
  - 交付日期写合同签订后、接通知后、若干天内。
  - 未说明自然日还是工作日，或出现多个起算点。
keywords_for_retrieval: [交付日期, 合同签订后, 接通知后, 自然日, 工作日, 起算点]
typical_source_pattern:
  - “合同签订后，接采购人通知后 N 天内交付”。
  - “交付期 N 天”未说明起算条件。
bad_case_core: 交付期限必须可计算，否则影响供应商排产和违约责任判断。
recommended_comment_policy:
  - 建议新增或明确：请明确交付日期的起算点、触发条件以及自然日/工作日口径。
non_retain_reason: 原样保留会造成交付期限争议。
applicability_boundary:
  - 对框架或分批交付项目，还应明确批次和通知方式。
anchor_policy: 锚点取完整交付日期条款。
basis_hint: 履约期限应明确、可计算。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_032
risk_layer: general_tender
risk_type: 售后保修
risk_pattern: “整机保修”范围不清
comment_action: 建议新增或明确
evidence_strength: high
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 出现整机保修、整机质保、附件、器械、耗材、软件。
  - 人工意见出现“整机包含器械吗？”。
keywords_for_retrieval: [整机保修, 附件, 器械, 耗材, 软件, 保修范围]
typical_source_pattern:
  - “整机保修期不少于 N 年”但未说明附件和耗材。
  - 质保范围中同时涉及主机、配件、软件。
bad_case_core: 整机概念不清会导致售后责任范围争议。
recommended_comment_policy:
  - 建议新增或明确：请明确“整机”是否包含附件、器械、易耗件和软件，以及各自质保期限。
non_retain_reason: 原样保留会让供应商和采购人对保修范围理解不一致。
applicability_boundary:
  - 若行业通用质保范围已有模板定义，可引用模板口径。
anchor_policy: 锚点取整机保修所在完整条款。
basis_hint: 售后责任应明确对象、期限和范围。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_033
risk_layer: general_tender
risk_type: 售后保修
risk_pattern: 质保后费用折扣或市场价口径不清
comment_action: 建议新增或明确
evidence_strength: high
source_signals: [删除线计划, 非黑色字体计划, 批注计划]
trigger_signals:
  - 质保后零件费用按市场价折扣、免人工费、免差旅费。
  - 市场价、折扣基准、工时费范围不清。
keywords_for_retrieval: [质保后, 市场价, 折扣, 工时费, 零件费, 差旅费]
typical_source_pattern:
  - “保修期满后零件费用按市场价折扣收取”。
  - “终身维修免人工费，仅收零件费”。
bad_case_core: 质保后费用条款若缺计价基准，会造成长期履约争议。
recommended_comment_policy:
  - 建议新增或明确：请明确质保后维修费用项目、计价基准、折扣口径和是否包含人工费、差旅费、零件费。
non_retain_reason: 原样保留无法判断后续收费是否合理。
applicability_boundary:
  - 若不要求长期维保报价，可弱化为供应商服务承诺。
anchor_policy: 锚点取质保后收费完整句。
basis_hint: 售后费用应可计算、可执行。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_034
risk_layer: general_tender
risk_type: 售后保修
risk_pattern: 售后响应时间过细或不现实
comment_action: 建议提示
evidence_strength: medium
source_signals: [删除线计划, 非黑色字体计划, 批注计划]
trigger_signals:
  - 电话响应、远程介入、到场、修复分别设置精确时间。
  - 时间要求明显严格但缺项目必要性。
keywords_for_retrieval: [售后响应, 到场时间, 修复时间, 远程响应, 备用机, 服务时限]
typical_source_pattern:
  - “2 小时响应、24 小时到场、48 小时修复”。
  - 分级响应时间设置过细。
bad_case_core: 售后时限影响服务成本和供应商覆盖范围，应与项目需求匹配。
recommended_comment_policy:
  - 建议提示：请确认该售后响应时限是否符合项目所在地、服务半径和设备重要性；过细或过严时建议调整为合理服务等级。
non_retain_reason: 原样保留可能限制外地或第三方服务商参与。
applicability_boundary:
  - 生命支持、关键业务连续性设备可保留更高服务要求，但应说明必要性。
anchor_policy: 锚点取包含响应、到场、修复时限的完整分句。
basis_hint: 服务要求应与项目履约需要相匹配。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_035
risk_layer: general_tender
risk_type: 售后保修
risk_pattern: 售后条款与前后文重复或冲突
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 报修响应、备用设备、培训、维保在多处重复出现。
  - 人工意见出现“与售后重复”“建议合并”。
keywords_for_retrieval: [售后重复, 维保重复, 备用设备, 培训重复, 条款冲突]
typical_source_pattern:
  - 技术参数、商务条款和售后服务都写同一响应要求。
  - 免费维护或备用设备多处表述不同。
bad_case_core: 重复条款可能出现口径差异，导致合同解释冲突。
recommended_comment_policy:
  - 建议提示：该售后要求与其他条款重复或可能冲突，建议合并到售后服务章节并统一口径。
non_retain_reason: 原样保留会增加不一致风险。
applicability_boundary:
  - 若只是章节引用，不需要重复批注。
anchor_policy: 锚点取当前重复出现的完整售后句。
basis_hint: 同类履约要求应集中、统一表述。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_036
risk_layer: general_tender
risk_type: 内部一致性
risk_pattern: 列举数量与前文数量要求不一致
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 原文写 `≥N 种`，后续枚举数量少于或多于 N。
  - 人工意见出现“与前文不一致”“7 种，与前文不一致”。
keywords_for_retrieval: [数量不一致, 枚举数量, 前文不一致, 至少包含, 列举项]
typical_source_pattern:
  - 要求不少于 N 种模式，但实际只列出 M 种。
  - 标题和配置明细数量不一致。
bad_case_core: 数量和列举不一致会直接影响响应和验收。
recommended_comment_policy:
  - 建议提示：该处列举数量与前文数量要求不一致，请核对并统一。
non_retain_reason: 原样保留会导致供应商不知应满足数量还是列举项。
applicability_boundary:
  - 若“等”明确允许不限于列举项，也应说明最低数量和示例关系。
anchor_policy: 锚点取当前列举片段。
basis_hint: 同一指标在全文中应保持一致。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_037
risk_layer: general_tender
risk_type: 内部一致性
risk_pattern: “和/或”导致必选与可选关系不清
comment_action: 建议新增或明确
evidence_strength: high
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 同一要求中出现“和”“或”“以及/或者”混用。
  - 人工意见出现“和还是或”“二选一，都可以？”。
keywords_for_retrieval: [和还是或, 二选一, 并列必选, 可选, 响应关系]
typical_source_pattern:
  - 要求支持 A 或 B，但未说明任一满足还是全部满足。
  - 配置写 A 和/或 B。
bad_case_core: 连接词决定供应商是否必须全部响应，是关键评审口径。
recommended_comment_policy:
  - 建议新增或明确：请明确该处是并列必选、二选一还是可选配置，避免“和/或”混用。
non_retain_reason: 原样保留会造成响应完整性争议。
applicability_boundary:
  - 若上下文明示“至少一种”或“全部满足”，不重复批注。
anchor_policy: 锚点取包含连接词的完整分句。
basis_hint: 条款逻辑关系应明确可判定。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_038
risk_layer: general_tender
risk_type: 内部一致性
risk_pattern: 同一对象名称前后不统一
comment_action: 建议提示
evidence_strength: medium
source_signals: [批注计划]
trigger_signals:
  - 同一设备、模块、探头、配件在前后使用不同名称。
  - 人工意见出现“是否同一种”“建议表述统一”。
keywords_for_retrieval: [名称不统一, 同一种模块, 前后不一致, 表述统一]
typical_source_pattern:
  - 前文写模块 A，后文写模块 B，疑似同一对象。
  - 配置名称与技术参数标题不一致。
bad_case_core: 名称不统一会影响供应商识别采购对象和响应范围。
recommended_comment_policy:
  - 建议提示：请确认前后是否指同一对象；如是，建议统一名称和表述。
non_retain_reason: 原样保留会造成配置与参数无法对应。
applicability_boundary:
  - 若确为不同对象，应补充区分说明。
anchor_policy: 锚点取当前名称不一致处的完整分句。
basis_hint: 同一采购对象应保持名称一致。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_039
risk_layer: general_tender
risk_type: 市场与业绩限制
risk_pattern: 历史销售、发票或引进家数作为限制
comment_action: 建议删除
evidence_strength: medium
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 要求三甲医院发票、引进家数、销售案例数量、市场覆盖量。
  - 与产品技术性能或项目履约无直接关系。
keywords_for_retrieval: [三甲医院, 发票, 引进家数, 销售案例, 业绩限制, 市场占有]
typical_source_pattern:
  - 要求提供若干医院引进或耗材发票。
  - 要求已有大量用户案例作为技术条件。
bad_case_core: 历史销售或市场应用不是当前产品性能本身，容易限制新供应商。
recommended_comment_policy:
  - 建议删除：该要求与产品技术性能或本项目履约能力关联不足，可能形成不合理限制。
non_retain_reason: 原样保留会把市场存量当作准入条件。
applicability_boundary:
  - 若作为评分项评价类似项目经验，应避免过窄且不得重复限制。
anchor_policy: 锚点取业绩或市场证据完整要求。
basis_hint: 履约能力评价应与项目实际需要相关。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_040
risk_layer: general_tender
risk_type: 市场与业绩限制
risk_pattern: 临床指南、专家共识或应用案例作为硬指标
comment_action: 建议提示
evidence_strength: medium
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 出现临床指南、专家共识、循证医学、应用案例、安全例数等。
  - 被作为必须满足的技术或资格条件。
keywords_for_retrieval: [临床指南, 专家共识, 循证医学, 应用案例, 安全例数, 硬指标]
typical_source_pattern:
  - 要求产品具有大量临床应用和指南支持。
  - 把专家共识作为供应商响应条件。
bad_case_core: 外部证据可能有参考价值，但不应替代客观采购指标或过度限制竞争。
recommended_comment_policy:
  - 建议提示：请确认该临床或市场证据是否作为硬性要求；如无必要，建议改为客观性能指标或删除。
non_retain_reason: 原样保留可能排除新技术或等效产品。
applicability_boundary:
  - 对高风险医疗技术，可保留必要安全有效性证据，但需客观、可核验。
anchor_policy: 锚点取证据要求的完整分句。
basis_hint: 证据要求应与项目履约和安全有效性直接相关。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_041
risk_layer: general_tender
risk_type: 免费额外与选配
risk_pattern: 免费、赠品或额外服务边界不清
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 出现免费、额外提供、赠送、无偿、终身免费等。
  - 未说明是否纳入报价、交付或售后承诺。
keywords_for_retrieval: [免费, 额外提供, 赠品, 无偿, 报价范围, 售后承诺]
typical_source_pattern:
  - 要求额外提供备件或服务。
  - 要求终身免费升级或免费培训。
bad_case_core: 免费和额外内容会影响报价范围及合同义务，应明确边界。
recommended_comment_policy:
  - 建议提示：请确认该内容是本次采购交付物、报价包含项还是售后承诺；无必要的免费额外要求建议删除或合并。
non_retain_reason: 原样保留会造成隐性成本和履约边界不清。
applicability_boundary:
  - 采购人确需包含的服务应写入配置或服务清单。
anchor_policy: 锚点取包含“免费/额外/无偿”的完整句。
basis_hint: 采购范围和合同价款应对应清楚。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_042
risk_layer: general_tender
risk_type: 免费额外与选配
risk_pattern: 可选配置被写成本次采购必配
comment_action: 建议提示
evidence_strength: medium
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 出现可选、选配、可配置、支持扩展。
  - 同时又要求供应商本次必须提供或报价。
keywords_for_retrieval: [选配, 可选配置, 本次采购, 必配, 报价范围]
typical_source_pattern:
  - 配置项写“可选配某部件”但未说明是否采购。
  - 参数中要求支持选配模块。
bad_case_core: 可选项与必配项混淆会导致报价和验收不一致。
recommended_comment_policy:
  - 建议提示：请确认该可选配置是否纳入本次采购；如纳入，应列入配置清单和报价范围，如不纳入，应改为可扩展能力说明。
non_retain_reason: 原样保留会造成供应商对供货义务理解不一。
applicability_boundary:
  - 对仅要求未来扩展能力的条款，应明确“不含本次供货”。
anchor_policy: 锚点取包含可选配置的完整配置行。
basis_hint: 必配、选配和扩展能力应分开表达。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_043
risk_layer: general_tender
risk_type: 采购人义务误入参数
risk_pattern: 外部环境或采购人条件作为设备参数
comment_action: 建议删除
evidence_strength: high
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 室温、湿度、场地、网络、电源、运输环境等被设为设备参数或星号。
  - 人工意见出现“对采购人的要求”“环境条件不建议作为参数”。
keywords_for_retrieval: [环境条件, 室温, 湿度, 工作环境, 采购人要求, 外部条件]
typical_source_pattern:
  - 设备参数要求采购现场满足特定温湿度。
  - 外部工作环境被标为星号条款。
bad_case_core: 采购人或外部环境条件不应作为供应商产品性能硬指标。
recommended_comment_policy:
  - 建议删除：该内容属于使用环境或采购人配套条件，不建议作为设备技术参数或星号条款；如必要，可移至安装环境或采购人配合条件。
non_retain_reason: 原样保留会把非供应商可控事项变成供应商响应风险。
applicability_boundary:
  - 设备对环境有运行要求时，可作为安装环境说明，不宜作为供应商产品否决项。
anchor_policy: 锚点取环境条件所在完整分句。
basis_hint: 技术参数应聚焦供应商可提供、可证明的内容。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_044
risk_layer: general_tender
risk_type: 文本质量
risk_pattern: 单位、符号或专业计量表达疑似错误
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 单位异常、大小写异常、符号错写、常见专业单位疑似误用。
  - 人工意见出现“单位是否正确”“表述是否正确”。
keywords_for_retrieval: [单位错误, 计量单位, 符号错误, 专业单位, 表述核对]
typical_source_pattern:
  - 扭力、流速、压力、浓度等单位疑似错写。
  - 数字和单位之间格式混乱。
bad_case_core: 单位错误会导致技术指标含义完全变化。
recommended_comment_policy:
  - 建议提示：该处单位或符号可能有误，请核对专业计量单位和参数含义。
non_retain_reason: 原样保留会影响供应商响应和验收。
applicability_boundary:
  - AI 不应擅自改单位，只提示业务员核对。
anchor_policy: 锚点取包含单位的完整指标句。
basis_hint: 技术指标的单位和符号应准确。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_045
risk_layer: general_tender
risk_type: 文本质量
risk_pattern: 角色称谓或模板身份词残留
comment_action: 建议删除
evidence_strength: high
source_signals: [删除线计划, 非黑色字体计划, 批注计划]
trigger_signals:
  - 采购人、招标人、投标人、供应商、买方、卖方混用。
  - 出现“供应商投标人”“采购招标人”等模板拼接。
keywords_for_retrieval: [角色称谓, 模板残留, 采购人, 招标人, 投标人, 供应商, 买方卖方]
typical_source_pattern:
  - 同一条款同时出现买方/招标人/采购人。
  - 句子中保留多个候选角色词。
bad_case_core: 角色称谓混乱会影响合同责任主体和文档严谨性。
recommended_comment_policy:
  - 建议删除：该处存在角色称谓混用或模板残留，请统一为当前文件适用主体。
non_retain_reason: 原样保留会造成责任主体不清。
applicability_boundary:
  - 合同条款中买卖双方称谓可保留，但需前后一致。
anchor_policy: 锚点取称谓混用所在完整分句。
basis_hint: 合同和招标文件主体称谓应一致。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_046
risk_layer: general_tender
risk_type: 文本质量
risk_pattern: 病句、漏字或语义不完整
comment_action: 建议提示
evidence_strength: medium
source_signals: [批注计划, 删除线计划]
trigger_signals:
  - 句子明显不通顺、缺谓语或宾语、语义断裂。
  - 人工意见出现“表述是否正确”“不通顺”“这是什么描述”。
keywords_for_retrieval: [病句, 漏字, 表述不完整, 不通顺, 语义不清]
typical_source_pattern:
  - 参数句缺少对象或动作。
  - 功能描述无法判断“谁做什么、达到什么标准”。
bad_case_core: 文本错误虽不一定是合规问题，但会影响理解、响应和验收。
recommended_comment_policy:
  - 建议提示：该处表述不完整或不通顺，请补充主语、对象、指标或验收含义。
non_retain_reason: 原样保留会让供应商难以准确响应。
applicability_boundary:
  - 只对影响理解的文本错误生成批注，不对纯排版小问题过度批注。
anchor_policy: 锚点取语病所在最小完整句。
basis_hint: 采购文件应表达清楚、逻辑完整。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_047
risk_layer: medical_device
risk_type: 医疗注册与耗材
risk_pattern: 未采购耗材却要求耗材注册证或证明
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划]
trigger_signals:
  - 原文要求耗材注册证、耗材证明、配套耗材材料。
  - 采购范围未明确包含耗材。
  - 人工意见出现“本项目提供耗材吗？不提供不建议要求注册证”。
keywords_for_retrieval: [耗材, 注册证, 本次采购, 配套耗材, 涉证]
typical_source_pattern:
  - 设备采购条款要求提供耗材注册证。
  - 配置清单未列耗材但技术条款要求耗材证明。
bad_case_core: 未采购耗材时要求耗材注册证，会扩大响应范围并可能限制设备供应商。
recommended_comment_policy:
  - 建议提示：请确认本项目是否采购耗材；如不采购，不建议要求提供耗材注册证或相关证明。
non_retain_reason: 原样保留会让非采购对象成为响应门槛。
applicability_boundary:
  - 若耗材随设备交付或为合法使用必需，应在配置清单中明确。
anchor_policy: 锚点取耗材注册或证明要求完整句。
basis_hint: 证明要求应对应本次采购范围。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_048
risk_layer: medical_device
risk_type: 医疗注册与耗材
risk_pattern: 配置中哪些部件涉证不清
comment_action: 建议新增或明确
evidence_strength: high
source_signals: [批注计划]
trigger_signals:
  - 配置包含主机、附件、耗材、软件、模块等。
  - 原文笼统要求注册证或涉证材料。
  - 人工意见出现“以下哪些涉证”“哪些要证”。
keywords_for_retrieval: [涉证, 注册证, 配置部件, 主机, 附件, 耗材, 医疗器械]
typical_source_pattern:
  - 配置清单多项部件但只笼统写提供注册证。
  - 主机和附件是否均在注册证范围内不清。
bad_case_core: 医疗器械注册证应对应具体产品和配置范围，笼统索证不利于响应。
recommended_comment_policy:
  - 建议新增或明确：请确认各配置部件是否属于医疗器械注册证覆盖范围，并明确哪些部件需要提供注册证。
non_retain_reason: 原样保留会导致供应商提供材料范围不清。
applicability_boundary:
  - 对非医疗器械附件，不应机械要求注册证。
anchor_policy: 锚点取配置清单中涉证不清的具体行或章节标题。
basis_hint: 医疗器械证明材料应与注册产品范围一致。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_049
risk_layer: medical_device
risk_type: 医疗注册与耗材
risk_pattern: 设备必须适配指定品牌耗材或导管
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 出现兼容指定品牌耗材、导管、配件或“本公司导管”。
  - 未说明兼容标准、接口要求或临床必要性。
keywords_for_retrieval: [指定耗材, 指定导管, 兼容品牌, 配套使用, 医疗耗材, 指向性]
typical_source_pattern:
  - 设备要求与某品牌导管配合使用。
  - 参数要求兼容特定厂家耗材。
bad_case_core: 指定耗材或导管可能排斥其他合法注册产品。
recommended_comment_policy:
  - 建议提示：该处兼容要求可能指向特定耗材或导管，建议改为通用接口、注册范围或“兼容经认可的主流同类产品”等中立表述。
non_retain_reason: 原样保留可能造成耗材绑定和品牌排他。
applicability_boundary:
  - 若设备注册证明确限定配套耗材，应按注册证范围表达。
anchor_policy: 锚点取兼容指定耗材或导管的完整分句。
basis_hint: 医疗设备兼容要求应以合法注册范围和实际使用需求为基础。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_050
risk_layer: medical_device
risk_type: 医疗售后与培训
risk_pattern: 原厂工程师现场培训或跟台指导作为硬要求
comment_action: 建议提示
evidence_strength: high
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 出现原厂工程师、原厂培训、技术跟台指导、原厂资料。
  - 与设备装机、应用培训、维护培训绑定。
keywords_for_retrieval: [原厂工程师, 现场培训, 技术跟台, 原厂培训, 培训服务]
typical_source_pattern:
  - 设备装机后要求原厂工程师免费现场培训。
  - 要求原厂提供技术跟台指导。
bad_case_core: 原厂培训要求可能提高服务主体门槛，应确认是否必要。
recommended_comment_policy:
  - 建议提示：请确认是否必须由原厂工程师提供培训；如无必要，建议改为制造商或授权服务机构提供培训，并明确培训内容、次数和对象。
non_retain_reason: 原样保留可能排除具备能力的授权服务商。
applicability_boundary:
  - 高风险设备或注册要求限定培训主体时可保留。
anchor_policy: 锚点取原厂培训或跟台要求完整句。
basis_hint: 服务主体要求应与设备风险和履约需要匹配。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_051
risk_layer: medical_device
risk_type: 医疗售后与培训
risk_pattern: 医疗设备首次校准、计量或检定责任不清
comment_action: 建议新增或明确
evidence_strength: high
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 出现首次校准、首次计量、检定、校验证书、计量报告。
  - 未明确时间节点、费用承担、机构资质和验收关系。
keywords_for_retrieval: [首次校准, 计量, 检定, 校验证书, 计量报告, 验收]
typical_source_pattern:
  - 设备验收前需完成首次校准并提供证书。
  - 后期检定费用承担不清。
bad_case_core: 医疗设备计量校准直接影响验收和后续使用，责任边界需明确。
recommended_comment_policy:
  - 建议新增或明确：请明确首次校准/计量/检定的完成时间、费用承担、报告出具机构资质及是否作为验收条件。
non_retain_reason: 原样保留会导致验收前置条件和费用责任争议。
applicability_boundary:
  - 对无需计量校准的设备不触发。
anchor_policy: 锚点取校准、计量或检定要求完整条款。
basis_hint: 医疗设备验收条件应明确、可执行。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_052
risk_layer: medical_device
risk_type: 医疗售后与培训
risk_pattern: 保养计划频次和耗材损耗品范围不清
comment_action: 建议新增或明确
evidence_strength: medium
source_signals: [删除线计划, 非黑色字体计划]
trigger_signals:
  - 出现每年保养次数、周期维护、预防性保养、损耗品清单。
  - 未说明保养内容、材料费用或损耗品是否包含。
keywords_for_retrieval: [保养计划, 周期维护, 损耗品, 预防性保养, 保养次数]
typical_source_pattern:
  - 要求每年不少于若干次现场保养。
  - 要求列明预防性保养损耗品。
bad_case_core: 医疗设备维保条款应明确保养内容、频次和费用范围。
recommended_comment_policy:
  - 建议新增或明确：请明确保养频次、检测内容、损耗品清单及费用是否包含在报价或维保费用中。
non_retain_reason: 原样保留会让维保服务范围不可计算。
applicability_boundary:
  - 简单设备可不要求详细保养计划。
anchor_policy: 锚点取保养计划或损耗品要求完整句。
basis_hint: 维保服务应有明确服务清单和费用边界。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_053
risk_layer: medical_device
risk_type: 信息化接口
risk_pattern: 数据对接或第三方接口费用责任过宽
comment_action: 建议提示
evidence_strength: medium
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 要求免费开放数据接口、配合院内系统对接、承担第三方费用。
  - 费用、工期、第三方责任和验收关系不清。
keywords_for_retrieval: [数据对接, 接口费用, 第三方公司, 联机授权, 系统对接, 免费开放]
typical_source_pattern:
  - 设备需随时免费开放数据对接并承担相关费用。
  - 要求投标前与第三方公司沟通接口费用和工期。
bad_case_core: 接口对接涉及采购人系统、第三方厂商和供应商多方责任，不能无限扩大供应商义务。
recommended_comment_policy:
  - 建议提示：请明确数据对接范围、接口标准、费用承担、第三方责任和工期边界，避免将不可控第三方因素全部转由供应商承担。
non_retain_reason: 原样保留可能形成无法报价或不可控履约风险。
applicability_boundary:
  - 对必须接入院内系统的项目，应明确具体系统、接口和验收标准。
anchor_policy: 锚点取数据对接和费用承担完整条款。
basis_hint: 对接义务应边界清晰、责任可执行。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_054
risk_layer: medical_device
risk_type: 信息化接口
risk_pattern: 特定接口、RFID 或读卡器功能缺必要性
comment_action: 建议提示
evidence_strength: medium
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 出现 RFID、专用读卡器、特定接口、特殊数据读取方式。
  - 未说明项目验收必要性或等效方案。
keywords_for_retrieval: [RFID, 读卡器, 特定接口, 数据读取, 结构冗余, 指向性]
typical_source_pattern:
  - 要求支持特定读卡器或特定数据识别方式。
  - 要求具备 RFID 接口但未说明用途。
bad_case_core: 特定接口或识别方式可能是厂商标配功能，不一定是项目必要需求。
recommended_comment_policy:
  - 建议提示：请确认该接口或识别功能是否为项目验收必需；如非必需，建议删除或改为通用数据读取/识别能力。
non_retain_reason: 原样保留可能引入特定厂商结构特征。
applicability_boundary:
  - 若院内系统或设备安全确需该接口，应补充接口标准和兼容要求。
anchor_policy: 锚点取接口或读卡器功能完整分句。
basis_hint: 接口要求应服务实际对接和验收场景。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_055
risk_layer: medical_device
risk_type: 医疗人员与资质
risk_pattern: 服务人员经验或资质作为资格条件
comment_action: 建议提示
evidence_strength: medium
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 要求专职工程师、应用工程师、特定培训资质、人员经验。
  - 与行政许可或项目履约关系不清。
keywords_for_retrieval: [人员资质, 工程师经验, 应用工程师, 培训资质, 资格条件]
typical_source_pattern:
  - 供应商需设专业维修站并配专职工程师。
  - 到场工程师需提供特定培训证书。
bad_case_core: 人员资质要求若与项目履约不直接相关，容易变成不合理资格限制。
recommended_comment_policy:
  - 建议提示：请确认该人员资质是否与项目履约直接相关；如需要，可作为服务能力要求或评分项，避免设置为过窄资格条件。
non_retain_reason: 原样保留可能排除具备实际服务能力的供应商。
applicability_boundary:
  - 对特种设备、法定维修资质等有明确要求的情形可保留。
anchor_policy: 锚点取人员资质或经验要求完整句。
basis_hint: 资格条件应与采购项目履约直接相关。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_056
risk_layer: medical_device
risk_type: 医疗功能参数
risk_pattern: 重量、颜色、外观等非核心指标设为星号
comment_action: 建议提示
evidence_strength: medium
source_signals: [批注计划]
trigger_signals:
  - 重量、颜色、外观、体积、轻巧等被设置为 `★` 或核心要求。
  - 人工意见出现“重量不建议标注星号”“颜色是否具有指向性”。
keywords_for_retrieval: [重量, 颜色, 外观, 体积, 星号, 指向性]
typical_source_pattern:
  - 设备重量或颜色作为星号参数。
  - 外观结构描述过细。
bad_case_core: 非核心外观类指标通常不应作为否决项，除非有临床或安装必要性。
recommended_comment_policy:
  - 建议提示：请确认重量、颜色或外观要求是否为项目必要条件；不建议作为星号否决项，必要时可改为合理范围或一般要求。
non_retain_reason: 原样保留可能形成外观或结构指向。
applicability_boundary:
  - 对移动设备、承重限制或空间安装确有要求时，可保留合理范围。
anchor_policy: 锚点取外观类指标和星号标识所在完整句。
basis_hint: 否决指标应聚焦实质性能和履约必要性。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_057
risk_layer: medical_device
risk_type: 医疗功能参数
risk_pattern: 报警、提示、显示功能过度细化为特定呈现方式
comment_action: 建议提示
evidence_strength: medium
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 声音、图像、颜色、图标、错误代码、报警联动等描述过细。
  - 未说明必须采用该呈现方式的理由。
keywords_for_retrieval: [报警提示, 声光报警, 图像提示, 错误代码, 显示方式, 特定呈现]
typical_source_pattern:
  - 要求以特定图像显示错误提示。
  - 报警必须同时触发多个具体呈现方式。
bad_case_core: 功能可达成即可，过度限定呈现方式可能指向特定设备。
recommended_comment_policy:
  - 建议提示：请确认该报警/显示呈现方式是否必要；如只需实现提醒功能，建议改为通用声光报警、错误提示或明确最低功能要求。
non_retain_reason: 原样保留可能把厂商界面设计写成硬参数。
applicability_boundary:
  - 对安全风险提示有标准要求时，应按标准明确。
anchor_policy: 锚点取报警或显示方式完整分句。
basis_hint: 功能要求应避免无必要限定具体实现界面。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_058
risk_layer: medical_device
risk_type: 医疗功能参数
risk_pattern: “高温高压灭菌”等通用能力未说明条件
comment_action: 建议新增或明确
evidence_strength: medium
source_signals: [批注计划]
trigger_signals:
  - 出现高温高压灭菌、低温灭菌、消毒、重复使用等。
  - 未说明适用部件、温度压力条件、循环次数或标准。
keywords_for_retrieval: [高温高压灭菌, 低温灭菌, 消毒, 重复使用, 适用部件, 灭菌条件]
typical_source_pattern:
  - 多个部件均写可高温高压灭菌。
  - 灭菌能力没有测试条件或标准。
bad_case_core: 灭菌能力应对应具体部件和条件，否则无法验收。
recommended_comment_policy:
  - 建议新增或明确：请明确可灭菌的部件范围、灭菌方式、条件和依据；如只是通用能力，应避免重复堆叠。
non_retain_reason: 原样保留会让灭菌要求泛化且不可核验。
applicability_boundary:
  - 对医疗器械关键感染控制要求应保留，但需清楚条件。
anchor_policy: 锚点取灭菌要求所在完整分句。
basis_hint: 医疗设备感染控制要求应具体、可证明。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_059
risk_layer: general_tender
risk_type: 隐私与文档安全
risk_pattern: 联系人、电话或个人信息进入技术商务条款
comment_action: 建议删除
evidence_strength: medium
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 原文出现联系人、联系电话、手机号、个人姓名。
  - 与供应商响应、技术指标或合同履行无必要关系。
keywords_for_retrieval: [联系人, 联系电话, 手机号, 个人信息, 隐私, 文档脱敏]
typical_source_pattern:
  - 技术或对接条款末尾附联系人和电话。
  - 报修或沟通要求写私人联系方式。
bad_case_core: 个人信息不应沉淀到通用招标条款或知识库中。
recommended_comment_policy:
  - 建议删除：该处包含联系人或电话等个人信息，建议从技术商务条款中删除或改为正式联系渠道。
non_retain_reason: 原样保留存在隐私泄露和文档复用污染风险。
applicability_boundary:
  - 正式公告或采购文件规定的公共联系方式应按发布要求处理。
anchor_policy: 锚点只取“联系人/联系电话”等字段及相邻最小片段，不扩展到完整私人信息。
basis_hint: 招标文档复用应避免保留个人信息。
---END_BAD_CASE---

---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_060
risk_layer: general_tender
risk_type: 知识库噪声
risk_pattern: 只有短词、符号或“同上”的记录不入库
comment_action: 不入库
evidence_strength: high
source_signals: [批注计划, 删除线计划, 非黑色字体计划]
trigger_signals:
  - 仅有“同上”“请确认”“？”。
  - 仅锚定 `★`、`▲`、`≥`、`≤`、`等`、`至少` 等短词。
  - 无法扩展到完整原文分句和业务原因。
keywords_for_retrieval: [同上, 请确认, 短词锚点, 符号锚点, 噪声过滤]
typical_source_pattern:
  - `business_comment` 只有“同上”。
  - `reference_text` 只有一个符号或高频词。
bad_case_core: 这类记录不能独立表达风险，直接入库会污染召回结果。
recommended_comment_policy:
  - 不入库：除非能结合上下文还原完整风险模式，否则不要保存为 bad case。
non_retain_reason: 原样保留会让检索召回大量无意义片段，降低批注准确率。
applicability_boundary:
  - 如果相邻条款已提供完整风险原因，可将其并入对应风险模式，不单独成条。
anchor_policy: 不使用孤立短词作锚点；必须扩展到完整可搜索分句。
basis_hint: 知识库质量优先于覆盖数量。
---END_BAD_CASE---

---

## 入库与召回建议

### 分块规则

- 每个 `---BEGIN_BAD_CASE---` 到 `---END_BAD_CASE---` 是一个最小召回块。
- 不按字符数、句号、换行或 Markdown 标题切分 bad case 条目。
- 入库时以 `bad_case_id` 为主键，整块写入向量库和关键词索引。
- 如果后续条目变长，优先压缩字段内容，不拆分同一个 bad case。

### 向量召回建议

- embedding 文本建议包含完整 bad case 块，尤其是 `risk_pattern`、`trigger_signals`、`typical_source_pattern`、`bad_case_core`、`recommended_comment_policy`。
- 不建议只向量化关键词；关键词适合倒排检索，不能承载批注口径。
- 同一项目召回时优先选择 `evidence_strength: high` 且 `risk_layer` 匹配的条目。

### 关键词召回建议

- 关键词索引优先使用：
  - `keywords_for_retrieval`
  - `trigger_signals`
  - `typical_source_pattern`
  - `risk_type`
  - `risk_pattern`
- 采用组合触发，不建议单词命中即召回：
  - 不能只因出现“至少”就批注，应结合固定枚举、过细范围或特定配置。
  - 不能只因出现“证明材料”就批注，应结合普通参数、材料过窄、制造商盖章或机构口径不清。
  - 不能只因出现品牌词就一律删除，应区分历史系统兼容、市场主流泛化表达和指定品牌型号。
  - 不能只因出现 `★` 就批注，应结合星号过多、缺证明材料、标在大点或采购方式不匹配。

### Prompt 注入建议

- 注入给批注生成模型时，优先保留字段：
  - `risk_pattern`
  - `trigger_signals`
  - `typical_source_pattern`
  - `recommended_comment_policy`
  - `applicability_boundary`
  - `anchor_policy`
- 对同一风险类型召回多条时，最多注入 3-5 条最相关模式，避免上下文过载。
- 模型输出批注时应使用知识库里的动作分级：
  - `建议提示`：风险需要业务员确认或补充依据。
  - `建议删除`：明显不宜保留的品牌、型号、国外认证、主观宣传、无关业绩、个人信息等。
  - `建议新增或明确`：缺数量、缺单位、缺起算点、缺证明材料口径、缺验收边界等。

### 不应入库或低优先召回的内容

- 完整客户原文、联系人、电话、真实项目私有路径。
- 单次设备专属细节，无法抽象成其他项目可复用规则。
- 纯删除线或纯标色动作，且不能反推出批注原因。
- 只有“同上”“请确认”“不建议”“？”等口语短句的记录。
- 只有孤立符号或高频词的片段，例如 `≥`、`≤`、`★`、`▲`、`等`、`至少`。
