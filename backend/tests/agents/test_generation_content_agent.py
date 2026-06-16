from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from deepagents import CompiledSubAgent

from backend.agents.generation import (
    AgentStepPayload,
    CONTENT_AGENT_SYSTEM_PROMPT,
    GenerationAgentProtocolError,
    GenerationAgentToolCallUnsupportedError,
    build_generation_subagents,
    parse_verify_agent_output,
    run_content_agent_generation,
    set_generation_agent_runner,
)
from backend.agents.generation import content_agents as content_agent_module
from backend.agents.generation import workspace as generation_workspace
from backend.agents.generation import revise_agent_graph as revise_agent_graph_module
from backend.agents.generation import verify_agent_graph as verify_agent_graph_module
from backend.agents.log_naming import build_agent_log_stem
from backend.agents.generation.model_factory import create_generation_chat_model
from backend.agents.generation.types import AuditFinding
from backend.agents.generation.workspace import (
    FINAL_POLISHED_TEXT_PATH,
    GENERATION_CONTEXT_PATH,
    read_backend_text,
)
from backend.prompts.types import GeneratePromptInput, RenderedPrompt


@pytest.fixture(autouse=True)
def _redirect_content_agent_workspace(tmp_path, monkeypatch) -> Path:
    workspace_root = tmp_path / "content_agent_workspace"
    def fake_create_workspace_dir(
        task_id: str,
        *,
        project_number: str | None = None,
        project_name: str | None = None,
        now: float | None = None,
    ) -> Path:
        stem = build_agent_log_stem(
            task_id,
            project_number=project_number,
            project_name=project_name,
            fallback="content-agent",
        )
        workspace_dir = workspace_root / f"{stem}_20260529-153000"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        return workspace_dir

    monkeypatch.setattr(
        "backend.agents.generation.workspace.CONTENT_AGENT_WORKSPACE_ROOT",
        workspace_root,
    )
    monkeypatch.setattr(
        content_agent_module,
        "create_workspace_dir",
        fake_create_workspace_dir,
    )
    return workspace_root


def test_create_workspace_dir_adds_project_metadata_to_name(
    _redirect_content_agent_workspace,
) -> None:
    workspace_dir = generation_workspace.create_workspace_dir(
        "task-1",
        project_number="NO/1",
        project_name="娴嬭瘯 椤圭洰",
    )

    assert workspace_dir.parent == _redirect_content_agent_workspace
    assert re.fullmatch(
        r"task-1_NO_1_娴嬭瘯_椤圭洰_\d{8}-\d{6}",
        workspace_dir.name,
    )


class FakeRunner:
    def __init__(self, outputs):
        self.outputs = outputs if isinstance(outputs, list) else [outputs]
        self.payloads: list[dict] = []
        self.configs: list[dict | None] = []

    def invoke(self, payload: dict, config: dict | None = None):
        raise AssertionError("workspace runner should stream, not invoke")

    def stream(self, payload: dict, config: dict | None = None, **_kwargs):
        self.payloads.append(payload)
        self.configs.append(config)
        backend = config["configurable"]["content_agent_backend"]
        for output in self.outputs:
            if "main" in output:
                yield {
                    "node": "content_agent",
                    "content": output["main"],
                    "is_complete": bool(output.get("is_complete", False)),
                }
            elif "draft" in output:
                backend.write("/drafts/round-1.md", output["draft"])
                yield {
                    "node": "content_generate_agent",
                    "round": 1,
                    "content": output["draft"],
                    "is_complete": True,
                }
            elif "audit" in output:
                round_index = output.get("round", 1)
                content = json.dumps(output["audit"], ensure_ascii=False)
                backend.write(f"/audits/round-{round_index}.json", content)
                yield {
                    "node": "content_verify_agent",
                    "round": round_index,
                    "content": content,
                    "is_complete": True,
                }
            elif "revision" in output:
                round_index = output.get("round", 1)
                backend.write(f"/revisions/round-{round_index}.md", output["revision"])
                yield {
                    "node": "content_revise_agent",
                    "round": round_index,
                    "content": output["revision"],
                    "is_complete": True,
                }
            elif "final" in output:
                backend.write(FINAL_POLISHED_TEXT_PATH, output["final"])
                if output.get("raw_physical") is not None:
                    final_path = Path(
                        config["configurable"]["content_agent_workspace_dir"]
                    ) / "final" / "polished_text.md"
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    final_path.write_text(output["raw_physical"], encoding="utf-8")
                yield {
                    "node": "content_agent",
                    "content": "final written",
                    "is_complete": True,
                }


class InvokeOnlyFakeRunner:
    def __init__(self, callback):
        self.payloads: list[dict] = []
        self.configs: list[dict | None] = []
        self.callback = callback

    def invoke(self, payload: dict, config: dict | None = None):
        self.payloads.append(payload)
        self.configs.append(config)
        self.callback(config["configurable"]["content_agent_backend"])
        return {"messages": []}


class ToolCallUnsupportedRunner:
    def invoke(self, payload: dict, config: dict | None = None):
        raise RuntimeError("model does not support tools or tool calls")


def _read_generation_context_from_runner(runner: FakeRunner) -> dict:
    backend = runner.configs[0]["configurable"]["content_agent_backend"]
    markdown = read_backend_text(backend, GENERATION_CONTEXT_PATH)
    match = re.search(r"```json\s*(.*?)\s*```", markdown, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


def test_build_generation_subagents_wraps_compiled_state_graphs() -> None:
    subagents = build_generation_subagents()

    assert isinstance(subagents.content_generate_agent, dict)
    assert isinstance(subagents.content_verify_agent, dict)
    assert isinstance(subagents.content_revise_agent, dict)
    assert subagents.content_generate_agent["name"] == "content_generate_agent"
    assert subagents.content_verify_agent["name"] == "content_verify_agent"
    assert subagents.content_revise_agent["name"] == "content_revise_agent"
    assert set(subagents.content_generate_agent) == set(CompiledSubAgent.__annotations__)
    assert set(subagents.content_verify_agent) == set(CompiledSubAgent.__annotations__)
    assert set(subagents.content_revise_agent) == set(CompiledSubAgent.__annotations__)
    assert hasattr(subagents.content_generate_agent["runnable"], "invoke")
    assert hasattr(subagents.content_verify_agent["runnable"], "invoke")
    assert hasattr(subagents.content_revise_agent["runnable"], "invoke")
    assert "/inputs/generation_context.md" in subagents.content_generate_agent["description"]
    assert "/audits/round-N.json" in subagents.content_verify_agent["description"]
    assert "/revisions/round-N.md" in subagents.content_revise_agent["description"]


def test_content_prompts_use_workspace_file_protocol() -> None:
    subagents = build_generation_subagents()

    assert "閲囪喘闇€姹傜敓鎴愪富鏅鸿兘浣? in CONTENT_AGENT_SYSTEM_PROMPT
    assert "TodoList" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "content_generate_agent" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "content_verify_agent" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "content_revise_agent" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "/final/polished_text.md" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "鍙湁 content_agent 鍙互鍐? in CONTENT_AGENT_SYSTEM_PROMPT
    assert "鏈€澶?3 杞? in CONTENT_AGENT_SYSTEM_PROMPT
    assert "Generate the first draft" not in subagents.content_generate_agent["description"]
    assert "Audit procurement requirement" not in subagents.content_verify_agent["description"]


def test_content_generate_agent_reuses_generate_prompt_and_model_config(monkeypatch) -> None:
    captured_prompt: dict[str, GeneratePromptInput] = {}
    captured_stream: dict[str, object] = {}

    def fake_render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
        captured_prompt["data"] = data
        return RenderedPrompt(system_prompt="system", user_prompt="user")

    async def fake_stream_llm_completion(**kwargs):
        captured_stream.update(kwargs)
        return "draft text"

    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.render_generate_prompt",
        fake_render_generate_prompt,
    )
    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.stream_llm_completion",
        fake_stream_llm_completion,
    )

    graph = build_generation_subagents().content_generate_agent["runnable"]
    result = graph.invoke(
        {
            "tender_type": "gngk",
            "generation_style": "param",
            "project_info": "project info",
            "tender_params": "template params",
            "template_reference_text": "new params",
            "model_provider": "qwen",
            "messages": [],
        }
    )

    assert captured_prompt["data"] == GeneratePromptInput(
        tender_type="gngk",
        generation_style="param",
        project_info="project info",
        tender_params="template params",
        template_reference_text="new params",
    )
    assert captured_stream["model_provider"] == "qwen"
    assert captured_stream["system_prompt"] == "system"
    assert captured_stream["user_prompt"] == "user"
    assert result["structured_response"] == {"draft_text": "draft text"}


def test_content_generate_agent_reads_parent_context_from_config(monkeypatch) -> None:
    captured_prompt: dict[str, GeneratePromptInput] = {}

    def fake_render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
        captured_prompt["data"] = data
        return RenderedPrompt(system_prompt="system", user_prompt="user")

    async def fake_stream_llm_completion(**kwargs):
        return "draft text"

    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.render_generate_prompt",
        fake_render_generate_prompt,
    )
    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.stream_llm_completion",
        fake_stream_llm_completion,
    )

    graph = build_generation_subagents().content_generate_agent["runnable"]
    result = graph.invoke(
        {"messages": []},
        {
            "configurable": {
                "generation_agent_context": {
                    "tender_type": "gngk_hw_zc",
                    "generation_style": "param",
                    "project_info": "config project",
                    "tender_params": "config tender params",
                    "template_reference_text": "config origin params",
                    "model_provider": "doubao",
                }
            }
        },
    )

    assert captured_prompt["data"] == GeneratePromptInput(
        tender_type="gngk_hw_zc",
        generation_style="param",
        project_info="config project",
        tender_params="config tender params",
        template_reference_text="config origin params",
    )
    assert result["structured_response"] == {"draft_text": "draft text"}


def test_content_generate_agent_streams_snapshots_to_existing_callback(monkeypatch) -> None:
    snapshots: list[str] = []
    agent_steps: list[object] = []

    def fake_render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
        return RenderedPrompt(system_prompt="system", user_prompt="user")

    async def fake_stream_llm_completion(**kwargs):
        kwargs["callbacks"].on_update("閮ㄥ垎")
        kwargs["callbacks"].on_update("閮ㄥ垎姝ｆ枃")
        return "閮ㄥ垎姝ｆ枃"

    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.render_generate_prompt",
        fake_render_generate_prompt,
    )
    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.stream_llm_completion",
        fake_stream_llm_completion,
    )
    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.AGENT_STEP_STREAM_INTERVAL_SECONDS",
        0,
    )

    graph = build_generation_subagents().content_generate_agent["runnable"]
    result = graph.invoke(
        {"messages": []},
        {
            "configurable": {
                "task_id": "task-agent-stream",
                "task_kind": "generate",
                "llm_stream_callback": snapshots.append,
                "agent_step_callback": agent_steps.append,
            }
        },
    )

    assert snapshots == ["閮ㄥ垎", "閮ㄥ垎姝ｆ枃"]
    assert [event.content for event in agent_steps] == ["閮ㄥ垎", "閮ㄥ垎姝ｆ枃"]
    assert all(event.is_complete is False for event in agent_steps)
    assert all(event.node == "content_generate_agent" for event in agent_steps)
    assert result["structured_response"] == {"draft_text": "閮ㄥ垎姝ｆ枃"}


def test_content_verify_agent_repairs_missing_fields_with_retry(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return '[{"evidence": "缂哄皯璐ㄤ繚鏈熼檺"}]'
        return '[{"evidence": "缂哄皯璐ㄤ繚鏈熼檺", "fix_hint": "琛ュ厖璐ㄤ繚鏈熼檺锛屼繚鎸佸叾瀹冨唴瀹逛笉鍙?}]'

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    graph = verify_agent_graph_module.create_verify_agent_graph()
    result = graph.invoke(
        {
            "current_text": "閲囪喘闇€姹傛鏂?,
            "template_reference_text": "鍙傝€冨唴瀹规棫璐ㄤ繚鏈熼檺锛?骞?,
            "tender_params": "璐ㄤ繚鏈熼檺锛?骞?,
            "model_provider": "deepseek",
        }
    )

    expected = [{"evidence": "缂哄皯璐ㄤ繚鏈熼檺", "fix_hint": "琛ュ厖璐ㄤ繚鏈熼檺锛屼繚鎸佸叾瀹冨唴瀹逛笉鍙?}]
    assert len(calls) == 2
    assert calls[1]["extra_params_override"] == {"temperature": 0.1}
    assert "涓ユ牸鍚堟硶鐨?JSON 鏁扮粍" in str(calls[1]["user_prompt"])
    assert result["structured_response"] == expected
    assert json.loads(result["messages"][-1].content) == expected


def test_content_verify_agent_reads_current_text_from_config(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {"messages": []},
        {
            "configurable": {
                "generation_agent_context": {
                    "generation_style": "param",
                    "current_text": "config draft text",
                    "project_info": "config project info",
                    "template_reference_text": "config origin params",
                    "tender_params": "config tender params",
                    "model_provider": "qwen",
                }
            }
        },
    )

    assert result["structured_response"] == []
    assert calls[0]["model_provider"] == "qwen"
    user_prompt = str(calls[0]["user_prompt"])
    system_prompt = str(calls[0]["system_prompt"])
    assert "銆愮敓鎴愰鏍笺€慭nparam" in user_prompt
    assert "銆愰」鐩熀纭€淇℃伅銆慭nconfig project info" in user_prompt
    assert "銆愬弬鑰冨唴瀹癸紙浠呭灞傛牸寮忕嚎绱紱鏃т簨瀹炲拰鏃у弬鏁颁笉寰楃户鎵匡級銆慭nconfig origin params" in user_prompt
    assert "銆愭妧鏈弬鏁帮紙鍘熸潗鏂欙紝浜嬪疄鐪熸簮锛夈€慭nconfig tender params" in user_prompt
    assert "銆愬緟瀹℃牳姝ｆ枃銆慭nconfig draft text" in user_prompt
    assert "濡傛灉姣斿缁撹鏄€滃疄璐ㄤ竴鑷淬€佹棤闂銆佹棤闇€淇敼鈥濓紝蹇呴』杈撳嚭 []" in user_prompt
    assert "template 鍜?param 閮戒笉鑳介檷浣庛€愭妧鏈弬鏁般€戝鍙傛暟鏈綋" in user_prompt
    assert "涓嶈兘鐢ㄥ弬鑰冨唴瀹瑰鏍稿弬鏁版湰浣? in user_prompt
    assert "鍙傛暟绔犺妭鏄惁绗﹀悎褰撳墠鐢熸垚椋庢牸" in user_prompt
    assert "鈽呫€佲柌 鎸囨爣" in user_prompt
    assert "绗﹀彿绫诲瀷銆佹寚鏍囧綊灞炪€佹牳蹇冩枃瀛椼€佹暟鍊煎拰鍗曚綅蹇呴』瀹屽叏涓€鑷? in user_prompt
    assert "寤虹珛 鈽?鈻?鐧藉悕鍗? in user_prompt
    assert "涓嶈鐩存帴鎸夊弬鑰冨唴瀹规Ы浣嶆垨鏃у簭鍙峰尮閰? in user_prompt
    assert "鍙槸鏍煎紡宸紓" in user_prompt
    assert "澶氫釜鍖呬欢/鏍囨/閲囪喘鍖?鐙珛璁惧缁? in user_prompt
    assert "椤圭洰姒傝堪/椤圭洰鍩烘湰鎯呭喌/椤圭洰姒傚喌/鎬讳綋闇€姹? in user_prompt
    assert "閫愰」姣斿璇ョ珷鑺傜殑妯℃澘瀛楁鍒楄〃銆佸瓧娈甸『搴忓拰瀛楁琛?瀛楁琛ㄥ鍣? in user_prompt
    assert "瀛楁鍊兼槸鍚︿粛涓庡瓧娈靛悕淇濇寔妯℃澘涓殑鍚屼竴琛屾垨鍚屼竴鍗曞厓鏍煎叧绯? in user_prompt
    assert "涓嶅緱鎶婂瓧娈垫敼鍐欐垚娈佃惤銆佸悎骞舵垚鏁ｆ枃鍙ャ€佹媶鍒板叾浠栫珷鑺傛垨鎹㈠鍣? in user_prompt
    assert "妯℃澘鏈夊瓧娈典絾褰撳墠椤圭洰鏉愭枡鏃犳柊浜嬪疄鏃讹紝搴斾繚鐣欐ā鏉垮瓧娈靛３鍜屽崰浣?鍥哄畾琛ㄨ揪" in user_prompt
    assert "`椤圭洰棰勭畻` 绛夊瓧娈靛彧鏈夊湪妯℃澘鍩虹淇℃伅绔犺妭鏈潵瀛樺湪鏃舵墠绾冲叆璇ョ珷鑺傚鏍? in user_prompt
    assert "鍙傝€冨唴瀹逛腑鐨勬妧鏈?鏈嶅姟/鍟嗗姟/鍞悗鏃у弬鏁般€佹棫琛ㄦ牸銆佹棫 鈽?鈻?涓嶅緱浣滀负 finding 渚濇嵁" in user_prompt
    assert "鍙兘杈撳嚭涓ユ牸鍚堟硶鐨?JSON 鏁扮粍鏈韩" in system_prompt
    assert "Few-shots" in system_prompt
    assert "绂佹杈撳嚭鈥滅 1 杞鏍糕€? in system_prompt
    assert "涓嶈鐢ㄦ妧鏈弬鏁颁腑鐨勮澶囨爣棰樿鐩栭」鐩熀纭€淇℃伅" in system_prompt
    assert "鎵€鏈夌敓鎴愰鏍间笅锛屽緟瀹℃牳姝ｆ枃鍙兘缁ф壙鍙傝€冨唴瀹圭殑鍩虹闈炲弬鏁版牸寮? in system_prompt
    assert "鍩虹淇℃伅绔犺妭鏍煎紡闀滃儚瑙勫垯" in system_prompt
    assert "椤圭洰姒傝堪/椤圭洰鍩烘湰鎯呭喌/椤圭洰姒傚喌/鎬讳綋闇€姹? in system_prompt
    assert "鍩虹淇℃伅瀛楁鍚嶃€佺紪鍙枫€佸啋鍙枫€佸浐瀹氭彁绀鸿銆佸崰浣嶇銆佹柟鎷彿鍜屽瓧娈靛鍣ㄥ彲浠ョ户鎵? in system_prompt
    assert "涓嶅厑璁稿缓璁垹闄ゅ瓧娈点€佹媶绔犳垨缂栭€犲€? in system_prompt
    assert "绂佹鎶婂瓧娈垫敼鍐欐垚鏁ｆ枃鍙ャ€佸悎骞舵垚涓€娈点€佹媶鍒板叾瀹冪珷鑺傘€佹崲鎴愬彟涓€濂楃紪鍙? in system_prompt
    assert "鎶€鏈?鏈嶅姟/鍟嗗姟/鍞悗鏉℃鐢辨妧鏈弬鏁版寜鐗╃悊椤哄簭" in system_prompt
    assert "鍙傝€冨唴瀹归噷鐨?鈽?鈻?鏄棫妯℃澘鑴忔爣璁? in system_prompt
    assert "鈽?鈻?瀹℃牳娴佺▼" in system_prompt
    assert "鎶娿€愭妧鏈弬鏁般€戞寜鐗╃悊鎹㈣銆佽〃鏍艰銆佹樉寮忕紪鍙峰拰鍐掑彿鎸傝浇鍒楄〃鎷嗘垚鍘熷瓙鏉℃" in system_prompt
    assert "璇ヨ鏄惁甯?鈽?鈻?鍙兘鐪嬪搴旀妧鏈弬鏁板師瀛愭潯娆? in system_prompt
    assert "绂佹杈撳嚭 evidence 鍐欌€滀袱鑰呬竴鑷?鏃犻棶棰樷€濅笖 fix_hint 鍐欌€滄棤闇€淇敼鈥? in system_prompt


def test_content_verify_agent_prompt_covers_basic_info_shell_mirroring(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "generation_style": "template",
            "project_info": "椤圭洰鍚嶇О锛氭柊椤圭洰\n浜や粯鍦扮偣锛氭柊闄㈠尯",
            "template_reference_text": (
                "涓€銆侀」鐩杩癨n"
                "1銆佽澶囧悕绉板強鏁伴噺锛歔寰呭～鍐橾\n"
                "2銆佷氦浠樻棩鏈燂細[寰呭畾]\n"
                "3銆佷粯娆炬柟寮忥細鎸夊悎鍚岀害瀹歕n"
                "4銆侀」鐩绠楋細[浠ユ渶缁堟壒澶嶄负鍑哴\n"
            ),
            "tender_params": "鎶€鏈弬鏁帮細璁惧A",
            "current_text": (
                "涓€銆佹妧鏈弬鏁癨n"
                "1銆佽澶嘇鍙傛暟濡備笅銆俓n"
                "浜屻€佷氦浠樻棩鏈焅n"
                "鍚堝悓绛捐鍚?0鏃ュ唴銆俓n"
            ),
            "model_provider": "deepseek",
        }
    )

    assert result["structured_response"] == []
    assert len(calls) == 1
    user_prompt = str(calls[0]["user_prompt"])
    system_prompt = str(calls[0]["system_prompt"])

    assert "瀛楁琛?瀛楁琛ㄦ牸寮忓３蹇呴』缁ф壙妯℃澘" in user_prompt
    assert "瀛楁鍊兼槸鍚︿粛涓庡瓧娈靛悕淇濇寔妯℃澘涓殑鍚屼竴琛屾垨鍚屼竴鍗曞厓鏍煎叧绯? in user_prompt
    assert "涓嶅緱鎶婂瓧娈垫敼鍐欐垚娈佃惤銆佸悎骞舵垚鏁ｆ枃鍙ャ€佹媶鍒板叾浠栫珷鑺傛垨鎹㈠鍣? in user_prompt
    assert "妯℃澘鏈夊瓧娈典絾褰撳墠椤圭洰鏉愭枡鏃犳柊浜嬪疄鏃讹紝搴斾繚鐣欐ā鏉垮瓧娈靛３鍜屽崰浣?鍥哄畾琛ㄨ揪" in user_prompt
    assert "`椤圭洰棰勭畻` 绛夊瓧娈靛彧鏈夊湪妯℃澘鍩虹淇℃伅绔犺妭鏈潵瀛樺湪鏃舵墠绾冲叆璇ョ珷鑺傚鏍? in user_prompt

    assert "鍩虹淇℃伅绔犺妭蹇呴』鎸夋ā鏉垮師鏍煎紡澹崇敓鎴? in system_prompt
    assert "妯℃澘閲屽嚭鐜板摢浜涘瓧娈碉紝灏卞鏍稿摢浜涘瓧娈? in system_prompt
    assert "鎸夌函鏂囨湰瀛楁琛屾帓鍒? in system_prompt
    assert "鎭㈠ `1銆侀」鐩绠楋細[浠ユ渶缁堟壒澶嶄负鍑哴` 杩欑被妯℃澘瀛楁琛? in system_prompt
    assert "涓嶈鍒犻櫎璇ュ瓧娈垫垨缂栭€犻绠楅噾棰? in system_prompt


def test_content_verify_agent_prompt_blocks_reference_parameter_restoration(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "generation_style": "param",
            "project_info": "椤圭洰鍚嶇О锛氭柊椤圭洰",
            "template_reference_text": (
                "鍏€佸敭鍚庢湇鍔¤姹俓n"
                "鈽呰川閲忎繚璇佹湡鈮?骞碶n"
                "鈽呮姇鏍囦汉蹇呴』鍏嶈垂鎻愪緵 HIS銆丳ACS 鎺ュ彛鏈嶅姟\n"
            ),
            "tender_params": (
                "涓夈€佸敭鍚庢湇鍔¤姹俓n"
                "3. 璐ㄩ噺淇濊瘉鏈熲墺5骞碶n"
                "4. 璐ㄤ繚鏈熶负鍏ㄤ繚鏈嶅姟\n"
            ),
            "current_text": (
                "涓夈€佸敭鍚庢湇鍔¤姹俓n"
                "3. 璐ㄩ噺淇濊瘉鏈熲墺5骞碶n"
                "4. 璐ㄤ繚鏈熶负鍏ㄤ繚鏈嶅姟\n"
            ),
            "model_provider": "deepseek",
        }
    )

    assert result["structured_response"] == []
    assert len(calls) == 1
    user_prompt = str(calls[0]["user_prompt"])
    system_prompt = str(calls[0]["system_prompt"])

    assert "鍙傝€冨唴瀹逛腑鐨勬妧鏈?鏈嶅姟/鍟嗗姟/鍞悗鏃у弬鏁般€佹棫琛ㄦ牸銆佹棫 鈽?鈻?涓嶅緱浣滀负 finding 渚濇嵁" in user_prompt
    assert "鍙傝€冨唴瀹归噷鐨?鈽?鈻?鏄棫妯℃澘鑴忔爣璁? in system_prompt
    assert "鍙傝€冨唴瀹瑰惈 `鈽呰川閲忎繚璇佹湡鈮?骞碻" in system_prompt
    assert "寰呭鏍告鏂囧啓鎴?`3. 璐ㄩ噺淇濊瘉鏈熲墺5骞碻" in system_prompt


def test_content_verify_agent_drops_noop_findings(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return (
            '[{"evidence":"鎶€鏈弬鏁扮3.1鏉′笌寰呭鏍告鏂囩3.1鏉″畬鍏ㄤ竴鑷达紝鏃犻棶棰樸€?,'
            '"fix_hint":"鏃犻渶淇敼銆?}]'
        )

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {"current_text": "閲囪喘闇€姹傛鏂?, "model_provider": "deepseek"}
    )

    assert len(calls) == 1
    assert result["structured_response"] == []
    assert json.loads(result["messages"][-1].content) == []


def test_content_verify_agent_flags_placeholder_current_text_without_llm(monkeypatch) -> None:
    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        lambda **_kwargs: pytest.fail("placeholder current_text should not call LLM"),
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {"current_text": "<瀹屾暣閲囪喘闇€姹傛鏂?", "model_provider": "deepseek"}
    )

    finding = result["structured_response"][0]
    assert "鍗犱綅绗? in finding["evidence"]
    assert "涓嶆槸瀹為檯閲囪喘闇€姹傛鏂? in finding["evidence"]
    assert "涓嶅緱杈撳嚭灏栨嫭鍙峰崰浣嶇" in finding["fix_hint"]
    assert json.loads(result["messages"][-1].content) == result["structured_response"]


def test_content_verify_agent_repairs_common_json_issues_without_retry(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return (
            "```json\n"
            + r'[{"evidence": "璺緞 C:\Temp", "fix_hint": "琛ュ厖璺緞璇存槑",}]'
            + "\n```"
        )

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {"current_text": "閲囪喘闇€姹傛鏂?, "model_provider": "deepseek"}
    )

    assert len(calls) == 1
    assert result["structured_response"] == [
        {"evidence": r"璺緞 C:\Temp", "fix_hint": "琛ュ厖璺緞璇存槑"}
    ]


def test_content_verify_agent_falls_back_to_valid_json_after_repair_failure(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return "not json"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {"current_text": "閲囪喘闇€姹傛鏂?, "model_provider": "deepseek"}
    )

    assert len(calls) == 2
    fallback = result["structured_response"][0]
    assert "瀹℃牳鏅鸿兘浣撹緭鍑烘牸寮忓紓甯? in fallback["evidence"]
    assert "淇濇寔 current_text 鍘熸枃涓嶅彉" in fallback["fix_hint"]
    assert json.loads(result["messages"][-1].content) == result["structured_response"]


def test_content_verify_agent_output_is_coerced_to_json_schema() -> None:
    findings = parse_verify_agent_output(
        '[{"evidence": "missing warranty", "fix_hint": "add warranty"}]'
    )

    assert findings[0].evidence == "missing warranty"
    assert findings[0].fix_hint == "add warranty"

    single_object = parse_verify_agent_output('{"evidence": "bad"}')
    assert single_object[0].evidence == "bad"
    assert "鏈€灏忓繀瑕佷慨澶? in single_object[0].fix_hint

    missing_evidence = parse_verify_agent_output('[{"fix_hint": "add"}]')
    assert "鏈彁渚?evidence" in missing_evidence[0].evidence
    assert missing_evidence[0].fix_hint == "add"

    fallback = parse_verify_agent_output("not json")
    assert "瀹℃牳鏅鸿兘浣撹緭鍑烘牸寮忓紓甯? in fallback[0].evidence


def test_content_verify_agent_streams_raw_json_snapshots(monkeypatch) -> None:
    agent_steps: list[object] = []

    async def fake_stream_llm_completion(**kwargs):
        kwargs["callbacks"].on_update('[{"evidence":"缂?)
        kwargs["callbacks"].on_update('[{"evidence":"缂哄皯璐ㄤ繚鏈熼檺","fix_hint":"琛ュ厖璐ㄤ繚鏈熼檺"}]')
        return '[{"evidence":"缂哄皯璐ㄤ繚鏈熼檺","fix_hint":"琛ュ厖璐ㄤ繚鏈熼檺"}]'

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": "閲囪喘闇€姹傛鏂?,
            "model_provider": "deepseek",
        },
        {
            "configurable": {
                "task_id": "task-agent-verify-stream",
                "agent_step_callback": agent_steps.append,
            }
        },
    )

    assert result["structured_response"] == [
        {"evidence": "缂哄皯璐ㄤ繚鏈熼檺", "fix_hint": "琛ュ厖璐ㄤ繚鏈熼檺"}
    ]
    assert [event.content for event in agent_steps] == [
        '[{"evidence":"缂?,
        '[{"evidence":"缂哄皯璐ㄤ繚鏈熼檺","fix_hint":"琛ュ厖璐ㄤ繚鏈熼檺"}]',
    ]
    assert all(event.node == "content_verify_agent" for event in agent_steps)
    assert all(event.step_type == "stream" for event in agent_steps)
    assert all(event.is_complete is False for event in agent_steps)


def test_content_revise_agent_streams_revision_snapshots(monkeypatch) -> None:
    agent_steps: list[object] = []

    async def fake_stream_llm_completion(**kwargs):
        kwargs["callbacks"].on_update("淇涓?)
        kwargs["callbacks"].on_update("淇鍚庣殑姝ｆ枃")
        return "淇鍚庣殑姝ｆ枃"

    monkeypatch.setattr(
        revise_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = revise_agent_graph_module.create_revise_agent_graph().invoke(
        {
            "current_text": "鍘熸鏂?,
            "audit_findings": [{"evidence": "缂哄皯瀛楁", "fix_hint": "琛ュ厖瀛楁"}],
            "revision_round": 1,
            "model_provider": "deepseek",
        },
        {
            "configurable": {
                "task_id": "task-agent-revise-stream",
                "agent_step_callback": agent_steps.append,
            }
        },
    )

    assert result["structured_response"] == {"revision_path": "/revisions/round-1.md"}
    assert result["polished_text"] == "淇鍚庣殑姝ｆ枃"
    assert [event.content for event in agent_steps] == [
        "淇涓?,
        "淇鍚庣殑姝ｆ枃",
    ]
    assert all(event.node == "content_revise_agent" for event in agent_steps)
    assert all(event.step_type == "stream" for event in agent_steps)
    assert all(event.is_complete is False for event in agent_steps)


def test_content_revise_agent_skips_empty_audit_without_rewriting(monkeypatch) -> None:
    agent_steps: list[object] = []

    async def fake_stream_llm_completion(**_kwargs):
        pytest.fail("empty audit should not call revision LLM")

    monkeypatch.setattr(
        revise_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = revise_agent_graph_module.create_revise_agent_graph().invoke(
        {
            "current_text": "鍘熸鏂囦笉搴旇閲嶆柊杈撳嚭",
            "audit_findings": [],
            "revision_round": 1,
            "model_provider": "deepseek",
        },
        {
            "configurable": {
                "task_id": "task-agent-revise-empty-audit",
                "agent_step_callback": agent_steps.append,
            }
        },
    )

    assert result["structured_response"] == {
        "status": "no_revision",
        "message": "鏃犻渶淇",
    }
    assert result["no_revision"] is True
    assert "polished_text" not in result
    assert "revision_path" not in result
    assert [event.content for event in agent_steps] == ["鏃犻渶淇"]
    assert all(event.node == "content_revise_agent" for event in agent_steps)
    assert all(event.is_complete is True for event in agent_steps)


def test_content_runner_creates_workspace_and_reads_final_file(
    _redirect_content_agent_workspace,
) -> None:
    runner = FakeRunner(
        [
            {"main": "璁″垝锛氱敓鎴愩€佸鏍搞€侀獙鏀?},
            {"draft": "draft text"},
            {"audit": [{"evidence": "missing warranty", "fix_hint": "add it"}], "round": 1},
            {"revision": "revised text", "round": 1},
            {"audit": [], "round": 2},
            {"final": "final text"},
        ]
    )
    events = []

    result = run_content_agent_generation(
        {
            "tender_type": "xjcg",
            "generation_style": "template",
            "project_number": "XJ-001",
            "project_name": "娴嬭瘯 椤圭洰",
            "project_content": "project",
            "tender_params": "params",
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "deepseek", "task_id": "task-agent-42"}},
        runner=runner,
        step_callback=events.append,
    )

    workspace_dir = result.workspace_dir
    assert workspace_dir == (
        _redirect_content_agent_workspace
        / "task-agent-42_XJ-001_娴嬭瘯_椤圭洰_20260529-153000"
    )
    assert (workspace_dir / "inputs" / "generation_context.md").exists()
    assert (workspace_dir / "drafts" / "round-1.md").read_text(encoding="utf-8") == "draft text"
    assert (workspace_dir / "audits" / "round-1.json").exists()
    assert (workspace_dir / "revisions" / "round-1.md").read_text(encoding="utf-8") == "revised text"
    assert (workspace_dir / "final" / "polished_text.md").read_text(encoding="utf-8") == "final text"
    assert result.polished_text == "final text"
    assert result.audit_findings == []
    assert result.revision_rounds == 1
    assert [event.node for event in events] == [
        "content_generate_agent",
        "content_verify_agent",
        "content_revise_agent",
        "content_verify_agent",
        "content_agent",
    ]
    assert [event.round for event in events] == [1, 1, 1, 2, 2]
    assert [event.step_type for event in events] == [
        "stream",
        "stream",
        "stream",
        "stream",
        "final",
    ]
    assert [event.content_agent["phase"] for event in events] == [
        "draft",
        "audit",
        "revision",
        "audit",
        "final",
    ]
    assert [event.content_agent["summary"] for event in events] == [
        "鍒濈鐢熸垚瀹屾垚锛岀害 10 瀛椼€?,
        "绗?1 杞鏍稿彂鐜?1 涓棶棰樸€?,
        "绗?1 杞慨澶嶅畬鎴愶紝宸插鐞?1 涓棶棰樸€?,
        "绗?2 杞慨澶嶅鏍搁€氳繃銆?,
        "鏈€缁堝畬鎴愶紝淇 1 杞紝鏈€缁堟鏂囩害 10 瀛椼€?,
    ]
    assert events[2].content_agent["rounds"][2]["fix_count"] == 1
    assert events[-1].content_agent["final_result"]["content"] == "final text"


def test_content_agent_tracker_preserves_completed_audit_after_late_empty_update() -> None:
    tracker = content_agent_module.ContentAgentProcessTracker()
    finding = {"evidence": "缂哄皯 鈽?鎸囨爣", "fix_hint": "琛ュ厖 鈽?绗﹀彿"}

    tracker.build_step(
        AgentStepPayload(
            step_type="stream",
            round=1,
            node="content_verify_agent",
            content=json.dumps([finding], ensure_ascii=False),
            is_complete=True,
        )
    )
    tracker.build_step(
        AgentStepPayload(
            step_type="stream",
            round=1,
            node="content_revise_agent",
            content="宸茶ˉ鍏?鈽?绗﹀彿",
            is_complete=True,
        )
    )
    late_update = tracker.build_step(
        AgentStepPayload(
            step_type="stream",
            round=1,
            node="content_verify_agent",
            content="",
            is_complete=False,
        )
    )

    assert late_update is not None
    audit_round = late_update.rounds[0]
    revision_round = late_update.rounds[1]
    assert audit_round.phase == "audit"
    assert audit_round.issue_count == 1
    assert audit_round.summary == "绗?1 杞鏍稿彂鐜?1 涓棶棰樸€?
    assert audit_round.findings[0].evidence == "缂哄皯 鈽?鎸囨爣"
    assert revision_round.phase == "revision"
    assert revision_round.fix_count == 1
    assert revision_round.findings[0].evidence == "缂哄皯 鈽?鎸囨爣"


def test_content_runner_writes_complete_generation_context() -> None:
    runner = FakeRunner([{"draft": "draft text"}, {"audit": [], "round": 1}, {"final": "draft text"}])

    result = run_content_agent_generation(
        {
            "tender_type": "gngk_hw_zc",
            "generation_style": "param",
            "project_content": "project",
            "tender_params": {"name": "params"},
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "qwen", "task_id": "task-agent-context"}},
        runner=runner,
    )

    context = _read_generation_context_from_runner(runner)
    assert context == {
        "task_id": "task-agent-context",
        "tender_type": "gngk_hw_zc",
        "generation_style": "param",
        "project_info": "project",
        "template_reference_text": "origin",
        "tender_params": {"name": "params"},
        "model_provider": "qwen",
    }
    assert result.polished_text == "draft text"
    assert result.workspace_dir.name == "task-agent-context_20260529-153000"
    assert runner.payloads[0]["messages"][0]["content"].startswith("璇锋寜鏂囦欢鍗忚鑷富瀹屾垚閲囪喘闇€姹傜敓鎴?)
    assert runner.configs[0]["configurable"]["generation_agent_context"] == context


def test_content_runner_fails_when_final_file_missing() -> None:
    runner = FakeRunner([{"draft": "draft text"}, {"audit": [], "round": 1}])

    with pytest.raises(GenerationAgentProtocolError, match="/final/polished_text.md"):
        run_content_agent_generation({}, runner=runner)


def test_content_runner_fails_when_final_file_empty() -> None:
    runner = FakeRunner([{"final": "non-empty", "raw_physical": "   "}])

    with pytest.raises(GenerationAgentProtocolError, match="涓虹┖"):
        run_content_agent_generation({}, runner=runner)


def test_content_runner_fails_when_final_file_is_placeholder() -> None:
    runner = FakeRunner([{"final": "<瀹屾暣閲囪喘闇€姹傛鏂?"}])

    with pytest.raises(GenerationAgentProtocolError, match="鍗犱綅绗?):
        run_content_agent_generation({}, runner=runner)


def test_content_runner_rejects_round_four_artifacts() -> None:
    runner = FakeRunner(
        [
            {"draft": "draft"},
            {"audit": [{"evidence": "e4", "fix_hint": "f4"}], "round": 4},
            {"final": "final"},
        ]
    )

    with pytest.raises(GenerationAgentProtocolError, match="瓒呭嚭鍗忚杞"):
        run_content_agent_generation({}, runner=runner)


def test_content_runner_rechecks_final_text_when_last_audit_has_findings(monkeypatch) -> None:
    runner = FakeRunner(
        [
            {"draft": "draft"},
            {"audit": [{"evidence": "澶氫綑 鈻?, "fix_hint": "鍒犻櫎澶氫綑 鈻?}], "round": 1},
            {"revision": "revision 1", "round": 1},
            {"audit": [{"evidence": "浠嶆湁鏃т簨瀹?, "fix_hint": "鏇挎崲鏃т簨瀹?}], "round": 2},
            {"revision": "revision 2", "round": 2},
            {"audit": [{"evidence": "浠嶆湁鏃т簨瀹?, "fix_hint": "鏇挎崲鏃т簨瀹?}], "round": 3},
            {"revision": "fixed final", "round": 3},
            {"final": "fixed final"},
        ]
    )
    calls = []

    def fake_verify_final_text_findings(*, final_text, generation_context, model_provider):
        calls.append((final_text, generation_context, model_provider))
        return []

    monkeypatch.setattr(
        content_agent_module,
        "verify_final_text_findings",
        fake_verify_final_text_findings,
    )

    result = run_content_agent_generation(
        {
            "generation_style": "param",
            "project_content": "project",
            "tender_params": "params",
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "deepseek", "task_id": "task-final-clean"}},
        runner=runner,
    )

    assert result.polished_text == "fixed final"
    assert result.audit_findings == []
    assert calls == [
        (
            "fixed final",
            {
                "task_id": "task-final-clean",
                "tender_type": "xjcg",
                "generation_style": "param",
                "project_info": "project",
                "template_reference_text": "origin",
                "tender_params": "params",
                "model_provider": "deepseek",
            },
            "deepseek",
        )
    ]


def test_content_runner_returns_warning_findings_when_final_recheck_still_has_findings(
    monkeypatch,
) -> None:
    runner = FakeRunner(
        [
            {"draft": "draft"},
            {"audit": [{"evidence": "澶氫綑 鈻?, "fix_hint": "鍒犻櫎澶氫綑 鈻?}], "round": 3},
            {"revision": "bad 鈻?final", "round": 3},
            {"final": "bad 鈻?final"},
        ]
    )
    warnings: list[str] = []

    monkeypatch.setattr(
        content_agent_module,
        "verify_final_text_findings",
        lambda **_kwargs: [
            AuditFinding(evidence="姝ｆ枃浠嶆湁澶氫綑 鈻?鎸囨爣", fix_hint="鍒犻櫎澶氫綑 鈻?鎸囨爣")
        ],
    )
    monkeypatch.setattr(
        content_agent_module.progress_log,
        "warning",
        lambda message, *args: warnings.append(str(message) % args if args else str(message)),
    )

    result = run_content_agent_generation(
        {
            "generation_style": "param",
            "project_content": "project",
            "tender_params": "params",
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "deepseek", "task_id": "task-final-bad"}},
        runner=runner,
    )

    assert result.polished_text == "bad 鈻?final"
    assert result.audit_findings == [
        AuditFinding(evidence="姝ｆ枃浠嶆湁澶氫綑 鈻?鎸囨爣", fix_hint="鍒犻櫎澶氫綑 鈻?鎸囨爣")
    ]
    assert any("鏈€缁堝鏍告湭閫氳繃锛屾寜闄嶇骇 warning 缁х画浜や粯" in message for message in warnings)


def test_content_runner_accepts_invoke_only_test_runner() -> None:
    def write_final(backend):
        backend.write(FINAL_POLISHED_TEXT_PATH, "invoke final")

    runner = InvokeOnlyFakeRunner(write_final)

    result = run_content_agent_generation({}, runner=runner)

    assert result.polished_text == "invoke final"
    assert len(runner.payloads) == 1


def test_content_rejects_tool_call_unsupported_errors() -> None:
    with pytest.raises(GenerationAgentToolCallUnsupportedError, match="涓嶆敮鎸佸伐鍏疯皟鐢?):
        run_content_agent_generation({}, runner=ToolCallUnsupportedRunner())


def test_fake_runner_injection_point(monkeypatch) -> None:
    set_generation_agent_runner(FakeRunner([{"final": "injected text"}]))
    monkeypatch.setattr(
        content_agent_module,
        "create_content_agent_runner",
        lambda _model_provider, backend=None: pytest.fail("real runner should not be created"),
    )
    try:
        result = run_content_agent_generation({})
    finally:
        set_generation_agent_runner(None)

    assert result.polished_text == "injected text"


def test_model_factory_reuses_existing_llm_config(monkeypatch) -> None:
    class FakeSettings:
        def get_llm_config(self, provider: str):
            assert provider == "qwen"
            return {
                "base_url": "https://example.test/v1",
                "api_key": "test-key",
                "model": "qwen-test",
            }

    monkeypatch.setattr(
        "backend.agents.generation.model_factory.ensure_llm_env",
        lambda _provider: None,
    )
    monkeypatch.setattr(
        "backend.agents.generation.model_factory.settings",
        FakeSettings(),
    )
    monkeypatch.setattr(
        "backend.agents.generation.model_factory.get_llm_timeout_seconds",
        lambda: 37,
    )

    model = create_generation_chat_model("qwen")

    assert model.model_name == "qwen-test"
    assert model.openai_api_base == "https://example.test/v1"
    assert model.request_timeout == 37
    assert model.max_retries == 0
    assert model.max_tokens == 32768
    assert model.temperature == 0.1
    assert model.extra_body == {"enable_thinking": False}


# ---------------------------------------------------------------------------
# TABLE 鍗犱綅绗︾‖濂戠害锛氱‘瀹氭€ф鏌ヤ笌鏈€缁堝鏍?# ---------------------------------------------------------------------------

_TABLE_PARAM_FIXTURE = (
    "鎶€鏈弬鏁帮細\n"
    "| 搴忓彿 | 鍙傛暟 |\n"
    "| --- | --- |\n"
    "[[TABLE:TP1_1]]\n"
)


def test_content_verify_agent_flags_missing_table_placeholder_when_llm_returns_empty(
    monkeypatch,
) -> None:
    """LLM 杩斿洖 []锛屼絾 current_text 鍙湁 Markdown 琛ㄤ笖鏃犲崰浣嶇锛?    鏈€缁?structured_response 蹇呴』鍖呭惈缂哄け鍗犱綅绗?finding銆?""

    async def fake_stream_llm_completion(**_kwargs):
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": (
                "鎶€鏈弬鏁帮細\n"
                "| 搴忓彿 | 鍙傛暟 |\n"
                "| --- | --- |\n"
                "| 1 | A |\n"
            ),
            "tender_params": _TABLE_PARAM_FIXTURE,
            "model_provider": "deepseek",
        }
    )

    findings = result["structured_response"]
    assert len(findings) == 1
    assert "[[TABLE:TP1_1]]" in findings[0]["evidence"]
    assert "寰呭鏍告鏂囩己澶辫鍗犱綅绗? in findings[0]["evidence"]
    assert "琛ュ洖鍗犱綅绗?[[TABLE:TP1_1]]" in findings[0]["fix_hint"]
    assert json.loads(result["messages"][-1].content) == findings


def test_content_verify_agent_keeps_empty_when_all_table_placeholders_present(
    monkeypatch,
) -> None:
    """current_text 宸插寘鍚墍鏈?TABLE id锛孡LM 杩斿洖 []锛屾渶缁堜粛涓?[]銆?""

    async def fake_stream_llm_completion(**_kwargs):
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": "鎶€鏈弬鏁帮細\n[[TABLE:TP1_1]]\n",
            "tender_params": _TABLE_PARAM_FIXTURE,
            "model_provider": "deepseek",
        }
    )

    assert result["structured_response"] == []


def test_content_verify_agent_reports_only_missing_table_placeholder(monkeypatch) -> None:
    """TP1_1 瀛樺湪銆乀P1_2 缂哄け鏃讹紝鍙姤 TP1_2銆?""

    async def fake_stream_llm_completion(**_kwargs):
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": "鎶€鏈弬鏁帮細\n[[TABLE:TP1_1]]\n",
            "tender_params": (
                "鎶€鏈弬鏁帮細\n[[TABLE:TP1_1]]\n[[TABLE:TP1_2]]\n"
            ),
            "model_provider": "deepseek",
        }
    )

    findings = result["structured_response"]
    assert len(findings) == 1
    assert "[[TABLE:TP1_2]]" in findings[0]["evidence"]
    assert "[[TABLE:TP1_1]]" not in findings[0]["evidence"]


def test_content_verify_agent_appends_placeholder_finding_to_llm_findings(monkeypatch) -> None:
    """LLM 宸茶繑鍥為潪绌?findings锛岀己澶卞崰浣嶇 finding 搴旇拷鍔犲湪鍚庨潰銆?""

    async def fake_stream_llm_completion(**_kwargs):
        return '[{"evidence":"缂哄皯 鈽?鎸囨爣","fix_hint":"琛ュ厖 鈽?绗﹀彿"}]'

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": (
                "鎶€鏈弬鏁帮細\n"
                "| 搴忓彿 | 鍙傛暟 |\n"
                "| --- | --- |\n"
                "| 1 | A |\n"
            ),
            "tender_params": _TABLE_PARAM_FIXTURE,
            "model_provider": "deepseek",
        }
    )

    findings = result["structured_response"]
    assert len(findings) == 2
    assert findings[0]["evidence"] == "缂哄皯 鈽?鎸囨爣"
    assert "[[TABLE:TP1_1]]" in findings[1]["evidence"]


def test_content_verify_agent_prompt_states_table_placeholder_is_hard_contract(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": "姝ｆ枃\n[[TABLE:TP1_1]]",
            "tender_params": "[[TABLE:TP1_1]]",
            "model_provider": "deepseek",
        }
    )

    user_prompt = str(calls[0]["user_prompt"])
    assert "缁撴瀯鍖栬〃鍗犱綅绗︾‖濂戠害" in user_prompt
    assert "Markdown 琛ㄦ牸銆佹墜缁樿〃鏍笺€佹暎鏂囧紡鍙傛暟鍒楄〃銆佽〃鏍兼姇褰辨枃鏈兘涓嶈兘瑙嗕负鍗犱綅绗︾殑绛変环鏇夸唬" in user_prompt
    assert "鍗犱綅绗﹀唴瀹?`[[TABLE:...]]` 鏈韩蹇呴』閫愬瓧淇濈暀" in user_prompt


def test_verify_final_text_findings_reports_missing_placeholder_when_llm_empty(
    monkeypatch,
) -> None:
    """verify_final_text_findings 鍦?LLM 澶嶆牳杩斿洖 [] 鏃讹紝浠嶈鍙犲姞鍗犱綅绗︽鏌ャ€?""

    async def fake_stream_llm_completion(**_kwargs):
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    findings = verify_agent_graph_module.verify_final_text_findings(
        final_text=(
            "鎶€鏈弬鏁帮細\n"
            "| 搴忓彿 | 鍙傛暟 |\n"
            "| --- | --- |\n"
            "| 1 | A |\n"
        ),
        generation_context={
            "generation_style": "template",
            "tender_params": _TABLE_PARAM_FIXTURE,
        },
        model_provider="deepseek",
    )

    assert len(findings) == 1
    assert "[[TABLE:TP1_1]]" in findings[0].evidence


def test_content_runner_exposes_missing_table_finding_when_audit_empty(
    _redirect_content_agent_workspace,
) -> None:
    """runner 鍐欏叆缂哄け TABLE 鐨?final锛屽嵆浣?audit 涓?[]锛?    run_content_agent_generation() 杩斿洖鐨?audit_findings 蹇呴』鍖呭惈缂哄け TABLE finding銆?""
    runner = FakeRunner(
        [
            {"draft": "draft text"},
            {"audit": [], "round": 1},
            {
                "final": (
                    "鎶€鏈弬鏁帮細\n"
                    "| 搴忓彿 | 鍙傛暟 |\n"
                    "| --- | --- |\n"
                    "| 1 | A |\n"
                )
            },
        ]
    )

    result = run_content_agent_generation(
        {
            "generation_style": "param",
            "project_content": "project",
            "tender_params": _TABLE_PARAM_FIXTURE,
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "deepseek", "task_id": "task-final-missing-table"}},
        runner=runner,
    )

    assert len(result.audit_findings) == 1
    assert "[[TABLE:TP1_1]]" in result.audit_findings[0].evidence
    assert "寰呭鏍告鏂囩己澶辫鍗犱綅绗? in result.audit_findings[0].evidence


def test_content_runner_final_recheck_unifies_llm_and_placeholder_findings(
    monkeypatch,
    _redirect_content_agent_workspace,
) -> None:
    """鏈€鍚庝竴杞?audit 闈炵┖銆乫inal 鏃㈡湁 LLM finding 鍙堢己鍗犱綅绗︼紝鏈€缁堝簲鍚屾椂鏆撮湶涓よ€呫€?""
    runner = FakeRunner(
        [
            {"draft": "draft"},
            {"audit": [{"evidence": "澶氫綑 鈻?, "fix_hint": "鍒犻櫎澶氫綑 鈻?}], "round": 3},
            {
                "revision": (
                    "姝ｆ枃 澶氫綑 鈻瞈n"
                    "| 搴忓彿 | 鍙傛暟 |\n"
                    "| --- | --- |\n"
                    "| 1 | A |\n"
                ),
                "round": 3,
            },
            {
                "final": (
                    "姝ｆ枃 澶氫綑 鈻瞈n"
                    "| 搴忓彿 | 鍙傛暟 |\n"
                    "| --- | --- |\n"
                    "| 1 | A |\n"
                )
            },
        ]
    )

    monkeypatch.setattr(
        content_agent_module,
        "verify_final_text_findings",
        lambda **_kwargs: [
            AuditFinding(evidence="姝ｆ枃浠嶆湁澶氫綑 鈻?鎸囨爣", fix_hint="鍒犻櫎澶氫綑 鈻?鎸囨爣")
        ],
    )

    result = run_content_agent_generation(
        {
            "generation_style": "param",
            "project_content": "project",
            "tender_params": _TABLE_PARAM_FIXTURE,
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "deepseek", "task_id": "task-final-union"}},
        runner=runner,
    )

    evidences = [finding.evidence for finding in result.audit_findings]
    assert any("姝ｆ枃浠嶆湁澶氫綑 鈻?鎸囨爣" in evidence for evidence in evidences)
    assert any("[[TABLE:TP1_1]]" in evidence for evidence in evidences)
