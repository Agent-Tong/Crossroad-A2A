"""Dropbox backend for the ChatGPT lobby (ChatGPT). OFFLINE DRAFT, NOT INSTALLED.

The lobby 0.3.0 (lobby_server.py, reviewed bytes, unchanged) talks to ONE duck-typed adapter object (`host_adapter`):
list_pending(), captured_statuses(), read_one(call_id), reply(call_id, payload). On PC1 that object drives a mailbox CLI.
On VPS1 (a container-fleet island) there is no such CLI, so this module gives the lobby the SAME four calls on top of
the DropboxPort (../dropbox-port/dropbox_port.py), which implements that island's dropbox contract:

  mission in   : <dropbox_root>/<agent>/in/<cid>.mission.md        (written by the island bridge; read-only here)
  answer out   : <dropbox_root>/<agent>/out/<ca><YYMMDD>a_Answer_<cid>.md, then out/answer-<cid>.json   (body first, then JSON)
  confirmation : <dropbox_root>/<agent>/in/<cid>.answered.txt      (written by the island bridge after it signed and posted)

Semantics (all of them come from DropboxPort; nothing here re-implements the contract):
  * list_pending : verified, unanswered, unexpired missions we have not started to answer. Never blocks on a bad file.
  * read_one     : the verified mission body as bytes. Read only; no ack, no write.
  * reply        : ack (ledger line, once) then DropboxPort.reply. Exactly once: the same bytes again is a no-op, other bytes
                   are `id_collision`. It answers `reply_submitted` while the island bridge has not written answered.txt and
                   `result_admitted` when it has. The lobby reports that status to ChatGPT as it is.
  * statuses     : derived from the port ledger plus answered.txt / refusal notices. Nothing is stored twice.
send_mail is OFF in the lobby config (enabled_tools has no send_mail), so this adapter has no send path at all.
Nothing here deletes, overwrites or moves a file.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from dropbox_port import CALL_ID_RE, MAX_BODY_BYTES, MISSION_NAME_RE, PHASES, DropboxPort, _Unverified
from gemini_p2 import PortError, Refusal
from lobby_server import LobbyRefusal

AGENTS = ("chatgpt", "lobby")          # `lobby` is the name already listed in the route policy; `chatgpt` is the other choice. The owner decides.
CONFIG_KEYS = frozenset(("dropbox_root", "state_dir", "inbox_owner_uid", "agent"))
MAX_LISTED = 200
MAX_STATUSES = 200            # captured_statuses never returns more rows than this (newest kept); finished work is not listed
DESTINATION_ISLAND = "vps1"


class AdapterRefusal(LobbyRefusal):
    """Fixed lowercase code. It IS a LobbyRefusal, so a refusal that lobby_server does not wrap itself (check_mail and
    job_status call list_pending / captured_statuses bare) still reaches ChatGPT as a coded refusal, never as internal_error."""

    def __init__(self, code: str):
        super().__init__(code if isinstance(code, str) else "adapter_refused")


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate_key")
        out[key] = value
    return out


def load_config(path: str) -> Dict[str, Any]:
    if not isinstance(path, str) or not os.path.isabs(path):
        raise AdapterRefusal("config_path_invalid")
    try:
        with open(path, "rb") as handle:
            value = json.loads(handle.read(4097).decode("utf-8"), object_pairs_hook=_unique)
    except Exception:
        raise AdapterRefusal("config_invalid")
    if (type(value) is not dict or set(value) != CONFIG_KEYS or value["agent"] not in AGENTS
            or type(value["inbox_owner_uid"]) is not int or isinstance(value["inbox_owner_uid"], bool)
            or value["inbox_owner_uid"] < 0
            or any(type(value[k]) is not str or not os.path.isabs(value[k]) or ".." in value[k].split("/")
                   for k in ("dropbox_root", "state_dir"))):
        raise AdapterRefusal("config_invalid")
    return value


class LobbyDropboxPort(DropboxPort):
    """The reviewed port plus two read-only views (scan, status_row). It overrides nothing."""

    def scan(self):
        """(open missions, expired cids, unverified cid -> reason). Read only."""
        opened: List[dict] = []
        expired: List[str] = []
        unverified: Dict[str, str] = {}
        try:
            names = sorted(os.listdir(self.in_dir))
        except OSError:
            raise PortError("storage_failure")
        for name in names:
            match = MISSION_NAME_RE.fullmatch(name)
            if match is None:
                continue
            cid = match.group(1)
            if self._answered(cid):
                continue
            try:
                events = self._events(cid)
            except PortError as exc:
                unverified[cid] = exc.code
                continue
            if self._find(events, "intent") is not None:
                continue                                    # we already started the answer: it shows as reply_pending
            try:
                mission = self._load_mission(cid)
            except _Unverified as exc:
                unverified[cid] = exc.reason
                continue
            except PortError as exc:                        # wrong owner, extra hard link, over the size cap: skipped, never a block
                unverified[cid] = exc.code
                continue
            except FileNotFoundError:
                continue
            if self._expired(cid, self.margin):
                expired.append(cid)
                continue
            opened.append(mission)
            if len(opened) >= MAX_LISTED:
                break
        return opened, expired, unverified

    def status_row(self, cid: str) -> Optional[dict]:
        """One call's row, in the shape of DropboxPort.status() but read for ONE ledger file (the full scan grows with history).
        A test compares it with the reviewed status() on every state."""
        events = self._events(cid)
        if not events:
            return None
        have = {e["event"] for e in events}
        phase = next((p for p in reversed(("ack",) + PHASES) if p in have), "none")
        intent = self._find(events, "intent")
        answered = self._answered(cid)
        notice = bool(intent) and os.path.lexists(os.path.join(self.in_dir, "ref-" + intent["request_sha256"][:24] + ".refused.txt"))
        published = self._find(events, "published")
        age = int(self.clock() - float(published.get("ts", 0))) if published else None
        present = []
        if intent:
            present = [n for n in (intent.get("ref"), "answer-%s.json" % cid) if n and os.path.lexists(os.path.join(self.out_dir, n))]
        flags = []
        if phase == "published" and not answered and not notice:
            if not present:
                flags.append("consumed_unconfirmed")
            elif age is not None and age > self.grace:
                flags.append("bridge_silent_past_grace")
            else:
                flags.append("waiting_for_bridge")
        if phase == "request_started":
            flags.append("publish_unfinished")
        if answered and not ({"request_started", "published", "admitted"} & have):
            flags.append("answered_by_someone_else")
        if notice:
            flags.append("bridge_refused")
        return {"cid": cid, "phase": phase, "answered_txt": answered, "refused_notice": notice, "flags": flags}


class LobbyDropboxAdapter(object):
    """Drop-in for lobby_server's `SaasAdapter(config_path)` (the launcher aliases the module name)."""

    def __init__(self, config_path: str, *, port: Optional[LobbyDropboxPort] = None):
        self.config = load_config(config_path)
        self.agent = self.config["agent"]
        if port is None:
            try:
                port = LobbyDropboxPort(self.config["dropbox_root"], self.config["state_dir"],
                                        inbox_owner_uid=self.config["inbox_owner_uid"], agent=self.agent)
            except Refusal as exc:
                raise AdapterRefusal(exc.code)
        self.port = port

    # ------------------------------------------------------------------ helpers
    def _meta(self, mission: dict) -> Dict[str, str]:
        return {"call_id": mission["cid"], "source_island": mission["island"], "source_agent": mission["caller"],
                "destination_island": DESTINATION_ISLAND, "destination_agent": self.agent}

    def _mission(self, call_id: str) -> dict:
        if not isinstance(call_id, str) or not CALL_ID_RE.fullmatch(call_id):
            raise AdapterRefusal("mission_id_invalid")
        try:
            return self.port._load_mission(call_id)
        except FileNotFoundError:
            raise AdapterRefusal("mission_not_found")
        except _Unverified:
            raise AdapterRefusal("mission_unverified")
        except PortError as exc:
            raise AdapterRefusal(exc.code)

    def _rows(self) -> List[dict]:
        try:
            view = self.port.status()
        except (PortError, OSError):
            raise AdapterRefusal("tray_or_state_unreadable")
        if not view.get("ok"):
            raise AdapterRefusal("tray_or_state_unreadable")
        return view["missions"]

    @staticmethod
    def _state(row: dict) -> str:
        flags = set(row.get("flags", ()))
        if "bridge_refused" in flags:
            return "refused"
        if row.get("answered_txt") and row["phase"] in ("published", "admitted"):
            return "result_admitted"
        if flags & {"consumed_unconfirmed", "bridge_silent_past_grace", "answered_by_someone_else", "state_unreadable"}:
            return "needs_owner"
        if row["phase"] in ("intent", "body_published", "request_started", "published"):
            return "reply_pending"
        if row["phase"] == "admitted":
            return "result_admitted"
        return "captured"

    # ------------------------------------------------------------------ the four lobby calls
    def list_pending(self) -> List[Dict[str, str]]:
        try:
            opened, _expired, _bad = self.port.scan()
        except PortError as exc:
            raise AdapterRefusal(exc.code)
        return [self._meta(mission) for mission in opened]

    def captured_statuses(self) -> List[Dict[str, str]]:
        """Open and troubled answers only. A finished answer (result_admitted) is not listed, like the lobby's own jobs query
        (it hides 'replied'); the list is capped at MAX_STATUSES, newest kept. owner_view() reports the count of finished ones."""
        out = []
        for row in self._rows():
            state = self._state(row)
            if state == "result_admitted":
                continue
            out.append((row["cid"], state))
        out = out[-MAX_STATUSES:]
        result = []
        for cid, state in out:
            try:
                source = self.port._load_mission(cid)["caller"]
            except (FileNotFoundError, _Unverified, PortError):
                source = "unknown"
            result.append({"call_id": cid, "source_agent": source, "status": state})
        return result

    def read_one(self, expected_call_id: str) -> Dict[str, Any]:
        mission = self._mission(expected_call_id)
        meta = self._meta(mission)
        if not mission["body_token_verified"]:
            meta["body_normalised"] = "true"          # line breaks were rewritten by the island renderer after it made the token
        try:
            row = self.port.status_row(expected_call_id)
        except PortError as exc:
            raise AdapterRefusal(exc.code)
        state = self._state(row) if row is not None else "captured"
        return {"metadata": meta, "payload": mission["body"].encode("utf-8"), "status": state}

    def reply(self, call_id: str, payload: bytes) -> Dict[str, str]:
        if (not isinstance(call_id, str) or not CALL_ID_RE.fullmatch(call_id) or type(payload) is not bytes
                or not payload or len(payload) > MAX_BODY_BYTES):
            raise AdapterRefusal("reply_invalid")
        mission = self._mission(call_id)
        try:
            first = self.port._find(self.port._events(call_id), "intent") is None
            self.port.ack(call_id)                                         # ledger line, once; the port requires it before reply
            result = self.port.reply(call_id, mission["caller"], payload)
        except PortError as exc:
            if exc.code == "post_transport_uncertain":                     # written; the island bridge confirms on its next cycle
                return {"status": "reply_submitted", "call_id": call_id, "replay": "false" if first else "true"}
            raise AdapterRefusal(exc.code)
        return {"status": "result_admitted", "call_id": call_id, "replay": str(result.get("replay", "unknown"))}

    # ------------------------------------------------------------------ owner view (not a lobby call)
    def owner_view(self) -> Dict[str, Any]:
        opened, expired, unverified = self.port.scan()
        rows = self._rows()
        troubled = [r for r in rows if self._state(r) != "result_admitted"][-MAX_STATUSES:]
        return {"open": [m["cid"] for m in opened], "expired": expired, "unverified": unverified,
                "answers": [{"call_id": r["cid"], "state": self._state(r), "flags": r["flags"]} for r in troubled],
                "finished_count": len(rows) - len([r for r in rows if self._state(r) != "result_admitted"]),
                "needs_owner": self.port.status().get("needs_owner", [])}


SaasAdapter = LobbyDropboxAdapter       # the name lobby_server imports; see lobby_main.py
