"""Background pack builds.

One build per pack, running as an asyncio task in the API process. Status is
not held in memory — it is whatever the pack's meta.json says — so a poll can
be answered without touching the task.
"""

import asyncio
import time

from pipeline.run import (
    IN_PROGRESS,
    PACKS_DIR,
    build_pack,
    list_packs,
    pack_id_for,
    read_meta,
    subject_for,
    write_meta,
)

_tasks: dict[str, asyncio.Task] = {}


def is_building(pack_id: str) -> bool:
    task = _tasks.get(pack_id)
    return task is not None and not task.done()


def start(source: str, max_pages: int = 40) -> dict:
    """Queues a build. Rebuilding an existing pack reuses its directory."""
    pack_id = pack_id_for(source)
    if is_building(pack_id):
        return read_meta(pack_id)

    (PACKS_DIR / pack_id / "build").mkdir(parents=True, exist_ok=True)
    meta = write_meta(pack_id, source=source, subject=subject_for(source),
                      stage="queued", created_at=time.time(), error=None)

    task = asyncio.create_task(build_pack(source, max_pages))
    task.add_done_callback(lambda _: _tasks.pop(pack_id, None))
    _tasks[pack_id] = task
    return meta


def reconcile() -> None:
    """Marks packs left mid-build by a previous process as failed."""
    for meta in list_packs():
        stage = meta.get("stage")
        if (stage in IN_PROGRESS or stage == "queued") and not is_building(meta["pack_id"]):
            write_meta(meta["pack_id"], stage="failed", error="build was interrupted")
