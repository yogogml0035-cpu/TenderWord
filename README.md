# TenderWord Web (Streamlit) 快速上手

基于 LangGraph/Streamlit 的招标文档处理。页面已简化：仅需上传 2 个文件，其余参数使用 `graph.py` 中的固定默认值。

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
1) 上传参考 Word 文件 → 对应 `origin_tender_path`  
2) 上传技术参数文件 → 对应 `tender_param_paths`  
3) 点击“开始生成”，等待完成提示。

说明：
- 其他参数（项目名称/编号、插入位置文本等）均已固定为 `graph.py` 的默认值，无需填写。
- 上传目录固定在 `D:/PythonProject/TenderFile`，若同名文件存在会自动在文件名后加时间戳。
- 生成完成后页面会显示输出文件路径，并提供下载按钮。

## 常见问题

### Word COM 相关问题
- **错误：无法创建 Word 应用程序实例**
  - 运行 `python diagnose_word.py` 检查环境
  - 确保已安装 Microsoft Word 或 WPS Office
  - 检查 pywin32 是否正确安装：`pip install pywin32`
  - 详细排查指南：[Word COM 问题排查指南](docs/Word_COM_问题排查指南.md)

### Streamlit 相关问题
- 直接运行 `python streamlit_app.py` 会出现 `missing ScriptRunContext` 警告，请使用 `streamlit run TenderWord\streamlit_app.py` 启动。
- 如需更改默认参数，请修改 `TenderWord/graph.py` 中的 `initial_state` 示例或对应节点逻辑后再启动。

