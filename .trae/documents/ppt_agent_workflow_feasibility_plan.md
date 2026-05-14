# PPT Agent Workflow 应用可行性方案

## 一、项目背景与现状分析

### 1.1 项目概述

基于现有的 `ppt-master` Skill，构建一个独立的 Agent Workflow 服务，通过 SSE (Server-Sent Events) 接口对外提供 PPT 生成能力。

**核心价值**：
- 将原本需要人工交互的 PPT 生成流程自动化
- 通过流式输出提供实时进度反馈
- 支持外部系统集成（HTTP API）

### 1.2 现有资产评估

#### ✅ 已具备的能力

| 模块 | 状态 | 说明 |
|------|------|------|
| **PPT Master Skill** | ✅ 完整 | 7步流水线（解析→初始化→模板→策略→图像→排版→导出） |
| **Agent Service 基础框架** | ✅ 可用 | FastAPI + SSE + Session管理 + 状态机 |
| **LLM Client** | ✅ 可用 | OpenAI兼容协议，支持流式/非流式 |
| **PPT Tools 封装** | ✅ 可用 | 脚本调用、项目初始化、文档转换等 |
| **Web UI** | ✅ 可用 | 聊天界面、SSE事件处理、SVG渲染、会话管理 |

#### ⚠️ 需要优化的环节

根据 [optimize_ppt_agent_workflow.md](../optimize_ppt_agent_workflow.md) 的分析：

1. **Step 3 模板选择** - 当前已实现LLM智能选择 ✅
2. **Step 4 人工确认** - 已移除拦截，自动流转 ✅  
3. **Step 6 SVG生成** - 已实现流式输出，但SVG渲染需优化 ⚠️
4. **Step 7 后处理** - 已实现异步流式日志 ✅

### 1.3 技术栈现状

```
Backend:  Python 3.x + FastAPI + Uvicorn
Frontend:  Vanilla HTML/CSS/JS + TailwindCSS + Marked.js
LLM:      OpenAI Python SDK (AsyncOpenAI)
SSE:      FastAPI StreamingResponse
Storage:  Local File System (projects/)
```

---

## 二、整体架构设计

### 2.1 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Web UI     │  │  Third-Party │  │   CLI Tool   │          │
│  │  (Browser)   │  │    System    │  │              │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼──────────────────┘
          │  HTTP/SSE       │  HTTP/SSE       │  HTTP/SSE
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway Layer                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  FastAPI Application                     │    │
│  │  POST /chat          → SSE Stream                        │    │
│  │  GET  /sessions      → Session List                      │    │
│  │  GET  /sessions/:id  → Session Detail                    │    │
│  │  DELETE /sessions/:id → Clear Session                    │    │
│  │  GET  /health        → Health Check                      │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Agent Orchestrator                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │ Session    │  │  State     │  │  Pipeline  │                │
│  │ Manager    │  │  Machine   │  │  Executor  │                │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘                │
│        └────────────────┼────────────────┘                     │
│                         │                                      │
│  ┌──────────────────────▼──────────────────────┐               │
│  │            SSE Event Generator               │               │
│  │  - session_plan / step_status / trace        │               │
│  │  - chunk / message / usage / summary         │               │
│  └─────────────────────────────────────────────┘               │
└────────────────────────────────┬────────────────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   LLM Client    │    │   PPT Tools     │    │  Template Mgr   │
│  (OpenAI SDK)   │    │  (Script Wrap)  │    │  (Layouts)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PPT Master Skill Scripts                     │
│  project_manager.py | image_gen.py | svg_to_pptx.py | ...       │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件职责

| 组件 | 职责 | 关键文件 |
|------|------|----------|
| **API Gateway** | HTTP接口、CORS、静态文件服务 | `api/main.py` |
| **Session Manager** | 会话生命周期、上下文存储 | `agent/orchestrator.py` |
| **State Machine** | 流程状态管理（7步+异常态） | `agent/orchestrator.py` |
| **Pipeline Executor** | 7步流水线编排与执行 | `agent/orchestrator.py` |
| **SSE Event Generator** | 结构化事件生成与推送 | `agent/orchestrator.py` |
| **LLM Client** | 大模型调用（流式/非流式） | `llm/client.py` |
| **PPT Tools** | Skill脚本封装 | `tools/ppt_tools.py` |
| **Web UI** | 用户界面、SSE消费、渲染 | `web/app.js`, `web/index.html` |

---

## 三、业务流程设计

### 3.1 完整用户旅程

```
用户输入PPT内容
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: 源内容解析                                           │
│ - 接收用户输入（文本/文件路径/URL）                            │
│ - 如果是文件/URL，调用转换脚本转为 Markdown                   │
│ - 输出：source_content (Markdown文本)                        │
│ - SSE事件：step_status(开始→执行→完成) + trace                │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: 项目初始化                                           │
│ - 调用 project_manager.py init 创建项目目录                  │
│ - 生成项目结构：sources/, images/, svg_output/, notes/       │
│ - 输出：project_path, project_name                           │
│ - SSE事件：step_status + trace                               │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: 模板智能选择                                         │
│ - 读取 layouts_index.json 获取可用模板列表                    │
│ - 构造Prompt提交LLM，根据主题智能匹配模板                     │
│ - 流式输出LLM思考过程                                        │
│ - 提取 [TEMPLATE:key] 标记确定最终模板                       │
│ - 输出：template_key                                         │
│ - SSE事件：step_status + chunk(思考过程) + trace             │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: 策略规划 (Strategist Phase)                          │
│ - 加载 strategist.md 角色定义                                │
│ - LLM生成 design_spec.md (设计叙事)                         │
│ - LLM生成 spec_lock.md (执行契约)                           │
│ - 包含：八项确认（画幅/页数/受众/风格/色彩/图标/字体/图像）   │
│ - 流式输出生成过程                                          │
│ - 输出：design_spec.md, spec_lock.md                        │
│ - SSE事件：step_status + chunk(大纲内容) + trace             │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 5: 图像获取 (Conditional)                               │
│ - 解析 spec_lock.md 中的图像资源列表                         │
│ - 按 Acquire Via 分发：ai / web / user / placeholder        │
│ - AI图像：调用 image_gen.py --manifest 批量生成              │
│ - Web图像：调用 image_search.py 搜索下载                     │
│ - 输出：image_prompts.json, image_sources.json              │
│ - SSE事件：step_status + trace(每张图片进度)                 │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 6: 执行排版 (Executor Phase) ★核心步骤                  │
│ - 加载 executor-base.md + shared-standards.md               │
│ - 按风格加载 executor-general.md / consultant.md 等          │
│ - 逐页读取 spec_lock.md 获取页面参数                         │
│ - LLM逐页生成SVG代码（顺序生成，禁止批量）                   │
│ - 流式输出每个SVG代码块                                      │
│ - 前端实时渲染SVG预览                                       │
│ - 运行 svg_quality_checker.py 质量检查                      │
│ - 生成 speaker notes → notes/total.md                       │
│ - 输出：svg_output/P01.svg ~ P0N.svg, notes/total.md        │
│ - SSE事件：step_status + chunk(SVG代码) + trace + SVG预览   │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 7: 后处理 & 导出                                        │
│ 7.1 total_md_split.py - 拆分演讲者备注                       │
│ 7.2 finalize_svg.py - SVG后处理（图标嵌入/图像裁剪/文本展平）│
│ 7.3 svg_to_pptx.py - 导出PPTX（支持动画配置）               │
│ - 异步流式执行，实时推送stdout/stderr                        │
│ - 输出：exports/<project>_<timestamp>.pptx                  │
│ - SSE事件：step_status + trace(脚本日志逐行) + artifacts     │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ Complete                                                     │
│ - 发送 session_summary 事件                                  │
│ - 包含产物列表：项目目录、PPTX路径、SVG文件数等              │
│ - 状态机转入 DONE                                            │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 状态机定义

```python
class AgentState(Enum):
    INIT = "INIT"                          # 初始状态
    STEP_1_PARSE = "STEP_1_PARSE"          # 源内容解析中
    STEP_2_PROJECT = "STEP_2_PROJECT"      # 项目初始化中
    STEP_3_TEMPLATE = "STEP_3_TEMPLATE"    # 模板选择中
    STEP_4_STRATEGIST = "STEP_4_STRATEGIST"# 策略规划中
    STEP_5_IMAGE = "STEP_5_IMAGE"          # 图像生成中
    STEP_6_EXECUTOR = "STEP_6_EXECUTOR"    # SVG排版中
    STEP_7_POSTPROCESS = "STEP_7_POSTPROCESS" # 后处理导出中
    DONE = "DONE"                          # 完成
    ERROR = "ERROR"                        # 异常
```

**状态流转规则**：
- INIT → STEP_1_PARSE (收到用户消息)
- STEP_N → STEP_N+1 (顺序推进，不可跳跃)
- ANY → ERROR (异常发生)
- STEP_7_POSTPROCESS → DONE (成功完成)
- DONE → STEP_1_PARSE (新请求，重置会话)

---

## 四、SSE 事件协议设计

### 4.1 事件类型总览

| 事件类型 | 用途 | 触发时机 | 数据结构 |
|----------|------|----------|----------|
| `state` | 状态变更通知 | 状态切换时 | `{state: string}` |
| `session_plan` | 执行计划 | 开始时一次性 | `{steps: [], total_steps: number}` |
| `step_status` | 步骤进度更新 | 每个步骤开始/执行/完成 | `{step_id, step_no, step_title, status}` |
| `trace` | 调试日志 | 任意时刻 | `{content: string}` |
| `chunk` | 流式内容片段 | LLM生成时 | `{content: string, step_id?: string}` |
| `message` | 结构化消息 | 重要节点通知 | `{content: string, step_id?: string}` |
| `usage` | Token用量 | LLM调用完成后 | `{content: string}` |
| `session_summary` | 完成总结 | 全部完成时 | `{summary: string, artifacts: []}` |
| `error` | 错误信息 | 异常发生时 | `{code: number, message: string}` |
| `artifact` | 产物通知 | 文件生成时 | `{type: string, path: string, metadata?: {}}` |

### 4.2 核心事件数据格式

#### session_plan 事件
```json
{
  "type": "session_plan",
  "content": "本轮将执行 7 个步骤。",
  "session_id": "abc123",
  "plan_title": "整体执行计划",
  "total_steps": 7,
  "steps": [
    {"step_no": 1, "step_id": "step_1_parse", "step_title": "源内容解析"},
    {"step_no": 2, "step_id": "step_2_project", "step_title": "项目初始化"},
    {"step_no": 3, "step_id": "step_3_template", "step_title": "模板匹配"},
    {"step_no": 4, "step_id": "step_4_strategist", "step_title": "策略规划"},
    {"step_no": 5, "step_id": "step_5_image", "step_title": "图像生成"},
    {"step_no": 6, "step_id": "step_6_executor", "step_title": "执行排版"},
    {"step_no": 7, "step_id": "step_7_postprocess", "step_title": "后处理导出"}
  ]
}
```

#### step_status 事件
```json
{
  "type": "step_status",
  "content": "第 6 步 执行排版: 执行",
  "session_id": "abc123",
  "step_id": "step_6_executor",
  "step_no": 6,
  "step_title": "执行排版",
  "status": "执行",
  "status_icon_key": "executing"
}
```

**status 可选值**：
- `开始` (start) 🟢
- `思考` (thinking) 🤔
- `计划` (planning) 🗺️
- `执行` (executing) ⚙️
- `完成` (completed) ✅

#### chunk 事件（流式内容）
```json
{
  "type": "chunk",
  "content": "## Slide 1\n\n```svg\n<svg viewBox=\"0 0 1920 1080\">...",
  "step_id": "step_6_executor"
}
```

#### session_summary 事件
```json
{
  "type": "session_summary",
  "content": "已完成 7 个步骤，项目目录：/projects/demo_123。",
  "session_id": "abc123",
  "title": "完成总结",
  "summary": "已完成 7 个步骤，项目目录：/projects/demo_123。已生成 PPTX 文件。",
  "artifacts": [
    {"label": "项目目录", "path": "/projects/demo_123"},
    {"label": "PPTX 文件", "path": "/projects/demo_123/exports/demo_123_20260514.pptx"},
    {"label": "SVG 页面", "path": "/projects/demo_123/svg_output/ (10 files)"},
    {"label": "设计规格", "path": "/projects/demo_123/design_spec.md"},
    {"label": "执行契约", "path": "/projects/demo_123/spec_lock.md"}
  ]
}
```

#### artifact 事件（新增 - 产物实时通知）
```json
{
  "type": "artifact",
  "session_id": "abc123",
  "artifact_type": "svg_page",
  "path": "/projects/demo_123/svg_output/P01_slide.svg",
  "metadata": {
    "page_number": 1,
    "page_title": "封面页",
    "file_size": 45230
  }
}
```

### 4.3 SSE 时序图示例

```
Client                              Server
  │                                   │
  │──── POST /chat {message} ────────►│
  │                                   │
  │◄── data: {"type":"state",...} ───┤  INIT
  │◄── data: {"type":"session_plan"} ─┤  计划卡片
  │                                   │
  │◄── data: {"type":"step_status",   │  Step 1 开始
  │           "status":"开始"} ───────┤
  │◄── data: {"type":"step_status",   │  Step 1 执行
  │           "status":"执行"} ───────┤
  │◄── data: {"type":"trace",         │  日志
  │           "content":"..."} ───────┤
  │◄── data: {"type":"step_status",   │  Step 1 完成
  │           "status":"完成"} ───────┤
  │                                   │
  │◄── ... Step 2-5 类似 ... ────────┤
  │                                   │
  │◄── data: {"type":"step_status",   │  Step 6 开始
  │           "status":"执行"} ───────┤
  │◄── data: {"type":"chunk",         │  SVG 流式输出
  │           "content":"<svg..."} ──┤  (多个chunk)
  │◄── data: {"type":"chunk",         │
  │           "content":"...</svg>"} ─┤
  │◄── data: {"type":"artifact",      │  SVG文件生成完毕
  │           "type":"svg_page"} ────┤
  │◄── data: {"type":"step_status",   │  Step 6 完成
  │           "status":"完成"} ───────┤
  │                                   │
  │◄── data: {"type":"trace",         │  Step 7 脚本日志
  │           "content":"Running..."}─┤  (多行流式)
  │◄── data: {"type":"step_status",   │  Step 7 完成
  │           "status":"完成"} ───────┤
  │                                   │
  │◄── data: {"type":"session_        │  总结
  │           summary",...} ──────────┤
  │◄── data: {"type":"state",         │  DONE
  │           "content":"DONE"} ──────┤
  │                                   │
  │═════════ Stream End ══════════════│
```

---

## 五、核心模块详细设计

### 5.1 API 接口规范

#### 主接口：POST /chat

**请求**：
```http
POST /chat HTTP/1.1
Content-Type: application/json

{
  "session_id": "string (optional, 首次可省略)",
  "message": "string (required, PPT内容描述或主题)",
  "options": {
    "template_path": "string (optional, 显式指定模板路径)",
    "format": "string (optional, 默认 ppt169)",
    "auto_confirm": "boolean (optional, 是否跳过确认, default true)"
  }
}
```

**响应**：SSE Stream (`text/event-stream`)

**响应头**：
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

#### 辅助接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/sessions` | 列出所有会话 |
| GET | `/sessions/{id}` | 获取会话详情 |
| DELETE | `/sessions/{id}` | 清除会话数据 |
| GET | `/download/{session_id}/{filename}` | 下载生成的文件 |

### 5.2 Orchestrator 核心逻辑伪代码

```python
class Orchestrator:
    async def process_message(self, session_id: str, message: str) -> AsyncGenerator[str, None]:
        """
        主入口：处理用户消息，返回SSE事件流
        """
        session = self.session_manager.get_session(session_id)
        
        # 0. 状态检查与初始化
        if state in [INIT, DONE, ERROR]:
            yield state_event(INIT)
            yield session_plan_event()  # 发送执行计划
            
            # Step 1: 源内容解析
            async for event in self._execute_step1(session, message):
                yield event
                
            # Step 2: 项目初始化
            async for event in self._execute_step2(session):
                yield event
                
            # Step 3: 模板选择
            async for event in self._execute_step3(session):
                yield event
                
            # Step 4: 策略规划
            async for event in self._execute_step4(session):
                yield event
                
            # Step 5: 图像获取（条件触发）
            if self._need_image_acquisition(session):
                async for event in self._execute_step5(session):
                    yield event
                    
            # Step 6: SVG执行排版
            async for event in self._execute_step6(session):
                yield event
                
            # Step 7: 后处理导出
            async for event in self._execute_step7(session):
                yield event
                
            # 完成
            yield session_summary_event(session)
            yield state_event(DONE)
            
        else:
            yield message_event("当前状态不允许处理新请求")
    
    async def _execute_step6(self, session) -> AsyncGenerator[str, None]:
        """Step 6: Executor Phase - 最复杂的步骤"""
        yield step_status_event("step_6_executor", 6, "执行排版", "开始")
        yield step_status_event("step_6_executor", 6, "执行排版", "思考")
        
        # 读取spec_lock获取页面列表
        spec = self._read_spec_lock(session["project_path"])
        pages = spec.get("pages", [])
        
        yield step_status_event("step_6_executor", 6, "执行排版", "执行")
        
        # 逐页生成SVG（关键：顺序生成）
        for idx, page in enumerate(pages, 1):
            yield trace_event(f"Generating page {idx}/{len(pages)}: {page['title']}")
            
            # 重新读取spec_lock（抵抗上下文压缩漂移）
            spec = self._re_read_spec_lock(session)
            
            # 构造该页的Prompt
            prompt = self._build_page_prompt(spec, page, idx)
            
            # 流式调用LLM
            full_svg = ""
            async for chunk in self.llm_client.chat_completion_stream([prompt]):
                full_svg += chunk
                yield chunk_event(chunk, step_id="step_6_executor")
                
                # 定期推送进度
                if len(full_svg) % 1000 == 0:
                    yield trace_event(f"Page {idx}: {len(full_svg)} chars generated...")
            
            # 保存SVG文件
            svg_path = self._save_svg(session, idx, full_svg)
            
            # 推送artifact事件
            yield artifact_event("svg_page", svg_path, {
                "page_number": idx,
                "page_title": page.get("title", f"Page {idx}")
            })
        
        # 质量检查
        yield trace_event("Running quality checker...")
        qc_result = await self._run_quality_check(session)
        if qc_result.errors:
            yield trace_event(f"Quality check found {len(qc_result.errors)} errors, fixing...")
            # 修复逻辑...
        
        # 生成演讲者备注
        yield trace_event("Generating speaker notes...")
        await self._generate_notes(session)
        
        yield step_status_event("step_6_executor", 6, "执行排版", "完成")
```

### 5.3 关键技术点

#### A. 流式输出的三种模式

| 场景 | 实现方式 | 示例 |
|------|----------|------|
| **LLM生成** | `async for chunk in llm.stream()` | Step 3/4/6的思考过程和内容 |
| **子进程日志** | `async for line in run_script_stream_async()` | Step 7的脚本输出 |
| **自定义进度** | `yield event()` | 步骤状态变更、artifact通知 |

#### B. 并发控制

```python
# 使用Semaphore限制同Session并发
class SessionManager:
    def __init__(self):
        self.locks: Dict[str, asyncio.Lock] = {}
    
    async def acquire(self, session_id: str):
        if session_id not in self.locks:
            self.locks[session_id] = asyncio.Lock()
        await self.locks[session_id].acquire()
    
    def release(self, session_id: str):
        if session_id in self.locks:
            self.locks[session_id].release()
```

#### C. 错误恢复策略

| 错误类型 | 处理方式 | SSE事件 |
|----------|----------|---------|
| LLM超时 | 重试1次，降级到备用模型 | `error` + `trace` |
| 脚本失败 | 标记Needs-Manual，继续下一步 | `error` + `trace` |
| SVG质量不通过 | 自动修复，超过3次则跳过 | `trace` |
| 磁盘空间不足 | 停止流程，提示用户清理 | `error` + `state(ERROR)` |
| 用户中断 | AbortController终止流 | `trace` + `state(DONE)` |

---

## 六、前端交互设计

### 6.1 UI布局

```
┌────────────────────────────────────────────────────────────────┐
│  PPT Agent Service                              [−] [□] [×]   │
├──────────┬─────────────────────────────────────┬───────────────┤
│          │                                     │               │
│  会话列表 │         聊天区域                    │  Trace面板    │
│  ─────── │  ┌─────────────────────────────┐   │  ───────────  │
│  + 新建  │  │ U: 请帮我做一个AI趋势PPT     │   │  [14:30:01]  │
│          │  └─────────────────────────────┘   │  Step 1: Parse│
│  ● 会话1 │  ┌─────────────────────────────┐   │  [14:30:02]  │
│  会话2   │  │ 📋 整体执行计划 (Plan Card)  │   │  Project init │
│  会话3   │  │   1. 源内容解析              │   │  [14:30:05]  │
│          │  │   2. 项目初始化              │   │  Step 3: ... │
│          │  │   ...                        │   │  [14:30:10]  │
│          │  └─────────────────────────────┘   │  Template: ...│
│          │  ┌─────────────────────────────┐   │               │
│          │  │ □ Step 1: 源内容解析 ✅     │   │               │
│          │  │ □ Step 2: 项目初始化 ✅     │   │               │
│          │  │ □ Step 3: 模板匹配 ✅       │   │               │
│          │  │ □ Step 4: 策略规划 🔄       │   │               │
│          │  │   └─ 正在生成大纲...         │   │               │
│          │  └─────────────────────────────┘   │               │
│          │                                     │               │
│          │  ┌─────────────────────────────┐   │               │
│          │  │ 💻 SVG Preview (if any)     │   │               │
│          │  │  ┌─────────────────────┐    │   │               │
│          │  │  │   <svg rendered>    │    │   │               │
│          │  │  └─────────────────────┘    │   │               │
│          │  └─────────────────────────────┘   │               │
│          │                                     │               │
├──────────┴─────────────────────────────────────┴───────────────┤
│  [📎] [输入框.............................] [▶发送] [⏹停止]  │
│  State: STEP_4_STRATEGIST  ●  Tokens: ~2.5K                    │
└────────────────────────────────────────────────────────────────┘
```

### 6.2 交互要点

1. **实时性**：SSE事件到达后立即更新DOM，无需轮询
2. **SVG渲染**：识别 ````svg` 代码块，直接innerHTML渲染为可视化预览
3. **步骤卡片**：使用状态机单向推进规则，避免状态回退闪烁
4. **中断机制**：点击停止按钮调用 `abortController.abort()` 终止fetch
5. **会话持久化**：localStorage存储消息历史和Trace日志，刷新页面可恢复
6. **错误展示**：Error事件以红色Toast形式呈现，同时写入Trace面板

---

## 七、数据存储设计

### 7.1 目录结构

```
agent_service/
├── projects/                    # 动态生成的项目
│   └── project_{session_id}_{timestamp}/
│       ├── sources/             # 源文件
│       ├── images/              # 图像资源
│       │   ├── image_prompts.json
│       │   └── image_prompts.md
│       ├── templates/           # 模板文件（如果使用）
│       ├── svg_output/          # Executor生成的原始SVG
│       │   ├── P01_cover.svg
│       │   ├── P02_content.svg
│       │   └── ...
│       ├── svg_final/           # 后处理后的SVG
│       ├── notes/               # 演讲者备注
│       │   ├── total.md
│       │   ├── 01_cover.md
│       │   └── ...
│       ├── exports/             # 最终产物
│       │   └── demo_20260514.pptx
│       ├── design_spec.md       # 设计规格（人类可读）
│       └── spec_lock.md         # 执行契约（机器可读）
│
├── .env                         # 环境变量配置
├── requirements.txt
│
├── api/
│   └── main.py                  # FastAPI应用入口
├── agent/
│   └── orchestrator.py          # 编排器（核心）
├── llm/
│   └── client.py                # LLM客户端
├── tools/
│   └── ppt_tools.py             # PPT工具封装
└── web/
    ├── index.html               # 前端页面
    └── app.js                   # 前端逻辑
```

### 7.2 Session 内存模型

```python
{
    "session_id": "abc123",
    "state": "STEP_6_EXECUTOR",
    "history": [
        {"role": "user", "content": "做一个AI趋势PPT"},
        {"role": "ai", "plan": {...}, "steps": [...], "summary": None}
    ],
    "context": {
        "project_name": "project_abc123_1740000000",
        "project_path": "/workspace/projects/project_abc123_1740000000",
        "topic": "AI趋势",
        "source_content": "# AI Trends 2026\n\n...",
        "template": "google_style",
        "created_at": "2026-05-14T10:00:00Z"
    },
    "created_at": 1740000000.0,
    "updated_at": 1740000360.0
}
```

---

## 八、配置与环境

### 8.1 环境变量 (.env)

```bash
# LLM Configuration
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4o

# Alternative: Use a compatible provider (e.g., DeepSeek, Qwen, etc.)
# OPENAI_BASE_URL=https://api.deepseek.com/v1
# OPENAI_MODEL=deepseek-chat

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Image Generation (optional)
IMAGE_PROVIDER=dalle
IMAGE_API_KEY=...

# Logging
LOG_LEVEL=INFO
```

### 8.2 依赖清单

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
openai==1.50.0
python-dotenv==1.0.0
sse-starlette==2.1.0
```

**Skill脚本依赖**（由 `skills/ppt-master/scripts/requirements.txt` 管理）：
```
cairosvg, pillow, python-pptx, beautifulsoup4, lxml, ...
```

---

## 九、实施路径

### Phase 1: 基础验证 (Week 1)

**目标**：验证现有系统能够跑通完整流程

- [ ] 配置 `.env`，连接真实LLM服务
- [ ] 启动 `agent_service`，访问 Web UI
- [ ] 测试简单主题（如"自我介绍"PPT），观察完整7步流程
- [ ] 收集每个步骤的耗时、SSE事件完整性、错误情况
- [ ] **产出**：测试报告 + 问题清单

### Phase 2: 流式体验优化 (Week 2)

**目标**：提升Step 6和Step 7的可观测性

- [ ] **Step 6优化**：
  - [ ] 在chunk事件中携带完整的SVG代码块（而非碎片）
  - [ ] 前端实现增量SVG渲染（每完成一个 ```svg 块立即渲染）
  - [ ] 添加 `artifact` 事件通知单个文件生成完成
  - [ ] 实现页面计数器："正在生成第 3/10 页..."
  
- [ ] **Step 7优化**：
  - [ ] 验证 `run_script_stream_async()` 的跨平台兼容性
  - [ ] 解析脚本输出，提取关键里程碑（如"Slide 1 exported"）
  - [ ] 添加进度百分比估算（基于历史平均耗时）

- [ ] **产出**：优化的orchestrator + 前端渲染逻辑

### Phase 3: 生产化增强 (Week 3)

**目标**：提升稳定性、性能、可扩展性

- [ ] **可靠性**：
  - [ ] 实现重试机制（LLM调用、脚本执行）
  - [ ] 添加超时控制（单步最大耗时限制）
  - [ ] 实现断点续传（从任意步骤恢复）
  
- [ ] **性能**：
  - [ ] 引入任务队列（Celery/RQ）支持高并发
  - [ ] 缓存模板索引、角色定义等静态数据
  - [ ] 支持多模型路由（简单任务用快速模型，复杂任务用强模型）
  
- [ ] **可扩展性**：
  - [ ] 抽象Tool接口，支持动态注册新的PPT工具
  - [ ] 支持多Skill编排（未来可扩展到文档、视频等）
  - [ ] 添加RESTful API查询任务状态（除SSE外提供轮询接口）

- [ ] **产出**：生产级代码 + 部署文档 + API文档

### Phase 4: 监控与运维 (Week 4)

**目标**：建立可观测性体系

- [ ] **日志**：
  - [ ] 结构化JSON日志（request_id, session_id, duration）
  - [ ] 敏感信息脱敏（api_key, 用户内容hash）
  
- [ ] **监控**：
  - [ ] Prometheus指标暴露（请求数、成功率、P99延迟、Token消耗）
  - [ ] Grafana仪表盘（实时活跃任务数、各步骤耗时分布）
  
- [ ] **告警**：
  - [ ] 单步骤超时告警（>10min）
  - [ ] 错误率突增告警（>5%）
  - [ ] 磁盘空间不足告警（<10GB）

- [ ] **产出**：监控大盘 + 告警规则 + 运维手册

---

## 十、风险评估与应对

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| **LLM生成质量不稳定** | 高 | 高 | ① 多模型对比测试选最优 ② Prompt工程迭代 ③ 人工审核环节（可选） |
| **长耗时导致连接超时** | 中 | 高 | ① Nginx proxy_timeout调大 ② 心跳保活机制 ③ 任务状态持久化，支持重连 |
| **SVG兼容性问题** | 中 | 中 | ① 严格遵循shared-standards.md ② 质量检查门禁 ③ fallback模板 |
| **并发资源竞争** | 低 | 高 | ① Session级锁 ② 项目目录隔离 ③ 资源池限流 |
| **成本失控（Token消耗）** | 中 | 中 | ① 单任务Token上限 ② 分层模型策略 ③ 用量监控告警 |
| **前端内存溢出（大量SVG）** | 低 | 中 | ① 虚拟滚动 ② SVG懒加载 ③ 历史消息折叠 |

---

## 十一、可行性结论

### ✅ 技术可行性：**完全可行**

**理由**：

1. **现有基础扎实** - agent_service已实现80%功能，核心架构合理
2. **Skill成熟度高** - ppt-master经过大量实战验证，脚本稳定可靠
3. **SSE协议清晰** - 事件类型完备，前后端联调无障碍
4. **技术栈统一** - Python全栈，维护成本低

### ✅ 业务可行性：**满足需求**

**覆盖度**：

| 用户需求 | 支持程度 | 说明 |
|----------|----------|------|
| 输入PPT内容 | ✅ 完全支持 | 文本/文件/URL均可 |
| 按Skill流程生成 | ✅ 完全支持 | 7步流水线完整实现 |
| 流式输出进度 | ✅ 完全支持 | step_status + trace事件 |
| 流式输出产物 | ✅ 完全支持 | chunk(SVG) + artifact(文件) |
| 对外提供服务 | ✅ 完全支持 | HTTP API + SSE标准协议 |

### 📋 建议优先级

**P0 (必须做)**：
1. 端到端流程跑通验证
2. Step 6 SVG流式渲染优化
3. Step 7 脚本日志流式输出

**P1 (应该做)**：
4. 错误恢复与重试机制
5. Token用量监控与成本控制
6. API文档与Postman集合

**P2 (可以做)**：
7. 断点续传支持
8. 多模型路由
9. 分布式任务队列

---

## 附录A：快速启动指南

```bash
# 1. 进入agent_service目录
cd agent_service

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的LLM配置

# 4. 启动服务
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 5. 打开浏览器
# http://localhost:8000
```

## 附录B：curl 测试示例

```bash
# 发起PPT生成请求（SSE流）
curl -N http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-001",
    "message": "请帮我制作一个关于'人工智能发展趋势'的10页PPT，风格要现代科技感"
  }'

# 查看会话列表
curl http://localhost:8000/sessions

# 健康检查
curl http://localhost:8000/health
```

---

**文档版本**: v1.0
**创建日期**: 2026-05-14
**作者**: AI Assistant
**适用范围**: PPT Agent Workflow 应用设计与实施
