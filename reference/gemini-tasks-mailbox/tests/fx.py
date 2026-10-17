"""Shared test helpers. Fixture directories are created exclusively and are never cleaned up."""
from __future__ import annotations

import base64
import os
import pathlib
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent
PACKET = HERE.parent
if str(PACKET) not in sys.path:
    sys.path.insert(0, str(PACKET))

from gemini_p2 import Bridge, Config, NotSent, PortError  # noqa: E402

MEASURED = HERE / "fixtures"      # small synthetic fixtures
RETAINED = HERE / "retained"


def new_fixture_dir(prefix: str) -> pathlib.Path:
    RETAINED.mkdir(mode=0o700, exist_ok=True)
    path = RETAINED / (prefix + "-" + uuid.uuid4().hex)
    path.mkdir(mode=0o700)          # exclusive: fails if it already exists
    return path


def mission_payload(ref: str, body: bytes, to: str = "gemini") -> bytes:
    """Same construction as the installed sender (mission_payload)."""
    import json
    request = json.dumps({"to": to, "purpose": "queue_task", "ref": ref, "hop": 1, "parent": None},
                         ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return len(request).to_bytes(4, "big") + request + body


def cid(n: int) -> str:
    return "20261016T02%04dZ_%06x" % (n, 0xabc000 + n)


class FakeTasks(object):
    """Google Tasks shape modelled on a live Google Tasks listing: id, title, notes, status, updated."""

    def __init__(self, page_size: int = 2):
        self.rows = []
        self.page_size = page_size
        self.n = 0
        self.inserts = 0
        self.completed_ids = []
        self.fail_complete = False
        self.lose_after_store = False
        self.lose_before_store = False
        self.raise_not_sent = False

    def list_tasks(self, list_id, page_token, max_results=100, show_completed=True, show_hidden=True):
        assert list_id == "@default" and show_completed is True and show_hidden is True
        start = int(page_token or 0)
        page = [dict(r) for r in self.rows[start:start + self.page_size]]
        nxt = str(start + self.page_size) if start + self.page_size < len(self.rows) else None
        return page, nxt

    def insert_task(self, list_id, task):
        assert list_id == "@default"
        if self.raise_not_sent:
            self.raise_not_sent = False
            raise NotSent("token refresh failed before any request")
        if self.lose_before_store:
            self.lose_before_store = False
            raise OSError("request outcome unknown before any task was stored")
        self.n += 1
        row = {"id": "task%03d" % self.n, "status": "needsAction", "updated": "2026-10-16T00:00:00.000Z"}
        row.update(task)
        self.rows.append(row)
        self.inserts += 1
        if self.lose_after_store:
            self.lose_after_store = False
            raise OSError("response lost after the task was stored")
        return dict(row)

    def complete_task(self, list_id, task_id):
        if self.fail_complete:
            raise OSError("completion failed")
        self.completed_ids.append(task_id)
        for row in self.rows:
            if row["id"] == task_id:
                row["status"] = "completed"

    def add_answer(self, call_id, body, task_id=None):
        self.n += 1
        row = {"id": task_id or "ans%03d" % self.n, "title": "Answer " + call_id,
               "notes": "```text\n" + body + "\n```", "status": "needsAction", "updated": "2026-10-16T01:00:00.000Z"}
        self.rows.append(row)
        return row

    def add_raw(self, title, notes, task_id=None):
        self.n += 1
        row = {"id": task_id or "raw%03d" % self.n, "title": title, "notes": notes, "status": "needsAction"}
        self.rows.append(row)
        return row


class ModelMailPort(object):
    """A model of the installed reader semantics used for logic tests; real-core tests check the model."""

    def __init__(self):
        self.letters = []            # dicts as ReaderCliPort.read_head returns them
        self.acked = set()
        self.replies = {}            # call_id -> (caller, payload)
        self.reply_calls = []
        self.ack_fail = 0
        self.ack_commit_then_raise = 0
        self.reply_plan = []         # list of error codes (or None) consumed per reply call
        self.record_before_error = True

    def add_letter(self, call_id, source_agent, ref, body, source_island="pc1"):
        import hashlib
        payload = mission_payload(ref, body)
        self.letters.append({
            "call_id": call_id, "source_island": source_island, "source_agent": source_agent,
            "destination_island": "pc1", "destination_agent": "gemini", "sequence": len(self.letters) + 1,
            "envelope_sha256": hashlib.sha256(b"env" + call_id.encode()).hexdigest(),
            "payload_sha256": hashlib.sha256(payload).hexdigest(), "payload": payload})

    def read_head(self):
        for letter in self.letters:
            if letter["call_id"] not in self.acked:
                return dict(letter)
        return None

    def ack(self, call_id):
        head = self.read_head()
        if self.ack_fail:
            self.ack_fail -= 1
            raise PortError("storage_failure")
        if head is None or head["call_id"] != call_id:
            raise PortError("not_head")
        self.acked.add(call_id)
        if self.ack_commit_then_raise:
            self.ack_commit_then_raise -= 1
            raise PortError("port_exception")          # the pickup committed; the answer was lost
        return {"ok": True, "status": "picked_up"}

    def reply(self, call_id, caller_agent, payload):
        self.reply_calls.append((call_id, caller_agent, payload))
        code = self.reply_plan.pop(0) if self.reply_plan else None
        known = next((l for l in self.letters if l["call_id"] == call_id), None)
        if known is None or call_id not in self.acked:
            raise PortError("not_picked_up")
        if known["source_agent"] != caller_agent:
            raise PortError("wrong_caller")
        if call_id in self.replies and self.replies[call_id][1] != payload:
            raise PortError("id_collision")
        if code is not None:
            if self.record_before_error:
                self.replies.setdefault(call_id, (caller_agent, payload))
            raise PortError(code)
        first = call_id not in self.replies
        self.replies.setdefault(call_id, (caller_agent, payload))
        return {"status": "result_admitted", "call_id": call_id, "replay": "false" if first else "true"}


def make_bridge(prefix="logic", **cfg):
    root = new_fixture_dir(prefix)
    tasks = FakeTasks()
    port = ModelMailPort()
    bridge = Bridge(Config(str(root / "ledger.sqlite3"), **cfg), tasks, port)
    return root, tasks, port, bridge


__all__ = ["FakeTasks", "ModelMailPort", "make_bridge", "new_fixture_dir", "mission_payload", "cid",
           "MEASURED", "RETAINED", "PACKET", "base64"]
