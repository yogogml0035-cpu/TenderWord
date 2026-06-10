"""
批注生成节点

本模块实现 generate_comments 节点，使用 LLM 基于修改文本生成批注指令。

该节点遵循与 generate_polished_text.py 相同的架构模式，通过提示词注册表系统
支持多种招标类型（xjcg 和 gngk）。

需求引用：1.1, 1.2, 1.3
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Callable, Optional

from backend.prompts.comment_prompt import (
    COMMENT_PROMPT_REGISTRY,
    render_comment_prompt,
    render_comment_prompt_with_bad_case_context,
    render_comment_json_repair_prompt,
)
from backend.prompts.types import CommentPromptInput
from backend.retrieval.comment_bad_case_runtime import (
    build_bad_case_prompt_context,
    build_failed_bad_case_retrieval_payload,
    retrieve_bad_case_hits,
)
from backend.states import TenderGraphStateBase
from backend.util.common_util import (
    LLMTimeoutError,
    StreamCallbacks,
    stream_llm_completion,
)
from backend.util.log_util.context_log import get_generate_context_log_dir
from backend.util.log_util.progress_log import progress_log

# 模块级常量
CHECK_INTERVAL = 3.0  # 心跳检查间隔（秒）
JSON_REPAIR_RETRY_LIMIT = 1
JSON_REPAIR_TEMPERATURE = 0.1

# Prompt 注册表：根据 tender_type 选择对应的 prompt
PROMPT_REGISTRY = COMMENT_PROMPT_REGISTRY


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


def _strip_code_fence_wrappers(text: str) -> str:
    stripped = str(text or "").strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.IGNORECASE | re.DOTALL)
    if not match:
        return stripped
    return match.group(1).strip()


def _extract_first_json_array(text: str) -> Optional[str]:
    raw = str(text or "")
    start = raw.find("[")
    if start < 0:
        return None

    in_string = False
    escape = False
    depth = 0
    array_start = -1

    for index in range(start, len(raw)):
        char = raw[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "[":
            if depth == 0:
                array_start = index
            depth += 1
            continue
        if char == "]" and depth > 0:
            depth -= 1
            if depth == 0 and array_start >= 0:
                return raw[array_start : index + 1].strip()

    return None


def _escape_invalid_json_backslashes(text: str) -> str:
    valid_escapes = {'"', "\\", "/", "b", "f", "n", "r", "t"}
    raw = str(text or "")
    chars: list[str] = []
    in_string = False
    index = 0

    while index < len(raw):
        char = raw[index]
        if not in_string:
            chars.append(char)
            if char == '"':
                in_string = True
            index += 1
            continue

        if char == "\\":
            next_char = raw[index + 1] if index + 1 < len(raw) else ""
            if next_char in valid_escapes:
                chars.append("\\")
                chars.append(next_char)
                index += 2
                continue
            if next_char == "u" and index + 5 < len(raw):
                unicode_candidate = raw[index + 2 : index + 6]
                if re.fullmatch(r"[0-9a-fA-F]{4}", unicode_candidate):
                    chars.append(raw[index : index + 6])
                    index += 6
                    continue
                else:
                    chars.append("\\\\")
            else:
                chars.append("\\\\")
            index += 1
            continue

        chars.append(char)
        if char == '"':
            in_string = False
        index += 1

    return "".join(chars)


def _repair_common_json_issues(text: str) -> str:
    repaired = _strip_code_fence_wrappers(str(text or "").lstrip("\ufeff"))
    if repaired.lower().startswith("json\n"):
        repaired = repaired[5:].strip()
    repaired = _escape_invalid_json_backslashes(repaired)
    repaired = re.sub(r",(\s*[\]}])", r"\1", repaired)
    return repaired.strip()


def _build_json_candidates(raw_content: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(value: Optional[str]) -> None:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    initial = str(raw_content or "").strip()
    stripped_fence = _strip_code_fence_wrappers(initial)
    _add(initial)
    _add(stripped_fence)

    for base in tuple(candidates):
        _add(_extract_first_json_array(base))
        first_bracket = base.find("[")
        last_bracket = base.rfind("]")
        if 0 <= first_bracket < last_bracket:
            _add(base[first_bracket : last_bracket + 1])

    for base in tuple(candidates):
        _add(_repair_common_json_issues(base))

    return candidates


def _normalize_comment_items(comments: object) -> list[dict[str, str]]:
    if not isinstance(comments, list):
        raise ValueError(f"LLM 输出不是列表，而是 {type(comments).__name__}")

    return [
        {
            "reference_text": str(item.get("reference_text", "") or ""),
            "comment_text": str(item.get("comment_text", "") or ""),
        }
        for item in comments
        if isinstance(item, dict)
    ]


def _parse_comment_output(raw_content: str) -> list[dict[str, str]]:
    last_error: Optional[Exception] = None

    for candidate in _build_json_candidates(raw_content):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        return _normalize_comment_items(parsed)

    if last_error:
        raise last_error
    raise ValueError("未找到可解析的 JSON 数组")


def _write_text_if_possible(path, content: str) -> None:
    if not path:
        return
    with open(path, "w", encoding="utf-8") as file:
        file.write(str(content or ""))


def _write_json_if_possible(path, payload: dict[str, object]) -> None:
    if not path:
        return
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _with_polished_text_in_retrieval_payload(
    payload: dict[str, object] | None,
    polished_text: str,
) -> dict[str, object] | None:
    if payload is None:
        return None
    enriched_payload = dict(payload)
    enriched_payload["polished_text"] = polished_text
    return enriched_payload


def _build_bad_case_context_for_comments(
    polished_text: str,
) -> tuple[list[dict[str, str]], dict[str, object] | None]:
    try:
        retrieval_result = retrieve_bad_case_hits(polished_text)
    except Exception as e:
        progress_log.warning(
            f"[generate_comments] bad case 检索失败，已回退原批注 prompt: {e}"
        )
        return [], build_failed_bad_case_retrieval_payload(polished_text, e)

    for warning in retrieval_result.warnings:
        progress_log.warning(f"[generate_comments] bad case 检索警告: {warning}")

    bad_case_context = build_bad_case_prompt_context(retrieval_result)
    if bad_case_context:
        progress_log.debug(
            f"[generate_comments] bad case 检索命中 {len(bad_case_context)} 条，将注入批注 prompt"
        )
    to_log_payload = getattr(retrieval_result, "to_log_payload", None)
    retrieval_payload = to_log_payload() if callable(to_log_payload) else None
    return bad_case_context, retrieval_payload


def _coerce_bad_case_context_result(
    value: Any,
) -> tuple[list[dict[str, str]], dict[str, object] | None]:
    if (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[1], (dict, type(None)))
    ):
        return list(value[0] or []), value[1]
    return list(value or []), None


def generate_comments(state: TenderGraphStateBase, config) -> TenderGraphStateBase:
    """
    基于修改文本使用 LLM 生成批注指令。

    本函数分析修改文本并使用 LLM 生成可插入 Word 文档的结构化批注指令。

    Args:
        state (TenderGraphStateBase): 包含输入字段的当前图状态
            - polished_text: 来自 update_word 节点的精炼文本内容
            - tender_type: 招标文档类型（默认："xjcg"）
        config: 配置字典，包含可选的 model_provider 和回调函数
            - model_provider: LLM 提供商（默认："deepseek"）
            - llm_stream_callback: 可选的流式回调函数
            - suppress_llm_stdout: 是否抑制控制台输出

    Returns:
        TenderGraphStateBase: 仅包含 polished_comments 字段的状态字典
            - polished_comments: 生成的批注指令列表，每个元素包含：
                - reference_text: 文档中附加批注的文本内容
                - comment_text: 批注的具体内容

    Raises:
        ValueError: 当提供未知的 tender_type 时

    需求引用：1.4, 1.5, 8.1
    """
    # 初始化执行计时
    start_time = time.time()

    # 添加启动日志消息
    progress_log.debug("[generate_comments] 开始执行...")

    # 从 state 读取输入数据，使用防御性默认值
    polished_text = state.get("polished_text", "")
    tender_type = state.get("tender_type", "xjcg")

    # 记录正在使用的 tender_type
    progress_log.debug(f"[generate_comments] 招标类型: {tender_type}")

    # 实现提示词选择和验证
    prompt_input = CommentPromptInput(
        tender_type=str(tender_type or "xjcg"),
        polished_text=str(polished_text or ""),
    )
    bad_case_context, bad_case_retrieval_payload = _coerce_bad_case_context_result(
        _build_bad_case_context_for_comments(prompt_input.polished_text)
    )
    if bad_case_context:
        rendered_prompt = render_comment_prompt_with_bad_case_context(
            prompt_input,
            bad_case_context,
        )
    else:
        rendered_prompt = render_comment_prompt(prompt_input)
    system_prompt = rendered_prompt.system_prompt
    formatted_user_prompt = rendered_prompt.user_prompt

    # 准备 context_log/generate_log 输出路径：保存大模型生成的批注内容，使用 new_comments 后缀区分
    new_comments_file = None
    comments_prompt_file = None
    raw_comments_file = None
    repaired_comments_file = None
    comments_bad_case_retrieval_file = None
    try:
        context_log_dir = get_generate_context_log_dir(__file__)

        project_number = str(state.get("project_number", "") or "").strip()
        project_name = str(state.get("project_name", "") or "").strip()
        filename_parts = [
            _sanitize_filename(part) for part in (project_number, project_name) if part
        ]
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        prompt_base = "-".join(filename_parts + ["初稿"]) if filename_parts else "初稿"
        comments_prompt_file = (
            context_log_dir / f"prompt_{prompt_base}_comments_prompt_{timestamp}.txt"
        )
        raw_comments_file = (
            context_log_dir / f"prompt_{prompt_base}_comments_raw_output_{timestamp}.txt"
        )
        repaired_comments_file = (
            context_log_dir
            / f"prompt_{prompt_base}_comments_repaired_output_{timestamp}.txt"
        )
        new_comments_file = (
            context_log_dir / f"prompt_{prompt_base}_new_comments_{timestamp}.txt"
        )
        comments_bad_case_retrieval_file = (
            context_log_dir
            / f"prompt_{prompt_base}_comments_bad_case_retrieval_{timestamp}.json"
        )

        with open(comments_prompt_file, "w", encoding="utf-8") as f:
            f.write(system_prompt + "\n" + formatted_user_prompt)
        enriched_retrieval_payload = _with_polished_text_in_retrieval_payload(
            bad_case_retrieval_payload,
            prompt_input.polished_text,
        )
        if enriched_retrieval_payload is not None:
            _write_json_if_possible(
                comments_bad_case_retrieval_file,
                enriched_retrieval_payload,
            )
    except Exception as e:
        progress_log.warning(f"[generate_comments] 警告: 准备批注输出文件路径失败: {e}")

    # 实现配置提取和回调设置

    # 从 config 提取 model_provider，默认为 "deepseek"
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    model_provider = configurable.get("model_provider", "deepseek")

    llm_model_override = None
    llm_extra_params_override = None
    effective_model_display = model_provider
    if model_provider == "deepseek":
        llm_extra_params_override = {"temperature": 1.3}

    progress_log.debug(f"[generate_comments] 使用模型: {effective_model_display}")

    # 从 config 提取 llm_stream_callback（如果可用）
    stream_callback: Optional[Callable[[str], None]] = None
    suppress_llm_stdout = False

    if config:
        try:
            if isinstance(configurable, dict):
                stream_callback = configurable.get("llm_stream_callback")
                suppress_llm_stdout = bool(
                    configurable.get("suppress_llm_stdout", False)
                )
            # 如果 configurable 中没有，尝试从 config 根级别获取
            if not stream_callback and isinstance(config, dict):
                stream_callback = config.get("llm_stream_callback")
        except Exception:
            stream_callback = None

    # 定义 _push_stream_update 回调函数用于流式更新
    def _push_stream_update(text: str) -> None:
        """
        推送流式更新到回调函数。

        为了避免在日志 / 前端 UI 中打印 generate_comments 节点的完整 AI 输出，
        该回调在此节点中被显式禁用，仅在内部使用最终结果进行 JSON 解析。
        """
        # 不向外传播 LLM 的完整输出内容，保护批注文本不被直接打印
        return

    # 定义 _log_chunk 回调函数用于控制台输出
    def _log_chunk(text: str) -> None:
        """将 chunk 输出到控制台"""
        if suppress_llm_stdout:
            return
        progress_log.debug(text, end="", flush=True)

    # 创建 StreamCallbacks 对象，包含 on_chunk 和 on_update 回调
    callbacks = StreamCallbacks(
        on_chunk=_log_chunk,
        on_update=_push_stream_update,
    )

    # 实现带错误处理的 LLM 流式调用

    # 设置 asyncio 事件循环（获取现有或创建新的）
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # 在 try-except 块中包装 stream_llm_completion 调用
    try:
        # 使用 model_provider、system_prompt、user_prompt、callbacks、timeout_seconds 和 check_interval 调用 stream_llm_completion
        content = loop.run_until_complete(
            stream_llm_completion(
                model_provider=model_provider,
                system_prompt=system_prompt,
                user_prompt=formatted_user_prompt,
                callbacks=callbacks,
                model_override=llm_model_override,
                extra_params_override=llm_extra_params_override,
                check_interval=CHECK_INTERVAL,
            )
        )
    except LLMTimeoutError as e:
        # 捕获 LLMTimeoutError 并记录错误，返回空的 polished_comments 列表
        progress_log.error(f"\n[generate_comments] LLM 超时错误: {e}")
        return TenderGraphStateBase(polished_comments=[], generated_comment_count=0)
    except Exception as e:
        # 捕获一般异常，记录完整堆栈跟踪，返回空的 polished_comments 列表
        progress_log.exception(f"[generate_comments] 发生意外错误: {e}")
        return TenderGraphStateBase(polished_comments=[], generated_comment_count=0)

    try:
        _write_text_if_possible(raw_comments_file, content)
    except Exception as e:
        progress_log.warning(f"[generate_comments] 警告: 保存原始批注输出失败: {e}")

    # 实现带错误处理的 JSON 解析

    # 确保输出后有换行
    if not suppress_llm_stdout:
        progress_log.debug("")

    polished_comments: list[dict[str, str]] = []
    try:
        polished_comments = _parse_comment_output(content)
        progress_log.info(
            f"[generate_comments] 生成了 {len(polished_comments)} 条批注指令"
        )
    except (json.JSONDecodeError, ValueError) as first_error:
        progress_log.warning("[generate_comments] 批注输出格式无效，尝试自动修复")

        repaired_comments: Optional[list[dict[str, str]]] = None
        repair_error: Optional[Exception] = None

        for _ in range(JSON_REPAIR_RETRY_LIMIT):
            repair_prompt = render_comment_json_repair_prompt(content)
            try:
                repaired_content = loop.run_until_complete(
                    stream_llm_completion(
                        model_provider=model_provider,
                        system_prompt=repair_prompt.system_prompt,
                        user_prompt=repair_prompt.user_prompt,
                        callbacks=callbacks,
                        model_override=llm_model_override,
                        extra_params_override={
                            "temperature": JSON_REPAIR_TEMPERATURE
                        },
                        check_interval=CHECK_INTERVAL,
                    )
                )
            except LLMTimeoutError as e:
                progress_log.error(f"\n[generate_comments] JSON 修复重试超时: {e}")
                repair_error = e
                break
            except Exception as e:
                progress_log.exception(
                    f"[generate_comments] JSON 修复重试发生意外错误: {e}"
                )
                repair_error = e
                break

            try:
                _write_text_if_possible(repaired_comments_file, repaired_content)
            except Exception as e:
                progress_log.warning(
                    f"[generate_comments] 警告: 保存修复后批注输出失败: {e}"
                )

            if not suppress_llm_stdout:
                progress_log.debug("")

            try:
                repaired_comments = _parse_comment_output(repaired_content)
                break
            except (json.JSONDecodeError, ValueError) as e:
                repair_error = e

        if repaired_comments is not None:
            polished_comments = repaired_comments
            progress_log.info(
                f"[generate_comments] JSON 自动修复成功，生成了 {len(polished_comments)} 条批注指令"
            )
        else:
            error_to_log = repair_error or first_error
            if isinstance(error_to_log, json.JSONDecodeError):
                progress_log.error(
                    f"[generate_comments] JSON 解析失败 (JSONDecodeError): {error_to_log}"
                )
            elif isinstance(error_to_log, ValueError):
                progress_log.error(
                    f"[generate_comments] JSON 解析失败 (ValueError): {error_to_log}"
                )
            else:
                progress_log.error(
                    f"[generate_comments] JSON 解析时发生意外错误: {error_to_log}"
                )
            polished_comments = []

    except KeyError as e:
        # 捕获 KeyError 并记录错误
        progress_log.error(f"[generate_comments] JSON 解析失败 (KeyError): {e}")
        polished_comments = []

    except Exception as e:
        # 捕获其他异常并记录错误
        progress_log.exception(f"[generate_comments] JSON 解析时发生意外错误: {e}")
        polished_comments = []

    try:
        if new_comments_file:
            with open(new_comments_file, "w", encoding="utf-8") as f:
                f.write(json.dumps(polished_comments, ensure_ascii=False, indent=2))
    except Exception as e:
        progress_log.warning(f"[generate_comments] 警告: 保存批注内容到文件失败: {e}")

    # 计算执行持续时间
    duration = time.time() - start_time
    duration_ms = int(duration * 1000)

    # 记录包含执行时间的完成消息
    progress_log.info(
        f"[generate_comments] 执行完成，耗时: {duration:.2f} 秒 ({duration_ms} 毫秒)"
    )

    # 创建仅包含 polished_comments 字段的新状态字典
    # 确保不修改输入状态对象（不可变性）
    return TenderGraphStateBase(
        polished_comments=polished_comments,
        generated_comment_count=len(polished_comments),
    )
