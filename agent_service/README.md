# PPT Agent Service

这是一个基于 FastAPI 和 OpenAI 的 PPT 自动生成 Agent 服务，提供 HTTP API 接口和可视化的 Web 交互界面。

## 目录结构
- `api/`: FastAPI 接口定义
- `agent/`: Agent 调度器，状态机与工具调用逻辑
- `llm/`: 大语言模型客户端封装
- `tools/`: Python 工具封装（如调用 PPTX 生成脚本）
- `web/`: 前端静态页面（Tailwind CSS, SSE 流式输出）

## 依赖安装

请确保当前环境使用的是 Python 3.10+。

```bash
# 在 agent_service 目录下
pip install -r requirements.txt
```

请确保配置了必要的环境变量，例如：
```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_API_BASE="https://api.openai.com/v1" # 如果需要
export OPENAI_MODEL="gpt-4o" # 或其他模型名称
```

## 启动服务

```bash
# 在 agent_service 目录或上一级目录运行
uvicorn agent_service.api.main:app --host 0.0.0.0 --port 8000 --reload
```
服务启动后，可以通过浏览器访问可视化界面：[http://localhost:8000](http://localhost:8000)

## 端到端测试 (curl 示例)

你可以通过 HTTP API 直接发送 `POST` 请求触发 Agent 工作流。该接口返回的是 `text/event-stream` (SSE) 格式。

```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "session_id": "test_session_123",
           "message": "帮我生成一个关于人工智能未来发展趋势的PPT"
         }'
```

由于这是 SSE 数据流，`curl` 将持续打印后端返回的 Chunk、Trace 和 State 数据。

## 交互流程说明
1. **输入阶段**: 提供内容主题或大纲。
2. **生成大纲**: Agent 会生成 `spec_lock.md`，并通过 Web 界面请求你确认。
3. **确认修改**: 输入“确认”或“继续”，Agent 会进行后续步骤；如需修改，请直接输入修改意见，Agent 会更新大纲再次让你确认。
4. **生成幻灯片**: Agent 依次执行生成 SVG 和导出 PPTX，并在右侧面板实时输出追踪日志 (Trace)。
5. **获取结果**: 任务完成后，文件将保存在 `projects/project_<session_id>` 目录下。