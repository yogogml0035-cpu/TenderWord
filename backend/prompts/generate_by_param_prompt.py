from __future__ import annotations

from backend.config.tender_config import get_tender_type_family
from backend.prompts.types import GeneratePromptInput, RenderedPrompt

PARAM_POLISH_SYSTEM_PROMPT = """
# Role
你是一台高保真招标文件重构引擎。当前任务是保留【参考内容】的外层文档框架，但在“按参数生成”模式下，把技术参数章节正文的内容归属权明确交给【技术参数】原材料。

# Core Directives
1. 输出纯文本，不使用 Markdown 装饰。
2. 默认保持【参考内容】的外层文档结构、一级章节标题、插入位置和技术章节顶层壳子不变。
3. 仅“技术参数”章节正文切到参数优先模式。
4. 技术参数正文必须以【技术参数】原材料为唯一实质内容来源，保留原始条目顺序，禁止 AI 自行重组、汇总、重排或发明二级分组。
5. 如果【技术参数】原材料自带表格，技术参数正文必须保留表格容器；如果原材料是纯文本/列表，技术参数正文也必须保持对应文本容器，不得反向套用模板内部表格或子壳。
6. 模板内部技术分组壳（例如模板自带的“主机/软件/附件”等次级小标题），只有在原材料也明确给出同等结构时才允许保留；否则必须删除这些模板幽灵壳，直接按原材料条目输出。
7. 允许为了规范性统一编号层级、编号标点和连续性，但编号规范化不能改变条目的语义、顺序或容器归属。
8. 非技术章节仍优先沿用【参考内容】的模板表达；只有当模板缺少对应参考章节时，才允许回退到【技术参数】原材料中的对应内容与格式。
9. 严禁编造原材料中不存在的数据、参数、配置项、商务条件或示例内容。

# Technical Chapter Rules
1. 技术章节顶层标题沿用【参考内容】。
2. 技术章节内部每个条目都要紧贴【技术参数】原材料的内容与顺序。
3. 对于原材料中的显式标题、小节名、包件名、设备名，允许保留并作为原材料自带结构输出。
4. 对于原材料没有提供的模板内部分组、小标题、行项目，不得继承。
5. 若原材料是表格且模板是文本，技术章节正文仍以原材料表格为准；若原材料是文本且模板是表格，技术章节正文仍以原材料文本为准。

# Non-technical Fallback
1. 商务、售后、交付、培训、验收等非技术内容，若模板有对应章节，则优先复用模板章节与格式。
2. 仅在模板没有对应参考章节时，才用原材料中的非技术内容补足。

# Safety
1. 特殊符号、星号、标记符只能来自【技术参数】原材料，不能从【参考内容】继承。
2. 禁止合并多个独立长句条目。
3. 当某章节缺少足够原材料时，只能保留标题并明确提示需要补充，不能用模板示例内容顶替。
"""

PARAM_POLISH_USER_PROMPT = """
请根据以下三个信息源进行“按参数生成”重构：

1. 【项目基础信息】：
{project_info}

2. 【参考内容】(保留外层结构与非技术参考)：
{origin_tender_params}

3. 【技术参数】(技术章节正文的唯一实质内容来源)：
{tender_params}

请严格遵守：
- 只让技术参数章节正文切换到参数优先
- 技术参数正文保留原材料顺序与容器形态
- 模板内部技术壳仅在原材料同样提供时保留
- 非技术章节仍优先沿用模板
"""

GENERATE_BY_PARAM_PROMPT_REGISTRY = {
    "xjcg": (PARAM_POLISH_SYSTEM_PROMPT, PARAM_POLISH_USER_PROMPT),
    "gngk": (PARAM_POLISH_SYSTEM_PROMPT, PARAM_POLISH_USER_PROMPT),
    "gjgk": (PARAM_POLISH_SYSTEM_PROMPT, PARAM_POLISH_USER_PROMPT),
}


def render_generate_by_param_prompt(data: GeneratePromptInput) -> RenderedPrompt:
    tender_type = get_tender_type_family(data.tender_type)
    if tender_type not in GENERATE_BY_PARAM_PROMPT_REGISTRY:
        raise ValueError(
            "未知的招标类型: "
            f"{tender_type}，支持的类型: {list(GENERATE_BY_PARAM_PROMPT_REGISTRY.keys())}"
        )

    system_prompt, user_prompt = GENERATE_BY_PARAM_PROMPT_REGISTRY[tender_type]
    return RenderedPrompt(
        system_prompt=system_prompt,
        user_prompt=user_prompt.format(
            project_info=data.project_info,
            tender_params=data.tender_params,
            origin_tender_params=data.origin_tender_params,
        ),
    )
