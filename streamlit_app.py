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
from nodes.xjcg_word_nodes.fetch_tender_data import fetch_tender_data

GRAPH = build_graph()

# 定义上传目录
UPLOAD_DIR = pathlib.Path("D:/UploadFiles")
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

# 初始化 session_state 中的历史记录
if "history" not in st.session_state:
    st.session_state.history = []

# 初始化招标数据（初始为空，只有点击获取后才显示）
if "tender_data" not in st.session_state:
    st.session_state.tender_data = None

# 单页表单
tab, = st.tabs(["生成询价采购文件"])

with tab:
    st.markdown(
        "1. 上传待处理的 Word 模板文件\n"
        "2. 上传包含原始技术参数的 Word 文件\n"
        "3. 点击\"开始生成\"后等待完成提示，再到对应路径查看 Word 结果或直接下载\n\n"
    )
    
    # 招标编号输入和获取按钮
    col1, col2 = st.columns([3, 1])
    with col1:
        tender_no_input = st.text_input(
            "招标编号",
            value="",
            placeholder="请输入招标编号",
            key="tender_no_input"
        )
    with col2:
        st.write("")  # 占位，用于对齐按钮
        st.write("")  # 占位，用于对齐按钮
        fetch_button = st.button("获取", key="fetch_tender_data")
    
    # 处理获取按钮点击
    if fetch_button:
        if not tender_no_input or not tender_no_input.strip():
            st.error("请输入招标编号")
        else:
            try:
                with st.spinner("正在获取招标数据..."):
                    tender_data = fetch_tender_data(tender_no_input.strip())
                    # 更新 session_state
                    st.session_state.tender_data = tender_data
                    st.success("数据获取成功！")
            except Exception as e:
                st.error(f"获取数据失败：{str(e)}")
    
    # 显示当前使用的数据（只有获取到数据后才显示）
    if st.session_state.tender_data is not None:
        tender_data = st.session_state.tender_data
        st.markdown("**本次默认替换的内容：**")
        st.markdown(f"- 插入技术参数位置：在\"第三章  采购需求\"之后，\"第四章  响应文件有关格式\"之前")
        st.markdown(f"- 项目名称：{tender_data['project_name']}")
        st.markdown(f"- 项目编号：{tender_data['project_number']}")
        
        # 格式化显示项目内容
        project_content = tender_data['project_content'].strip()
        st.markdown("- 项目内容：")
        if project_content:
            # 如果有换行符，按行显示；否则直接显示
            if '\n' in project_content:
                project_content_lines = project_content.split('\n')
                for line in project_content_lines:
                    if line.strip():
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {line.strip()}", unsafe_allow_html=True)
            else:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {project_content}", unsafe_allow_html=True)
        
        # 格式化显示保证金规则
        bzj_rule = tender_data['bzj_rule'].strip()
        st.markdown("- 保证金规则：")
        if bzj_rule:
            # 如果有换行符，按行显示；否则直接显示
            if '\n' in bzj_rule:
                bzj_rule_lines = bzj_rule.split('\n')
                for line in bzj_rule_lines:
                    if line.strip():
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {line.strip()}", unsafe_allow_html=True)
            else:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {bzj_rule}", unsafe_allow_html=True)
        
        st.markdown(f"- 采购人名称：{tender_data['buyer_name']}")
        st.markdown(f"- 项目主办人/协办人：{tender_data['project_zbr_xbr']}")
        st.markdown(f"- 主办人/协办人电话：{tender_data['zbr_xbr_tel']}")
        st.markdown(f"- 主办人拼音：{tender_data['zbr_pinyin']}")

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
        
        # 添加模型选择
        model_option = st.selectbox(
            "选择生成模型",
            ["深度求索（DeepSeek）", "豆包 (Doubao)", "千问 (Qwen)"],
            index=0,
            key="llm_model_select"
        )
        
        submitted = st.form_submit_button("开始生成")

    if submitted:
        if not uploaded_file:
            st.error("请上传 Word 模板文件")
        elif not origin_text_file:
            st.error("请上传原始技术参数文件")
        elif st.session_state.tender_data is None:
            st.error("请先点击\"获取\"按钮获取招标数据")
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
            
            # 从 session_state 获取招标数据
            tender_data = st.session_state.tender_data
            
            initial_state = {
                # 上传文件路径
                "origin_tender_path": origin_tender_path,
                "tender_param_path": tender_param_path,
                # 固定参数（与 graph.py 中保持一致）
                "insertion_before_text": "第三章  采购需求",
                "insertion_after_text": "第四章  响应文件有关格式",
                "project_name": tender_data["project_name"],
                "project_number": tender_data["project_number"],
                "project_content": tender_data["project_content"],
                "bzj_rule": tender_data["bzj_rule"],
                "buyer_name": tender_data["buyer_name"],
                "project_zbr_xbr": tender_data["project_zbr_xbr"],
                "zbr_xbr_tel": tender_data["zbr_xbr_tel"],
                "zbr_pinyin": tender_data["zbr_pinyin"],
            }

            status_placeholder = st.empty()
            status_placeholder.info("正在生成询价采购文件，请稍候...")

            col_log, col_llm = st.columns(2)
            with col_log:
                st.markdown("**运行日志**")
                log_placeholder = st.empty()
            with col_llm:
                st.markdown("**AI生成采购需求**")
                # 显示当前选中的模型
                st.caption(f"当前模型: {model_option}")
                llm_placeholder = st.empty()

            # 使用队列在后台线程和主线程之间传递日志
            log_queue: queue.Queue = queue.Queue()
            log_writer = ThreadSafeLogWriter(log_queue)
            llm_streamer = ThreadSafeLLMStreamer(log_queue)

            # 用于存储后台线程的执行结果
            result_holder = {"result": None, "error": None, "done": False}
            
            # 映射模型名称到内部标识符
            model_map = {
                "深度求索（DeepSeek）": "deepseek",
                "豆包 (Doubao)": "doubao", 
                "千问 (Qwen)": "qwen"
            }
            selected_model_id = model_map.get(model_option, "deepseek")

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
                                            "model_provider": selected_model_id,  # 传递选择的模型
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

                        # 将生成记录添加到 session_state
                        st.session_state.history.append({
                            "path": str(prepared_path_obj),
                            "time": time.strftime("%H:%M:%S", time.localtime()),
                            "model": model_option
                        })
                        
                        # 显示文件路径和下载按钮
                        st.markdown(f"**输出文件：** `{prepared_path_obj}`")
                        st.download_button(
                            label="下载生成的文件",
                            data=file_data,
                            file_name=prepared_path_obj.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if prepared_path_obj.suffix == ".docx" else "application/msword",
                            key="download_prepared_doc"
                        )
                    else:
                        st.write(f"输出文件：`{prepared_path}` (文件不存在)")


# 渲染侧边栏历史记录
with st.sidebar:
    st.markdown("### 📜 历史生成记录")
    
    if not st.session_state.get("history"):
        st.info("暂无生成记录")
    else:
        # 倒序显示，最新的在最上面
        for i, item in enumerate(reversed(st.session_state.history)):
            path_str = item["path"]
            time_str = item["time"]
            path_obj = pathlib.Path(path_str)
            
            if path_obj.exists():
                try:
                    with open(path_obj, "rb") as f:
                        file_bytes = f.read()
                    
                    # 获取模型名称，兼容旧的历史记录
                    model_name = item.get("model", "DeepSeek")
                    # 显示模型和时间，文件名
                    st.caption(f"🤖 {model_name} | 🕒 {time_str}")
                    st.caption(f"📜 {path_obj.name}")
                    
                    st.download_button(
                        label=f"📥下载生成文件",
                        data=file_bytes,
                        file_name=path_obj.name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if path_obj.suffix == ".docx" else "application/msword",
                        key=f"hist_dl_{len(st.session_state.history) - i}",
                        help=f"文件名: {path_obj.name}"
                    )
                    st.divider()
                except Exception as e:
                    # 如果读取文件出错（例如文件被占用或删除），仅显示错误信息
                    st.warning(f"无法读取文件: {path_obj.name}")
