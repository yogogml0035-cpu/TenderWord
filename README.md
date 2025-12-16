# TenderWord Web (Streamlit) 快速上手

基于 LangGraph/Streamlit 的招标文档处理 MVP。页面已简化：仅需上传 2 个文件，其余参数使用 `graph.py` 中的固定默认值。

## 环境准备
- Python 3.10+（建议 64 位）
- Windows 建议在 PowerShell 中运行

```powershell
cd D:\PythonProject
python -m venv .venv
.\.venv\Scripts\activate
pip install -r TenderWord\requirements.txt
```

## 启动方式
```powershell
streamlit run streamlit_app.py
```

启动后浏览器会自动打开（或按照终端提示访问本地地址）。

## 使用说明（界面操作）
1) 上传参考 Word 文件 → 对应 `origin_tender_path`  
2) 上传技术参数文件 → 对应 `tender_param_path`  
3) 点击“开始生成”，等待完成提示。

说明：
- 其他参数（项目名称/编号、插入位置文本等）均已固定为 `graph.py` 的默认值，无需填写。
- 上传目录固定在 `D:/PythonProject/TenderFile`，若同名文件存在会自动在文件名后加时间戳。
- 生成完成后页面会显示输出文件路径，并提供下载按钮。

## 常见问题
- 直接运行 `python streamlit_app.py` 会出现 `missing ScriptRunContext` 警告，请使用 `streamlit run TenderWord\streamlit_app.py` 启动。
- 如需更改默认参数，请修改 `TenderWord/graph.py` 中的 `initial_state` 示例或对应节点逻辑后再启动。

