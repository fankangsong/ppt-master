- [x] Agent Service 目录结构已完整创建，且不影响原 `skills/ppt-master`。
- [x] 大模型客户端支持 `base_url`, `api_key`, `model_name` 的动态配置并能正常通信。
- [x] 现有的 Python CLI 脚本（如 `project_manager.py`, `svg_to_pptx.py`）已成功封装为可被调用的 Tools，能够正常获取执行日志。

- [x] 实现了管理 `session_id` 的 Orchestrator，并成功将 7 步 Pipeline 业务流程状态机串联起来。
- [x] Agent 能够顺利执行 Step 1 (源内容处理)、Step 2 (项目初始化)、Step 3 (模板选择)。
- [x] Step 4（Strategist Phase）生成 `design_spec.md` 后，Agent 能够正确挂起（返回状态），等待用户确认后继续。
- [x] 用户确认后，Agent 能够继续触发 Step 5 (可选生图) 以及 Step 6 (Executor 逐页排版生成)。
- [x] Agent 能够自动调用 Step 7 完成 SVG 清洗及 PPTX 的导出打包。
- [x] `POST /chat` 接口可通过 SSE 返回包含 `reply`, `usage`, `trace` 字段的流式响应。

- [x] 服务启动成功（如 `uvicorn agent_service.api.main:app`），可通过浏览器访问 `http://localhost:<port>`。
- [x] Web UI 支持多轮对话，展示用户消息和 Agent 回复。
- [x] Web UI 支持长文本输入，且能够自动滚动到底部。
- [x] Web UI 中的“可视化调试信息”面板能够正常展开并展示 `prompt`、Tool 调用记录、以及 Token 使用情况。
- [x] `curl` 示例可正常向 `POST /chat` 发起请求并接收流式响应。
- [x] 最终成功生成并可访问 PPTX 文件。

