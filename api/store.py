"""Chats, stored in one JSON file.

A chat is little more than a title plus the pack that gives it context — the
transcript itself lives in the session, not here.
"""

import json
import time
import uuid
from pathlib import Path

CHATS_PATH = Path("data") / "chats.json"


def _load() -> list[dict]:
    if not CHATS_PATH.exists():
        return []
    return json.loads(CHATS_PATH.read_text(encoding="utf-8"))


def _save(chats: list[dict]) -> None:
    CHATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHATS_PATH.write_text(json.dumps(chats, indent=2, ensure_ascii=False), encoding="utf-8")


def list_chats() -> list[dict]:
    return sorted(_load(), key=lambda c: c.get("created_at", 0), reverse=True)


def get_chat(chat_id: str) -> dict | None:
    return next((c for c in _load() if c["id"] == chat_id), None)


def create_chat(title: str = "New chat", pack_id: str | None = None) -> dict:
    chats = _load()
    chat = {"id": uuid.uuid4().hex[:8], "title": title,
            "pack_id": pack_id, "created_at": time.time()}
    chats.append(chat)
    _save(chats)
    return chat


def update_chat(chat_id: str, **fields) -> dict | None:
    chats = _load()
    chat = next((c for c in chats if c["id"] == chat_id), None)
    if chat is None:
        return None
    chat.update({k: v for k, v in fields.items() if v is not None})
    _save(chats)
    return chat


def delete_chat(chat_id: str) -> bool:
    chats = _load()
    remaining = [c for c in chats if c["id"] != chat_id]
    if len(remaining) == len(chats):
        return False
    _save(remaining)
    return True
