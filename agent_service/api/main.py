import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from agent_service.agent.orchestrator import Orchestrator

# Load environment variables explicitly from agent_service/.env
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="PPT Agent Service")

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = Orchestrator()

class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Endpoint to process a chat message.
    Returns a Server-Sent Events (SSE) stream.
    """
    return StreamingResponse(
        orchestrator.process_message(req.session_id, req.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# Ensure web directory exists
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
os.makedirs(web_dir, exist_ok=True)

# Create a dummy index.html if it doesn't exist so mounting doesn't fail immediately
index_path = os.path.join(web_dir, "index.html")
if not os.path.exists(index_path):
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("<html><body><h1>PPT Agent Service Web UI (Placeholder)</h1></body></html>")

# Mount web directory
app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
