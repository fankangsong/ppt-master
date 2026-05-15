# PPT Agent Service

基于 FastAPI 和 OpenAI 的 PPT 自动生成 **Agent Workflow** 服务，通过 SSE (Server-Sent Events) 对外提供流式输出能力。

## ✨ 核心特性

- 🎯 **7步完整流水线**: 源内容解析 → 项目初始化 → 模板匹配 → 策略规划 → 图像生成 → SVG排版 → 后处理导出
- 📡 **SSE 实时流式输出**: 10种事件类型，覆盖进度、产物、错误等全链路信息
- 🎨 **SVG 实时渲染**: 前端即时展示生成的PPT页面预览
- 📦 **产物追踪**: artifact事件实时通知每个生成的文件
- 🔄 **智能重试机制**: LLM调用自动重试 + 指数退避策略
- 🌐 **Web UI**: 类ChatGPT交互界面，支持多会话管理
- 🔧 **可配置**: 支持多种LLM提供商（OpenAI/DeepSeek/Qwen/Zhipu/Ollama）

## 目录结构

```
agent_service/
├── api/
│   └── main.py              # FastAPI应用入口 + SSE接口
├── agent/
│   └── orchestrator.py      # 编排器（状态机+流水线+SSE事件）
├── llm/
│   └── client.py            # LLM客户端（重试+超时+日志）
├── tools/
│   └── ppt_tools.py         # PPT工具封装（脚本调用）
├── web/
│   ├── index.html           # 前端页面
│   └── app.js               # 前端逻辑（SSE消费+UI渲染）
├── .env.example             # 配置模板
└── requirements.txt         # Python依赖
```

## 🚀 快速启动

### 1. 安装依赖

```bash
cd agent_service
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env，填入你的LLM配置
nano .env
```

**必需配置项**：
```env
OPENAI_BASE_URL=https://api.openai.com/v1    # 或其他兼容API
OPENAI_API_KEY=sk-your-key-here               # API密钥
OPENAI_MODEL=gpt-4o                            # 模型名称
```

### 3. 启动服务

```bash
# 开发模式（自动重载）
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2
```

### 4. 访问界面

打开浏览器访问：[http://localhost:8000](http://localhost:8000)

---

## 📡 API 接口说明

### 主接口：POST /chat

触发完整的PPT生成工作流，返回SSE数据流。

**请求格式**：
```json
{
  "session_id": "optional-session-id",
  "message": "请帮我制作一个关于'人工智能发展趋势'的10页PPT"
}
```

**响应格式** (SSE Stream)：
```
Content-Type: text/event-stream

data: {"type":"session_plan","content":"...","steps":[...]}
data: {"type":"step_status","step_id":"step_1_parse","status":"执行"}
data: {"type":"chunk","content":"正在分析...","step_id":"step_1_parse"}
data: {"type":"artifact","artifact_type":"svg_page","path":"/projects/.../P01_slide.svg"}
data: {"type":"progress","percentage":50,"message":"已保存第 5/10 页"}
data: {"type":"session_summary","artifacts":[...]}
```

### 辅助接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/` | Web UI 界面 |

---

## 📊 SSE 事件协议

本服务定义了 **10种事件类型**：

| 事件类型 | 触发时机 | 数据结构 |
|----------|----------|----------|
| `state` | 状态变更 | `{state: string}` |
| `session_plan` | 开始时 | `{steps: [], total_steps}` |
| `step_status` | 步骤进度 | `{step_id, step_no, status}` |
| `trace` | 调试日志 | `{content: string}` |
| **`chunk`** | **LLM流式内容** | `{content, step_id?}` |
| `message` | 结构化消息 | `{content, step_id?}` |
| `usage` | Token用量 | `{content: "~2.5K"}` |
| **`artifact`** | **产物通知** ⭐ | `{type, path, metadata}` |
| **`progress`** | **细粒度进度** ⭐ | `{current, total, percentage}` |
| **`error`** | **错误信息** ⭐ | `{code, message, details}` |

> ⭐ = 本次优化新增的事件类型

---

## 💡 使用示例

### curl 测试

```bash
# 发起PPT生成（观察SSE流）
curl -N http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "做一个关于机器学习的5页PPT"}'
```

### Python 调用示例

```python
import requests
import json

response = requests.post(
    "http://localhost:8000/chat",
    json={
        "session_id": "my-ppt-session",
        "message": "帮我做一个关于区块链技术的PPT"
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        data = json.loads(line.decode("utf-8").replace("data: ", ""))
        event_type = data.get("type")
        
        if event_type == "artifact":
            print(f"📦 文件生成: {data['filename']}")
        elif event_type == "progress":
            print(f"📊 进度: {data['percentage']}% - {data['message']}")
        elif event_type == "error":
            print(f"❌ 错误: {data['message']}")
        elif event_type == "session_summary":
            print(f"✅ 完成! 产物:")
            for artifact in data["artifacts"]:
                print(f"  - {artifact['label']}: {artifact['path']}")
```

### JavaScript / Fetch API

```javascript
const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        session_id: "session-123",
        message: "生成一个产品介绍PPT"
    })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const text = decoder.decode(value);
    const lines = text.split("\n\n").filter(l => l.startsWith("data: "));
    
    for (const line of lines) {
        const data = JSON.parse(line.replace("data: ", ""));
        console.log(`[${data.type}]`, data);
    }
}
```

---

## 🔧 配置选项

### LLM 配置

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `OPENAI_BASE_URL` | API端点 | `https://api.openai.com/v1` |
| `OPENAI_API_KEY` | API密钥 | （必需） |
| `OPENAI_MODEL` | 模型名称 | `gpt-4o` |
| `LLM_TIMEOUT` | 超时时间(秒) | `120` |
| `LLM_MAX_RETRIES` | 最大重试次数 | `2` |

### 服务配置

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `HOST` | 监听地址 | `0.0.0.0` |
| `PORT` | 监听端口 | `8000` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

### 多提供商示例

```env
# DeepSeek
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat

# 通义千问 (Qwen)
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus

# 智谱GLM
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_MODEL=glm-4

# 本地 Ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama3
```

---

## 🎨 UI 功能说明

### 主界面布局

```
┌─────────────────────────────────────────────────────┐
│  [会话列表] │     [聊天区域]          │ [Trace面板] │
│             │                      │              │
│  ● 会话1    │  📋 执行计划卡片       │  [14:30:01]  │
│  会话2      │  □ Step 1: 解析  ✅   │  Step 1...   │
│  + 新建     │  □ Step 2: 初始化✅   │  Step 2...   │
│             │  □ Step 3: 模板  ✅   │  ...         │
│             │  □ Step 6: 排版  🔄   │              │
│             │   ├ 进度条 ████░░ 60% │              │
│             │   ├ SVG实时预览       │              │
│             │  📦 产物列表 (3个)    │              │
│             │   ├ 🎨 P01_slide.svg │              │
│             │   ├ 🎨 P02_slide.svg │              │
│             │   └ 📄 final.pptx    │              │
│             │                      │              │
├─────────────────────────────────────────────────────┤
│  [输入框........................] [▶发送] [⏹停止]    │
│  State: STEP_6_EXECUTOR  ●  Tokens: ~5.2K          │
└─────────────────────────────────────────────────────┘
```

### 核心功能

1. **实时步骤卡片**: 显示7步流程的当前状态和内容
2. **SVG实时渲染**: 生成的PPT页面即时可视化预览
3. **产物追踪面板**: 列出所有已生成的文件（SVG/PPTX/Notes）
4. **进度条**: 细粒度的页面级进度指示
5. **Trace日志**: 右侧终端面板显示详细执行日志
6. **错误提示**: 红色卡片展示错误信息和技术详情
7. **多会话管理**: 左侧栏支持创建/切换/删除会话

---

## 🔄 工作流详解

### 7步Pipeline

```
用户输入
  ↓
[Step 1] 源内容解析 → 接收文本/文件/URL，转换为Markdown
  ↓
[Step 2] 项目初始化 → 创建项目目录结构
  ↓
[Step 3] 模板智能选择 → LLM从模板库中匹配合适风格
  ↓
[Step 4] 策略规划(Strategist) → 生成design_spec.md + spec_lock.md
  ↓
[Step 5] 图像获取(条件) → AI生成或网络搜索配图
  ↓
[Step 6] 执行排版(Executor) ★核心 → LLM逐页生成SVG代码
  ↓
[Step 7] 后处理导出 → 拆分备注→SVG后处理→导出PPTX
  ↓
完成！→ 返回产物列表（SVG文件 + PPTX文件）
```

### 输出产物

```
projects/project_xxx/
├── sources/              # 源文件
├── images/               # 图像资源
│   ├── image_prompts.json
│   └── image_prompts.md
├── svg_output/           # Executor生成的原始SVG (★)
│   ├── P01_cover.svg
│   ├── P02_content.svg
│   └── ... (每页一个)
├── svg_final/            # 后处理后的SVG
├── notes/                # 演讲者备注
│   ├── total.md
│   ├── 01_cover.md
│   └── ...
├── exports/              # 最终产物 (★)
│   └── project_xxx_20260514.pptx
├── design_spec.md        # 设计规格（人类可读）
└── spec_lock.md          # 执行契约（机器可读）
```

---

## ❓ 常见问题

### Q: 如何更换LLM模型？
A: 修改 `.env` 文件中的 `OPENAI_BASE_URL` 和 `OPENAI_MODEL` 即可。支持所有OpenAI兼容的API。

### Q: 生成的PPT在哪里？
A: 保存在 `projects/project_<timestamp>/exports/` 目录下，`.pptx` 格式。

### Q: 支持中文吗？
A: 完全支持！LLM会根据输入语言自动调整输出语言。

### Q: 如何查看详细日志？
A: 
- Web UI右侧的Trace面板实时显示日志
- 设置 `LOG_LEVEL=DEBUG` 可在控制台看到更详细的输出

### Q: 超时怎么办？
A: 
- LLM默认超时120秒，可通过 `LLM_TIMEOUT` 调整
- 自动重试机制会在失败后重试（默认2次）
- 使用更强的模型（如GPT-4o）可减少超时概率

---

## 🛠️ 开发指南

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境
cp .env.example .env
# 编辑 .env

# 启动开发服务器（热重载）
python -m uvicorn api.main:app --reload --port 8000
```

### 代码结构说明

- **orchestrator.py**: 核心编排器，包含状态机、SSE事件生成、7步流水线
- **client.py**: LLM客户端封装，包含重试逻辑和错误处理
- **ppt_tools.py**: ppt-master脚本的Python封装
- **app.js**: 前端逻辑，SSE消费、UI组件、状态管理
- **index.html**: 前端HTML结构，TailwindCSS样式

### 扩展开发

添加新的SSE事件类型：
1. 在 `orchestrator.py` 中添加 `_yield_xxx_event()` 方法
2. 在流水线适当位置调用 `yield await self._yield_xxx_event(...)`
3. 在 `app.js` 的 `handleServerEvent()` 中添加 `case "xxx"` 处理逻辑
4. 创建对应的UI组件函数

---

## 📄 License

MIT License

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**最后更新**: 2026-05-14  
**版本**: v2.0 (Enhanced with artifact tracking, progress bars, and error handling)
