from __future__ import annotations

import datetime
from typing import Callable, Optional
import os
import pathlib
import re
import time

from langchain_deepseek import ChatDeepSeek
from volcenginesdkarkruntime import Ark
from openai import OpenAI, AsyncOpenAI
import asyncio


    # 直接运行时使用绝对导入
import sys

from logging_utils import log_state
from state import TenderGraphState
   

def _sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


from dotenv import load_dotenv
load_dotenv()


async def generate_polished_text(state: TenderGraphState, config) -> TenderGraphState:
    start_time = time.perf_counter()
    print("[generate_polished_text] 开始执行...")
    
    # 优先使用文件路径，如果没有则使用文本内容
    origin_tender_path = state.get("origin_tender_path")
    origin_tender_params = state.get("origin_tender_params")
    tender_param_path = state.get("tender_param_path")
    
    tender_params = state.get("tender_params")
    
    
    # 获取配置的 model_provider，默认为 deepseek
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    model_provider = configurable.get("model_provider", "deepseek")
    print(f"[generate_polished_text] 使用模型: {model_provider}")

    from .xjcg_prompt import POLISH_PROMPT
    prompt = POLISH_PROMPT.format(
        tender_params=tender_params,
        origin_tender_params=origin_tender_params,
    )
    
    # 保存提示词到文件
    prompts_dir = pathlib.Path(__file__).resolve().parents[2] / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    project_number = str(state.get("project_number", "") or "").strip()
    project_name = str(state.get("project_name", "") or "").strip()
    filename_parts = [_sanitize_filename(part) for part in (project_number, project_name) if part]
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    prompt_file = "-".join(filename_parts + ["初稿"]) if filename_parts else "初稿"
    prompt_file = prompts_dir / f"prompt_{prompt_file}_{timestamp}.txt"
    try:
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)
    except Exception as e:
        print(f"警告: 保存提示词文件失败: {e}")
    
    stream_callback: Optional[Callable[[str], None]] = None
    suppress_llm_stdout = False
    if config:
        try:
            configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
            if isinstance(configurable, dict):
                stream_callback = configurable.get("llm_stream_callback")
                suppress_llm_stdout = bool(configurable.get("suppress_llm_stdout", False))
            if not stream_callback and isinstance(config, dict):
                stream_callback = config.get("llm_stream_callback")
        except Exception:
            stream_callback = None

    def _push_stream_update(text: str) -> None:
        if callable(stream_callback) and text is not None:
            try:
                stream_callback(str(text))
            except Exception as cb_exc:
                print(f"警告: LLM 流式回调失败: {cb_exc}")

    def _log_chunk(text: str) -> None:
        if suppress_llm_stdout:
            return
        print(text, end="", flush=True)

    content_parts = []
    content = ""
    TIMEOUT_SECONDS = 20  # 20秒超时

    # 根据模型提供商选择不同的调用方式
    if model_provider == "doubao":
        try:
            # Doubao (Ark) Implementation - 异步调用
            client = Ark(
                base_url=os.getenv('ARK_BASE_URL'),
                api_key=os.getenv('ARK_API_KEY')
            )
            
            # 定义同步非流式处理函数
            def _doubao_non_stream_sync():
                response = client.chat.completions.create(
                    model=os.getenv("DOUBAO_MODEL"),
                    messages=[
                        {"role": "user", "content": prompt},
                    ],
                    stream=False,
                    max_completion_tokens=32768,
                    thinking={"type": "disabled"},
                )
                return response.choices[0].message.content if response.choices else ""
            
            # 尝试异步流式调用
            try:
                # 使用 asyncio.to_thread 在线程中执行同步流式调用
                # 由于流式响应需要实时处理，我们需要在线程中处理并实时更新
                def _process_stream():
                    start_time = time.time()
                    completion = client.chat.completions.create(
                        model=os.getenv("DOUBAO_MODEL"),
                        messages=[
                            {"role": "user", "content": prompt},
                        ],
                        stream=True,
                        max_completion_tokens=32768,
                        thinking={"type": "disabled"},
                    )
                    parts = []
                    first_chunk_received = False
                    for chunk in completion:
                        if not first_chunk_received:
                            elapsed = time.time() - start_time
                            if elapsed > TIMEOUT_SECONDS:
                                print(f"\n警告: Doubao 流式调用超时（{TIMEOUT_SECONDS}秒内未收到响应）")
                                return ""
                            first_chunk_received = True
                        if chunk.choices[0].delta.content is not None:
                            chunk_text = chunk.choices[0].delta.content
                            parts.append(chunk_text)
                            content_parts.append(chunk_text)
                            _log_chunk(chunk_text)
                            _push_stream_update("".join(content_parts))
                    return "".join(parts)
                
                content = await asyncio.wait_for(
                    asyncio.to_thread(_process_stream),
                    timeout=TIMEOUT_SECONDS
                )
                print()
            except asyncio.TimeoutError:
                print(f"\n警告: Doubao 模型调用超时（{TIMEOUT_SECONDS}秒），返回空内容")
                content = ""
            except Exception as stream_exc:
                print(f"Doubao 流式调用失败，回退到非流式: {stream_exc}")
                try:
                    # 回退到非流式调用，也添加超时
                    content = await asyncio.wait_for(
                        asyncio.to_thread(_doubao_non_stream_sync),
                        timeout=TIMEOUT_SECONDS
                    )
                    _push_stream_update(str(content))
                except asyncio.TimeoutError:
                    print(f"\n警告: Doubao 非流式调用超时（{TIMEOUT_SECONDS}秒），返回空内容")
                    content = ""
            
        except Exception as e:
            print(f"Doubao 模型调用失败: {e}，返回空内容")
            content = ""

    elif model_provider == "qwen":
        try:
            # Qwen Implementation - 异步调用
            client = AsyncOpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url=os.getenv("DASHSCOPE_BASE_URL"),
            )
            
            # 尝试异步流式调用
            try:
                async def _qwen_stream_call():
                    start_time = time.time()
                    completion = await client.chat.completions.create(
                        model=os.getenv("QWEN_MODEL"),
                        messages=[{'role': 'user', 'content': prompt}],
                        stream=True,
                        stream_options={"include_usage": True},
                        extra_body={"max_input_tokens": 1000000, "enable_thinking": False}
                    )
                    
                    first_chunk_received = False
                    async for chunk in completion:
                        if not first_chunk_received:
                            elapsed = time.time() - start_time
                            if elapsed > TIMEOUT_SECONDS:
                                print(f"\n警告: Qwen 流式调用超时（{TIMEOUT_SECONDS}秒内未收到响应）")
                                return ""
                            first_chunk_received = True
                        # Qwen compatible mode might return chunk with choices
                        if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            if hasattr(delta, 'content') and delta.content:
                                chunk_text = delta.content
                                content_parts.append(chunk_text)
                                _log_chunk(chunk_text)
                                _push_stream_update("".join(content_parts))
                    return "".join(content_parts)
                
                content = await asyncio.wait_for(_qwen_stream_call(), timeout=TIMEOUT_SECONDS)
                print()
            except asyncio.TimeoutError:
                print(f"\n警告: Qwen 流式调用超时（{TIMEOUT_SECONDS}秒），返回空内容")
                content = ""
            except Exception as stream_exc:
                print(f"Qwen 流式调用失败，回退到非流式: {stream_exc}")
                try:
                    # 回退到非流式调用，也添加超时
                    response = await asyncio.wait_for(
                        client.chat.completions.create(
                            model=os.getenv("QWEN_MODEL"),
                            messages=[{'role': 'user', 'content': prompt}],
                            stream=False,
                            extra_body={"max_input_tokens": 1000000, "enable_thinking": False}
                        ),
                        timeout=TIMEOUT_SECONDS
                    )
                    content = response.choices[0].message.content if response.choices else ""
                    _push_stream_update(str(content))
                except asyncio.TimeoutError:
                    print(f"\n警告: Qwen 非流式调用超时（{TIMEOUT_SECONDS}秒），返回空内容")
                    content = ""

        except Exception as e:
            print(f"Qwen 模型调用失败: {e}，返回空内容")
            content = ""

    else:
        # Default: DeepSeek
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set")

        llm = ChatDeepSeek(
            model=os.getenv("DEEPSEEK_MODEL"),
            api_key=api_key,
            max_tokens=8192,
            temperature=0.1
        )

        def _chunk_to_text(chunk) -> str:
            if chunk is None:
                return ""
            text = getattr(chunk, "content", None)
            if isinstance(text, list):
                text = "".join([str(t) for t in text if t is not None])
            if not text and hasattr(chunk, "message"):
                text = getattr(chunk.message, "content", "")  # type: ignore[attr-defined]
            return str(text) if text else ""

        stream_method = getattr(llm, "astream", None)
        invoke_method = getattr(llm, "ainvoke", None)
        if callable(stream_method):
            try:
                async def _deepseek_stream_call():
                    start_time = time.time()
                    first_chunk_received = False
                    async for chunk in stream_method(prompt):
                        if not first_chunk_received:
                            elapsed = time.time() - start_time
                            if elapsed > TIMEOUT_SECONDS:
                                print(f"\n警告: DeepSeek 流式调用超时（{TIMEOUT_SECONDS}秒内未收到响应）")
                                return ""
                            first_chunk_received = True
                        chunk_text = _chunk_to_text(chunk)
                        if not chunk_text:
                            continue
                        content_parts.append(chunk_text)
                        _log_chunk(chunk_text)
                        _push_stream_update("".join(content_parts))
                    return "".join(content_parts)
                
                content = await asyncio.wait_for(_deepseek_stream_call(), timeout=TIMEOUT_SECONDS)
                print()  # 换行，避免日志粘连
            except asyncio.TimeoutError:
                print(f"\n警告: DeepSeek 流式调用超时（{TIMEOUT_SECONDS}秒），返回空内容")
                content = ""
            except Exception as stream_exc:
                print(f"流式获取失败，回退到非流式: {stream_exc}")
                try:
                    if callable(invoke_method):
                        response = await asyncio.wait_for(invoke_method(prompt), timeout=TIMEOUT_SECONDS)
                        content = getattr(response, "content", response)
                    else:
                        response = await asyncio.wait_for(
                            asyncio.to_thread(llm.invoke, prompt),
                            timeout=TIMEOUT_SECONDS
                        )
                        content = getattr(response, "content", response)
                    _push_stream_update(str(content))
                except asyncio.TimeoutError:
                    print(f"\n警告: DeepSeek 非流式调用超时（{TIMEOUT_SECONDS}秒），返回空内容")
                    content = ""
        else:
            try:
                if callable(invoke_method):
                    response = await asyncio.wait_for(invoke_method(prompt), timeout=TIMEOUT_SECONDS)
                    content = getattr(response, "content", response)
                else:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(llm.invoke, prompt),
                        timeout=TIMEOUT_SECONDS
                    )
                    content = getattr(response, "content", response)
                _push_stream_update(str(content))
            except asyncio.TimeoutError:
                print(f"\n警告: DeepSeek 非流式调用超时（{TIMEOUT_SECONDS}秒），返回空内容")
                content = ""
    # content = """"""

    # 将大模型生成的内容写入 txt 文件，命名：项目编号-项目名称-初稿.txt
    project_number = str(state.get("project_number", "") or "").strip()
    project_name = str(state.get("project_name", "") or "").strip()
    filename_parts = [_sanitize_filename(part) for part in (project_number, project_name) if part]
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    filename = "-".join(filename_parts + ["初稿"]) if filename_parts else "初稿"
    filename = f"{filename}-{timestamp}.txt"
    # 优先使用 origin_tender_path 所在目录，其次 tender_param_path，再次 prompts 目录
    output_dir = None
    try:
        if origin_tender_path:
            output_dir = pathlib.Path(origin_tender_path).resolve().parent
        elif tender_param_path:
            output_dir = pathlib.Path(tender_param_path).resolve().parent
    except Exception:
        output_dir = None
    if not output_dir:
        output_dir = prompts_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    polished_txt_path = output_dir / filename
    try:
        with open(polished_txt_path, "w", encoding="utf-8") as f:
            f.write(str(content))
    except Exception as e:
        print(f"警告: 保存润色文本到文件失败: {e}")

    # 只返回需要更新的键，避免并行执行时的状态冲突
    # 在 LangGraph 中，并行节点应该只返回部分状态更新
    new_state = TenderGraphState(polished_text=content, generate_polished_done=True)
    # 为了日志记录，创建完整状态（仅用于日志）
    full_state_for_log = dict(state)
    full_state_for_log.update({"polished_text": content, "generate_polished_done": True})
    log_state("generate_polished_text", TenderGraphState(**full_state_for_log))
    
    duration = time.perf_counter() - start_time
    duration_ms = duration * 1000
    print(f"[generate_polished_text] 执行完成，耗时: {duration:.2f} 秒 ({duration_ms:.0f} 毫秒)")
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
    from state import TenderGraphState
    from nodes.xjcg_word_nodes.extract_tender_params import extract_tender_params
    from util.word_extraction_utils import extract_text_from_word_file
    
    # 测试配置：参考文档路径和技术参数路径
    # 可以根据需要修改这两个路径
    reference_doc_path_str = "TenderFile/251918-询价文件-初稿.doc"  # 参考文档路径
    tech_spec_path_str = "TenderFile/恒温暖柜等设备招标参数.docx"  # 技术参数路径
    
    # 基于项目根目录解析路径
    reference_doc_path = (ROOT / reference_doc_path_str).resolve()
    tech_spec_path = (ROOT / tech_spec_path_str).resolve()
    
    print("\n" + "=" * 80)
    print("测试 extract_tender_params 和 generate_polished_text 节点")
    print("=" * 80)
    print(f"参考文档路径: {reference_doc_path}")
    print(f"参考文档是否存在: {reference_doc_path.exists()}")
    print(f"技术参数路径: {tech_spec_path}")
    print(f"技术参数文档是否存在: {tech_spec_path.exists()}")
    print()
    
    if not reference_doc_path.exists():
        print(f"错误: 参考文档不存在: {reference_doc_path}")
        sys.exit(1)
    
    if not tech_spec_path.exists():
        print(f"错误: 技术参数文档不存在: {tech_spec_path}")
        sys.exit(1)
    
    try:
        # 第一步：从参考文档中提取参数（调用 extract_tender_params）
        print("\n" + "-" * 80)
        print("第一步: 从参考文档中提取参数")
        print("-" * 80)
        
        extract_state: TenderGraphState = {
            "prepared_doc_path": str(reference_doc_path),
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
        }
        
        result_state = extract_tender_params(extract_state, config=None)
        tender_params = result_state.get("tender_params", "")
        
        if not tender_params:
            print("错误: 未能从参考文档中提取到内容")
            sys.exit(1)
        
        # 等待 Word 实例完全关闭
        print("等待 Word 实例完全关闭...")
        time.sleep(1.0)
        
        # 第二步：读取技术参数文档内容
        print("\n" + "-" * 80)
        print("第二步: 读取技术参数文档内容")
        print("-" * 80)
        
        origin_tender_params = extract_text_from_word_file(str(tech_spec_path))
        
        # 第三步：调用 generate_polished_text 生成润色后的文本
        print("\n" + "-" * 80)
        print("第三步: 生成润色后的文本")
        print("-" * 80)
        
        polish_state: TenderGraphState = {
            "tender_params": tender_params,
            "origin_tender_params": origin_tender_params,
        }
        
        polished_result_state = generate_polished_text(polish_state, config=None)
        polished_text = polished_result_state.get("polished_text", "")
        
        if polished_text:
            print(f"\n成功生成润色文本，长度: {len(polished_text)} 字符")
            
            # 保存完整内容到文件
            output_file = tech_spec_path.parent / f"{tech_spec_path.stem}_polished.txt"
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(polished_text)
                print(f"润色文本已保存到文件: {output_file}")
            except Exception as save_e:
                print(f"警告: 保存文件时出错: {save_e}")
            
            print("\n" + "=" * 80)
            print("生成的润色文本（完整内容）:")
            print("=" * 80)
            print(polished_text)
            print("=" * 80)
            print(f"\n内容总长度: {len(polished_text)} 字符")
            print(f"内容行数: {len(polished_text.splitlines())} 行")
        else:
            print("\n未生成任何内容")
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
