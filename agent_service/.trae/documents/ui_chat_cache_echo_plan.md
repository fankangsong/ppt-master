# 本地缓存与回显逻辑改进计划

## 1. 目标与背景
前端 UI 已经实现了按步骤展示独立的流转卡片，并且步骤内容已经能够精准渲染在对应的卡片内部。但是，**本地缓存和页面重载时的回显逻辑（`switchSession`）** 尚未适配这一新架构。
目前，AI 回复结束后仅仅将全局的无状态文本 `currentAssistantMarkdown` 存入了 `localStorage`，导致刷新页面或切换会话时，原本丰富的“计划卡片”、“步骤流转卡片（及其内部内容）”和“总结卡片”全部丢失，退化为一个旧版的全局气泡框。

我们需要改进数据持久化与回显逻辑，使其与当前的卡片展示逻辑完全一致。

## 2. 现状分析
- **缓存写入**：在 `app.js` 的 `chatForm.addEventListener("submit")` 的 `finally` 块中，当前仅执行了 `session.messages.push({ role: "ai", content: currentAssistantMarkdown })`。
- **状态丢失**：`planCardElement`、`stepCardMap`、`stepContentMap` 等结构化数据均未保存。
- **缓存读取**：在 `switchSession` 函数中，对 `msg.role === "ai"` 的数据，统一调用了 `appendAssistantMessageHistory(msg.content)`，该方法只能渲染旧版全局 Markdown。

## 3. 具体修改方案

### 3.1 引入结构化的 AI 响应对象
在 `app.js` 中新增一个全局变量 `currentAiResponse`，用于在生成期间收集结构化数据：
```javascript
let currentAiResponse = null;
// 数据结构预期为：
// {
//   role: "ai",
//   plan: null,
//   steps: [], // 数组，每个元素包含 { step_id, step_no, step_title, status, status_icon_key, content }
//   summary: null,
//   fallbackContent: "" // 用于保存无 step_id 的全局消息
// }
```
在每次 `chatForm` 提交时，初始化该对象。

### 3.2 在事件处理时实时缓冲结构化状态
在 `handleServerEvent` 方法中：
- `session_plan`: 将 `data` 赋值给 `currentAiResponse.plan`。
- `step_status`: 在 `currentAiResponse.steps` 中查找对应的 `step_id`，不存在则新增，存在则更新 `status`、`step_title` 等字段。
- `chunk` / `message`: 
  - 如果携带 `step_id`，将内容累加到 `currentAiResponse.steps` 对应步骤的 `content` 字段。
  - 如果无 `step_id`，将内容累加到 `currentAiResponse.fallbackContent`。
- `session_summary`: 将 `data` 赋值给 `currentAiResponse.summary`。

### 3.3 修改持久化写入逻辑
在流结束后的 `finally` 块中：
- 检查 `currentAiResponse` 是否有结构化数据，如果有，则将完整的 `currentAiResponse` 对象 push 到 `session.messages` 中。
- 考虑到容错，若没有任何结构化字段，仍可兼容保存普通 `content`。

### 3.4 重构会话回显渲染逻辑
在 `app.js` 中新增一个 `restoreAssistantMessage(msg)` 函数：
1. 先调用 `resetFlowCards()` 清除卡片引用指针，确保新一轮的消息能创建独立的 DOM 节点。
2. 如果存在 `msg.fallbackContent`（或兼容旧的 `msg.content`），则创建全局气泡框并渲染。
3. 如果存在 `msg.plan`，调用 `upsertPlanCard(msg.plan)` 恢复计划卡片。
4. 如果存在 `msg.steps`，遍历数组：
   - 调用 `upsertStepCard(step)` 恢复步骤卡片的最终状态。
   - 如果该步骤有 `content`，则手动恢复 `stepContentMap` 并修改该步骤对应的 DOM，移除 `hidden` 样式并渲染 Markdown 内容。
5. 如果存在 `msg.summary`，调用 `upsertSummaryCard(msg.summary)` 恢复总结卡片。

在 `switchSession` 方法中，对于 `ai` 类型的消息：
- 判断如果存在 `plan`、`steps` 或 `summary` 字段，则走 `restoreAssistantMessage(msg)`。
- 否则走旧版的 `appendAssistantMessageHistory(msg.content)` 以保证旧会话兼容。

## 4. 验证步骤
1. 在页面中进行一次新的对话生成，等待整个卡片流转和内容生成结束。
2. 点击浏览器的刷新按钮（或 F5）。
3. 检查页面加载后，刚才的执行计划、步骤卡片（包括卡片内部的 SVG 图或 Markdown）、完成总结是否完美还原。
4. 检查左侧点击历史旧会话（只有普通文本的会话），确认能正常渲染且不报错。