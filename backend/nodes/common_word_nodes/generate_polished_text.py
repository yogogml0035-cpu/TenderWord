from __future__ import annotations

import os
import pathlib
import re
import sys
import time
from typing import Callable, Optional

from backend.prompts.generate_prompt import GENERATE_PROMPT_REGISTRY, render_generate_prompt
from backend.prompts.rewrite_prompt import render_rewrite_prompt
from backend.prompts.types import GeneratePromptInput, RewritePromptInput
from backend.states import TenderGraphStateBase
from backend.util.common_util import (
    StreamCallbacks,
    stream_llm_completion,
)
from backend.util.log_util.progress_log import progress_log

PROMPT_REGISTRY = GENERATE_PROMPT_REGISTRY


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


def generate_polished_text(state: TenderGraphStateBase, config) -> TenderGraphStateBase:
    start_time = time.perf_counter()
    progress_log.debug("[generate_polished_text] 开始执行...")
    
    # 优先使用文件路径，如果没有则使用文本内容
    origin_tender_path = state.get("origin_tender_path")
    origin_tender_params = state.get("origin_tender_params")
    tender_param_paths = state.get("tender_param_paths") or []
    
    tender_params = state.get("tender_params")
    
    
    # 获取配置的 model_provider，默认为 deepseek
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    model_provider = configurable.get("model_provider", "deepseek")
    progress_log.debug(f"[generate_polished_text] 使用模型: {model_provider}")

    # 根据 tender_type 从 PROMPT_REGISTRY 中选择对应的 prompt
    tender_type = state.get("tender_type", "xjcg")  # 默认使用 xjcg
    progress_log.debug(f"[generate_polished_text] 招标类型: {tender_type}")
    
    rewrite_mode = bool(state.get("rewrite_mode"))
    if rewrite_mode:
        rewrite_base_text = str(
            state.get("rewrite_base_text")
            or state.get("polished_text")
            or origin_tender_params
            or ""
        )
        rewrite_user_prompt = str(state.get("rewrite_user_prompt") or "").strip()
        if not rewrite_user_prompt:
            raise ValueError("rewrite_user_prompt 不能为空")

        rendered_prompt = render_rewrite_prompt(
            RewritePromptInput(
                base_text=rewrite_base_text,
                user_prompt=rewrite_user_prompt,
            )
        )
    else:
        rendered_prompt = render_generate_prompt(
            GeneratePromptInput(
                tender_type=tender_type,
                project_info=str(state.get("project_content", "") or ""),
                tender_params=tender_params,
                origin_tender_params=origin_tender_params,
            )
        )

    system_prompt = rendered_prompt.system_prompt
    user_prompt = rendered_prompt.user_prompt
    
    # 保存提示词到文件
    prompts_dir = pathlib.Path(__file__).resolve().parents[2] / "prompts_log"
    prompts_dir.mkdir(exist_ok=True)
    project_number = str(state.get("project_number", "") or "").strip()
    project_name = str(state.get("project_name", "") or "").strip()
    filename_parts = [_sanitize_filename(part) for part in (project_number, project_name) if part]
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    prompt_file = "-".join(filename_parts + ["初稿"]) if filename_parts else "初稿"
    prompt_file = prompts_dir / f"prompt_{prompt_file}_polish_prompt_{timestamp}.txt"
    try:
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(system_prompt + "\n" + user_prompt)
    except Exception as e:
        progress_log.debug(f"警告: 保存提示词文件失败: {e}")
    
    stream_callback: Optional[Callable[[str], None]] = None
    complete_callback: Optional[Callable[[str], None]] = None
    suppress_llm_stdout = False
    if config:
        try:
            configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
            if isinstance(configurable, dict):
                stream_callback = configurable.get("llm_stream_callback")
                complete_callback = configurable.get("llm_stream_complete_callback")
                suppress_llm_stdout = bool(configurable.get("suppress_llm_stdout", False))
            if not stream_callback and isinstance(config, dict):
                stream_callback = config.get("llm_stream_callback")
        except Exception:
            stream_callback = None
            complete_callback = None

    def _push_stream_update(text: str) -> None:
        if callable(stream_callback) and text is not None:
            try:
                stream_callback(str(text))
            except Exception as cb_exc:
                progress_log.debug(f"警告: LLM 流式回调失败: {cb_exc}")

    def _log_chunk(text: str) -> None:
        if suppress_llm_stdout:
            return
        progress_log.debug(text)

    # 超时配置
    TIMEOUT_SECONDS = 10  # 超时时间
    CHECK_INTERVAL = 3.0  # 检查间隔

    # 创建回调函数集合
    callbacks = StreamCallbacks(
        on_chunk=_log_chunk,
        on_update=_push_stream_update,
    )
    
    # 调用统一的流式 LLM 接口，使用 system_prompt 和 user_prompt
    # 使用同步方式调用（在事件循环中运行异步函数）
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    content = loop.run_until_complete(stream_llm_completion(
        model_provider=model_provider,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        callbacks=callbacks,
        timeout_seconds=TIMEOUT_SECONDS,
        check_interval=CHECK_INTERVAL,
    ))
    if callable(complete_callback):
        try:
            complete_callback(str(content))
        except Exception as cb_exc:
            progress_log.debug(f"警告: LLM 完成回调失败: {cb_exc}")

    try:
        output_file_base = "-".join(filename_parts + ["初稿"]) if filename_parts else "初稿"
        polished_output_file = prompts_dir / f"prompt_{output_file_base}_polished_text_{timestamp}.txt"
        with open(polished_output_file, "w", encoding="utf-8") as f:
            f.write(str(content))
    except Exception as e:
        progress_log.debug(f"警告: 保存修改结果到 prompts_log 失败: {e}")

    # 将大模型生成的内容写入 txt 文件，命名：项目编号-项目名称-初稿.txt
    project_number = str(state.get("project_number", "") or "").strip()
    project_name = str(state.get("project_name", "") or "").strip()
    filename_parts = [_sanitize_filename(part) for part in (project_number, project_name) if part]
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    filename = "-".join(filename_parts + ["初稿"]) if filename_parts else "初稿"
    filename = f"{filename}-{timestamp}.txt"

    output_dir = None
    candidate_output_paths = [
        origin_tender_path,
        state.get("prepared_doc_path"),
        state.get("clean_draft_path"),
        state.get("rewrite_temp_output_path"),
    ]
    if tender_param_paths:
        candidate_output_paths.append(tender_param_paths[0])

    for candidate_path in candidate_output_paths:
        if not candidate_path:
            continue
        try:
            output_dir = pathlib.Path(str(candidate_path)).expanduser().resolve().parent
            break
        except Exception:
            continue

    if output_dir is not None:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            polished_txt_path = output_dir / filename
            with open(polished_txt_path, "w", encoding="utf-8") as f:
                f.write(str(content))
        except Exception as e:
            progress_log.debug(f"警告: 保存修改文本到文件失败: {e}")
    else:
        progress_log.debug("警告: 未找到修改文本输出目录，跳过落盘文本文件")

    # 只返回需要更新的键，避免并行执行时的状态冲突
    # 在 LangGraph 中，并行节点应该只返回部分状态更新
    new_state = TenderGraphStateBase(polished_text=content, generate_polished_done=True)
    # 为了日志记录，创建完整状态（仅用于日志）
    full_state_for_log = dict(state)
    full_state_for_log.update({"polished_text": content, "generate_polished_done": True})
    
    duration = time.perf_counter() - start_time
    duration_ms = duration * 1000
    progress_log.debug(f"[generate_polished_text] 执行完成，耗时: {duration:.2f} 秒 ({duration_ms:.0f} 毫秒)")
    return new_state


if __name__ == "__main__":
    """
    测试模块：测试 extract_tender_params 和 generate_polished_text 两个节点
    """
    import pathlib
    import sys
    import time
    
    # 添加项目根目录到路径，以便导入模块
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    
    # 重新导入必要的模块（从项目根目录直接导入）
    from backend.states import TenderGraphStateBase
    # xjcg 的提取节点已更名为 xjcg_extract_tender_params.py，并在包 __init__ 中对外导出
    from backend.nodes.xjcg_word_nodes import extract_tender_params
    from util.word_util import extract_text_from_word_file
    
    # 测试配置：参考文档路径和技术参数路径
    # 可以根据需要修改这两个路径
    reference_doc_path_str = "TenderFile/251918-询价文件-初稿.doc"  # 参考文档路径
    tech_spec_path_str = "TenderFile/恒温暖柜等设备招标参数.docx"  # 技术参数路径
    
    # 基于项目根目录解析路径
    reference_doc_path = (ROOT / reference_doc_path_str).resolve()
    tech_spec_path = (ROOT / tech_spec_path_str).resolve()
    
    progress_log.debug("") or progress_log.debug("=" * 80)
    progress_log.debug("测试 extract_tender_params 和 generate_polished_text 节点")
    progress_log.debug("=" * 80)
    progress_log.debug(f"参考文档路径: {reference_doc_path}")
    progress_log.debug(f"参考文档是否存在: {reference_doc_path.exists()}")
    progress_log.debug(f"技术参数路径: {tech_spec_path}")
    progress_log.debug(f"技术参数文档是否存在: {tech_spec_path.exists()}")
    progress_log.debug("")
    
    if not reference_doc_path.exists():
        progress_log.debug(f"错误: 参考文档不存在: {reference_doc_path}")
        sys.exit(1)
    
    if not tech_spec_path.exists():
        progress_log.debug(f"错误: 技术参数文档不存在: {tech_spec_path}")
        sys.exit(1)
    
    try:
        # 第一步：从参考文档中提取参数（调用 extract_tender_params）
        progress_log.debug("") or progress_log.debug("-" * 80)
        progress_log.debug("第一步: 从参考文档中提取参数")
        progress_log.debug("-" * 80)
        
        extract_state: TenderGraphStateBase = {
            "prepared_doc_path": str(reference_doc_path),
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
        }
        
        result_state = extract_tender_params(extract_state, config=None)
        tender_params = result_state.get("tender_params", "")
        
        if not tender_params:
            progress_log.debug("错误: 未能从参考文档中提取到内容")
            sys.exit(1)
        
        # 等待 Word 实例完全关闭
        progress_log.debug("等待 Word 实例完全关闭...")
        time.sleep(1.0)
        
        # 第二步：读取技术参数文档内容
        progress_log.debug("") or progress_log.debug("-" * 80)
        progress_log.debug("第二步: 读取技术参数文档内容")
        progress_log.debug("-" * 80)
        
        origin_tender_params = extract_text_from_word_file(str(tech_spec_path))
        
        # 第三步：调用 generate_polished_text 生成修改后的文本
        progress_log.debug("") or progress_log.debug("-" * 80)
        progress_log.debug("第三步: 生成修改后的文本")
        progress_log.debug("-" * 80)
        
        polish_state: TenderGraphStateBase = {
            "tender_params": tender_params,
            "origin_tender_params": origin_tender_params,
        }
        
        polished_result_state = generate_polished_text(polish_state, config=None)
        polished_text = polished_result_state.get("polished_text", "")
        
        if polished_text:
            progress_log.debug(f"成功生成修改文本，长度: {len(polished_text)} 字符")
            
            # 保存完整内容到文件
            output_file = tech_spec_path.parent / f"{tech_spec_path.stem}_polished.txt"
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(polished_text)
                progress_log.debug(f"修改文本已保存到文件: {output_file}")
            except Exception as save_e:
                progress_log.debug(f"警告: 保存文件时出错: {save_e}")
            
            progress_log.debug("") or progress_log.debug("=" * 80)
            progress_log.debug("生成的修改文本（完整内容）:")
            progress_log.debug("=" * 80)
            progress_log.debug(polished_text)
            progress_log.debug("=" * 80)
            progress_log.debug(f"内容总长度: {len(polished_text)} 字符")
            progress_log.debug(f"内容行数: {len(polished_text.splitlines())} 行")
        else:
            progress_log.debug("未生成任何内容")
        
    except Exception as e:
        progress_log.debug(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
