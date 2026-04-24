# PPT Agent 服务优化计划

## 一、 当前问题分析

根据用户在实际使用过程中的反馈，当前的 Agent 流程体验在以下四个方面存在不足：

1. **SVG 生成体验差（Step 6）**：耗时接近6分钟，但前端只能看到干巴巴的 Trace 日志，无法实时看到大模型生成的 PPT 页面内容，缺乏交互感。
2. **缺少模板智能选择（Step 3）**：当前代码中硬编码了 `ppt169` 作为默认模板，没有利用现有的丰富模板库（`layouts_index.json`），也缺少大模型根据主题智能挑选模板的决策过程。
3. **冗余的人工确认（Step 4）**：大纲生成后会强制挂起并等待用户输入 `yes`。在自动化生成的诉求下，这一步显得多余，阻断了整个自动化流程。
4. **后处理及导出过程黑盒（Step 7）**：最后一步导出 PPTX 耗时极长（约9分钟），由于采用阻塞式执行子进程并等待其结束才返回结果，用户在长达9分钟内得不到任何反馈。

## 二、 优化方案

### 1. 引入大模型智能选择模板 (Step 3)

**修改位置**: `agent_service/agent/orchestrator.py`
**具体修改**:

* 在 Step 3 阶段，读取 `skills/ppt-master/templates/layouts/layouts_index.json`。

* 构造提示词，将用户的输入主题（`source_content`）和可用的模板列表提交给大模型。

* 流式输出（`chunk`）大模型的思考与选择过程，让用户能看到为什么选择某个模板。

* 提取最终决定的模板 key 并应用于当前项目中，若无法提取则默认降级回 `ppt169`。

### 2. 移除 Step 4 的人工确认拦截

**修改位置**: `agent_service/agent/orchestrator.py`
**具体修改**:

* 在 `AgentState.STEP_4_STRATEGIST` 执行完毕、大纲生成并保存到 `spec_lock.md` 后，不再将状态更新为 `WAITING_CONFIRMATION` 并 `return` 挂起。

* 而是直接顺延执行，自动将状态切换到 `STEP_5_IMAGE` 和 `STEP_6_EXECUTOR` 并继续往下走。

* 彻底移除 `elif state == AgentState.WAITING_CONFIRMATION:` 的相关逻辑分支。

### 3. 流式输出并实时渲染 SVG 页面 (Step 6)

**修改位置**:

* `agent_service/agent/orchestrator.py`

* `agent_service/web/app.js`

* `agent_service/web/index.html` (可能需要引入 CSS 样式)
  **具体修改**:

* 在 `orchestrator.py` 中，将 Step 6 期间大模型生成的 `chunk` 像 Step 4 一样直接 `yield` 发送给前端，这样前端聊天框就能实时打出 Markdown 内容及 SVG 代码块。

* 在前端 `app.js` 的 Markdown 渲染管线中，拦截包含 `<svg>...</svg>` 的代码块。通过自定义的 `marked.js` 解析器或在 `innerHTML` 赋值后操作 DOM，将包含完整 `<svg>` 标签的代码块替换或直接转换为可视化的图片渲染框，使用户能在对话流中“眼见为实”地看着 PPT 一页页生成。

### 4. 流式输出后处理与 PPTX 生成日志 (Step 7)

**修改位置**:

* `agent_service/tools/ppt_tools.py`

* `agent_service/agent/orchestrator.py`
  **具体修改**:

* 在 `ppt_tools.py` 中新增一个异步子进程执行函数 `run_script_stream_async(script_name, args, cwd)`，使用 `asyncio.create_subprocess_exec` 替代阻塞的 `subprocess.run`，以 AsyncGenerator 形式逐行产出 `stdout` / `stderr`。

* 在 `orchestrator.py` 的 Step 7 中，不再使用阻塞的 `await self._run_tool`。而是使用 `async for line in ppt_tools.run_script_stream_async(...)`。

* 将捕获到的每一行终端输出，通过 `yield await self._yield_event("trace", line)` 实时推送给前端侧边栏，彻底消除9分钟的“黑盒”等待。

## 三、 假设与约束

* 前端使用 `marked.js`，可以通过 DOM 操作提取 `.language-svg` 的代码块并将其替换为 `div.innerHTML = svgCode` 以实现渲染。由于生成的 SVG 包含复杂的嵌套，直接插入 HTML 是最快捷的渲染方式。

* 第三方库（如 `svglib`，`reportlab`，`cairosvg`）在转换时耗时较长属于性能瓶颈，我们无法降低其绝对耗时，但通过流式日志能够大幅缓解用户的焦虑感。

* 以上所有操作不会破坏已有的 HTTP API 规范（依然走 SSE 传输）。

## 四、 验证步骤

1. 发起一个全新的聊天请求。
2. 观察对话框是否会首先打印出“大模型对于模板选择的思考和结果”（Step 3）。
3. 观察是否无需输入 `yes`，大纲生成后直接自动进入生成 SVG 阶段。
4. 观察对话框中是否能流式打印 SVG 代码，并在一段 SVG 生成完毕后直接在页面上渲染出画面内容（Step 6）。
5. 观察右侧 Trace 面板，在进入打包和 PPTX 生成阶段时，是否能逐行打印出 `finalize_svg` 和 `svg_to_pptx` 脚本的执行日志（Step 7）。

