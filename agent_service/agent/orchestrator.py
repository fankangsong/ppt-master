import os
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List
from enum import Enum

from ..llm.client import LLMClient
from ..tools import ppt_tools

class AgentState(Enum):
    INIT = "INIT"
    STEP_1_PARSE = "STEP_1_PARSE"
    STEP_2_PROJECT = "STEP_2_PROJECT"
    STEP_3_TEMPLATE = "STEP_3_TEMPLATE"
    STEP_4_STRATEGIST = "STEP_4_STRATEGIST"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    STEP_5_IMAGE = "STEP_5_IMAGE"
    STEP_6_EXECUTOR = "STEP_6_EXECUTOR"
    STEP_7_POSTPROCESS = "STEP_7_POSTPROCESS"
    DONE = "DONE"
    ERROR = "ERROR"

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "state": AgentState.INIT,
                "history": [],
                "context": {
                    "project_name": f"project_{session_id[:8]}",
                    "project_path": os.path.abspath(os.path.join("projects", f"project_{session_id[:8]}")),
                    "topic": "",
                    "source_content": ""
                }
            }
        return self.sessions[session_id]

    def update_state(self, session_id: str, state: AgentState):
        if session_id in self.sessions:
            self.sessions[session_id]["state"] = state

    def update_context(self, session_id: str, key: str, value: Any):
        if session_id in self.sessions:
            self.sessions[session_id]["context"][key] = value

class Orchestrator:
    def __init__(self):
        self.session_manager = SessionManager()
        self.llm_client = LLMClient()
        self.step_icon_map = {
            "开始": "start",
            "思考": "thinking",
            "计划": "planning",
            "执行": "executing",
            "完成": "completed",
        }
        self.pipeline_steps = [
            {"step_no": 1, "step_id": "step_1_parse", "step_title": "源内容解析"},
            {"step_no": 2, "step_id": "step_2_project", "step_title": "项目初始化"},
            {"step_no": 3, "step_id": "step_3_template", "step_title": "模板匹配"},
            {"step_no": 4, "step_id": "step_4_strategist", "step_title": "策略规划"},
            {"step_no": 5, "step_id": "step_5_image", "step_title": "图像生成"},
            {"step_no": 6, "step_id": "step_6_executor", "step_title": "执行排版"},
            {"step_no": 7, "step_id": "step_7_postprocess", "step_title": "后处理导出"},
        ]

    async def _yield_event(self, event_type: str, content: str, **extra_fields: Any) -> str:
        """
        核心的 SSE 事件生成函数。
        
        功能：
        - 将事件数据序列化为 JSON 格式并加上 `data: ` 前缀以符合 SSE 规范。
        - 为了兼容旧版 UI，始终保留 `content` 字段。
        - 允许通过 `**extra_fields` 传入针对特定 UI 卡片结构化数据。
        
        参数：
        - event_type: 事件类型（如 'session_plan', 'step_status', 'trace' 等）。
        - content: 文本内容或向后兼容的描述性文本。
        - extra_fields: 附加的数据字段，将合并到 JSON 的顶层。
        """
        # Keep legacy `content` while allowing structured fields for UI cards.
        data = {"type": event_type, "content": content, **extra_fields}
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def _yield_plan_event(self, session_id: str) -> str:
        """
        生成“执行计划”事件（session_plan）。
        用于在开始执行前，向前端 UI 通知完整的流水线步骤。
        """
        return await self._yield_event(
            "session_plan",
            "本轮将执行 7 个步骤。",
            session_id=session_id,
            plan_title="整体执行计划",
            total_steps=len(self.pipeline_steps),
            steps=self.pipeline_steps,
        )

    async def _yield_step_event(
        self,
        session_id: str,
        step_id: str,
        step_no: int,
        step_title: str,
        status: str,
    ) -> str:
        """
        生成“步骤状态更新”事件（step_status）。
        用于通知前端某个特定流水线步骤的状态发生了变化。
        """
        return await self._yield_event(
            "step_status",
            f"第 {step_no} 步 {step_title}: {status}",
            session_id=session_id,
            step_id=step_id,
            step_no=step_no,
            step_title=step_title,
            status=status,
            status_icon_key=self.step_icon_map.get(status, "start"),
        )

    async def _yield_summary_event(self, session_id: str, context: Dict[str, Any]) -> str:
        """
        生成“会话总结”事件（session_summary）。
        在所有步骤完成后，向前端发送最终的项目路径及生成的 PPTX 构件信息。
        """
        pptx_path = os.path.join(context["project_path"], f"{context['project_name']}.pptx")
        summary = (
            f"已完成 7 个步骤，项目目录：{context['project_path']}。"
            f"{'已生成 PPTX 文件。' if os.path.exists(pptx_path) else 'PPTX 生成脚本已执行。'}"
        )
        return await self._yield_event(
            "session_summary",
            summary,
            session_id=session_id,
            title="完成总结",
            summary=summary,
            artifacts=[
                {"label": "项目目录", "path": context["project_path"]},
                {"label": "PPTX 文件", "path": pptx_path},
            ],
        )

    async def _run_tool(self, tool_func, *args, **kwargs) -> tuple[int, str, str]:
        loop = asyncio.get_running_loop()
        # run_in_executor expects the function, then args. For kwargs we use lambda or partial.
        import functools
        func = functools.partial(tool_func, *args, **kwargs)
        return await loop.run_in_executor(None, func)

    async def process_message(self, session_id: str, message: str) -> AsyncGenerator[str, None]:
        session = self.session_manager.get_session(session_id)
        state = session["state"]
        context = session["context"]

        session["history"].append({"role": "user", "content": message})
        
        # We start by echoing state
        yield await self._yield_event("state", state.value)

        try:
            if state in [AgentState.INIT, AgentState.DONE, AgentState.ERROR]:
                context["topic"] = message
                
                # Reset history if starting fresh
                session["history"] = [{"role": "user", "content": message}]
                
                # Regenerate project name for new session or new request in DONE/ERROR state
                import time
                new_proj_name = f"project_{session_id[:8]}_{int(time.time())}"
                context["project_name"] = new_proj_name
                yield await self._yield_plan_event(session_id)
                
                # Step 1: Parse
                self.session_manager.update_state(session_id, AgentState.STEP_1_PARSE)
                yield await self._yield_event("state", AgentState.STEP_1_PARSE.value)
                yield await self._yield_step_event(session_id, "step_1_parse", 1, "源内容解析", "开始")
                yield await self._yield_step_event(session_id, "step_1_parse", 1, "源内容解析", "执行")
                yield await self._yield_event("trace", "Step 1: Parsing user input as source content...")
                context["source_content"] = message
                yield await self._yield_step_event(session_id, "step_1_parse", 1, "源内容解析", "完成")
                
                # Step 2: Init Project
                self.session_manager.update_state(session_id, AgentState.STEP_2_PROJECT)
                yield await self._yield_event("state", AgentState.STEP_2_PROJECT.value)
                yield await self._yield_step_event(session_id, "step_2_project", 2, "项目初始化", "开始")
                yield await self._yield_step_event(session_id, "step_2_project", 2, "项目初始化", "执行")
                yield await self._yield_event("trace", f"Step 2: Initializing project '{context['project_name']}'...")
                
                # We assume we are in agent_service dir, but let's be safe with absolute paths
                projects_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "projects"))
                os.makedirs(projects_dir, exist_ok=True)
                
                code, stdout, stderr = await self._run_tool(ppt_tools.init_project, context["project_name"], projects_dir=projects_dir)
                
                if code != 0:
                    yield await self._yield_event("trace", f"Project init error: {stderr}")
                    # Try to continue or handle error
                else:
                    yield await self._yield_event("trace", f"Project initialized successfully. Output:\n{stdout}")
                    # Extract the actual created project path from stdout
                    import re
                    match = re.search(r"Project created:\s*(.+)", stdout)
                    if match:
                        context["project_path"] = match.group(1).strip()
                    else:
                        context["project_path"] = os.path.join(projects_dir, context["project_name"])
                yield await self._yield_step_event(session_id, "step_2_project", 2, "项目初始化", "完成")
    
                # Step 3: Template Match
                self.session_manager.update_state(session_id, AgentState.STEP_3_TEMPLATE)
                yield await self._yield_event("state", AgentState.STEP_3_TEMPLATE.value)
                yield await self._yield_step_event(session_id, "step_3_template", 3, "模板匹配", "开始")
                yield await self._yield_step_event(session_id, "step_3_template", 3, "模板匹配", "思考")
                
                yield await self._yield_event("trace", "Step 3: Selecting template based on content...")
                
                # Read templates index
                templates_json_path = os.path.join(os.path.dirname(__file__), "..", "..", "skills", "ppt-master", "templates", "layouts", "layouts_index.json")
                templates_info = ""
                if os.path.exists(templates_json_path):
                    with open(templates_json_path, "r", encoding="utf-8") as f:
                        templates_info = f.read()
                
                template_prompt = (
                    "You are an expert PPT designer. Based on the user's topic, select the most suitable template from the available templates list.\n\n"
                    f"User Topic: {context['source_content']}\n\n"
                    f"Available Templates:\n{templates_info}\n\n"
                    "Think about the choice briefly, and then output your final decision by providing ONLY the exact template key wrapped in `[TEMPLATE:key]` tags, e.g. `[TEMPLATE:mckinsey]`."
                )
                
                template_messages = [{"role": "user", "content": template_prompt}]
                template_reply = ""
                yield await self._yield_event("message", "\n\n**🤖 思考模板选择...**\n\n", step_id="step_3_template")
                yield await self._yield_step_event(session_id, "step_3_template", 3, "模板匹配", "执行")
                async for chunk in self.llm_client.chat_completion_stream(template_messages):
                    template_reply += chunk
                    yield await self._yield_event("chunk", chunk, step_id="step_3_template")
                
                # Extract chosen template
                import re
                template_match = re.search(r"\[TEMPLATE:\s*(.+?)\]", template_reply)
                chosen_template = template_match.group(1).strip() if template_match else "ppt169"
                context["template"] = chosen_template
                yield await self._yield_event("trace", f"Step 3: Chosen template is '{chosen_template}'")
                yield await self._yield_step_event(session_id, "step_3_template", 3, "模板匹配", "完成")
                
                # We could run template copying logic here if we wanted to fully support templates
                # For now, we'll just record it and pass to strategist if needed
    
                # Step 4: Strategist
                self.session_manager.update_state(session_id, AgentState.STEP_4_STRATEGIST)
                yield await self._yield_event("state", AgentState.STEP_4_STRATEGIST.value)
                yield await self._yield_step_event(session_id, "step_4_strategist", 4, "策略规划", "开始")
                yield await self._yield_step_event(session_id, "step_4_strategist", 4, "策略规划", "计划")
                yield await self._yield_event("trace", "Step 4: Strategist generating PPT outline and specs...")
                
                prompt = (
                    "You are an expert PPT designer. The user wants to create a presentation about:\n"
                    f"{context['source_content']}\n\n"
                    "Please generate a structured outline for the PPT, including slide titles and key bullet points. "
                    "Output ONLY the markdown content for `spec_lock.md`."
                )
                messages = [{"role": "user", "content": prompt}]
                
                full_reply = ""
                # Stream the generation
                yield await self._yield_step_event(session_id, "step_4_strategist", 4, "策略规划", "执行")
                async for chunk in self.llm_client.chat_completion_stream(messages):
                    full_reply += chunk
                    yield await self._yield_event("chunk", chunk, step_id="step_4_strategist")
                
                # Dummy usage logging
                yield await self._yield_event("usage", "Tokens used: ~500 (estimate)")
                
                # Save to spec_lock.md
                spec_path = os.path.join(context["project_path"], "spec_lock.md")
                os.makedirs(os.path.dirname(spec_path), exist_ok=True)
                with open(spec_path, "w", encoding="utf-8") as f:
                    f.write(full_reply)
                
                yield await self._yield_event("trace", f"Saved outline to {spec_path}")
                yield await self._yield_step_event(session_id, "step_4_strategist", 4, "策略规划", "完成")
                
                # Automatically proceed to next steps
                yield await self._yield_event("message", "\n\n**🤖 大纲生成完毕，开始自动排版...**\n\n")
                
                # Step 5: Image Gen
                self.session_manager.update_state(session_id, AgentState.STEP_5_IMAGE)
                yield await self._yield_event("state", AgentState.STEP_5_IMAGE.value)
                yield await self._yield_step_event(session_id, "step_5_image", 5, "图像生成", "开始")
                yield await self._yield_step_event(session_id, "step_5_image", 5, "图像生成", "执行")
                yield await self._yield_event("trace", "Step 5: Image generation (skipped for now)...")
                yield await self._yield_step_event(session_id, "step_5_image", 5, "图像生成", "完成")
    
                # Step 6: Executor
                self.session_manager.update_state(session_id, AgentState.STEP_6_EXECUTOR)
                yield await self._yield_event("state", AgentState.STEP_6_EXECUTOR.value)
                yield await self._yield_step_event(session_id, "step_6_executor", 6, "执行排版", "开始")
                yield await self._yield_step_event(session_id, "step_6_executor", 6, "执行排版", "思考")
                
                yield await self._yield_event("trace", "Step 6: Executor generating SVG content...")
                
                # Read spec_lock.md
                spec_path = os.path.join(context["project_path"], "spec_lock.md")
                if os.path.exists(spec_path):
                    with open(spec_path, "r", encoding="utf-8") as f:
                        spec_content = f.read()
                else:
                    spec_content = "No spec_lock.md found."
    
                prompt = (
                    "You are an expert SVG presentation generator. Convert the following PPT outline into a single markdown file containing SVG code blocks for each slide. "
                    "Use the format:\n"
                    "## Slide 1\n```svg\n<svg>...</svg>\n```\n\n"
                    f"Outline:\n{spec_content}"
                )
                messages = [{"role": "user", "content": prompt}]
                
                full_reply = ""
                yield await self._yield_step_event(session_id, "step_6_executor", 6, "执行排版", "执行")
                async for chunk in self.llm_client.chat_completion_stream(messages):
                    # Yield progress to trace so we know it's not frozen
                    if len(full_reply) % 500 == 0 and len(full_reply) > 0:
                        yield await self._yield_event("trace", f"Generating SVG... ({len(full_reply)} chars)")
                    full_reply += chunk
                    yield await self._yield_event("chunk", chunk, step_id="step_6_executor")
                
                # Save total.md (contains only notes, SVGs stripped out)
                import re
                notes_only = re.sub(r"```svg\s*[\s\S]*?\s*```", "", full_reply, flags=re.IGNORECASE)
                total_md_path = os.path.join(context["project_path"], "notes", "total.md")
                os.makedirs(os.path.dirname(total_md_path), exist_ok=True)
                with open(total_md_path, "w", encoding="utf-8") as f:
                    f.write(notes_only.strip())
                
                # Extract SVGs from full_reply and save them
                svg_blocks = re.findall(r"```svg\s*([\s\S]*?)\s*```", full_reply, re.IGNORECASE)
                
                svg_dir = os.path.join(context["project_path"], "svg_output")
                os.makedirs(svg_dir, exist_ok=True)
                
                for idx, svg_content in enumerate(svg_blocks, start=1):
                    # Optional: clean up XML declaration if LLM added it, but usually cairosvg/svglib handle it
                    svg_filename = f"P{idx:02d}_slide.svg"
                    svg_path = os.path.join(svg_dir, svg_filename)
                    with open(svg_path, "w", encoding="utf-8") as f:
                        f.write(svg_content.strip())
                
                yield await self._yield_event("trace", f"Extracted {len(svg_blocks)} SVGs to svg_output/ and saved total.md")
                yield await self._yield_step_event(session_id, "step_6_executor", 6, "执行排版", "完成")
    
                # Step 7: Post-processing
                self.session_manager.update_state(session_id, AgentState.STEP_7_POSTPROCESS)
                yield await self._yield_event("state", AgentState.STEP_7_POSTPROCESS.value)
                yield await self._yield_step_event(session_id, "step_7_postprocess", 7, "后处理导出", "开始")
                yield await self._yield_step_event(session_id, "step_7_postprocess", 7, "后处理导出", "执行")
                
                yield await self._yield_event("trace", "Step 7: Post-processing (splitting MD, finalize SVG, generate PPTX)...")
                
                # We use the new async streaming tool to stream stdout/stderr
                yield await self._yield_event("trace", ">>> Running split_md...")
                async for line in ppt_tools.run_script_stream_async("total_md_split.py", [context["project_path"]]):
                    yield await self._yield_event("trace", line)
                    
                yield await self._yield_event("trace", ">>> Running finalize_svg...")
                async for line in ppt_tools.run_script_stream_async("finalize_svg.py", [context["project_path"]]):
                    yield await self._yield_event("trace", line)
                    
                yield await self._yield_event("trace", ">>> Running generate_pptx...")
                async for line in ppt_tools.run_script_stream_async("svg_to_pptx.py", [context["project_path"]]):
                    yield await self._yield_event("trace", line)
                yield await self._yield_step_event(session_id, "step_7_postprocess", 7, "后处理导出", "完成")
                
                self.session_manager.update_state(session_id, AgentState.DONE)
                yield await self._yield_event("state", AgentState.DONE.value)
                yield await self._yield_summary_event(session_id, context)
                yield await self._yield_event("message", f"**PPT Generation complete!**\n\nYou can find your files in `{context['project_path']}`")
                return
    
            else:
                yield await self._yield_event("message", f"Current state is {state.value}. Unable to process message.")
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            print(f"Error in orchestrator:\n{tb_str}")
            self.session_manager.update_state(session_id, AgentState.ERROR)
            yield await self._yield_event("state", AgentState.ERROR.value)
            yield await self._yield_event("message", f"\n\n**Error Occurred:** {str(e)}")
            yield await self._yield_event("trace", f"Exception trace:\n{tb_str}")
