# TenderWord Web (Streamlit) 快速上手

基于 LangGraph/Streamlit 的招标文档处理系统。采用分层架构设计，支持多表单路由和灵活扩展。

## 目录
- [环境准备](#环境准备)
- [启动方式](#启动方式)
- [使用说明](#使用说明界面操作)
- [架构说明](#架构说明)
- [开发指南](#开发指南)
- [常见问题](#常见问题)

## 环境准备
- Python 3.10+（建议 64 位）
- Windows 建议在 PowerShell 中运行
- **Microsoft Word 或 WPS Office**（必需，用于处理 Word 文档）

```powershell
cd D:\PythonProject
python -m venv .venv
.\.venv\Scripts\activate
pip install -r TenderWord\requirements.txt
```

### Word COM 环境检查
如果换电脑后出现 Word COM 相关错误，请先运行诊断工具：

```powershell
python diagnose_word.py
```

详细排查指南请参考：[Word COM 问题排查指南](docs/Word_COM_问题排查指南.md)

## 启动方式
```powershell
streamlit run streamlit_app.py
```

### 自定义IP和端口
如果需要自定义服务地址和端口，可以使用以下参数：

```powershell
# 绑定到所有网络接口，端口8502
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8502

# 绑定到特定IP和端口
streamlit run streamlit_app.py --server.address 192.168.1.100 --server.port 8080
```

启动后浏览器会自动打开（或按照终端提示访问指定地址）。

## 使用说明（界面操作）

### 基本使用流程
1. 输入招标编号，点击"获取信息"按钮获取项目信息
2. 上传参考 Word 文件（模板文件）
3. 上传技术参数文件（支持多文件上传）
4. 选择生成模型（DeepSeek/Qwen/Doubao）
5. 点击"开始生成"，等待完成提示

### URL 参数路由
系统支持通过 URL 参数自动显示对应的表单：

```
http://localhost:8501/?tender_lx=0&purchase_method=5&fund_lx=0
```

**参数说明：**
- `tender_lx`: 招标类型（0=询价, 1=公开招标, 2=邀请招标）
- `purchase_method`: 采购方式（5=询价采购, 1=公开招标, 2=邀请招标）
- `fund_lx`: 资金类型（0=国内, 1=国际）
- `tenderno`: 招标编号（可选，自动填充并获取数据）

**示例：**
```
# 询价采购表单 + 自动获取招标数据
http://localhost:8501/?tender_lx=0&purchase_method=5&fund_lx=0&tenderno=ZBGG-2024-001
```

**注意：** URL 参数会完整保留在地址栏中，包括 tenderno 参数。这样便于分享链接和刷新页面。

**说明：**
- 上传目录固定在 `D:/UploadFiles`，若同名文件存在会自动在文件名后加时间戳
- 生成完成后页面会显示输出文件路径，并提供下载按钮
- 支持多用户并发使用，系统会自动排队处理

## 架构说明

### 目录结构

```
project_root/
├── graphs/                          # Graph 层
│   ├── __init__.py                 # 导出所有 graph
│   ├── base_graph.py               # 基础 Graph 类
│   └── xjcg_tender_graph.py        # 询价采购 Graph
│
├── states/                          # State 层
│   ├── __init__.py                 # 导出所有 state
│   ├── base_state.py               # 基础 State 类
│   └── xjcg_tender_state.py        # 询价采购 State
│
├── nodes/                           # Node 层
│   ├── __init__.py
│   ├── common/                     # 通用节点（可复用）
│   │   ├── __init__.py
│   │   ├── file_operations.py     # 文件操作节点
│   │   └── llm_operations.py      # LLM 调用节点
│   └── xjcg_word_nodes/            # 询价采购专用节点
│       ├── __init__.py
│       ├── prepare_template.py
│       ├── extract_tender_params.py
│       └── ...
│
├── forms/                           # 表单层
│   ├── __init__.py
│   ├── base_form.py                # 基础表单类
│   └── xjcg_tender_form.py         # 询价采购表单
│
├── config/                          # 配置层
│   ├── __init__.py
│   └── form_config.py              # 表单配置和路由
│
├── task/                            # 任务管理
│   ├── __init__.py
│   └── task_queue_manager.py       # 任务队列管理器
│
├── util/                            # 工具模块
│   ├── __init__.py
│   ├── fetch_tender_data.py        # 招标数据获取
│   ├── word_*.py                   # Word 操作工具
│   └── ...
│
├── streamlit_app.py                 # 主应用
├── requirements.txt                 # 依赖列表
└── README.md                        # 本文档
```

### 分层职责

#### Graph 层（graphs/）
- **职责**：定义节点连接关系和执行流程
- **核心类**：`BaseGraph` - 提供通用功能（锁机制、进度追踪、执行方法）
- **具体实现**：`XjcgTenderGraph` - 询价采购文档生成工作流

#### State 层（states/）
- **职责**：定义 graph 执行过程中的状态结构
- **核心类**：`BaseState` - 定义通用字段（task_id、user_session_id）
- **具体实现**：`XjcgTenderGraphState` - 询价采购状态定义

#### Node 层（nodes/）
- **职责**：实现具体的业务逻辑
- **通用节点**：`nodes/common/` - 可在多个 graph 之间复用
- **专用节点**：`nodes/xjcg_word_nodes/` - 询价采购专用

#### 表单层（forms/）
- **职责**：渲染用户输入界面、验证输入、准备初始状态
- **核心类**：`BaseForm` - 定义表单标准接口
- **具体实现**：`XjcgTenderForm` - 询价采购表单

#### 配置层（config/）
- **职责**：管理表单配置和 URL 参数映射
- **核心类**：`FormConfig` - 表单配置数据类
- **路由函数**：`match_form_by_url_params()` - URL 参数匹配

### 核心特性

#### 1. 跨进程文件锁
- 使用 `CrossProcessFileLock` 确保 Word COM 操作的并发安全
- 支持多用户并发访问，自动排队处理
- 防止多个进程同时操作 Word 导致冲突

#### 2. 进度追踪
- 实时追踪每个节点的执行状态
- 支持任务取消功能
- 提供友好的进度显示界面

#### 3. 表单路由系统
- 基于 URL 参数自动显示对应表单
- 支持多表单配置和动态路由
- 便于集成到其他系统

#### 4. 任务队列管理
- 自动管理并发任务
- 公平调度，按提交顺序执行
- 支持任务取消和超时处理

## 开发指南

### 如何添加新的 Graph

1. **创建 State 类**（在 `states/` 目录）

```python
# states/my_new_state.py
from states.base_state import BaseState

class MyNewGraphState(BaseState):
    """新 Graph 的状态定义"""
    # 添加特定字段
    input_file: str
    output_file: str
    result: str
```

2. **创建 Graph 类**（在 `graphs/` 目录）

```python
# graphs/my_new_graph.py
from graphs.base_graph import BaseGraph
from states import MyNewGraphState
from langgraph.graph import StateGraph, START, END

class MyNewGraph(BaseGraph):
    """新 Graph 的实现"""
    
    def get_state_class(self):
        return MyNewGraphState
    
    def build_graph(self):
        builder = StateGraph(MyNewGraphState)
        
        # 添加节点（使用 self.wrap_node 包装以获得进度追踪）
        builder.add_node("node1", self.wrap_node("node1", node1_func))
        builder.add_node("node2", self.wrap_node("node2", node2_func))
        
        # 定义边（执行流程）
        builder.add_edge(START, "node1")
        builder.add_edge("node1", "node2")
        builder.add_edge("node2", END)
        
        return builder
```

3. **导出 Graph**（在 `graphs/__init__.py`）

```python
from .my_new_graph import MyNewGraph

__all__ = [
    # ... 其他导出
    "MyNewGraph",
]
```

### 如何添加新的表单

1. **创建表单类**（在 `forms/` 目录）

```python
# forms/my_new_form.py
from forms.base_form import BaseForm
import streamlit as st

class MyNewForm(BaseForm):
    """新表单的实现"""
    
    def render_input_fields(self):
        """渲染输入字段"""
        name = st.text_input("名称")
        file = st.file_uploader("上传文件", type=["txt"])
        return {"name": name, "file": file}
    
    def validate_inputs(self, form_data):
        """验证输入"""
        if not form_data["name"]:
            return False, "请输入名称"
        if not form_data["file"]:
            return False, "请上传文件"
        return True, ""
    
    def prepare_initial_state(self, form_data):
        """准备初始状态"""
        # 保存文件、准备数据等
        return {
            "task_id": str(uuid.uuid4()),
            "name": form_data["name"],
            # ... 其他字段
        }
```

2. **注册表单配置**（在 `config/form_config.py`）

```python
FORM_REGISTRY["my_new_form"] = FormConfig(
    form_id="my_new_form",
    tab_name="我的新表单",
    graph_name="my_new_graph",
    state_name="MyNewGraphState",
    url_params={"tender_lx": 2, "purchase_method": 2, "fund_lx": 0},
    description="新表单的描述"
)
```

3. **注册表单类**（在 `forms/__init__.py`）

```python
from .my_new_form import MyNewForm

def create_form(form_config):
    form_map = {
        "xjcg_tender": XjcgTenderForm,
        "my_new_form": MyNewForm,  # 新增
    }
    # ...
```

### 如何添加通用节点

1. **创建节点函数**（在 `nodes/common/` 目录）

```python
# nodes/common/my_operations.py

def my_operation_node(state, config=None):
    """
    通用操作节点
    
    Args:
        state: 当前状态
        config: 配置参数
    
    Returns:
        更新后的状态
    """
    # 实现节点逻辑
    result = do_something(state["input"])
    
    return {
        **state,
        "output": result
    }
```

2. **导出节点**（在 `nodes/common/__init__.py`）

```python
from .my_operations import my_operation_node

__all__ = ["my_operation_node"]
```

3. **在 Graph 中使用**

```python
from nodes.common import my_operation_node

class MyGraph(BaseGraph):
    def build_graph(self):
        builder = StateGraph(MyState)
        builder.add_node("my_op", self.wrap_node("my_op", my_operation_node))
        # ...
```

## 常见问题

### Word COM 相关问题
- **错误：无法创建 Word 应用程序实例**
  - 运行 `python diagnose_word.py` 检查环境
  - 确保已安装 Microsoft Word 或 WPS Office
  - 检查 pywin32 是否正确安装：`pip install pywin32`
  - 详细排查指南：[Word COM 问题排查指南](docs/Word_COM_问题排查指南.md)

### Streamlit 相关问题
- **警告：missing ScriptRunContext**
  - 不要直接运行 `python streamlit_app.py`
  - 请使用 `streamlit run streamlit_app.py` 启动

### 并发相关问题
- **多用户同时使用时出现冲突**
  - 系统已实现自动排队机制，无需担心
  - 如果出现长时间等待，检查是否有任务卡住
  - 可以在界面上取消卡住的任务

### 表单路由问题
- **URL 参数不生效**
  - 检查参数名称是否正确（tender_lx、purchase_method、fund_lx）
  - 检查参数值是否为有效整数
  - 确保参数组合在 `FORM_REGISTRY` 中已注册

### 开发相关问题
- **如何调试 Graph 执行**
  - 查看 `logs/task_execution.log` 日志文件
  - 在节点函数中添加 print 语句
  - 使用 Streamlit 界面的实时日志显示

- **如何测试新添加的 Graph**
  - 创建测试脚本，直接调用 Graph 的 invoke 方法
  - 使用 Streamlit 界面进行端到端测试
  - 检查生成的文件是否符合预期

## 技术栈

- **前端框架**：Streamlit
- **工作流引擎**：LangGraph
- **LLM 集成**：支持 DeepSeek、Qwen、Doubao
- **文档处理**：pywin32（Word COM）
- **并发控制**：跨进程文件锁 + 任务队列

## 许可证

[添加许可证信息]

## 联系方式

[添加联系方式]
