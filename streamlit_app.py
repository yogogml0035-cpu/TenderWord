from __future__ import annotations

import asyncio
import io
import pathlib
import queue
import sys
import threading
import time
import traceback
import uuid

import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from graph import build_graph
from task.task_queue_manager import get_task_queue, TaskStatus, NODE_DISPLAY_NAMES, NodeName
from nodes.xjcg_word_nodes.fetch_tender_data import fetch_tender_data

GRAPH = build_graph()
TASK_QUEUE = get_task_queue()

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


class ThreadSafeProgressTracker:
    """线程安全的进度追踪器，将进度更新写入队列供主线程消费并更新 UI。"""

    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue

    def update(self, progress) -> None:
        """更新进度信息"""
        self.log_queue.put(("progress", progress))


st.set_page_config(
    page_title="招标文件生成MVP", 
    layout="wide",
    initial_sidebar_state="expanded"
)
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

# 初始化 session_state
if "is_generating" not in st.session_state:
    st.session_state.is_generating = False
if "generation_params" not in st.session_state:
    st.session_state.generation_params = {}
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# 初始化 session_state 中的历史记录
if "history" not in st.session_state:
    st.session_state.history = []

# 初始化用户会话ID
if "user_session_id" not in st.session_state:
    st.session_state.user_session_id = str(uuid.uuid4())[:8]

# 初始化招标数据（初始为空，只有点击获取后才显示）
if "tender_data" not in st.session_state:
    st.session_state.tender_data = None

# 初始化取消请求标志
if "cancel_requested" not in st.session_state:
    st.session_state.cancel_requested = False

# 检查是否需要禁用下载按钮
if st.session_state.get("should_disable_downloads", False):
    # 注入JavaScript来禁用下载按钮
    st.components.v1.html("""
        <script>
            (function() {
                function disableDownloadButtons() {
                    try {
                        const parentDoc = window.parent.document;
                        const sidebar = parentDoc.querySelector('[data-testid="stSidebar"]');
                        
                        if (sidebar) {
                            // 查找所有下载按钮（通过按钮文本或key属性）
                            const allButtons = sidebar.querySelectorAll('button');
                            allButtons.forEach(btn => {
                                const buttonText = btn.textContent || '';
                                const buttonLabel = btn.getAttribute('aria-label') || '';
                                // 检查是否是下载按钮
                                if (buttonText.includes('下载') || 
                                    buttonText.includes('download') ||
                                    buttonLabel.includes('下载') ||
                                    buttonLabel.includes('download')) {
                                    // 禁用按钮
                                    btn.disabled = true;
                                    btn.style.opacity = '0.5';
                                    btn.style.cursor = 'not-allowed';
                                    // 添加一个标记，方便后续恢复
                                    btn.setAttribute('data-was-disabled', 'true');
                                }
                            });
                            return true;
                        }
                    } catch (e) {
                        console.log('Disable download buttons error:', e);
                    }
                    return false;
                }
                
                // 禁用下载按钮
                disableDownloadButtons();
                // 延迟再次尝试，确保DOM已加载
                setTimeout(disableDownloadButtons, 100);
                setTimeout(disableDownloadButtons, 300);
            })();
        </script>
    """, height=0)
    # 清除标志，避免重复执行
    st.session_state.should_disable_downloads = False

# 检查是否需要恢复下载按钮（生成完成后）
if st.session_state.get("should_enable_downloads", False):
    # 注入JavaScript来恢复下载按钮
    st.components.v1.html("""
        <script>
            (function() {
                function enableDownloadButtons() {
                    try {
                        const parentDoc = window.parent.document;
                        const sidebar = parentDoc.querySelector('[data-testid="stSidebar"]');
                        
                        if (sidebar) {
                            // 查找所有被禁用的下载按钮并恢复
                            const allButtons = sidebar.querySelectorAll('button');
                            allButtons.forEach(btn => {
                                // 检查是否是我们之前禁用的按钮
                                if (btn.getAttribute('data-was-disabled') === 'true') {
                                    // 恢复按钮
                                    btn.disabled = false;
                                    btn.style.opacity = '1';
                                    btn.style.cursor = 'pointer';
                                    btn.removeAttribute('data-was-disabled');
                                }
                            });
                            return true;
                        }
                    } catch (e) {
                        console.log('Enable download buttons error:', e);
                    }
                    return false;
                }
                
                // 恢复下载按钮
                enableDownloadButtons();
                // 延迟再次尝试，确保DOM已加载
                setTimeout(enableDownloadButtons, 100);
                setTimeout(enableDownloadButtons, 300);
                setTimeout(enableDownloadButtons, 500);
            })();
        </script>
    """, height=0)
    # 清除标志
    st.session_state.should_enable_downloads = False

# 单页表单
tab, = st.tabs(["生成询价采购文件"])

with tab:
    st.markdown(
        "1. 输入完整的招标编号（包含招标编号前缀），点击\"获取项目信息\"获取项目信息\n"
        "2. 上传待处理的 Word 模板文件\n"
        "3. 上传包含原始技术参数的 Word 文件\n"
        "4. 点击\"开始生成\"后等待完成提示，再到对应路径查看 Word 结果或直接下载\n\n"
    )
    
    # 招标编号输入和获取按钮
    col1, col2 = st.columns([10, 1])
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
        fetch_button = st.button("获取项目信息", key="fetch_tender_data", use_container_width=True)
    
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
        st.markdown("**本次文件生成替换的内容：**")
        st.markdown(f"- AI生成的内容插入采购参数位置：在\"第三章  采购需求\"之后，\"第四章  响应文件有关格式\"之前")
        st.markdown(f"- 项目名称替换为：{tender_data['project_name']}")
        st.markdown(f"- 项目编号替换为：{tender_data['project_number']}")
        
        # 格式化显示项目内容
        project_content = tender_data['project_content'].strip()
        st.markdown("- 项目内容替换为：")
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
        st.markdown("- 保证金规则替换为：")
        if bzj_rule:
            # 如果有换行符，按行显示；否则直接显示
            if '\n' in bzj_rule:
                bzj_rule_lines = bzj_rule.split('\n')
                for line in bzj_rule_lines:
                    if line.strip():
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {line.strip()}", unsafe_allow_html=True)
            else:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {bzj_rule}", unsafe_allow_html=True)
        
        st.markdown(f"- 采购人名称替换为：{tender_data['buyer_name']}")
        st.markdown(f"- 项目主办人/协办人替换为：{tender_data['project_zbr_xbr']}")
        st.markdown(f"- 主办人/协办人电话替换为：{tender_data['zbr_xbr_tel']}")
        st.markdown(f"- 主办人拼音替换为：{tender_data['zbr_pinyin']}")

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
            ["千问 (Qwen)", "深度求索（DeepSeek）", "豆包 (Doubao)"],
            index=0,
            key="llm_model_select"
        )
        
        submitted = st.form_submit_button("开始生成", disabled=st.session_state.is_generating, use_container_width=True)

    # 在表单外显示取消按钮（只在生成过程中显示）
    if st.session_state.is_generating:
        task_id_for_cancel = st.session_state.get("current_task_id")
        if st.button("❌ 取消生成", key="cancel_task_btn", type="secondary", use_container_width=True):
            # 执行取消操作
            if task_id_for_cancel and TASK_QUEUE.cancel_task(task_id_for_cancel):
                st.session_state.cancel_requested = True
                st.session_state.is_generating = False
                st.session_state.current_task_id = None
                st.session_state.should_enable_downloads = True  # 恢复下载按钮
                st.session_state.last_result = {
                    "success": False,
                    "error": "任务已被用户取消",
                    "cancelled": True
                }
                st.rerun()
            else:
                st.warning("无法取消任务（可能已完成或已取消）")

    # 1. 处理点击事件：验证并准备环境，触发重运行
    if submitted and not st.session_state.is_generating:
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
            
            # 存储生成参数到 session_state
            st.session_state.generation_params = {
                "origin_tender_path": origin_tender_path,
                "tender_param_path": tender_param_path,
                "model_option": model_option,
                "tender_data": st.session_state.tender_data  # 显式保存一份，防止意外
            }
            
            # 设置状态并重运行
            st.session_state.is_generating = True
            st.session_state.last_result = None  # 清除旧结果
            st.session_state.should_disable_downloads = True  # 标记需要禁用下载按钮
            st.rerun()

    # 2. 处理生成过程：在 is_generating 状态下运行
    if st.session_state.is_generating:
        # 在生成过程中持续禁用侧边栏中的下载按钮，并检测用户离开页面
        task_id_for_js = st.session_state.get("current_task_id", "")
        st.components.v1.html(f"""
            <script>
                (function() {{
                    const taskId = "{task_id_for_js}";
                    
                    function disableDownloadButtons() {{
                        try {{
                            const parentDoc = window.parent.document;
                            const sidebar = parentDoc.querySelector('[data-testid="stSidebar"]');
                            
                            if (sidebar) {{
                                // 查找所有下载按钮
                                const allButtons = sidebar.querySelectorAll('button');
                                allButtons.forEach(btn => {{
                                    const buttonText = btn.textContent || '';
                                    const buttonLabel = btn.getAttribute('aria-label') || '';
                                    // 检查是否是下载按钮
                                    if (buttonText.includes('下载') || 
                                        buttonText.includes('download') ||
                                        buttonLabel.includes('下载') ||
                                        buttonLabel.includes('download')) {{
                                        // 禁用按钮
                                        btn.disabled = true;
                                        btn.style.opacity = '0.5';
                                        btn.style.cursor = 'not-allowed';
                                        // 添加标记
                                        btn.setAttribute('data-was-disabled', 'true');
                                    }}
                                }});
                            }}
                        }} catch (e) {{
                            // 静默处理错误
                        }}
                    }}
                    
                    // 立即执行
                    disableDownloadButtons();
                    // 定期检查并禁用（防止用户手动展开侧边栏后按钮恢复）
                    setInterval(disableDownloadButtons, 1000);
                    
                    // 监听页面关闭/离开事件
                    // 注意：由于浏览器安全限制，beforeunload 中无法发送可靠的请求
                    // 心跳超时机制会处理用户离开的情况
                    window.addEventListener('beforeunload', function(e) {{
                        // 在页面关闭时，心跳会停止，后台线程会自动检测并取消任务
                        console.log('用户正在离开页面，任务将在心跳超时后自动取消');
                    }});
                    
                    // 监听页面可见性变化（用户切换标签页）
                    document.addEventListener('visibilitychange', function() {{
                        if (document.hidden) {{
                            console.log('页面进入后台，心跳可能会受影响');
                        }}
                    }});
                }})();
            </script>
        """, height=0)
        
        # 获取参数
        params = st.session_state.generation_params
        tender_data = params["tender_data"]
        model_option = params["model_option"]
        origin_tender_path = params["origin_tender_path"]
        tender_param_path = params["tender_param_path"]

        # 准备 initial_state
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

        # 检查是否已有正在运行的任务
        task_id = st.session_state.get("current_task_id")

        if not task_id:
            # === 新任务初始化 ===
            # 使用队列在后台线程和主线程之间传递日志
            log_queue: queue.Queue = queue.Queue()
            
            # 用于存储后台线程的执行结果
            result_holder = {"result": None, "error": None, "done": False}

            # 创建任务并加入队列
            task = TASK_QUEUE.create_task(st.session_state.user_session_id)
            task_id = task.task_id
            st.session_state.current_task_id = task_id
            
            # 辅助对象
            log_writer = ThreadSafeLogWriter(log_queue)
            llm_streamer = ThreadSafeLLMStreamer(log_queue)
            progress_tracker = ThreadSafeProgressTracker(log_queue)

            # 映射模型名称到内部标识符
            model_map = {
                "深度求索（DeepSeek）": "deepseek",
                "豆包 (Doubao)": "doubao", 
                "千问 (Qwen)": "qwen"
            }
            selected_model_id = model_map.get(model_option, "deepseek")
            
            # 注册进度回调
            TASK_QUEUE.register_progress_callback(task_id, progress_tracker.update)

            def run_graph_in_thread():
                """在后台线程中执行 graph"""
                try:
                    from graph import invoke_with_timing_async

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
                                        "task_id": task_id,
                                        "llm_stream_callback": llm_streamer.update,
                                        "suppress_llm_stdout": True,
                                        "model_provider": selected_model_id,
                                        "stdout_writer": log_writer,
                                        "stderr_writer": log_writer,
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
            
            # 保存关键状态到 session_state
            st.session_state.log_queue = log_queue
            st.session_state.result_holder = result_holder
            st.session_state.worker_thread = worker_thread
        
        else:
            # === Rerun 恢复状态 ===
            log_queue = st.session_state.get("log_queue")
            result_holder = st.session_state.get("result_holder")
            
            # 简单的错误检查
            if log_queue is None or result_holder is None:
                st.error("生成状态丢失，请刷新页面重试。")
                st.session_state.is_generating = False
                st.session_state.current_task_id = None
                st.stop()

        # === UI 显示逻辑 (通用) ===
        
        # 显示队列状态区域
        queue_status_container = st.container()
        with queue_status_container:
            queue_col1, queue_col2 = st.columns([1, 1])
            with queue_col1:
                queue_status_placeholder = st.empty()
            with queue_col2:
                progress_placeholder = st.empty()
        
        # 初始队列状态显示
        waiting_count = TASK_QUEUE.get_waiting_count(task_id)
        current_running_task = TASK_QUEUE.get_current_running_task()
        
        if waiting_count > 0:
            queue_status_placeholder.warning(f"⏳ 排队中，前面还有 **{waiting_count}** 位用户等待")
            if current_running_task:
                running_progress = current_running_task.progress
                current_node_name = running_progress.get_current_node_display()
                progress_placeholder.info(
                    f"📊 当前执行任务进度：**{running_progress.completed_count}/{running_progress.total_nodes}** "
                    f"- {current_node_name}"
                )
            else:
                progress_placeholder.info("📊 等待执行...")
        else:
            queue_status_placeholder.info("🚀 任务即将开始执行...")
            progress_placeholder.info("📊 文件生成进度：0/7")

        col_log, col_llm = st.columns(2)
        with col_log:
            st.markdown("**运行日志**")
            log_placeholder = st.empty()
        with col_llm:
            st.markdown(f"**AI生成采购需求（当前模型: {model_option}）**")
            llm_placeholder = st.empty()

        # 主线程循环消费队列，实时更新 UI
        current_log = ""
        current_llm = ""
        current_progress_count = 0
        last_heartbeat_time = time.time()
        heartbeat_interval = 3.0  # 每3秒发送一次心跳
        
        while not result_holder["done"] or not log_queue.empty():
            try:
                # 定期发送心跳（在循环开始时检查）
                current_time = time.time()
                if current_time - last_heartbeat_time >= heartbeat_interval:
                    TASK_QUEUE.update_heartbeat(task_id)
                    last_heartbeat_time = current_time
                
                # 检查任务是否被取消（可能是心跳超时或用户主动取消）
                task = TASK_QUEUE.get_task(task_id)
                if task and task.status == TaskStatus.CANCELLED:
                    # 任务已被取消，退出循环
                    result_holder["error"] = (Exception("任务已被取消"), "任务已被用户取消或心跳超时")
                    result_holder["done"] = True
                    break
                
                # 非阻塞获取，超时 0.05 秒
                msg_type, msg_content = log_queue.get(timeout=0.05)
                
                if msg_type == "log":
                    current_log = msg_content
                    log_placeholder.code(current_log, language="text")
                elif msg_type == "llm":
                    current_llm = msg_content
                    llm_placeholder.code(current_llm, language="text")
                elif msg_type == "progress":
                    # 更新进度显示
                    progress = msg_content
                    completed = progress.completed_count
                    total = progress.total_nodes
                    
                    # 更新队列状态
                    queue_status_placeholder.success("🚀 **文件生成执行中...**")
                    
                    # 使用 get_current_node_display() 获取包含状态的节点名称
                    node_status = progress.get_current_node_display()
                    progress_placeholder.info(f"📊 文件生成进度：**{completed}/{total}** - {node_status}")
                    
                    current_progress_count = completed
                elif msg_type == "done":
                    break
            except queue.Empty:
                # 队列为空时，检查并更新队列等待状态
                task = TASK_QUEUE.get_task(task_id)
                
                # 检查任务是否被取消
                if task and task.status == TaskStatus.CANCELLED:
                    result_holder["error"] = (Exception("任务已被取消"), "任务已被用户取消或心跳超时")
                    result_holder["done"] = True
                    break
                
                # 如果任务已完成/失败但 log_queue 还没空，继续 loop
                if task and task.status == TaskStatus.QUEUED:
                    waiting = TASK_QUEUE.get_waiting_count(task_id)
                    current_running = TASK_QUEUE.get_current_running_task()
                    if waiting > 0:
                        queue_status_placeholder.warning(f"⏳ 排队中，前面还有 **{waiting}** 位用户，请耐心等待")
                        if current_running:
                            running_progress = current_running.progress
                            current_node_name = running_progress.get_current_node_display()
                            progress_placeholder.info(
                                f"📊 当前正在执行的用户任务进度：**{running_progress.completed_count}/{running_progress.total_nodes}** "
                                f"- {current_node_name}"
                            )
                        else:
                            progress_placeholder.info("📊 等待执行...")
                    else:
                        queue_status_placeholder.info("🚀 任务即将开始执行...")
                        progress_placeholder.info("📊 文件生成进度：0/7")
                continue

        # 等待线程完全结束 (如果是当前会话持有的线程)
        worker_thread = st.session_state.get("worker_thread")
        if worker_thread and worker_thread.is_alive():
            worker_thread.join(timeout=5.0)
        
        # 取消注册进度回调
        TASK_QUEUE.unregister_progress_callback(task_id)

        # 标记任务完成 (重要：防止任务卡在运行中)
        if result_holder["error"]:
             TASK_QUEUE.complete_task(task_id, error=str(result_holder["error"][1]))
        else:
             TASK_QUEUE.complete_task(task_id, result=result_holder["result"])

        # 处理结果并保存到 last_result
        task = TASK_QUEUE.get_task(task_id)
        is_cancelled = task and task.status == TaskStatus.CANCELLED
        
        if is_cancelled:
            st.session_state.last_result = {
                "success": False,
                "error": "任务已被取消（用户主动取消或心跳超时）",
                "cancelled": True
            }
        elif result_holder["error"]:
            exc, tb = result_holder["error"]
            st.session_state.last_result = {
                "success": False,
                "error": tb
            }
        else:
            result_state, elapsed_time = result_holder["result"]
            # 格式化时间显示
            if elapsed_time >= 60:
                minutes = int(elapsed_time // 60)
                seconds = elapsed_time % 60
                time_str = f"{minutes} 分 {seconds:.2f} 秒"
            else:
                time_str = f"{elapsed_time:.2f} 秒"
            
            prepared_path = result_state.get("prepared_doc_path")
            
            # 更新历史记录
            if prepared_path and pathlib.Path(prepared_path).exists():
                 st.session_state.history.append({
                    "path": prepared_path,
                    "time": time.strftime("%H:%M:%S", time.localtime()),
                    "model": model_option
                })

            st.session_state.last_result = {
                "success": True,
                "time_str": time_str,
                "prepared_path": prepared_path,
                "model_option": model_option,
                "logs": current_log,
                "llm_logs": current_llm
            }

        # 结束生成状态，恢复下载按钮，重运行
        st.session_state.is_generating = False
        st.session_state.should_enable_downloads = True  # 标记需要恢复下载按钮
        st.session_state.current_task_id = None # 清除任务ID
        st.rerun()

    else:
        # 3. 显示结果（只在不在生成过程中时显示）
        # 使用 else 分支确保与 is_generating 互斥
        if st.session_state.last_result:
            result = st.session_state.last_result
            if result["success"]:
                st.success(f"✅ 生成完成！总耗时: {result['time_str']}")
                # 恢复显示日志（可选，如果需要查看）
                with st.expander("查看本次运行日志"):
                    st.code(result.get("logs", ""), language="text")
                with st.expander("查看 AI 生成内容"):
                    st.code(result.get("llm_logs", ""), language="text")
                    
            elif result.get("cancelled"):
                st.warning("⚠️ **任务已取消**")
                st.info(result.get("error", "任务被取消"))
            else:
                error_msg = result.get("error", "")
                # 检测是否是大模型超时错误，显示更友好的提示
                if "大模型响应超时失败" in error_msg or "LLMTimeoutError" in error_msg:
                    st.error("❌ **大模型响应超时**")
                    st.warning("⏱️ 大模型响应超时失败，请尝试其他模型或者重新生成")
                    with st.expander("查看详细错误信息"):
                        st.code(error_msg, language="text")
                else:
                    st.error("❌ **生成失败**")
                    st.code(error_msg, language="text")

    # 确保 History 在生成成功时被更新
    # 可以在 is_generating 块结束前做，或者在这里做检查。
    # 既然 st.rerun() 会导致变量丢失，我们必须依靠 session_state。
    # 我们在 is_generating 块结束前处理 history 更新最安全。
    



# 渲染侧边栏
with st.sidebar:
    # 历史记录
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
                    st.caption(f"🕒 {time_str}:{model_name} ")
                    st.caption(f"📜 {path_obj.name}")
                    
                    st.download_button(
                        label="📥下载生成文件",
                        data=file_bytes,
                        file_name=path_obj.name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if path_obj.suffix == ".docx" else "application/msword",
                        key=f"hist_dl_{len(st.session_state.history) - i}",
                        help=f"文件名: {path_obj.name}",
                        disabled=st.session_state.get("is_generating", False)
                    )
                    st.divider()
                except Exception as e:
                    # 如果读取文件出错（例如文件被占用或删除），仅显示错误信息
                    st.warning(f"无法读取文件: {path_obj.name}")
