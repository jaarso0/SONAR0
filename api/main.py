"""HTTP API for the dashboard: chats, the packs that give them context, and
the LiveKit sessions that put a caller and an agent in the same room."""

import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from livekit import api as lk
from pydantic import BaseModel

from api import jobs, store
from pipeline.run import PACKS_DIR, list_packs, read_meta

load_dotenv()

STATIC_DIR = Path(__file__).parent / "static"
UPLOAD_DIR = PACKS_DIR / "_uploads"

# Must match the agent_name the worker registers with in worker/agent.py.
AGENT_NAME = "sonar"


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.reconcile()
    yield


app = FastAPI(title="Sonar", lifespan=lifespan)


class BuildRequest(BaseModel):
    source: str                       # https://... or a local .pdf path
    max_pages: int = 40


class ChatRequest(BaseModel):
    title: str | None = None
    pack_id: str | None = None


class SessionRequest(BaseModel):
    chat_id: str


# ---------- pages ----------

@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/dashboard")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "dashboard.html")


# ---------- packs ----------

@app.get("/api/packs")
def get_packs() -> list[dict]:
    return list_packs()


@app.get("/api/packs/{pack_id}")
def get_pack(pack_id: str) -> dict:
    meta = read_meta(pack_id)
    if not meta:
        raise HTTPException(404, "no such pack")
    return meta


@app.post("/api/packs", status_code=202)
async def build(request: BuildRequest) -> dict:
    """Starts a build and returns immediately — poll the pack for progress.

    Must stay async: the build is an asyncio task on this loop, and a sync
    route would be handed to a worker thread that has no loop to attach to.
    """
    return jobs.start(request.source, request.max_pages)


@app.post("/api/packs/upload", status_code=202)
async def upload(file: UploadFile) -> dict:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "only .pdf uploads are supported")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / Path(file.filename).name
    path.write_bytes(await file.read())
    return jobs.start(str(path))


# ---------- chats ----------

@app.get("/api/chats")
def get_chats() -> list[dict]:
    return store.list_chats()


@app.post("/api/chats", status_code=201)
def post_chat(request: ChatRequest) -> dict:
    return store.create_chat(request.title or "New chat", request.pack_id)


@app.patch("/api/chats/{chat_id}")
def patch_chat(chat_id: str, request: ChatRequest) -> dict:
    chat = store.update_chat(chat_id, title=request.title, pack_id=request.pack_id)
    if chat is None:
        raise HTTPException(404, "no such chat")
    return chat


@app.delete("/api/chats/{chat_id}", status_code=204)
def remove_chat(chat_id: str) -> None:
    if not store.delete_chat(chat_id):
        raise HTTPException(404, "no such chat")


# ---------- voice sessions ----------

@app.post("/api/sessions")
async def create_session(request: SessionRequest) -> dict:
    """Opens a room for one call: dispatches the agent onto it carrying the
    chat's pack, and hands the browser a token to join the same room."""
    for name in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
        if not os.getenv(name):
            raise HTTPException(500, f"{name} is not set")

    chat = store.get_chat(request.chat_id)
    if chat is None:
        raise HTTPException(404, "no such chat")

    pack = read_meta(chat.get("pack_id") or "")
    if pack.get("stage") != "ready":
        raise HTTPException(409, "attach a pack that has finished building")

    room = f"sonar-{chat['id']}-{uuid.uuid4().hex[:6]}"

    async with lk.LiveKitAPI() as client:
        await client.agent_dispatch.create_dispatch(
            lk.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=room,
                metadata=json.dumps({"pack_id": pack["pack_id"], "chat_id": chat["id"]}),
            )
        )

    token = (
        lk.AccessToken()
        .with_identity(f"caller-{chat['id']}")
        .with_name("You")
        .with_grants(lk.VideoGrants(room_join=True, room=room,
                                    can_publish=True, can_subscribe=True,
                                    can_publish_data=True))
        .to_jwt()
    )

    return {"url": os.environ["LIVEKIT_URL"], "token": token, "room": room,
            "pack_id": pack["pack_id"], "subject": pack.get("subject")}
