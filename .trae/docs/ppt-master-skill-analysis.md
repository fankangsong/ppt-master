# `ppt-master` Skill 业务流程与技术栈说明文档

本文档基于 `ppt-master` 现有实现（`SKILL.md` 及源码），详细拆解其作为独立 Skill 的功能、执行流程、调用链路、输入输出及技术栈。这将为后续将其改造为“独立 Agent 服务”提供基础。

---

## 1. 核心业务流程 (Business Workflow)

`ppt-master` 是一个 AI 驱动的多格式 SVG 内容生成系统。其核心职责是将任意形式的源文档（PDF/DOCX/URL/Markdown 等）通过多角色协作（Strategist 策略师 -> Executor 执行者），转化为高质量的 SVG 页面，并最终导出为 PPTX。

整个流程被严格划分为 **7 个串行步骤 (Pipeline)**，必须按顺序执行，部分环节强依赖用户的确认（Blocking）。

1. **Step 1: 源内容处理 (Source Content Processing)**
   - 接收用户提供的任意格式资料，提取内容并转换为统一的 Markdown 格式。
2. **Step 2: 项目初始化 (Project Initialization)**
   - 创建标准化的项目目录结构（`sources/`, `images/`, `svg_output/` 等），并将源文件归档。
3. **Step 3: 模板选择 (Template Option)**
   - 根据用户意图（或静默默认）选择合适的版式模板和设计资产，将其引入项目。
4. **Step 4: 策略规划阶段 (Strategist Phase) ⛔ BLOCKING**
   - AI 阅读源文件和模板信息，生成全局的**设计规范 (Design Specification)** 与 **执行契约 (Spec Lock)**。
   - **强制拦截**：向用户展示 8 项核心设计决策（画幅、页数、配色、字体等），等待用户确认。
5. **Step 5: 图像生成阶段 (Image_Generator Phase) [条件触发]**
   - 如果设计规范中包含 AI 配图需求，则提取 Prompt 并批量生成/下载图片。
6. **Step 6: 执行与排版阶段 (Executor Phase)**
   - AI 逐页阅读 `spec_lock.md`，根据规范和内容，依次生成每一页的 **SVG 代码**。
   - AI 为每页生成对应的**演讲备注 (Speaker Notes)**。
7. **Step 7: 后处理与导出 (Post-processing & Export)**
   - 对 SVG 进行格式化处理（图片裁剪、文本压平、Icon 嵌入等）。
   - 将处理后的 SVG 结合演讲备注，打包输出为原生的 PPTX 演示文稿。

---

## 2. 代码执行、调用链路与输入输出

在 Agent 化改造时，这些执行链路将被封装为 LLM 可以调用的 Tools，整个流程的驱动将由“外层大模型（Agent 编排器）”与“内层大模型（Skill 具体环节执行者）”协同完成。以下是每个步骤中 LLM 调用的时机、输入与输出：

### Step 1: 源内容处理
- **执行逻辑**: 工具脚本自动解析，**无 LLM 调用**。
- **调用链路**: `python3 scripts/source_to_md/[pdf|doc|ppt|web]_to_md.py <file/URL>`
- **输入**: 原始文件 (PDF/DOCX等) 或 URL
- **输出**: Markdown 文本

### Step 2: 项目初始化
- **执行逻辑**: 工具脚本自动创建目录，**无 LLM 调用**。
- **调用链路**: 执行 `project_manager.py init` 和 `import-sources`
- **输入**: 项目名、画幅比例、源文件路径
- **输出**: 完整的 `<project_path>` 目录树

### Step 3: 模板选择
- **执行逻辑**: Agent 根据用户意图匹配模板，执行文件拷贝。**外层 Agent (LLM) 决策时机**。
- **调用链路**: Agent 读取 `templates/layouts/layouts_index.json`，并执行 `cp` 命令。
- **输入**: 用户的风格诉求
- **输出**: 项目目录下新增 `templates/`、`images/` 相关设计资产

### Step 4: 策略规划 (Strategist) ⛔ 核心 LLM 调用节点 1
- **LLM 调用时机**: Step 3 完成后，Agent 扮演 Strategist 角色，进行首次重度推理。
- **LLM 输入 (Prompt Context)**: 
  - Role Prompt: `references/strategist.md`
  - 源内容 Markdown (Step 1 产出)
  - 模板参考结构 `templates/design_spec_reference.md`
  - (可选) 图片分析脚本 `analyze_images.py` 的输出结果
- **LLM 输出**: 
  - 生成 `design_spec.md` (人类可读的设计大纲与 8 项确认清单)
  - 生成 `spec_lock.md` (机器可读的配置契约，锁死颜色/字体/页面节奏)
- **阻塞机制**: 输出大纲后，Agent 必须**挂起并返回响应给前端**，等待用户对 8 项决策（画幅、页数、配色等）进行确认或修改。

### Step 5: 图像生成 (Image Generator) [可选]
- **执行逻辑**: 若需要配图，Agent 调用外部脚本生图。脚本内部包含 **生图模型 (LLM/Diffusion) 的调用**。
- **调用链路**: `python3 scripts/image_gen.py "prompt" ...`
- **输入**: `design_spec.md` 中的图像 prompt
- **输出**: 生成的图片文件 (`.png` 等) 和 `image_prompts.md`

### Step 6: 执行与排版 (Executor) ⛔ 核心 LLM 调用节点 2
- **LLM 调用时机**: 用户确认 Step 4 的设计规范，且 Step 5 (若有) 结束后，Agent 扮演 Executor 角色，进行**循环/流式的重度代码生成**。
- **LLM 输入 (Prompt Context)**:
  - Role Prompt: `references/executor-base.md` 及选定的具体风格定义 (`executor-general.md` 等)
  - 全局契约: `spec_lock.md` (硬性规定：每生成一页前必须重新读取该文件，防止长文本幻觉)
  - 当前页面的内容大纲 (`design_spec.md` 对应章节)
- **LLM 输出**:
  - 逐页输出 SVG 代码（需 Agent 框架拦截并写入 `<project_path>/svg_output/Pxx_xxx.svg`）
  - 统一输出演讲逐字稿（需 Agent 框架拦截并写入 `<project_path>/notes/total.md`）

### Step 7: 后处理与 PPTX 导出
- **执行逻辑**: 工具脚本自动处理清洗与格式打包，**无 LLM 调用**。
- **调用链路**: 依次执行 `total_md_split.py` -> `finalize_svg.py` -> `svg_to_pptx.py`
- **输入**: 未处理的 SVG 和汇总的演讲稿
- **输出**: 最终的 `<project_name>.pptx` 演示文稿

---

## 3. 技术栈说明 (Technology Stack)

基于源码和 `requirements.txt` 分析，该项目属于一个 **以 Python 为核心、重度依赖 LLM 文本/代码生成能力** 的 AI 自动化系统。

### 核心语言与环境
- **Python 3.x**：绝大多数脚本使用 Python 编写，是核心执行引擎。
- **Node.js** (可选)：作为抓取特定高防网页的 Fallback (`web_to_md.cjs`)。

### 核心依赖库 (Python Packages)
1. **PPTX 构建与导出**
   - `python-pptx`: 用于构建最终的 PowerPoint 文件结构，注入幻灯片与备注。
   - `cairosvg` / `svglib` / `reportlab`: 用于将 SVG 降级/光栅化为 PNG，以保证所有 Office 版本的兼容性（Office 兼容模式）。

2. **文档解析与转换 (Source to MD)**
   - `PyMuPDF`: 解析 PDF，提取文本、图片、表格。
   - `mammoth`: 解析 DOCX 为 HTML，进而转 Markdown。
   - `markdownify` / `beautifulsoup4`: HTML 转 Markdown 格式。
   - `ebooklib` / `nbconvert` / `pandoc`: 处理 EPUB, IPYNB 及传统 Office/LaTeX 等小众格式。

3. **网络抓取 (Web to MD)**
   - `requests` / `beautifulsoup4`: 基础网页抓取。
   - `curl_cffi`: 模拟浏览器 TLS 指纹，用于突破微信公众号等网站的反爬拦截。

4. **图像处理与 AI 生成**
   - `Pillow` / `numpy`: 处理图片比例修复、水印擦除、图片裁剪拼接等。
   - `google-genai` / `openai`: 接入大模型生图接口（Gemini / DALL-E 或兼容接口）。

### 架构特征与改造启示
当前架构是一个典型的 **CLI 工具集合 + LLM 提示词工作流 (Prompt-chaining)**：
- **Agent 化改造的重点**：当前流程强依赖 IDE 或 Trae 的对话系统（人工触发下一步，IDE 代写文件）。在将其改造为**独立的 HTTP Agent 服务**时，需要一个代码层面的 **编排引擎 (Orchestrator)**（如 LangChain/CrewAI/自定义循环引擎），来自动调度上述 7 个步骤的 CLI 脚本，并自动解析 LLM 返回的文本（如拦截并保存 `.svg` 文本内容到本地，而不是依赖 IDE 的写入能力）。
- **工具调用 (Tool Calling)**：需将 `pdf_to_md.py`、`svg_to_pptx.py` 等 CLI 命令，包装为 LLM 可直接调用的 Functions (Tools)。
- **阻塞机制 (Blocking)**：在 Web UI 和 Agent 的改造中，需实现 Step 4 的“中断-等待”机制：当 Agent 运行到 Step 4 抛出设计规范后，挂起 Session 等待前端提交确认，确认后再恢复执行后续步骤。