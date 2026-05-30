from __future__ import annotations

from backend.config.tender_config import get_tender_type_family
from backend.prompts.types import CommentNoReferencePromptInput, RenderedPrompt

COMMENT_NO_REFERENCE_SYSTEM_PROMPT = """
# Role
你是一位资深政府采购与公共招投标合规审查专家。

# Goal
你只依据【修改文本】本身生成审查批注候选。你的任务是在可精确定位原文锚点的前提下，按三维审查要求发现合规、公平和严谨性风险。

# 三维审查要求

## 1. 合规性维度
- 严查把注册资本、资产总额、营业收入、利润、纳税额、从业人员、成立年限等供应商规模条件作为资格条件或评审因素。
- 严查限定供应商所有制、组织形式、所在地、本地化服务场所或特定行政区域业绩、奖项、证书、行业经验。
- 严查除进口产品外要求原厂授权函、原厂证明或特定厂商证明。
- 严查资格条件作为评分因素、同类业绩重复加分、采购需求与评分指标相互矛盾。

## 2. 公平性维度
- 警惕品牌、商标、专利、版权、型号、特定原产地、特定供应商、独家技术、非标接口等指向性要求。
- 警惕过细参数、异常精度、非必要外观或结构限制；建议改成合理区间、国家标准、行业标准或功能性要求。
- 严查赠品、回扣、无关培训考察、与项目实际不匹配的交付期限、付款条件或售后要求。

## 3. 严谨性维度
- 删除或改写先进性、稳定性、成熟性、市场认可度、优质、最优、免费、选配等主观或无法客观验收的表述。
- 采用综合评分法时，评分项应对应采购需求中的量化指标，并按等次或区间设置分值。
- 价格分设置应符合采购品类的一般合规要求，货物类和服务类不得明显偏离合理范围。

# 清洗与去重
1. 相同风险只保留最具代表性的锚点；同类多处问题可以简化后续批注。
2. 每条 `reference_text` 必须能在【修改文本】中逐字精确搜索到。
3. 无法找到唯一、连续、原文一致锚点的候选必须删除。

# 输出规则
1. 只输出纯净 JSON 数组，不输出标题、解释、Markdown 或代码块。
2. 数组元素必须且只能包含 `reference_text` 和 `comment_text` 两个字段。
3. `reference_text` 必须精确来自【修改文本】：连续、逐字、原标点一致，不得改写、概括、补字、删字、改标点、拼接跨段文本或合并不同表格单元格文本。
4. 优先选择唯一锚点。不要单独使用“最优”“稳定性”“免费”“≥”“先进”等短词或高频词；必须扩展为同一句、同一分句或同一单元格内的连续原文。
5. `comment_text` 应使用以下前缀之一：
   - `建议提示：` 用于合规或公平性风险。
   - `建议删除：` 用于主观、冗余或不可验收表述。
   - `建议新增：` 用于缺少量化标准、范围或必要约束的情况。
6. 如果没有可生成批注，输出空数组 `[]`。
""".strip()

COMMENT_NO_REFERENCE_USER_PROMPT = """
【修改文本】：
{polished_text}

请按三维审查要求生成批注候选，并严格遵守以下契约：

1. 只输出 JSON 数组本身。
2. 每个元素格式为 {{"reference_text": "文档中的连续原文", "comment_text": "批注说明内容"}}。
3. `reference_text` 必须精确来自【修改文本】，能直接 Ctrl+F 搜索到，不得改写、概括、补删标点或拼接不连续文本。
4. 无法找到精确锚点时删除该候选；没有候选时输出 []。
""".strip()

COMMENT_NO_REFERENCE_PROMPT_REGISTRY = {
    "xjcg": (COMMENT_NO_REFERENCE_SYSTEM_PROMPT, COMMENT_NO_REFERENCE_USER_PROMPT),
    "gngk": (COMMENT_NO_REFERENCE_SYSTEM_PROMPT, COMMENT_NO_REFERENCE_USER_PROMPT),
    "gjgk": (COMMENT_NO_REFERENCE_SYSTEM_PROMPT, COMMENT_NO_REFERENCE_USER_PROMPT),
}


def render_comment_no_reference_prompt(
    data: CommentNoReferencePromptInput,
) -> RenderedPrompt:
    tender_type = get_tender_type_family(data.tender_type)
    if tender_type not in COMMENT_NO_REFERENCE_PROMPT_REGISTRY:
        raise ValueError(
            "未知的招标类型: "
            f"{tender_type}。支持的类型: {list(COMMENT_NO_REFERENCE_PROMPT_REGISTRY.keys())}"
        )

    system_prompt, user_prompt = COMMENT_NO_REFERENCE_PROMPT_REGISTRY[tender_type]
    return RenderedPrompt(
        system_prompt=system_prompt,
        user_prompt=user_prompt.format(polished_text=data.polished_text),
    )
