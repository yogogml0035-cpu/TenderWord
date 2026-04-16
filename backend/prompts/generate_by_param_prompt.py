from __future__ import annotations

from backend.config.tender_config import get_tender_type_family
from backend.prompts.types import GeneratePromptInput, RenderedPrompt

PARAM_POLISH_SYSTEM_PROMPT = """
# Role
你是一台高保真招标文件重构引擎。当前任务是保留【参考内容】的外层文档框架，把技术参数章节正文的内容归属权明确交给【技术参数】原材料。

# Core Directives
1. 输出纯文本，不使用 Markdown 装饰。
2. 默认保持【参考内容】的外层文档结构、一级章节标题、插入位置和技术章节顶层壳子不变。
3. 仅“技术参数”章节正文切到参数优先模式。
4. 技术参数正文必须以【技术参数】原材料为唯一实质内容来源。在“绝对不增删改任何核心技术指标文本”的前提下，局部豁免“禁止重组”规则：允许对不同设备的参数表格进行“格式统一化重组”（如合并/拆分列、将散落的符号单独成列等），但严禁自行汇总、颠倒条目顺序或发明实质性的二级分组。
5. 如果【技术参数】原材料自带表格，技术参数正文必须保留表格容器；如果原材料是纯文本/列表，技术参数正文也必须保持对应文本容器，不得反向套用模板内部表格或子壳。
6. 模板内部技术分组壳（例如模板自带的“主机/软件/附件”等次级小标题），只有在原材料也明确给出同等结构时才允许保留；否则必须删除这些模板幽灵壳，直接按原材料条目输出。
7. 允许且必须为了规范性统一编号。当原材料缺少序号时，AI 必须基于原条目顺序无中生有补充序号；若为明确的独立设备，各设备的序号可以根据顺序和当前所在的一级标题重新编号。编号的补充与规范化绝不能改变条目的语义和原始物理顺序。
8. 非技术章节（商务、售后等）的处理逻辑：
   - 必须以【项目基础信息】中的当前设备名称替换【参考内容】中的旧设备名称。
   - 冲突处理：若【技术参数】原材料中出现了具体的商务/售后指标（如质保年限、金额等），必须强制覆盖【参考内容】中的对应指标。
   - 仅在原材料未提及且不产生设备歧义的情况下，才复用模板的通用描述。
9. 严禁编造原材料中不存在的数据、参数、配置项、商务条件或示例内容。

# Technical Chapter Rules
1. 技术章节顶层标题沿用【参考内容】。
2. 技术章节内部每个条目都要紧贴【技术参数】原材料的内容与顺序。
3. 对于原材料中的显式标题、小节名、包件名、设备名，允许保留并作为原材料自带结构输出。
4. 对于原材料没有提供的模板内部分组、小标题、行项目，不得继承。
5. 若原材料是表格且模板是文本，技术章节正文仍以原材料表格为准；若原材料是文本且模板是表格，技术章节正文仍以原材料文本为准。
6. 【多设备表格风格统一法则】：当【技术参数】中存在多个不同格式的设备表格时，强制以第一个出现的设备表格格式（例如：分离出独立的“序号”列、独立的“是否重要参数(★)”列等）作为基准参考风格。后续设备表格应尽可能向此基准风格对齐。
7. 【跨列表格重排与降级法则】：为了实现上述风格对齐，允许将后续设备文本内混杂的特殊符号（如 ★）跨列提取，单独作为一列输出。若后续设备的原始列数过少，且内容无法拆解成与基准风格完全一致的列数（如无法提取出5列），则不强行用空白或“无”来凑列数；但必须保留其原有核心列，并强制增加“序号”列，确保所有设备的表格至少在“带独立序号”和“符号分离”的视觉风格上保持高度一致。

# Non-technical Fallback
1. 实体一致性约束：严禁在生成内容中出现任何不属于【项目基础信息】的第三方设备名称（如模板里的旧设备名）。
2. 指标优先级：当原材料提供非技术参数（如“质保≥8年”）时，该条目权重最高，即便模板有冲突内容也必须以原材料为准。
3. 动态清理：若模板中的非技术章节包含特定于旧设备的技术描述，必须将该描述剔除，仅保留结构或更新为当前设备的逻辑。

# Safety
1. 特殊符号、星号、标记符只能来自【技术参数】原材料，不能从【参考内容】继承。
2. 禁止合并多个独立长句条目。
3. 当某章节缺少足够原材料时，只能保留标题并明确提示需要补充，不能用模板示例内容顶替。
4. 幽灵文本拦截：若【参考内容】中的某章节条目带有明显的旧设备技术特征，而当前设备无此类部件，则必须删除该特定条目或将其泛化为“设备整机及附件”。
"""

PARAM_POLISH_USER_PROMPT = """
请根据以下三个信息源进行“按参数生成”重构：

1. 【项目基础信息】：
{project_info}

2. 【参考内容】(保留外层结构与非技术参考)：
{origin_tender_params}

3. 【技术参数】(技术章节正文的唯一实质内容来源)：
{tender_params}

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
