"""
Job tracker for ManuelIA v2 — Mongo-backed so jobs survive backend reloads.

Schema:
{
  id: str (uuid4),
  user_id: str,
  state: "pending" | "running" | "done" | "error",
  progress: int 0-100,
  label: str,             # short label e.g. "Étape 3/7"
  status_text: str,       # long status e.g. "gpt-image-2 génère…"
  steps_status: [         # one entry per step for the parallel grid UI
    {"idx": 0, "title": "...", "state": "pending"|"running"|"validating"|"done"|"error",
     "attempt": 0, "validated": null|bool}
  ],
  error: Optional[str],
  manual_id: Optional[str],
  created_at: ISO str,
  updated_at: ISO str,
}
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

log = logging.getLogger("jobs")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MongoJobTracker:
    """Async, mongo-persisted job tracker."""

    def __init__(self, collection) -> None:
        self._col = collection
        self._lock = asyncio.Lock()
        # tiny in-process cache to debounce identical updates (best-effort)
        self._mem: Dict[str, dict] = {}

    async def create(self, user_id: str, n_steps: int = 0, step_titles: Optional[List[str]] = None) -> str:
        jid = str(uuid.uuid4())
        steps_status = []
        for i in range(n_steps):
            steps_status.append({
                "idx": i,
                "title": (step_titles[i] if step_titles and i < len(step_titles) else f"Étape {i+1}"),
                "state": "pending",
                "attempt": 0,
                "validated": None,
            })
        doc = {
            "id": jid,
            "user_id": user_id,
            "state": "pending",
            "progress": 0,
            "label": "En attente",
            "status_text": "Initialisation…",
            "steps_status": steps_status,
            "error": None,
            "manual_id": None,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        await self._col.insert_one(doc)
        self._mem[jid] = doc
        return jid

    async def set_steps(self, jid: str, step_titles: List[str]) -> None:
        steps_status = [{
            "idx": i, "title": t, "state": "pending", "attempt": 0, "validated": None,
        } for i, t in enumerate(step_titles)]
        await self._patch(jid, {"steps_status": steps_status})

    async def update(self, jid: str, **fields) -> None:
        fields["updated_at"] = _now_iso()
        await self._patch(jid, fields)

    async def update_step(self, jid: str, idx: int, **fields) -> None:
        """Patch one entry inside steps_status by index. Atomic via $set with positional."""
        upd = {f"steps_status.$[el].{k}": v for k, v in fields.items()}
        upd["updated_at"] = _now_iso()
        try:
            await self._col.update_one(
                {"id": jid},
                {"$set": upd},
                array_filters=[{"el.idx": idx}],
            )
        except Exception as e:
            log.error("update_step failed: %s", e)
        # update cache
        cached = self._mem.get(jid)
        if cached and "steps_status" in cached:
            for s in cached["steps_status"]:
                if s.get("idx") == idx:
                    s.update(fields)
                    break

    async def get(self, jid: str) -> Optional[dict]:
        # try cache first, then mongo
        if jid in self._mem:
            doc = await self._col.find_one({"id": jid}, {"_id": 0})
            if doc:
                self._mem[jid] = doc
                return doc
        doc = await self._col.find_one({"id": jid}, {"_id": 0})
        if doc:
            self._mem[jid] = doc
        return doc

    async def get_active_for_user(self, user_id: str) -> Optional[dict]:
        """Return the most recent running/pending job for this user, if any."""
        cur = self._col.find(
            {"user_id": user_id, "state": {"$in": ["pending", "running"]}},
            {"_id": 0},
        ).sort("created_at", -1).limit(1)
        async for d in cur:
            return d
        return None

    async def _patch(self, jid: str, fields: dict) -> None:
        try:
            await self._col.update_one({"id": jid}, {"$set": fields})
        except Exception as e:
            log.error("job patch failed: %s", e)
        cached = self._mem.get(jid)
        if cached:
            cached.update(fields)


# This will be initialized at module import time in server.py
tracker: Optional[MongoJobTracker] = None


def init_tracker(collection) -> MongoJobTracker:
    global tracker
    tracker = MongoJobTracker(collection)
    return tracker
