# Build Agent Service Spec

## Why
目前 `ppt-master` skill 作为 IDE 工具链的一部分，只能通过工具的形式被调用，缺乏独立的上下文管理和外部访问能力。为了支持外部系统集成以及自定义大模型（LLM）配置，需要将其改造为一个“可独立运行的 Agent 服务”，对外提供标准的 HTTP API，并配套一个交互式 Web UI 用于展示生成过程、工具调用细节及最终结果。

## What Changes
- 构建基于 **Python (FastAPI)** 的独立后端服务（与现有脚本技术栈一致，便于无缝集成）。
- 新增 `agent_service/` 目录结构，包含 `agent/`（核心调度与上下文）、`llm/`（大模型接口封装）、`tools/`（现有 skill 脚本的工具化封装）、`api/`（FastAPI 路由）。
- 将原有的 7 步串行 Pipeline 深度集成至 Agent 的工作流中：
  1. **Step 1 源内容处理**：Agent 调用 `source_to_md` 脚本。
  2. **Step 2 项目初始化**：Agent 调用 `project_manager.py`。
  3. **Step 3 模板选择**：Agent 意图匹配并挂载模板资产。
  4. **Step 4 策略规划 (Strategist)**：Agent 扮演策略师，调用 LLM 生成 `design_spec.md` 和 `spec_lock.md`。此节点挂起并等待用户确认 8 项核心决策。
  5. **Step 5 图像生成**：Agent 视情况调用 `image_gen.py`。
  6. **Step 6 执行与排版 (Executor)**：用户确认后，Agent 扮演执行者，读取契约并逐页流式生成 SVG 代码及演讲稿。
  7. **Step 7 后处理与导出**：Agent 自动串联执行拆分、SVG清洗和 PPTX 打包。
- 实现 HTTP API：提供 `POST /chat` 接口，支持多轮对话（通过 `session_id`）、流式输出（SSE / chunked response）、以及返回 `usage` 和 `trace` 等调试信息。
- 开发一个基于原生 HTML + TailwindCSS 的 Web UI（放在 `agent_service/web/` 下），支持聊天交互、Markdown 渲染、以及可视化调试面板（展开查看 prompt、tool 调用记录、token usage）。

## Impact
- Affected specs: 增加了 HTTP 服务和 Agent 调度能力。
- Affected code:
  - 新增 `agent_service/api/main.py`
  - 新增 `agent_service/agent/orchestrator.py`
  - 新增 `agent_service/llm/client.py`
  - 新增 `agent_service/tools/ppt_tools.py`
  - 新增 `agent_service/web/index.html` 及相关前端静态文件
  - `skills/ppt-master/` 现有代码**不修改**，仅作为子进程或模块被 `tools/ppt_tools.py` 调用。

## ADDED Requirements
### Requirement: 独立 Agent 封装与多轮对话
Agent 必须能够根据 `session_id` 管理多轮对话上下文，记录用户的源文件信息、生成进度和配置状态。

#### Scenario: 成功处理带确认流程的对话
- **WHEN** 用户通过 Web UI 发送源文档链接或文本。
- **THEN** Agent 调度前 3 步，并在 Step 4 生成 `design_spec.md` 后，返回给前端等待用户确认；用户回复“确认”后，Agent 自动完成后续 SVG 生成与 PPTX 导出。

### Requirement: 自定义大模型接入
系统必须支持通过环境变量或请求体动态配置大模型参数。

#### Scenario: 使用非默认的 OpenAI 兼容模型
- **WHEN** 用户在配置中设置了自定义的 `endpoint`, `api_key`, `model`。
- **THEN** Agent 在进行文本生成和排版（Step 4 & Step 6）时，通过配置的客户端向指定端点发起请求。

### Requirement: 可视化 Web UI
前端必须提供类似 ChatGPT 的对话体验，并能透出 Agent 内部的思考与工具调用过程。

#### Scenario: 查看调试信息
- **WHEN** 用户在聊天界面点击“调试信息”面板。
- **THEN** UI 展开并展示当前请求的 Prompt、调用的 Python 脚本日志（Tool Traces）以及 Token 消耗量（Usage）。
