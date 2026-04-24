# Tasks
- [x] Task 1: 定义 UI 对话卡片的数据契约与状态枚举
  - [x] SubTask 1.1: 明确整体执行计划卡片、步骤卡片、完成总结卡片的字段结构。
  - [x] SubTask 1.2: 统一步骤状态枚举（开始/思考/计划/执行/完成）与图标映射键。
  - [x] SubTask 1.3: 约定后端事件类型与前端渲染分支，保证与现有文本流兼容。

- [x] Task 2: 扩展后端流式事件输出
  - [x] SubTask 2.1: 在 Orchestrator 中补充“会话开始计划事件”与“会话完成总结事件”。
  - [x] SubTask 2.2: 在步骤执行节点输出结构化步骤状态事件，包含步骤序号、标题与状态。
  - [x] SubTask 2.3: 在 API SSE 层透传新事件字段并保持旧字段可用。

- [x] Task 3: 重构前端对话渲染为卡片化流程视图
  - [x] SubTask 3.1: 在 `app.js` 中新增计划卡片渲染逻辑与去重更新策略。
  - [x] SubTask 3.2: 为每个步骤创建独立卡片组件，展示序号、标题、状态文本与图标。
  - [x] SubTask 3.3: 在任务完成时渲染总结卡片，并与常规回复区分视觉层级。
  - [x] SubTask 3.4: 在 `index.html` 与样式层补充卡片区域与状态样式。

- [x] Task 4: 联调验证与回归检查
  - [x] SubTask 4.1: 使用一轮完整会话验证卡片顺序、状态流转与完成总结展示。
  - [x] SubTask 4.2: 验证普通聊天文本、调试信息面板等现有能力未回归。
  - [x] SubTask 4.3: 补充必要的开发说明或注释，确保后续维护可读性。

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 1], [Task 2]
- [Task 4] depends on [Task 2], [Task 3]
