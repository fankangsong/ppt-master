# Tasks

- [x] Task 1: 初始化 Agent 服务项目结构
  - [x] SubTask 1.1: 创建 `agent_service/` 目录以及 `api/`, `agent/`, `llm/`, `tools/`, `web/` 子目录。
  - [x] SubTask 1.2: 添加 `agent_service/requirements.txt`（FastAPI, uvicorn, openai, sse-starlette）。
- [x] Task 2: 封装大模型客户端与工具集
  - [x] SubTask 2.1: 在 `llm/client.py` 中实现支持配置 `endpoint`, `api_key`, `model` 的 OpenAI 兼容接口，并支持流式返回。
  - [x] SubTask 2.2: 在 `tools/ppt_tools.py` 中将 `skills/ppt-master/scripts` 下的 CLI 工具封装为 Python 可调用的函数（包含标准输出日志的捕获）。
- [x] Task 3: 构建 Agent 调度器 (Orchestrator) 与 7 步业务流程状态机
  - [x] SubTask 3.1: 在 `agent/orchestrator.py` 中实现 `SessionManager`，管理 `session_id`、对话历史以及当前处于 7 步管线中的哪一步。
  - [x] SubTask 3.2: 实现 **Step 1 - Step 3**（解析文档、初始化项目、模板匹配）的自动化工具链调用逻辑。
  - [x] SubTask 3.3: 实现 **Step 4 (Strategist)**，包含组装 Role Prompt，调用自定义大模型生成 `design_spec.md` 与 `spec_lock.md`，随后触发 **Blocking 挂起**机制，向前端返回待确认信息。
  - [x] SubTask 3.4: 实现 **Step 5 (Image Gen)** 的条件触发逻辑。
  - [x] SubTask 3.5: 实现 **Step 6 (Executor)** 的逐页循环生成，包含循环读取 `spec_lock.md`、分块输出 SVG 代码至本地文件系统、以及输出演讲稿。
  - [x] SubTask 3.6: 实现 **Step 7 (Post-processing)**，串联执行 `total_md_split.py`、`finalize_svg.py` 和 `svg_to_pptx.py` 导出最终 PPTX。
  - [x] SubTask 3.7: 实现基于生成流的回调机制，向 HTTP 接口流式返回大模型的 Token Usage、Agent 的 Tool Trace 等日志。
- [x] Task 4: 实现 FastAPI HTTP 接口
  - [x] SubTask 4.1: 在 `api/main.py` 创建 FastAPI 应用。
  - [x] SubTask 4.2: 实现 `POST /chat` 接口，解析 `session_id` 和 `message`。
  - [x] SubTask 4.3: 实现 SSE (Server-Sent Events) 返回，流式传输 `reply`, `usage`, `trace` 信息。
  - [x] SubTask 4.4: 挂载静态文件目录 `web/`，提供前端访问入口。
- [x] Task 5: 开发 Web UI
  - [x] SubTask 5.1: 创建 `web/index.html`，引入 TailwindCSS，设计聊天界面和配置面板。
  - [x] SubTask 5.2: 创建 `web/app.js`，实现 SSE 请求，解析后端返回的数据块，动态渲染聊天内容与调试面板（Prompt、Tool 调用、Token 使用）。
  - [x] SubTask 5.3: 实现输入框（支持 Enter 发送与长文本）、自动滚动、加载状态。
- [x] Task 6: 集成与测试
  - [x] SubTask 6.1: 配置启动脚本或命令。
  - [x] SubTask 6.2: 提供 `curl` 调用示例并进行端到端测试。

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 2]
- [Task 4] depends on [Task 3]
- [Task 5] depends on [Task 4]
- [Task 6] depends on [Task 4], [Task 5]
