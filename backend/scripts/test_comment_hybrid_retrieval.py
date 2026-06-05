from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.retrieval.bad_case_loader import BadCaseChunk  # noqa: E402
from backend.retrieval.bm25 import BM25Index  # noqa: E402
from backend.retrieval.config import load_retrieval_config  # noqa: E402
from backend.retrieval.embeddings import EmbeddingClient  # noqa: E402
from backend.retrieval.hybrid import HybridHit, hybrid_search  # noqa: E402
from backend.retrieval.qdrant_store import QdrantBadCaseStore  # noqa: E402


TEST_USER_DOCUMENT = """
第1包：团体心率变异检测仪
一、项目概述
1、设备名称及数量：团体心率变异检测仪 壹套
2、交付日期：接到医院通知后的一周内交付
3、交付地点：采购人指定地点
4、付款方式：验收合格后2个月内支付剩余100%货款
5、主要用途：用于心率变异的测定，通过分析结果为诊断自主神经功能变化提供依据
6、主要配置（要求提供配置清单）：
无线信号终端含电池7台、心电电极线*7根、充电线*7根、记忆卡*7张、心电电极夹*7组、工作站*2套、笔记本电脑*2台、台车*1辆、打印机*2台
二、技术需求
1、★设备采用无线信号采集终端
2、设备内置充电式锂电池，符合安全规定，电池容量≥1000mAh。
3、★无线信号采集终端支持双手握持检测、直连心电导联线等检测方式,方便临床快速检测。
4、设备可测量心率范围30-200bpm，心率误差：0bpm。
5、自动侦别与异常处理:自动侦别心率指数，检测中如有异常指标系统自动侦测，系统自动剃除异常心率并延长检测时间,确保临床数据采集足量。
6、ECG采样率:125~512Hz。
7、无线采集在无遮蔽物3米的传输范围及2.4GHz固定频段内不掉包传输。
8、无线信号采集终端具备4G记忆卡,可储存20000笔独立资料,可即时传输或通过USB端口传输保存。
9、无线采集终端有实体按键可启动/取消测量。
10、★集成式系统最多同时支持16台无线信号终端进行检测。
11、无线采集终端: 可独立进行检测操作无需搭配工作站或笔记本电脑, 完成患者数据采集及存储, 方便医院科室在多种场景(如社区义诊ˎ病房巡查)下完成检测诊断需求。
12、★心率变异分析指标时域参数应包含：平均RR间期（ms）、平均心率（次/分钟）、最大心率(次/分钟)、最小心率(次/分钟)、NN50（次）、pNN50（%）、心率变异标准偏差(SDNN)、连续RR间期差。
13、★心率变异分析指标频域参数应包含析：总能量（TP）、极低频（VLF）、低频（LF）、高频（HF）、高低频比率(LF/HF)。
14、植物神经分析指标：提供植物神经分析功能，提供交感神经与副交感神经的五阶分类图，并清晰表述交感神经与副交感神经的临床统计偏差指标(б), 作为临床诊治的参考依据。
15、将测量结果对比标准数据库，可至少得到心电图波形和阴阳太极图。
16、提供个性化的亚健康心身健康评估≥16种，系统可根据评估结果给与饮食，营养，运动，作息等四方面的个性化指导建议。
17、报告自定义：可自定义设置报告建议内容，设置调整文字说明。
18、个性化模版设置，可供医院设置诊断报告名称，操作人员，方便病情追踪与报告解读。
三、售后服务及其他要求
1、投标方必须为产品制造商，或授权的销售代理商,如为销售代理商，须在投标文件中提供产品制造商出具的针对本次招标的投标授权函原件。
2、具备医疗器械注册证
3、提供用户名单。
4、投标产品必须符合国家相关法律法规要求，如因违犯国家法律法规，由此引的任何责任和损失，由投标方全部承担。
5、投标方负责确认安装环境达到装机要求并确保器械安全无损地运抵医院指定现场，同时承担器械的运费、保险费、装卸费等费用。投标方还应在发货前通知院方器械的运输信息以及到货时间，以便院方做好验货准备。
6、投标方负责免费完成器械的现场安装和调试，并提供器械安装和维修所需的专用工具和辅助材料，同时提供设备安装方案。
7、安装完成后投标方负责免费提供原厂工程师现场培训，在使用一段时间后可根据院方的要求另行安排培训计划，并随时接受院方使用人员有关器械使用的咨询，积极解答相关操作问题。
8、★原厂免费保修不少于五年（包含所有零配件需制造商盖章）、终身免费提供软件升级维护，并提供终生维修和维护服务，保修期过后的维修免除一切人工费、差旅费等费用。接到报修2小时内响应，24小时内到达现场维修。
9、保修期过后设备提供终生维修和维护服务，每年对设备进行定期巡检。提供的维修、移机、咨询、培训等服务免除一切人工费、差旅费、咨询费、服务费等费用。接到报修2小时内响应，24小时内到达现场维修。
10、在设备达到使用年限后每年提供免费的原厂设备性能检测服务并出具检测报告（检测报告需制造商盖章），供医院判断设备是否能够继续正常使用。
11、提供系统的软件清单（如有）、现有硬件部分的主要零配件及壹万元以上易损易耗件的价格清单，未提供价格的配件默认为在壹万元人民币以下。
12、储备足够的零配件备库，保修期满后以优惠价格供应维修零配件。
13、★免费开放所提供检测设备的数字化接口，并承担接入医院信息系统所需的所有接口费用
14、投标方负责免费提供中文操作手册及其他有关文字资料。
15、投标产品必须为2025年5月以后生产的设备。
16、★投标方需按招标文件要求提交必要的资质证明文件复印件并加盖公章。
17、投标方根据医院实际情况制定相应的安装和服务规程。
18、★中标供应商应在1个月内完成设备的备货工作，完成备货并接到医院通知后的一周内交付。

第2包：肌电图诱发电位仪
一、项目概述
1、设备名称及数量：肌电图诱发电位仪 壹套
2、交付日期：接到医院通知后的一周内交付
3、交付地点：采购人指定地点
4、付款方式：验收合格后2个月内支付剩余100%货款
5、主要用途：用于肌电图、神经传导、诱发电位记录，用于神经肌肉疾病的辅助诊断。
6、主要配置（要求提供配置清单）：
主机病人单元1套、肌电图诱发电位信号采集放大器2个、黑白激光打印机1台、电脑工作站1台、仪器推车1台、肌电图和诱发电位专业软件1套、声学耳机1个、肌电诱发电位标准配件1套
二、技术需求
1、★肌电图通道数：≥6通道，双放大器配置，内置标准5芯屏蔽信号采集大圆插孔≥6个 。
2、放大器噪声水平：≤0.4uV；共模抑制比≥124dB(平衡模式)
3、★听刺激器耳机最大强度：≤132 dB，音调频率：125Hz–20000Hz可自定义。
4、输入阻抗：≥1000MΩ
5、放大器A/D转换≥16 bit
6、低通滤波至少包含20Hz-13KHz
7、高通滤波至少包含0.01Hz-3KHz
8、电流刺激类型：仅限恒流；刺激频率至少包含0.01Hz～200Hz
9、刺激分辨率至少具备0.1mA与0.01mA两种模式可选
10、电流刺激强度至少包含0-100mA
11、电流刺激输出模式至少包含单、交替、突发、串、冲撞
12、听觉刺激器输出: 声学耳机。
13、听觉刺激刺激波形至少包含喀喇音、纯音、爆发音、半正弦、正弦
14、台式电脑主机配置不低于i3处理器，内存≥8G，硬盘≥256固态+2T机械
15、★具备独立的专用控制键盘（非普通电脑键盘）,快捷按键数量≥50个，内含刺激输出调节及0-9数字输入键盘功能，支持升级原厂便携式掌上肌电和电刺激器（刺激强度至少包含0-15mA，电池供电）功能。
16、具备运动传导速度测定,感觉传导速度测定,inch微移定位,F-波,H-反射功能
17、具备重复频率电刺激, 瞬目反射，植物神经电反应功能
18、具备定量肌电图分析：静息电位、单MUP、多MUP自动及手动分析、干扰相(重收缩)自动分析功能
19、具备终端潜伏期指数（TLI）
20、具备体感诱发电位（上肢体感、下肢体感、脊髓诱发、三叉神经体感等）
21、具备脑干听觉诱发电位
22、具备腕管综合征专用程序
三、售后服务及其他要求
1、投标方必须为产品制造商，或授权的销售代理商,如为销售代理商，须在投标文件中提供产品制造商出具的针对本次招标的投标授权函原件。
2、具备医疗器械注册证
3、提供用户名单。
4、投标产品必须符合国家相关法律法规要求，如因违犯国家法律法规，由此引的任何责任和损失，由投标方全部承担。
5、投标方负责确认安装环境达到装机要求并确保器械安全无损地运抵医院指定现场，同时承担器械的运费、保险费、装卸费等费用。投标方还应在发货前通知院方器械的运输信息以及到货时间，以便院方做好验货准备。
6、投标方负责免费完成器械的现场安装和调试，并提供器械安装和维修所需的专用工具和辅助材料，同时提供设备安装方案。
7、安装完成后投标方负责免费提供原厂工程师现场培训，在使用一段时间后可根据院方的要求另行安排培训计划，并随时接受院方使用人员有关器械使用的咨询，积极解答相关操作问题。
8、原厂免费保修不少于5年（包含所有零配件制造商盖章或总代理商盖章）、终身免费提供软件升级维护，并提供终生维修和维护服务，保修期过后的维修免除一切人工费、差旅费等费用。接到报修2小时内响应，24小时内到达现场维修。
9、保修期过后设备提供终生维修和维护服务，每年对设备进行定期巡检。提供的维修、移机、咨询、培训等服务免除一切人工费、差旅费、咨询费、服务费等费用。接到报修2小时内响应，24小时内到达现场维修。
10、在设备达到使用年限后每年提供免费的原厂设备性能检测服务并出具检测报告（检测报告需制造商或总代理商盖章），供医院判断设备是否能够继续正常使用。
11、提供系统的软件清单（如有）、现有硬件部分的主要零配件及壹万元以上易损易耗件的价格清单，未提供价格的配件默认为在壹万元人民币以下。
12、储备足够的零配件备库，保修期满后以优惠价格供应维修零配件。
13、★免费开放所提供检测设备的数字化接口，并承担接入医院信息系统所需的所有接口费用
14、投标方负责免费提供中文操作手册及其他有关文字资料。
15、投标产品必须为2025年5月以后生产的设备。
16、★投标方需按招标文件要求提交必要的资质证明文件复印件并加盖公章。
17、投标方根据医院实际情况制定相应的安装和服务规程。
18、★中标供应商应在1个月内完成设备的备货工作，完成备货并接到医院通知后的一周内交付。
""".strip()


TEST_KNOWLEDGE_FILE = PROJECT_ROOT / "backend" / "test_doc" / "comments_bad_case_knowledge_essence_v2.md"


@dataclass(frozen=True)
class KnowledgeCase:
    bad_case_id: str
    text: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class QueryClause:
    clause_id: str
    package: str
    section: str
    title: str
    text: str


@dataclass(frozen=True)
class ClauseRiskProfile:
    risk_types: tuple[str, ...]
    reasons: tuple[str, ...]


DISPLAY_HYBRID_THRESHOLD = 0.8


def configure_console_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(errors="replace")
        except Exception:
            pass


def _preview(text: str, limit: int = 220) -> str:
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def load_real_bad_case_chunks(path: Path) -> list[BadCaseChunk]:
    raw_text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"---BEGIN_BAD_CASE---\s*(.*?)\s*---END_BAD_CASE---",
        re.DOTALL,
    )
    field_pattern = re.compile(r"^([a-z_]+):\s*(.*)$")
    chunks: list[BadCaseChunk] = []

    for block_index, match in enumerate(pattern.finditer(raw_text)):
        block = match.group(1).strip()
        lines = block.splitlines()
        fields: dict[str, str] = {}
        current_key: str | None = None
        current_lines: list[str] = []

        def flush_field() -> None:
            nonlocal current_key, current_lines
            if current_key:
                fields[current_key] = "\n".join(current_lines).strip()
            current_key = None
            current_lines = []

        for raw_line in lines:
            line = raw_line.rstrip()
            field_match = field_pattern.match(line)
            if field_match:
                key = field_match.group(1)
                if key.islower():
                    flush_field()
                    current_key = key
                    current_lines = [field_match.group(2).strip()]
                    continue
            if current_key:
                current_lines.append(line)

        flush_field()

        bad_case_id = fields.get("bad_case_id", f"unknown_{block_index:03d}")
        title = fields.get("risk_pattern", bad_case_id)
        risk_layer = fields.get("risk_layer", "")
        risk_type = fields.get("risk_type", "")
        comment_action = fields.get("comment_action", "")
        evidence_strength = fields.get("evidence_strength", "")

        full_text = block
        chunks.append(
            BadCaseChunk(
                chunk_id=f"{bad_case_id}:full",
                case_id=bad_case_id,
                title=title,
                field="full",
                text=full_text,
                metadata={
                    "case_id": bad_case_id,
                    "title": title,
                    "risk_layer": risk_layer,
                    "risk_type": risk_type,
                    "comment_action": comment_action,
                    "evidence_strength": evidence_strength,
                    "field": "full",
                    "chunk_type": "case",
                },
            )
        )

        for field_name in (
            "risk_pattern",
            "trigger_signals",
            "keywords_for_retrieval",
            "typical_source_pattern",
            "bad_case_core",
            "recommended_comment_policy",
            "applicability_boundary",
            "anchor_policy",
            "basis_hint",
        ):
            content = fields.get(field_name, "").strip()
            if not content:
                continue
            chunk_text = "\n".join(
                [
                    f"bad_case_id: {bad_case_id}",
                    f"risk_layer: {risk_layer}",
                    f"risk_type: {risk_type}",
                    f"{field_name}: {content}",
                ]
            )
            chunks.append(
                BadCaseChunk(
                    chunk_id=f"{bad_case_id}:{field_name}",
                    case_id=bad_case_id,
                    title=title,
                    field=field_name,
                    text=chunk_text,
                    metadata={
                        "case_id": bad_case_id,
                        "title": title,
                        "risk_layer": risk_layer,
                        "risk_type": risk_type,
                        "comment_action": comment_action,
                        "evidence_strength": evidence_strength,
                        "field": field_name,
                        "chunk_type": "field",
                    },
                )
            )

    return chunks


def split_user_document_into_clauses(raw_text: str) -> list[QueryClause]:
    package_pattern = re.compile(r"^第\d+包：.*$")
    section_pattern = re.compile(r"^[一二三四五六七八九十]+、.*$")
    clause_pattern = re.compile(r"^\d+、.*$")

    package = ""
    section = ""
    current_title = ""
    current_lines: list[str] = []
    clauses: list[QueryClause] = []
    clause_count = 0

    def flush_clause() -> None:
        nonlocal current_title, current_lines, clause_count
        if not current_title or not current_lines:
            return
        clause_count += 1
        clause_text = "\n".join(current_lines).strip()
        clauses.append(
            QueryClause(
                clause_id=f"clause_{clause_count:03d}",
                package=package,
                section=section,
                title=current_title,
                text=clause_text,
            )
        )
        current_title = ""
        current_lines = []

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if package_pattern.match(line):
            flush_clause()
            package = line
            section = ""
            continue
        if section_pattern.match(line):
            flush_clause()
            section = line
            continue
        if clause_pattern.match(line):
            flush_clause()
            current_title = line
            current_lines = [line]
            continue
        if current_lines:
            current_lines.append(line)

    flush_clause()
    return clauses


def build_clause_only_query(clause: QueryClause) -> str:
    return clause.text


def build_package_section_clause_query(clause: QueryClause) -> str:
    return "\n".join(
        part
        for part in (
            clause.package.strip(),
            clause.section.strip(),
            clause.text.strip(),
        )
        if part
    )


def generate_clause_risk_profile(clause: QueryClause) -> ClauseRiskProfile:
    """Route a user clause to likely bad-case risk types using deterministic signals."""

    source_text = build_package_section_clause_query(clause)
    section = clause.section
    text = clause.text
    ordered_risk_types: list[str] = []
    reasons: list[str] = []

    def add(risk_type: str, reason: str) -> None:
        if risk_type in ordered_risk_types:
            return
        ordered_risk_types.append(risk_type)
        reasons.append(reason)

    def contains_any(patterns: tuple[str, ...]) -> bool:
        return any(pattern in source_text for pattern in patterns)

    def matches(pattern: str) -> bool:
        return re.search(pattern, source_text, re.IGNORECASE) is not None

    if "技术" in section:
        add("医疗功能参数", "section=技术需求")

    if "售后" in section or contains_any(("保修", "维修", "维护", "巡检", "培训")):
        add("售后保修", "section/keyword=售后保修维修培训")

    if contains_any(("付款", "支付", "货款", "验收合格", "发票", "财政资金", "中小企业")):
        add("付款交付", "keyword=付款/支付/验收")

    if contains_any(("交付", "到货", "备货", "送达", "交付地点", "交付日期")):
        add("付款交付", "keyword=交付/到货/备货")

    if contains_any(("配置", "清单", "数量", "单位", "规格", "壹套", "壹批", "主机", "附件", "配件")):
        add("配置与采购范围", "keyword=配置/数量/采购范围")

    if contains_any(("注册证", "医疗器械", "耗材", "涉证", "导管")):
        add("医疗注册与耗材", "keyword=注册证/医疗器械/耗材")

    if contains_any(("接口", "数据对接", "数字化", "医院信息系统", "第三方", "联机", "RFID", "读卡器")):
        add("信息化接口", "keyword=接口/数据对接/第三方")

    if contains_any(("原厂工程师", "原厂培训", "现场培训", "计量", "检定", "校准", "校验证书", "计量报告")):
        add("医疗售后与培训", "keyword=原厂培训/计量校准")

    if contains_any(("专职工程师", "应用工程师", "人员资质", "培训资质", "维修站")):
        add("医疗人员与资质", "keyword=人员/工程师/资质")

    if contains_any(("用户名单", "用户案例", "销售案例", "三甲医院", "引进家数", "市场占有", "循证医学", "专家共识")):
        add("市场与业绩限制", "keyword=用户案例/市场证据")

    if contains_any(("免费", "赠送", "赠品", "额外", "终身免费", "免除")):
        add("免费额外与选配", "keyword=免费/赠送/额外")

    if contains_any(("联系人", "联系电话", "手机号", "手机号码")):
        add("隐私与文档安全", "keyword=联系人/电话")

    if matches(r"\b(CE|FDA|ISO|IEC|EN|ASTM|UL)\b") or contains_any(("国外认证", "国外标准", "境外认证")):
        add("国外认证标准", "keyword=国外认证/标准")

    if contains_any(("品牌", "型号", "本公司", "我公司", "同品牌", "OEM", "原装", "专用", "厂家授权", "制造商授权")):
        add("品牌型号指向", "keyword=品牌/型号/厂家授权")

    if contains_any(("证明", "承诺函", "盖章", "检测报告", "检验报告", "证书", "专利", "资料复印件")):
        add("证明材料", "keyword=证明/报告/证书")

    if "★" in text or "▲" in text:
        add("指标等级", "keyword=星号/三角号指标")

    if (
        matches(r"[≥≤><＞＜]")
        or matches(r"\d+(?:\.\d+)?\s*(?:mAh|Hz|KHz|GHz|bpm|dB|bit|mA|MΩ|ms|%|米|台|套|个|根|张|组|辆|笔|种|通道)")
        or contains_any(("不小于", "不大于", "不少于", "至少", "范围", "误差", "精度", "采样率", "容量"))
    ):
        add("参数边界", "keyword=数值/范围/边界")

    if contains_any(("至少包含", "最多同时", "固定频段", "实体按键", "直连", "双手握持", "专用控制键盘", "固定档位")):
        add("参数指纹", "keyword=固定组合/结构特征")

    if contains_any(("快速", "智能", "先进", "稳定", "高效", "清晰", "方便", "个性化", "自动")):
        add("表述可验收性", "keyword=主观/效果性表述")

    if contains_any(("心率", "肌电", "诱发电位", "神经", "ECG", "导联", "RR", "NN50", "SDNN", "LF", "HF", "植物神经", "工作站")):
        add("医疗功能参数", "keyword=医疗功能/临床指标")

    if contains_any(("和/或", "或者", "前文", "不一致")):
        add("内部一致性", "keyword=逻辑关系/一致性")

    if contains_any(("包含析", "由此引", "给与", "剃除", "模版", "ˎ")):
        add("文本质量", "keyword=疑似错字/病句")

    if not ordered_risk_types and "项目概述" in section:
        add("配置与采购范围", "fallback=项目概述")

    if not ordered_risk_types:
        add("表述可验收性", "fallback=未命中具体规则")

    return ClauseRiskProfile(
        risk_types=tuple(ordered_risk_types[:5]),
        reasons=tuple(reasons[:5]),
    )


def dedupe_hits_by_case_id(hits: list[HybridHit], *, top_k: int) -> list[HybridHit]:
    deduped: list[HybridHit] = []
    seen_case_ids: set[str] = set()
    for hit in hits:
        case_id = hit.chunk.case_id
        if case_id in seen_case_ids:
            continue
        seen_case_ids.add(case_id)
        deduped.append(
            HybridHit(
                rank=len(deduped) + 1,
                chunk=hit.chunk,
                hybrid_score=hit.hybrid_score,
                bm25_score=hit.bm25_score,
                vector_score=hit.vector_score,
            )
        )
        if len(deduped) >= top_k:
            break
    return deduped


def _normalize_scores(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    values = list(scores.values())
    low = min(values)
    high = max(values)
    if high <= low:
        return {key: 1.0 for key in scores}
    return {key: (value - low) / (high - low) for key, value in scores.items()}


def run_one_query_mode(
    *,
    query_text: str,
    chunks: list[BadCaseChunk],
    bm25_index: BM25Index,
    embedder: EmbeddingClient,
    store: QdrantBadCaseStore,
    top_k: int,
) -> list[HybridHit]:
    query_vector = embedder.embed_query(query_text)
    hits = hybrid_search(
        query=query_text,
        chunks=chunks,
        bm25_index=bm25_index,
        query_vector=query_vector,
        store=store,
        top_k=max(top_k * 4, 30),
    )
    deduped = dedupe_hits_by_case_id(hits, top_k=top_k)
    return [hit for hit in deduped if hit.hybrid_score > DISPLAY_HYBRID_THRESHOLD]


def run_risk_filtered_query_mode(
    *,
    query_text: str,
    risk_profile: ClauseRiskProfile,
    chunks: list[BadCaseChunk],
    bm25_index: BM25Index,
    embedder: EmbeddingClient,
    store: QdrantBadCaseStore,
    top_k: int,
) -> list[HybridHit]:
    risk_types = set(risk_profile.risk_types)
    allowed_indexes = {
        index
        for index, chunk in enumerate(chunks)
        if chunk.metadata.get("risk_type", "") in risk_types
    }
    if not allowed_indexes:
        return []

    bm25_hits = [
        hit
        for hit in bm25_index.score(query_text)
        if hit.index in allowed_indexes
    ]
    query_vector = embedder.embed_query(query_text)
    vector_hits = [
        hit
        for hit in store.search(query_vector=query_vector, limit=len(chunks))
        if hit.index in allowed_indexes
    ]

    raw_bm25 = {hit.index: hit.score for hit in bm25_hits}
    raw_vector = {hit.index: hit.score for hit in vector_hits}
    normalized_bm25 = _normalize_scores(raw_bm25)
    normalized_vector = _normalize_scores(raw_vector)

    ranked: list[HybridHit] = []
    for index in set(raw_bm25) | set(raw_vector):
        hybrid_score = 0.6 * normalized_bm25.get(index, 0.0) + 0.4 * normalized_vector.get(index, 0.0)
        ranked.append(
            HybridHit(
                rank=0,
                chunk=chunks[index],
                hybrid_score=hybrid_score,
                bm25_score=raw_bm25.get(index, 0.0),
                vector_score=raw_vector.get(index, 0.0),
            )
        )

    ranked.sort(key=lambda item: item.hybrid_score, reverse=True)
    deduped = dedupe_hits_by_case_id(
        [
            HybridHit(
                rank=rank,
                chunk=hit.chunk,
                hybrid_score=hit.hybrid_score,
                bm25_score=hit.bm25_score,
                vector_score=hit.vector_score,
            )
            for rank, hit in enumerate(ranked, start=1)
        ],
        top_k=top_k,
    )
    return [hit for hit in deduped if hit.hybrid_score > DISPLAY_HYBRID_THRESHOLD]


def print_hits(hits: list[HybridHit]) -> None:
    if not hits:
        print(f"Top hits: none (all hits below hybrid threshold {DISPLAY_HYBRID_THRESHOLD:.1f})")
        return
    print("Top hits:")
    for hit in hits:
        chunk = hit.chunk
        print(
            f"  #{hit.rank} hybrid={hit.hybrid_score:.4f} "
            f"bm25={hit.bm25_score:.4f} vector={hit.vector_score:.4f} "
            f"id={chunk.case_id} field={chunk.field}"
        )
        print(
            f"     layer={chunk.metadata.get('risk_layer', '')} "
            f"type={chunk.metadata.get('risk_type', '')} "
            f"action={chunk.metadata.get('comment_action', '')}"
        )
        print(f"     {_preview(chunk.text, limit=260)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a real bad-case KB and run BM25 + vector hybrid retrieval."
    )
    parser.add_argument("--top-k", type=int, default=3, help="Maximum number of hybrid hits to print.")
    parser.add_argument("--clause-limit", type=int, default=20, help="Max number of clauses to test.")
    parser.add_argument("--collection", default=None, help="Qdrant collection name.")
    parser.add_argument("--qdrant-url", default=None, help="Qdrant base URL.")
    parser.add_argument(
        "--compare-modes",
        action="store_true",
        help="Compare clause_only, package_section_clause, and risk_filtered_query for each clause.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not recreate the collection before upsert.",
    )
    return parser.parse_args()


def main() -> int:
    configure_console_output()
    args = parse_args()
    effective_top_k = max(1, int(args.top_k))
    config = load_retrieval_config(
        collection_name=args.collection,
        qdrant_url=args.qdrant_url,
    )

    chunks = load_real_bad_case_chunks(TEST_KNOWLEDGE_FILE)
    if not chunks:
        raise RuntimeError(f"No bad-case chunks were parsed from {TEST_KNOWLEDGE_FILE}")

    clauses = split_user_document_into_clauses(TEST_USER_DOCUMENT)
    if not clauses:
        raise RuntimeError("No user clauses were parsed.")
    clauses = clauses[: args.clause_limit]

    print(f"Knowledge file: {TEST_KNOWLEDGE_FILE}")
    print(f"Parsed chunks: {len(chunks)}")
    print(f"Parsed user clauses: {len(clauses)}")
    print(f"Qdrant: {config.qdrant_url}")
    print(f"Collection: {config.collection_name}")
    print(f"Embedding model: {config.embedding_model}")

    bm25_index = BM25Index([chunk.text for chunk in chunks])
    embedder = EmbeddingClient(
        api_key=config.embedding_api_key,
        base_url=config.embedding_base_url,
        model=config.embedding_model,
        dimensions=config.embedding_dimensions,
    )
    store = QdrantBadCaseStore(
        url=config.qdrant_url,
        collection_name=config.collection_name,
        api_key=config.qdrant_api_key,
    )

    try:
        store.healthcheck()
    except Exception as exc:
        raise RuntimeError("Qdrant is not reachable.") from exc

    print("Embedding knowledge chunks...")
    vectors = embedder.embed_texts([chunk.text for chunk in chunks])
    vector_size = len(vectors[0])
    print(f"Embedding dimension: {vector_size}")

    if args.keep_existing:
        store.ensure_collection(vector_size=vector_size)
    else:
        store.recreate_collection(vector_size=vector_size)

    print("Upserting chunks into Qdrant...")
    store.upsert_chunks(chunks=chunks, vectors=vectors)

    for clause in clauses:
        clause_only_query = build_clause_only_query(clause)
        contextual_query = build_package_section_clause_query(clause)
        risk_profile = generate_clause_risk_profile(clause)
        print("\n" + "=" * 120)
        print(f"{clause.clause_id} | {clause.package} | {clause.section}")
        print(f"Title: {clause.title}")
        print(f"Text: {_preview(clause.text, limit=320)}")
        modes = [("clause_only", clause_only_query)]
        if args.compare_modes:
            modes.append(("package_section_clause", contextual_query))

        for mode_name, query_text in modes:
            print(f"\nQuery mode: {mode_name}")
            print(f"Query text: {_preview(query_text, limit=360)}")
            hits = run_one_query_mode(
                query_text=query_text,
                chunks=chunks,
                bm25_index=bm25_index,
                embedder=embedder,
                store=store,
                top_k=effective_top_k,
            )
            print_hits(hits)

        if args.compare_modes:
            print("\nQuery mode: risk_filtered_query")
            print(f"Query text: {_preview(contextual_query, limit=360)}")
            print(f"Risk filter: {', '.join(risk_profile.risk_types)}")
            print(f"Risk reasons: {'; '.join(risk_profile.reasons)}")
            hits = run_risk_filtered_query_mode(
                query_text=contextual_query,
                risk_profile=risk_profile,
                chunks=chunks,
                bm25_index=bm25_index,
                embedder=embedder,
                store=store,
                top_k=effective_top_k,
            )
            print_hits(hits)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
