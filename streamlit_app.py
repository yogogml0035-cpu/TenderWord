from __future__ import annotations

import asyncio
import contextlib
import io
import pathlib
import queue
import sys
import threading
import time
import traceback

import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from graph import build_graph

GRAPH = build_graph()

# 定义上传目录
UPLOAD_DIR = pathlib.Path("D:/PythonProject/TenderWord/UploadFiles")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class ThreadSafeLogWriter(io.StringIO):
    """线程安全的日志写入器，将日志写入队列供主线程消费并更新 UI。"""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
        self._buffer = ""

    def write(self, s: str) -> int:  # type: ignore[override]
        if not s:
            return 0
        self._buffer += s
        # 将当前累积的日志放入队列
        self.log_queue.put(("log", self._buffer))
        return len(s)

    def flush(self) -> None:  # noqa: D401
        return None

    def get_buffer(self) -> str:
        return self._buffer


class ThreadSafeLLMStreamer:
    """线程安全的 LLM 流式输出器，将输出写入队列供主线程消费并更新 UI。"""

    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue
        self._buffer = ""

    def update(self, text: str) -> None:
        """Replace current buffer with latest streamed content."""
        if text is None:
            return
        self._buffer = str(text)
        # 将 LLM 输出放入队列
        self.log_queue.put(("llm", self._buffer))

    def append(self, text: str) -> None:
        if not text:
            return
        self.update(self._buffer + text)

    def get_buffer(self) -> str:
        return self._buffer


st.set_page_config(page_title="招标文件生成MVP", layout="wide")
# 收紧页面顶部留白，让主体区域上移，但保留足够空间避免 tabs 被顶栏遮挡
st.markdown(
    """
    <style>
    /* 适当缩小顶部内边距，避免过大空白又不遮挡 tabs */
    div.block-container {padding-top: 2rem;}
    </style>
    """,
    unsafe_allow_html=True,
)
# 单页表单
tab, = st.tabs(["生成询价采购文件"])

with tab:
    st.markdown(
        "1. 上传待处理的 Word 模板文件\n"
        "2. 上传包含原始技术参数的 Word 文件\n"
        "3. 点击\"开始生成\"后等待完成提示，再到对应路径查看 Word 结果或直接下载\n\n"
        "**本次默认替换的内容：**\n"
        "- 插入技术参数位置：在\"第三章  采购需求\"之后，\"第四章  响应文件有关格式\"之前\n"
        "- 项目名称：测试项目名称\n"
        "- 项目编号：测试项目编号\n"
        "- 项目内容：\n"
        "  - 第1包：测试包件1   贰台\n"
        "  - 第2包：测试包件2   壹套\n"
        "  - 第3包：测试包件3   壹套\n"
        "- 保证金规则：\n"
        "  - 第1包：人民币1000元整；\n"
        "  - 第2包：人民币2000元整；\n"
        "  - 第3包：人民币3000元整\n"
        "- 采购人名称：测试采购人医院\n"
        "- 项目主办人/协办人：测试主办人、测试协办人\n"
        "- 主办人/协办人电话：8888、6666\n"
        "- 主办人拼音：wangshiqi"
    )

    with st.form("tender_doc_form"):
        uploaded_file = st.file_uploader(
            "参考 Word 文件（origin_tender_path）",
            type=["doc", "docx"],
            help="请上传作为参考的 Word 文件（.doc 或 .docx）",
        )
        origin_text_file = st.file_uploader(
            "技术参数文件（tender_param_path）",
            type=["doc", "docx"],
            help="请上传包含原始技术参数的 Word 文件（.doc 或 .docx）",
        )
        submitted = st.form_submit_button("开始生成")

    if submitted:
        if not uploaded_file:
            st.error("请上传 Word 模板文件")
        elif not origin_text_file:
            st.error("请上传原始技术参数文件")
        else:
            # 保存上传的模板文件到指定目录
            template_extension = pathlib.Path(uploaded_file.name).suffix
            saved_reference_path = UPLOAD_DIR / uploaded_file.name
            
            # 如果文件已存在，添加时间戳（精确到时分秒）避免覆盖
            if saved_reference_path.exists():
                timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
                name_without_ext = saved_reference_path.stem
                saved_reference_path = UPLOAD_DIR / f"{name_without_ext}_{timestamp}{template_extension}"
            
            # 保存模板文件
            with open(saved_reference_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # 保存原始技术参数文件到指定目录
            origin_extension = pathlib.Path(origin_text_file.name).suffix
            saved_param_path = UPLOAD_DIR / origin_text_file.name
            
            # 如果文件已存在，添加时间戳（精确到时分秒）避免覆盖
            if saved_param_path.exists():
                timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
                name_without_ext = saved_param_path.stem
                saved_param_path = UPLOAD_DIR / f"{name_without_ext}_{timestamp}{origin_extension}"
            
            # 保存原始技术参数文件
            with open(saved_param_path, "wb") as f:
                f.write(origin_text_file.getbuffer())
            
            # 使用保存后的文件路径
            origin_tender_path = str(saved_reference_path.resolve())
            tender_param_path = str(saved_param_path.resolve())
            
            initial_state = {
                # 上传文件路径
                "origin_tender_path": origin_tender_path,
                "tender_param_path": tender_param_path,
                # 固定参数（与 graph.py 中保持一致）
                "insertion_before_text": "第三章  采购需求",
                "insertion_after_text": "第四章  响应文件有关格式",
                "project_name": "测试项目名称",
                "project_number": "测试项目编号",
                "project_content": "第1包：测试包件1  贰台\n第2包：测试包件2  壹套\n第3包：测试包件3  壹套",
                "bzj_rule": "第1包：人民币1000元整；\n                第2包：人民币2000元整；\n                第3包：人民币3000元整",
                "buyer_name": "测试采购人医院",
                "project_zbr_xbr": "测试主办人、测试协办人",
                "zbr_xbr_tel": "8888、6666",
                "zbr_pinyin": "wangshiqi",
            }

            status_placeholder = st.empty()
            status_placeholder.info("正在生成询价采购文件，请稍候...")

            col_log, col_llm = st.columns(2)
            with col_log:
                st.markdown("**运行日志**")
                log_placeholder = st.empty()
            with col_llm:
                st.markdown("**DeepSeek大模型响应**")
                llm_placeholder = st.empty()

            # 使用队列在后台线程和主线程之间传递日志
            log_queue: queue.Queue = queue.Queue()
            log_writer = ThreadSafeLogWriter(log_queue)
            llm_streamer = ThreadSafeLLMStreamer(log_queue)

            # 用于存储后台线程的执行结果
            result_holder = {"result": None, "error": None, "done": False}

            def run_graph_in_thread():
                """在后台线程中执行 graph"""
                try:
                    from graph import invoke_with_timing_async

                    with contextlib.redirect_stdout(log_writer), contextlib.redirect_stderr(log_writer):
                        # 创建新的事件循环
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            result_state, elapsed_time = loop.run_until_complete(
                                invoke_with_timing_async(
                                    GRAPH,
                                    initial_state,
                                    verbose=True,
                                    config={
                                        "configurable": {
                                            "llm_stream_callback": llm_streamer.update,
                                            "suppress_llm_stdout": True,
                                        }
                                    },
                                )
                            )
                            result_holder["result"] = (result_state, elapsed_time)
                        finally:
                            loop.close()
                except Exception as exc:
                    result_holder["error"] = (exc, traceback.format_exc())
                finally:
                    result_holder["done"] = True
                    # 发送完成信号
                    log_queue.put(("done", None))

            # 启动后台线程
            worker_thread = threading.Thread(target=run_graph_in_thread, daemon=True)
            worker_thread.start()

            # 主线程循环消费队列，实时更新 UI
            current_log = ""
            current_llm = ""
            
            while not result_holder["done"] or not log_queue.empty():
                try:
                    # 非阻塞获取，超时 0.05 秒
                    msg_type, msg_content = log_queue.get(timeout=0.05)
                    
                    if msg_type == "log":
                        current_log = msg_content
                        log_placeholder.code(current_log, language="text")
                    elif msg_type == "llm":
                        current_llm = msg_content
                        llm_placeholder.code(current_llm, language="text")
                    elif msg_type == "done":
                        break
                except queue.Empty:
                    # 队列为空，继续等待
                    continue

            # 等待线程完全结束
            worker_thread.join(timeout=5.0)

            # 处理结果
            if result_holder["error"]:
                exc, tb = result_holder["error"]
                status_placeholder.error(f"生成失败：{exc}")
                log_placeholder.code(tb, language="text")
            else:
                result_state, elapsed_time = result_holder["result"]
                # 格式化时间显示
                if elapsed_time >= 60:
                    minutes = int(elapsed_time // 60)
                    seconds = elapsed_time % 60
                    time_str = f"{minutes} 分 {seconds:.2f} 秒"
                else:
                    time_str = f"{elapsed_time:.2f} 秒"
                
                status_placeholder.success(f"生成完成！总耗时: {time_str}，请前往对应路径查看 Word 文档。")

                prepared_path = result_state.get("prepared_doc_path")
                insertion_log = result_state.get("insertion_log")
                comments_summary = result_state.get("comments_summary")

                if prepared_path:
                    prepared_path_obj = pathlib.Path(prepared_path)
                    if prepared_path_obj.exists():
                        # 读取文件内容用于下载
                        with open(prepared_path_obj, "rb") as f:
                            file_data = f.read()
                        
                        # 显示文件路径和下载按钮
                        st.markdown(f"**输出文件：** `{prepared_path}`")
                        st.download_button(
                            label="下载生成的文件",
                            data=file_data,
                            file_name=prepared_path_obj.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if prepared_path_obj.suffix == ".docx" else "application/msword",
                            key="download_prepared_doc"
                        )
                    else:
                        st.write(f"输出文件：`{prepared_path}` (文件不存在)")


