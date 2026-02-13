"""
批注生成节点

本模块实现 generate_comments 节点，使用 LLM 基于润色文本和从 Word 文档中提取的
各种计划详情生成批注指令。

该节点遵循与 generate_polished_text.py 相同的架构模式，通过提示词注册表系统
支持多种招标类型（xjcg 和 gngk）。

需求引用：1.1, 1.2, 1.3
"""

from __future__ import annotations

import asyncio
import json
import time
import pathlib
from typing import Callable, Optional

from states import TenderGraphStateBase
from util.llm_stream_utils import (
    LLMTimeoutError,
    StreamCallbacks,
    stream_llm_completion,
)
from nodes.common_word_nodes.generate_polished_text import _sanitize_filename

from prompt.comment_prompt import (
    COMMENT_SYSTEM_PROMPT,
    COMMENT_USER_PROMPT,
)

# 模块级常量
TIMEOUT_SECONDS = 10  # LLM 超时时间（秒）
CHECK_INTERVAL = 3.0  # 心跳检查间隔（秒）

# Prompt 注册表：根据 tender_type 选择对应的 prompt
PROMPT_REGISTRY = {
    "xjcg": (COMMENT_SYSTEM_PROMPT, COMMENT_USER_PROMPT),
    "gngk": (COMMENT_SYSTEM_PROMPT, COMMENT_USER_PROMPT),
}


def generate_comments(
    state: TenderGraphStateBase,
    config
) -> TenderGraphStateBase:
    """
    基于润色文本和计划使用 LLM 生成批注指令。
    
    本函数分析润色文本以及从 Word 文档中提取的批注计划、删除线计划和非黑色字体计划，
    使用 LLM 生成可插入 Word 文档的结构化批注指令。
    
    Args:
        state (TenderGraphStateBase): 包含输入字段的当前图状态
            - polished_text: 来自 update_word 节点的精炼文本内容
            - comment_plan_detail: 批注详情，包含 content 和 scope_text
            - strikethrough_plan: 包含删除线文本的段落
            - non_black_font_plan: 包含非黑色字体文本的段落
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
    print("[generate_comments] 开始执行...")
    
    # 从 state 读取输入数据，使用防御性默认值
    # 需求引用：2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 7.1, 8.2
    polished_text = state.get("polished_text", "")
    comment_plan_detail = state.get("comment_plan_detail", [])
    strikethrough_plan = state.get("strikethrough_plan", [])
    non_black_font_plan = state.get("non_black_font_plan", [])
    tender_type = state.get("tender_type", "xjcg")
    
    # 记录正在使用的 tender_type
    print(f"[generate_comments] 招标类型: {tender_type}")
    
    # 实现提示词选择和验证
    # 需求引用：5.1, 5.2, 5.3, 5.4, 5.5
    if tender_type not in PROMPT_REGISTRY:
        raise ValueError(
            f"未知的招标类型: {tender_type}。"
            f"支持的类型: {list(PROMPT_REGISTRY.keys())}"
        )
    
    # 从 PROMPT_REGISTRY 获取 (system_prompt, user_prompt) 元组
    system_prompt, user_prompt = PROMPT_REGISTRY[tender_type]
    
    # 实现提示词格式化
    # 需求引用：5.6, 6.5, 6.6, 6.7, 6.8
    # 将输入数据转换为字符串格式，以便插入到提示词中
    formatted_user_prompt = user_prompt.format(
        polished_text=polished_text,
        comment_plan_detail=json.dumps(comment_plan_detail, ensure_ascii=False, indent=2),
        strikethrough_plan=json.dumps(strikethrough_plan, ensure_ascii=False, indent=2),
        non_black_font_plan=json.dumps(non_black_font_plan, ensure_ascii=False, indent=2)
    )

    # 准备 prompts 输出路径：保存大模型生成的批注内容，使用 new_comments 后缀区分
    new_comments_file = None
    comments_prompt_file = None
    try:
        prompts_dir = pathlib.Path(__file__).resolve().parents[2] / "prompts"
        prompts_dir.mkdir(exist_ok=True)

        project_number = str(state.get("project_number", "") or "").strip()
        project_name = str(state.get("project_name", "") or "").strip()
        filename_parts = [
            _sanitize_filename(part)
            for part in (project_number, project_name)
            if part
        ]
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        prompt_base = "-".join(filename_parts + ["初稿"]) if filename_parts else "初稿"
        comments_prompt_file = prompts_dir / f"prompt_{prompt_base}_comments_prompt_{timestamp}.txt"
        new_comments_file = prompts_dir / f"prompt_{prompt_base}_new_comments_{timestamp}.txt"

        with open(comments_prompt_file, "w", encoding="utf-8") as f:
            f.write(system_prompt + "\n" + formatted_user_prompt)
    except Exception as e:
        print(f"[generate_comments] 警告: 准备批注输出文件路径失败: {e}")
    
    # 实现配置提取和回调设置
    # 需求引用：4.2, 4.4, 8.3
    
    # 从 config 提取 model_provider，默认为 "deepseek"
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    model_provider = configurable.get("model_provider", "deepseek")
    
    llm_model_override = None
    llm_extra_params_override = None
    effective_model_display = model_provider
    if model_provider == "deepseek":
        llm_model_override = "deepseek-chat"
        llm_extra_params_override = {"temperature": 1.3}
        effective_model_display = llm_model_override

    print(f"[generate_comments] 使用模型: {effective_model_display}")
    
    # 从 config 提取 llm_stream_callback（如果可用）
    stream_callback: Optional[Callable[[str], None]] = None
    suppress_llm_stdout = False
    
    if config:
        try:
            if isinstance(configurable, dict):
                stream_callback = configurable.get("llm_stream_callback")
                suppress_llm_stdout = bool(configurable.get("suppress_llm_stdout", False))
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
        print(text, end="", flush=True)
    
    # 创建 StreamCallbacks 对象，包含 on_chunk 和 on_update 回调
    callbacks = StreamCallbacks(
        on_chunk=_log_chunk,
        on_update=_push_stream_update,
    )
    
    # 实现带错误处理的 LLM 流式调用
    # 需求引用：4.1, 4.2, 4.3, 4.4, 7.2, 7.4, 7.5, 7.6
    
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
                timeout_seconds=TIMEOUT_SECONDS,
                check_interval=CHECK_INTERVAL,
            )
        )
    except LLMTimeoutError as e:
        # 捕获 LLMTimeoutError 并记录错误，返回空的 polished_comments 列表
        print(f"\n[generate_comments] LLM 超时错误: {e}")
        return TenderGraphStateBase(polished_comments=[])
    except Exception as e:
        # 捕获一般异常，记录完整堆栈跟踪，返回空的 polished_comments 列表
        print(f"\n[generate_comments] 发生意外错误: {e}")
        import traceback
        traceback.print_exc()
        return TenderGraphStateBase(polished_comments=[])
    
    # 实现带错误处理的 JSON 解析
    # 需求引用：4.5, 4.6, 7.3, 7.4, 7.5, 8.4
    
    # 确保输出后有换行
    if not suppress_llm_stdout:
        print()
    
    try:
        # 使用 json.loads 解析 LLM 输出
        comments = json.loads(content)
        
        # 验证结果是一个列表
        if not isinstance(comments, list):
            print(f"[generate_comments] 警告: LLM 输出不是列表，而是 {type(comments).__name__}")
            polished_comments = []
        else:
            # 将每个字典转换为包含 reference_text 和 comment_text 字段的 CommentInstruction
            # 对缺失字段使用 .get() 和空字符串默认值
            # 过滤掉非字典项
            polished_comments = [
                {
                    "reference_text": c.get("reference_text", ""),
                    "comment_text": c.get("comment_text", "")
                }
                for c in comments
                if isinstance(c, dict)
            ]
            
            # 成功时记录生成的批注数量
            print(f"[generate_comments] 生成了 {len(polished_comments)} 条批注指令")
    
    except json.JSONDecodeError as e:
        # 捕获 JSONDecodeError 并记录错误
        print(f"[generate_comments] JSON 解析失败 (JSONDecodeError): {e}")
        polished_comments = []
    
    except ValueError as e:
        # 捕获 ValueError 并记录错误
        print(f"[generate_comments] JSON 解析失败 (ValueError): {e}")
        polished_comments = []
    
    except KeyError as e:
        # 捕获 KeyError 并记录错误
        print(f"[generate_comments] JSON 解析失败 (KeyError): {e}")
        polished_comments = []
    
    except Exception as e:
        # 捕获其他异常并记录错误
        print(f"[generate_comments] JSON 解析时发生意外错误: {e}")
        import traceback
        traceback.print_exc()
        polished_comments = []

    try:
        if new_comments_file:
            with open(new_comments_file, "w", encoding="utf-8") as f:
                f.write(json.dumps(polished_comments, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[generate_comments] 警告: 保存批注内容到文件失败: {e}")
    
    # 计算执行持续时间
    duration = time.time() - start_time
    duration_ms = int(duration * 1000)
    
    # 记录包含执行时间的完成消息
    print(f"[generate_comments] 执行完成，耗时: {duration:.2f} 秒 ({duration_ms} 毫秒)")
    
    # 创建仅包含 polished_comments 字段的新状态字典
    # 确保不修改输入状态对象（不可变性）
    # 需求引用：1.5, 3.1, 3.4, 7.5, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4
    return TenderGraphStateBase(polished_comments=polished_comments)
