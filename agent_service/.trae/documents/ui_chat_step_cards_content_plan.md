# UI 对话步骤卡片内容流转优化计划

## 1. 目标与背景
当前实现中，`/chat` 接口虽然已经支持推送独立的步骤卡片（包含状态和图标），但 AI 实际生成的具体内容（如大纲 Markdown、SVG 代码等）仍然是通过 `chunk` / `message` 事件流式输出到了底部的一个全局气泡框中。

**用户的真实诉求**是：
1. 交互流程应为顺序推进的卡片流。
2. 步骤产生的内容（`content`）应当直接包裹并渲染在对应的**步骤卡片内部**。
3. 当上一个卡片完成其状态流转和内容加载后，再出现下一个卡片，以此类推。

## 2. 现状分析
- **后端 (`orchestrator.py`)**: 
  - `process_message` 方法在循环推进时，分别调用了 `_yield_step_event`（生成步骤卡片状态）和 `_yield_event("chunk", ...)`（生成流式文本）。
  - `chunk` 事件当前没有携带 `step_id`，前端无法将其与特定的卡片关联。
- **前端 (`app.js`)**:
  - `handleServerEvent` 处理 `chunk` 和 `message` 时，统一将文本追加到全局变量 `currentAssistantMarkdown`，并渲染在 `currentAssistantMessageDiv` 中。
  - `upsertStepCard` 生成的卡片 DOM 结构中，只有标题和状态标签，没有预留用于展示详情内容的容器。

## 3. 具体修改方案

### 3.1 后端修改 (`agent_service/agent/orchestrator.py`)
- **传递上下文关联**：在 `process_message` 执行不同步骤时，维护一个 `current_step_id` 变量。
- **扩展事件载荷**：在调用大模型流式接口并向前端 `yield "chunk"` 或 `yield "message"` 事件时，在 `extra_fields` 中带上 `step_id=current_step_id`。
  - 示例：`yield await self._yield_event("chunk", chunk, step_id="step_4_strategist")`。

### 3.2 前端修改 (`agent_service/web/app.js`)
- **扩展步骤卡片 UI**：修改 `upsertStepCard` 函数的 DOM 模板，在卡片内部（状态标签下方）新增一个隐藏的内容容器（如 `<div class="step-content-wrapper hidden"><div class="markdown-body" id="step-content-{stepId}"></div></div>`）。
- **按步骤缓冲内容**：新增一个 `Map`（例如 `stepContentMap`），用于按 `step_id` 独立记录每个步骤的 Markdown 累加文本。
- **精准路由渲染**：
  - 修改 `handleServerEvent` 中的 `chunk` / `message` 逻辑。
  - 检查传入的 `data.step_id`。如果存在，则将文本追加到对应步骤的缓冲中，移除该步骤内容容器的 `hidden` 样式，并调用 `renderMarkdownWithSVG` 仅更新该卡片内部的 DOM。
  - 如果不存在 `step_id`（例如全局通知），则降级回退到现有的全局气泡框中。
- **卡片顺序展示**：由于后端是严格按顺序 `yield` 的，只要前端收到对应的 `step_status` 和带有 `step_id` 的 `chunk` 时再渲染对应卡片，即可自然实现“第一个卡片完成后，出现第二个卡片”的视觉效果。

## 4. 验证步骤
1. 启动 `agent_service` 后端服务。
2. 在前端发起一个 PPT 生成请求。
3. 观察 UI 变化：
   - 确认不会再出现一个大杂烩的 AI 回复气泡框。
   - 确认“策略规划”步骤卡片出现后，生成的大纲 Markdown 实时打字机渲染在该卡片内部。
   - 确认“执行排版”步骤卡片出现后，生成的 SVG 预览图渲染在该卡片内部。
   - 确认每个卡片的状态依然能正常从“开始 -> 思考/计划/执行 -> 完成”流转。