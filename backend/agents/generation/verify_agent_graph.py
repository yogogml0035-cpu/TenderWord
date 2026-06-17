import asyncio
import json
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from backend.agents.generation.agent_step_events import (
    emit_agent_step_event,
    get_configurable,
)
from backend.agents.generation.json_utils import (
    build_audit_findings_fallback,
    coerce_audit_findings,
    filter_noop_audit_findings,
    is_contract_placeholder_text,
    parse_audit_findings,
)
from backend.agents.generation.table_placeholder_utils import (
    build_missing_table_placeholder_findings,
    extract_table_placeholders,
    find_required_table_placeholders,
)
from backend.agents.generation.types import (
    AuditFinding,
    GenerationAgentProtocolError,
    GenerationAgentState,
)
from backend.agents.generation.workspace import (
    audit_path,
    context_value,
    get_workspace_backend,
    infer_current_text_path,
    infer_next_audit_round,
    read_backend_text,
    read_generation_context,
    write_backend_text,
)
from backend.util.common_util import StreamCallbacks, stream_llm_completion
from backend.util.log_util.progress_log import progress_log


CHECK_INTERVAL = 3.0
VERIFY_JSON_REPAIR_RETRY_LIMIT = 1
VERIFY_JSON_REPAIR_TEMPERATURE = 0.1
VERIFY_SYSTEM_PROMPT = """
你是招标文件采购需求审核智能体 content_verify_agent。

输出硬契约：
1. 只能输出严格合法的 JSON 数组本身，禁止输出“第 1 轮审核”、解释、Markdown、代码块、前后缀文本或自然语言总结。
2. 无问题时只输出 []。
3. 有问题时数组元素只能是对象，且只能包含两个非空字符串字段：evidence 和 fix_hint。
4. 字段名必须固定为英文 evidence 与 fix_hint，禁止使用“证据”“修复建议”等中文字段名，禁止增加 severity、type、round 等其它字段。
5. evidence 必须指出【待审核正文】中的具体问题、缺漏或多余内容，并引用可定位的正文片段或缺失的技术参数片段。
6. fix_hint 必须给出最小必要修复方式，要求保持其它内容不变。
7. 只输出需要修复的问题；不需要修改、实质一致、且不影响参数硬格式的外层格式差异必须省略，不能作为 finding 输出。技术参数内部格式、表格 schema、物理顺序、★/▲ 符号、符号归属或参数文字差异必须作为 finding 输出。
8. 禁止输出 evidence 写“两者一致/无问题”且 fix_hint 写“无需修改”的对象；这种情况等价于 []。

审核真源：
0. 本提示词中的“提供的参数”只指【技术参数（原材料，事实真源）】，绝不指【参考内容】或模板旧参数。
1. 【技术参数（原材料，事实真源）】是实质参数、参数格式、表格 schema、物理顺序、★/▲符号、包件数量和业务要求的事实真源。
2. 【项目基础信息】是项目名称、数量、交付地点、付款方式等基础信息的事实真源；不要用技术参数中的设备标题覆盖项目基础信息。
3. 【参考内容】只是受限的基础外层格式线索：只用于一级章节名称与顺序、项目概述/项目基本情况/项目概况/总体需求等基础信息章节中的项目元数据字段壳、编号标点、冒号形式、单行/多行字段容器、表格/纯文本容器、占位符/方括号样式和语气模具；它不得作为技术/服务/商务/售后参数正文、表格列名、表格行数、条款顺序、★/▲符号或参数格式的审核依据。项目元数据字段仅包括项目名称/采购名称/服务名称/设备名称及数量、地点、期限/日期、付款方式、预算/最高限价、包号/标段号、数量/单位。
4. template 生成风格要求镜像参考内容的外层格式壳，再用项目基础信息和技术参数替换事实内容；凡属于技术/服务/商务/售后参数本体的内容、格式、表格结构、条款顺序和 ★/▲ 符号，只能以技术参数为准。参数章节的行内格式和表格 schema 不属于可从参考内容继承的外层格式壳。
5. param 生成风格同样只继承受限基础格式；参数章节内部必须按参数优先生成提示词执行技术/服务条款接管、旧标题粉碎、无源旧事实删除、旧表壳清洗和连续重编号。
6. 投标评分细则、评分标准、评分要素、评审因素、分值、得分公式、评审价、评标基准价、评标方法与程序、评审办法和评分索引属于投标阶段打分规则，不是采购需求正文；即使夹在技术参数或参考内容中，也应删除，不得作为缺失参数要求补回。

必查规则：
1. 先从【技术参数】逐行/逐表格行抽取所有带 ★ 或 ▲ 的原子指标，形成唯一白名单；再审核【待审核正文】中的 ★/▲ 指标。技术参数中的每一条 ★ 或 ▲ 指标都必须在待审核正文中保留同类符号和对应参数内容，符号类型、指标归属、核心文字、数值、单位、所在原子条款或表格行必须与技术参数完全一致；除必要编号重排外，不能缺漏、降级为普通条款、换成另一种符号、合并到其它条款或拆散导致符号归属变化。
2. 待审核正文中不得额外增加技术参数原文没有的 ★ 或 ▲ 指标；参考内容里的 ★/▲ 是旧模板脏标记，不能继承到新正文，也不能作为要求补 ★/▲ 的依据。
3. 如果技术参数明显包含多个包件、标段、采购包或多个独立设备组，待审核正文必须覆盖全部包件；只生成其中一个包件时必须报缺失包件。
4. 技术参数中的实质参数、商务/售后要求、配置清单、表格列名、表格列数、表格行数和文本/表格容器不得被参考内容旧数据或旧格式替换；发现正文保留旧模板事实或旧表壳时才报错。
5. 所有生成风格下，待审核正文只能继承参考内容的基础非参数格式：一级章节名称与顺序、项目概述/项目基本情况/项目概况/总体需求等基础信息结构、字段标签、字段顺序、编号标点、冒号形式和字段容器。参考内容里的旧事实必须被项目基础信息或技术参数替换；不得因为参考内容存在旧技术/服务/商务/售后章节，就要求恢复其旧参数、旧表格、旧 ★/▲ 或旧子章节。
6. 基础信息章节格式镜像规则：若参考内容含有“项目概述/项目基本情况/项目概况/总体需求”等基础信息章节，必须按模板动态识别其中的项目元数据字段行/字段表，不得硬编码只审核交付日期或付款方式；只有项目名称、地点、期限/日期、付款方式、预算/最高限价、包号/标段号、数量/单位等静态元数据字段需要按模板字段壳审核。
7. 基础信息章节中的项目元数据字段必须按模板原格式壳生成：章节名、章节编号样式、字段标签、字段顺序、冒号形式、字段值与字段名同一行或同一单元格关系、单行/多行容器、表格/纯文本容器、占位符/方括号样式都要跟随模板。禁止把字段改写成散文句、合并成一段、拆到其它章节、换成另一套编号或从表格改成纯文本/从纯文本改成表格。
8. 区分“旧事实”“可继承的项目元数据字段壳”和“技术正文伪装字段”：旧设备名、旧日期、旧金额、旧参数值、旧服务范围、旧商务/售后条款、旧 ★/▲ 和旧表格 schema 不能继承；项目元数据字段名、编号、冒号、固定提示语、占位符、方括号和字段容器可以继承。若基础信息章节模板有白名单元数据字段但项目基础信息和技术参数没有给出新值，finding 必须要求恢复该字段行/字段表并保留模板占位符或固定表达；但服务范围、维保范围、功能检测范围、维护保养内容、设备清单、过滤器清单、备品备件、人员配备、资质要求、服务其他要求、报价要求、质量保证、执行标准等即使出现在项目概述里，也不得当作基础信息字段壳要求恢复。
9. template 生成风格下，技术参数应注入参考内容中的第一个核心技术章节；技术参数中出现的服务、商务、售后、配置清单、表格等内容必须按技术参数的内容、顺序、容器和 ★/▲ 生成。仅当技术参数已经接管旧技术章节时，才允许删除参考内容后续冗余技术类章节并顺延大标题序号；不能恢复参考内容中无新材料支撑的旧参数章节。
10. param 生成风格下，参数章节内部必须按参数优先生成提示词审核：项目元数据只覆盖参考内容已有语义槽位；技术/服务/商务/售后条款由技术参数按物理顺序、原始表格 schema、文本/表格容器和 ★/▲ 归属接管；旧模板中无新材料支撑的引导段、设备专属子标题、旧章节主体、旧表格列名/行数和旧商务事实必须删除；删除后编号必须从当前有效条目连续重排。
11. 技术参数内部的参数正文、商务/售后要求、配置清单、表格列名/列数/行数、文本/表格容器、物理顺序和 ★/▲ 归属是硬审核项，必须按技术参数比对；只有外层章节标题壳、章节编号样式和基础信息字段壳可以按参考内容基础格式与当前生成风格判断。不得用“语义相近”“格式差异”“参考内容是模板格式”放过 ★/▲ 或参数硬格式不一致。
12. param 生成风格下，如果技术参数自己的项目概述只提供项目名称、地点、期限、付款方式等元数据，而参考内容项目概述含旧服务范围、旧设备清单、旧过滤器清单、旧服务其他要求等，待审核正文删除这些旧字段是正确行为；不得因模板包含这些字段而输出 finding 要求恢复。
13. 待审核正文如包含“投标评分细则（100分）”、评分表、评分要素/分值/评分标准、报价得分公式、评审价/评标基准价等投标阶段打分内容，必须输出 finding 要求删除；但中标后履约服务质量考核、验收标准、整改扣罚等履约管理内容不按评分污染处理。

★/▲ 审核流程：
1. 把【技术参数】按物理换行、表格行、显式编号和冒号挂载列表拆成原子条款。
2. 对每个原子条款只看条款开头或编号前的 ★/▲，建立 `符号 + 核心参数文字 + 数值 + 单位 + 所属行/条款` 白名单。
3. 对【待审核正文】执行同样拆分，逐项匹配白名单；匹配不上就是多余 ★/▲、错符号、错归属或参数改写。
4. 【参考内容】中的 ★/▲ 必须先视为脏标记归零，不得作为固定前缀、编号样式、旧壳、表格格式或原样克隆文本。
5. 只要正文行的内容来自【技术参数】或由【技术参数】替换参考旧正文，该行是否带 ★/▲ 只能看对应技术参数原子条款，不能看参考内容对应槽位。
6. 如果正文缺少技术参数中的 ★/▲、把 ★ 写成 ▲ 或把 ▲ 写成 ★、把 ★/▲ 指标改写成普通描述、把普通条款误加 ★/▲，都必须输出 finding。

Few-shots：
输入要点：技术参数含 `★1.1、波长范围：400-700nm`，待审核正文写成 `1、波长范围：400-700nm`。
输出：
[{"evidence":"技术参数中的 `★1.1、波长范围：400-700nm` 是 ★ 指标，但待审核正文对应条款 `1、波长范围：400-700nm` 缺少 ★ 符号。","fix_hint":"将该正文条款改为带 ★ 的指标条款，保持参数文字不变。"}]

输入要点：技术参数含 `1.1、重量≤10kg` 且没有 ★/▲，待审核正文写成 `★1、重量≤10kg`。
输出：
[{"evidence":"技术参数中的 `1.1、重量≤10kg` 没有 ★ 或 ▲，但待审核正文额外写成 `★1、重量≤10kg`。","fix_hint":"删除该条正文中多余的 ★ 符号，保持参数文字不变。"}]

输入要点：技术参数包含“包件一：显微镜”和“包件二：离心机”，待审核正文只生成“包件一：显微镜”。
输出：
[{"evidence":"技术参数明显包含包件一和包件二，但待审核正文只覆盖包件一，缺少包件二 `离心机` 的采购需求内容。","fix_hint":"补充包件二及其对应技术参数内容，保持包件一内容不变。"}]

输入要点：参考内容含 `★质量保证期≥5年`，但技术参数为 `3. 质量保证期≥5年` 且没有 ★/▲，待审核正文写成 `3. 质量保证期≥5年`。
输出：
[]

输入要点：生成风格为 template 或 param，参考内容含 `一、项目概述\n1、设备名称及数量：球管/壹个\n2、交付日期：合同签订后两个月内交货\n3、付款方式：设备安装验收合格后的三个月内付清全款。`，待审核正文直接从 `一、技术参数` 开始，并把交付日期和付款方式拆成独立大章或普通段落。
输出：
[{"evidence":"参考内容包含 `一、项目概述` 以及按纯文本字段行排列的 `设备名称及数量`、`交付日期`、`付款方式` 字段，但待审核正文缺少该项目概述字段行格式壳，并将交付日期、付款方式拆成独立大章或普通段落。","fix_hint":"按参考内容恢复项目概述章节、编号样式和纯文本字段行顺序，用当前项目事实替换已有事实值；保持已生成的技术参数内容不变。"}]

输入要点：生成风格为 template 或 param，参考内容含 `一、项目基本情况\n1、项目预算：[以最终批复为准]\n2、交付地点：采购人指定地点`，项目基础信息和技术参数没有提供项目预算，待审核正文删除了 `项目预算` 字段。
输出：
[{"evidence":"参考内容的基础信息章节 `一、项目基本情况` 含有字段行 `1、项目预算：[以最终批复为准]`，但待审核正文删除了该字段；当前项目材料没有提供新预算值时也应保留该模板字段壳和占位表达。","fix_hint":"恢复 `1、项目预算：[以最终批复为准]` 这类模板字段行，保留模板占位/固定表达；不要删除该字段或编造预算金额，保持其它字段不变。"}]

输入要点：项目基础信息为“项目名称及数量：细胞电转仪 壹套”，参考内容旧设备名为“细胞自动计数仪”，技术参数为细胞电转仪参数，待审核正文使用“细胞电转仪”且参数完整。
输出：
[]

输入要点：技术参数第 3.1 条和待审核正文第 3.1 条的 ★ 符号、尺寸要求、接口数量和文字内容完全一致。
输出：
[]

输入要点：技术参数含 `★2.3、接口：USB≥4个，HDMI≥1个`，参考内容旧模板含 `▲2.3、接口：USB≥2个`，待审核正文写成 `▲2.3、接口：USB≥4个，HDMI≥1个`。
输出：
[{"evidence":"技术参数中的 `★2.3、接口：USB≥4个，HDMI≥1个` 是 ★ 指标，但待审核正文写成 `▲2.3、接口：USB≥4个，HDMI≥1个`，符号类型被参考内容旧 ▲ 劫持。","fix_hint":"将该正文条款的 ▲ 改为技术参数中的 ★，保持接口参数文字不变。"}]

输入要点：技术参数表格行含 `▲ 响应时间 ≤2s`，待审核正文将该指标拆成普通描述 `系统响应时间不超过2秒，符合要求`。
输出：
[{"evidence":"技术参数表格行 `▲ 响应时间 ≤2s` 是 ▲ 指标，但待审核正文将其改写为普通描述 `系统响应时间不超过2秒，符合要求`，缺少 ▲ 符号且参数文字不完全一致。","fix_hint":"按技术参数表格行恢复 `▲ 响应时间 ≤2s` 这类指标表达；不要改写为普通描述，保持其它内容不变。"}]

输入要点：待审核正文包含 `投标评分细则（100分）` 以及 `评分要素/分值/评分标准` 表格。
输出：
[{"evidence":"待审核正文包含 `投标评分细则（100分）` 和 `评分要素/分值/评分标准` 表格，这属于投标阶段打分规则，不是采购需求正文。","fix_hint":"删除该评分章节及其评分表，保留前后真实采购需求内容并连续重排编号。"}]
""".strip()
VERIFY_JSON_REPAIR_SYSTEM_PROMPT = (
    "你是 JSON 修复助手。只把输入修复为严格合法的 JSON 数组。"
    "数组每项必须包含非空字符串 evidence 和 fix_hint。禁止新增审核问题，禁止解释。"
)

# 确定性硬契约提示：[[TABLE:id]] 占位符只能原样保留，LLM 不得将其视为格式差异或用 Markdown 表等价替代。
TABLE_PLACEHOLDER_CONTRACT_PROMPT = (
    "【结构化表占位符硬契约】技术参数中的 `[[TABLE:<id>]]` 是结构化表的写回入口，属于运行时硬契约。\n"
    "- 只要【技术参数】包含 `[[TABLE:id]]`，待审核正文必须原样保留该占位符（独占一行），不得删除、改写、拆散或替换。\n"
    "- Markdown 表格、手绘表格、散文式参数列表、表格投影文本都不能视为占位符的等价替代；缺失占位符必须输出 finding。\n"
    "- 占位符内容 `[[TABLE:...]]` 本身必须逐字保留，不得改写括号、冒号或 id。\n"
)


def _merge_missing_table_findings(
    findings: list[AuditFinding],
    *,
    tender_params: Any,
    current_text: str,
) -> list[AuditFinding]:
    """在 LLM 审核结果基础上，追加确定性占位符缺失检查。

    只对 `tender_params` 中存在但 `current_text` 缺失的占位符报 finding；
    已命中的占位符不会被覆盖或重复报告。
    """
    required_ids = find_required_table_placeholders(tender_params, current_text)
    present_ids = set(extract_table_placeholders(current_text))
    missing_ids = [table_id for table_id in required_ids if table_id not in present_ids]
    if not missing_ids:
        return findings
    extra_findings = build_missing_table_placeholder_findings(missing_ids)
    if not extra_findings:
        return findings
    return [*findings, *extra_findings]


def _emit_verify_agent_step_snapshot(
    config: dict[str, Any] | None,
    *,
    content: str,
    round_index: int,
    is_complete: bool,
) -> None:
    try:
        emit_agent_step_event(
            config,
            round_index=round_index,
            node="content_verify_agent",
            content=content,
            is_complete=is_complete,
        )
    except Exception as exc:
        progress_log.debug(f"警告: content_verify_agent 过程回调失败: {exc}")


def _build_stream_callbacks(
    config: dict[str, Any] | None,
    *,
    round_index: int,
) -> StreamCallbacks:
    def _on_update(text: str) -> None:
        snapshot = str(text or "")
        if not snapshot:
            return
        _emit_verify_agent_step_snapshot(
            config,
            content=snapshot,
            round_index=round_index,
            is_complete=False,
        )

    return StreamCallbacks(on_update=_on_update)


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    raise RuntimeError("verify_agent cannot run inside an active event loop")


def _get_generation_context(config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    configurable = get_configurable(config)
    if not isinstance(configurable, dict):
        return {}
    context = configurable.get("generation_agent_context")
    return context if isinstance(context, dict) else {}


def _context_value(
    state: GenerationAgentState,
    config: dict[str, Any] | None,
    key: str,
    default: Any = "",
) -> Any:
    return context_value(state, config, key, default)


def _contract_error_needs_retry(error: BaseException) -> bool:
    message = str(error)
    return any(
        marker in message
        for marker in ("缺少 evidence", "必须是对象", "必须是 JSON 数组")
    )

def _render_json_repair_prompt(raw_content: str, error: BaseException) -> str:
    return (
        "请修复下面的审核智能体输出，使其成为严格合法的 JSON 数组。\n"
        "输出规则：\n"
        "1. 只输出 JSON 数组本身，不要解释，不要代码块。\n"
        "2. 每一项必须包含非空字符串字段 evidence 和 fix_hint。\n"
        "3. 不要新增原输出中没有表达的审核问题；只能补齐字段名、数组包裹、引号、逗号、转义和缺失字段。\n"
        "4. 如果某项只有 evidence，请根据 evidence 写最小修复建议；如果某项只有 fix_hint，"
        "请把该建议概括为 evidence，同时保留 fix_hint。\n"
        "5. 如果原输出表达“没有问题”，请输出 []。\n\n"
        f"解析错误：{error}\n\n"
        f"原始输出：\n{raw_content}"
    )

def _request_json_repair(
    raw_content: str,
    *,
    error: BaseException,
    model_provider: str,
) -> str:
    return str(
        _run_async(
            stream_llm_completion(
                model_provider=model_provider,
                system_prompt=VERIFY_JSON_REPAIR_SYSTEM_PROMPT,
                user_prompt=_render_json_repair_prompt(raw_content, error),
                callbacks=StreamCallbacks(),
                extra_params_override={"temperature": VERIFY_JSON_REPAIR_TEMPERATURE},
                check_interval=CHECK_INTERVAL,
            )
        )
    )

def _render_verify_user_prompt(
    *,
    generation_style: Any,
    project_info: Any,
    template_reference_text: Any,
    tender_params: Any,
    current_text: str,
) -> str:
    return (
        "请审核【待审核正文】是否违反当前项目的生成契约。\n\n"
        "输出必须是严格 JSON 数组：[] 或 "
        '[{"evidence":"...","fix_hint":"..."}]。'
        "不要输出解释、Markdown、代码块、轮次标题或其它字段。\n\n"
        "审核时请严格区分四类输入：\n"
        "1. 【生成风格】决定外层章节壳和基础信息字段壳的审核方式；template 和 param 都不能降低【技术参数】对参数本体、表格 schema、物理顺序和 ★/▲ 的硬审核优先级，不能用参考内容审核参数本体。\n"
        "2. 【项目基础信息】提供项目名称、数量、交付、付款等基础事实。\n"
        "3. 【参考内容】不是旧事实真源，也不是“提供的参数”；它只提供一级章节壳、基础信息章节中的项目元数据字段壳、编号标点、冒号、占位符和通用排版线索，不能提供技术/服务/商务/售后参数正文、表格 schema、条款顺序或 ★/▲。项目元数据字段仅包括项目名称、地点、期限/日期、付款方式、预算/最高限价、包号/标段号、数量/单位等。\n"
        "4. 【技术参数（原材料，事实真源）】才是本次审核所说的“提供的参数”，提供必须进入正文的实质参数、参数格式、技术/服务/商务/售后要求、表格 schema、物理顺序、★/▲指标和包件数量。\n\n"
        "重点检查：\n"
        "- 按审核流程先拆分【技术参数】原子条款，再建立 ★/▲ 白名单；不要直接按参考内容槽位或旧序号匹配。\n"
        "- 先从【技术参数】逐行/逐表格行抽取所有带 ★ 或 ▲ 的原子指标，形成唯一白名单；待审核正文中的每一个 ★/▲ 指标都必须命中该白名单。\n"
        "- 技术参数中出现的 ★、▲ 指标是否在正文中逐项保留同类符号和对应参数内容，符号类型、指标归属、核心文字、数值和单位必须完全一致。\n"
        "- ★/▲ 指标不允许用“语义相近”“只是格式差异”“按模板格式重排”判定通过；只要符号、参数文字、数值、单位、表格行归属或条款归属不一致，就必须输出 finding。\n"
        "- 正文是否额外增加了技术参数没有的 ★、▲ 指标；参考内容中的 ★、▲ 不能作为补符号依据。\n"
        "- 技术参数明显是多个包件/标段/采购包/独立设备组时，正文是否只生成了其中一个。\n"
        "- 正文是否用参考内容旧事实、旧表壳或旧参数格式替换了技术参数或项目基础信息中的新事实。\n"
        "- 基础信息章节按模板动态识别，覆盖项目概述/项目基本情况/项目概况/总体需求；只逐项比对其中的项目元数据字段列表、字段顺序和字段行/字段表容器。\n"
        "- 基础信息元数据字段行/字段表格式壳必须继承模板：章节名、编号样式、字段标签、冒号形式、单行/多行容器、表格/纯文本容器、占位符/方括号样式都要跟随参考内容。\n"
        "- 检查字段值是否仍与字段名保持模板中的同一行或同一单元格关系；不得把字段改写成段落、合并成散文句、拆到其他章节或换容器。\n"
        "- 模板有白名单元数据字段但当前项目材料无新事实时，应保留模板字段壳和占位/固定表达；不得建议删除字段或编造值。`项目预算` 等字段只有在模板基础信息章节本来存在时才纳入该章节审核。\n"
        "- 所有生成风格下，正文是否丢失或拆散参考内容的项目概述、项目基本情况、项目概况、总体需求等基础信息结构；不得把参考内容中的旧技术/服务/商务/售后章节或项目概述里的旧服务范围、旧设备清单、旧过滤器清单当作必须恢复的基础结构。\n"
        "- 参数章节是否符合当前生成风格：技术/服务/商务/售后条款由技术参数按物理顺序、原始表格 schema、文本/表格容器和 ★/▲ 归属接管；旧标题粉碎、无源旧事实删除、旧表壳清洗和连续重编号。\n"
        "- 参考内容中的技术/服务/商务/售后旧参数、旧表格、旧 ★/▲ 不得作为 finding 依据；只有技术参数或项目基础信息支持时才允许报缺失。\n"
        "- 正文是否误保留投标评分细则、评分标准、评分要素、评审因素、分值、得分公式、评审价、评标基准价、评标方法与程序、评审办法或评分索引；这些投标阶段打分内容必须删除，不得作为采购需求或商务条款保留。\n"
        "- 不要因为外层章节编号或标题壳与技术参数原文不同而报错；但参数正文、表格 schema、条款顺序和 ★/▲ 必须按技术参数审核。\n\n"
        + TABLE_PLACEHOLDER_CONTRACT_PROMPT
        + "\n"
        "只返回需要修复的问题；不需要修改的问题不要出现在 JSON 数组里。"
        "如果比对结论是“实质一致、无问题、无需修改”，必须输出 []，"
        "不要把一致性说明写成 evidence。\n\n"
        f"【生成风格】\n{generation_style or 'template'}\n\n"
        f"【项目基础信息】\n{project_info or ''}\n\n"
        f"【参考内容（仅外层格式线索；旧事实和旧参数不得继承）】\n{template_reference_text or ''}\n\n"
        f"【技术参数（原材料，事实真源）】\n{tender_params or ''}\n\n"
        f"【待审核正文】\n{current_text}"
    )

def _parse_or_repair_audit_findings(
    raw_content: str,
    *,
    model_provider: str,
) -> list[AuditFinding]:
    try:
        return filter_noop_audit_findings(parse_audit_findings(raw_content))
    except GenerationAgentProtocolError as first_error:
        last_error: BaseException = first_error

    if _contract_error_needs_retry(last_error):
        try:
            repaired_content = _request_json_repair(
                raw_content,
                error=last_error,
                model_provider=model_provider,
            )
            return coerce_audit_findings(repaired_content)
        except Exception as exc:
            last_error = exc

    try:
        return coerce_audit_findings(raw_content)
    except GenerationAgentProtocolError as exc:
        last_error = exc

    for _ in range(VERIFY_JSON_REPAIR_RETRY_LIMIT):
        try:
            repaired_content = _request_json_repair(
                raw_content,
                error=last_error,
                model_provider=model_provider,
            )
            return coerce_audit_findings(repaired_content)
        except Exception as exc:
            last_error = exc

    return build_audit_findings_fallback(last_error)


def _build_placeholder_text_findings(current_text: str) -> list[AuditFinding]:
    return [
        AuditFinding(
            evidence=(
                f"待审核正文只有占位符 `{current_text}`，不是实际采购需求正文。"
            ),
            fix_hint=(
                "返回上一轮真实采购需求正文并按审核意见做最小修复；"
                "不得输出尖括号占位符。"
            ),
        )
    ]


def _verify_text(
    state: GenerationAgentState,
    config: RunnableConfig | None = None,
) -> GenerationAgentState:
    backend = get_workspace_backend(config)
    file_context: dict[str, Any] = read_generation_context(backend) if backend else {}
    merged_state: GenerationAgentState = {**file_context, **state}
    if backend:
        current_text_path = str(
            _context_value(merged_state, config, "current_text_path")
            or infer_current_text_path(backend)
        )
        current_text = read_backend_text(backend, current_text_path)
        round_index = int(
            _context_value(merged_state, config, "revision_round", 0)
            or infer_next_audit_round(backend)
        )
    else:
        round_index = int(_context_value(state, config, "revision_round", 1) or 1)
        current_text = str(
            _context_value(state, config, "current_text")
            or _context_value(state, config, "draft_text")
            or ""
        )
    model_provider = str(_context_value(merged_state, config, "model_provider", "deepseek") or "deepseek")
    tender_params = _context_value(merged_state, config, "tender_params")
    if is_contract_placeholder_text(current_text):
        findings = _build_placeholder_text_findings(current_text)
    else:
        user_prompt = _render_verify_user_prompt(
            generation_style=_context_value(merged_state, config, "generation_style", "template"),
            project_info=_context_value(merged_state, config, "project_info"),
            template_reference_text=_context_value(merged_state, config, "template_reference_text"),
            tender_params=tender_params,
            current_text=current_text,
        )
        raw_content = _run_async(
            stream_llm_completion(
                model_provider=model_provider,
                system_prompt=VERIFY_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                callbacks=_build_stream_callbacks(config, round_index=round_index),
                check_interval=CHECK_INTERVAL,
            )
        )
        findings = _parse_or_repair_audit_findings(
            str(raw_content),
            model_provider=model_provider,
        )
    findings = _merge_missing_table_findings(
        findings,
        tender_params=tender_params,
        current_text=current_text,
    )
    findings_payload = [finding.model_dump() for finding in findings]
    findings_json = json.dumps(findings_payload, ensure_ascii=False)
    if backend:
        write_backend_text(backend, audit_path(round_index), findings_json)
        _emit_verify_agent_step_snapshot(
            config,
            content=findings_json,
            round_index=round_index,
            is_complete=True,
        )
    return {
        "messages": [AIMessage(content=findings_json)],
        "structured_response": findings_payload,
        "findings": findings_payload,
        **({"audit_path": audit_path(round_index)} if backend else {}),
    }


def verify_final_text_findings(
    *,
    final_text: str,
    generation_context: dict[str, Any],
    model_provider: str,
) -> list[AuditFinding]:
    """Run the verify contract without writing another audit artifact.

    即使 LLM 复核返回 `[]`，仍会叠加确定性 TABLE 占位符缺失检查，
    以保证最终正文不会静默丢失结构化表占位符。
    """
    current_text = str(final_text or "").strip()
    tender_params = generation_context.get("tender_params")
    if is_contract_placeholder_text(current_text):
        return _build_placeholder_text_findings(current_text)

    raw_content = _run_async(
        stream_llm_completion(
            model_provider=model_provider,
            system_prompt=VERIFY_SYSTEM_PROMPT,
            user_prompt=_render_verify_user_prompt(
                generation_style=generation_context.get("generation_style", "template"),
                project_info=generation_context.get("project_info"),
                template_reference_text=generation_context.get("template_reference_text"),
                tender_params=tender_params,
                current_text=current_text,
            ),
            callbacks=StreamCallbacks(),
            check_interval=CHECK_INTERVAL,
        )
    )
    findings = _parse_or_repair_audit_findings(
        str(raw_content),
        model_provider=model_provider,
    )
    return _merge_missing_table_findings(
        findings,
        tender_params=tender_params,
        current_text=current_text,
    )


def create_verify_agent_graph():
    builder = StateGraph(GenerationAgentState)
    builder.add_node("verify_text", _verify_text)
    builder.add_edge(START, "verify_text")
    builder.add_edge("verify_text", END)
    return builder.compile()


__all__ = [
    "VERIFY_JSON_REPAIR_SYSTEM_PROMPT",
    "VERIFY_SYSTEM_PROMPT",
    "create_verify_agent_graph",
    "verify_final_text_findings",
]
