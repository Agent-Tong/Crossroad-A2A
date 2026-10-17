"""Gemini <-> Crossroad bridge core (P2). OFFLINE CANDIDATE.

Export side : letters queued in the host mailbox for receiver "gemini" become
              Google Tasks titled "Letter <cid>" (list @default).
Collect side: tasks titled "Answer <cid>" with one strict fenced body are
              admitted into Crossroad EXACTLY ONCE as the reply to the original
              call, through the installed reader/reply mechanism (a MailPort).

Nothing here talks to Google or to Town Hall. Both are injected.
Nothing here removes anything: tasks are only inserted or marked completed,
ledger rows are only inserted or updated.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sqlite3
import stat
import time
from typing import Callable, Dict, Iterator, List, Optional, Protocol, Tuple

RECEIVER = "gemini"
DEFAULT_TASKS_LIST_ID = "@default"
MAX_NOTES_CHARS = 8192            # Google Tasks notes field limit (documented by the Google Tasks API)
MAX_MISSION_PAYLOAD_BYTES = 8192  # installed MAX_MISSION_PAYLOAD_BYTES
MAX_REQUEST_BYTES = 4096          # installed MAX_REQUEST_BYTES
MAX_RESULT_BYTES = 8000           # the island bridge's answer cap; below the mailbox reply cap 16384, so one cap serves both port kinds
CALL_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}$")      # installed CALL_ID_RE
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")                  # installed NAME_RE
REPORT_REF_RE = re.compile(r"^[a-z]{2}[0-9]{6}[a-z]{1,3}_[A-Za-z0-9._-]{1,120}\.md$")
LETTER_TITLE = re.compile(r"^Letter ([0-9]{8}T[0-9]{6}Z_[a-f0-9]{6})$")
ANSWER_TITLE = re.compile(r"^Answer ([0-9]{8}T[0-9]{6}Z_[a-f0-9]{6})$")
NEAR_MISS_ANSWER = re.compile(r"^\s*answer\b", re.I)
FENCED = re.compile(r"\A```(?:text|markdown)?\n(.*?)\n```\Z", re.S)
REQUEST_FIELDS = frozenset(("to", "purpose", "ref", "hop", "parent"))

# Port error classes (codes are the installed reader/reply fixed refusal codes).
RETRYABLE_CODES = frozenset((
    "post_transport_uncertain", "post_response_invalid", "post_request_id_invalid",
    "reply_ledger_unavailable", "storage_failure", "signer_failed", "port_exception",
    "post_initialize_refused", "post_refused", "post_metadata_invalid", "post_request_id_mismatch",
    "clock_invalid",
))
# Codes the installed core raises about THIS answer or THIS mission; retrying cannot change them.
PERMANENT_CODES = frozenset((
    "wrong_caller", "id_collision", "mission_not_found", "mission_ambiguous", "mission_binding_mismatch",
    "mission_hash_mismatch", "mission_type_mismatch", "mission_route_invalid", "pickup_mismatch",
    "call_id_invalid", "caller_invalid", "result_oversize", "payload_invalid", "envelope_oversize",
))
# Any other code is neither retried nor called final: the answer is held for the owner (owner_reset_held).
HALT_CODES = frozenset((
    "mailbox_off", "mail_off", "reply_off", "switch_untrusted", "switch_invalid",
    "reply_state_untrusted", "reply_state_unavailable", "reply_ledger_invalid",
    "policy_mismatch", "policy_expired", "signer_unavailable", "unknown_agent",
    "invalid_cli", "contract_expired", "peer_pin_changed", "post_peer_unverified",
    "reply_journal_mode", "signer_untrusted", "reply_ledger_exists",
))


class Refusal(RuntimeError):
    """A per-item or per-run refusal with a fixed lowercase code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class PortError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        self.retryable = code in RETRYABLE_CODES
        self.halt = code in HALT_CODES
        self.permanent = code in PERMANENT_CODES
        super().__init__(code)


class NotSent(Exception):
    """Raised by a TasksTransport when it failed BEFORE any request left the machine (token, validation, DNS).
    Any other exception from insert_task means the outcome is unknown."""


class HaltRun(RuntimeError):
    """Run-wide stop: a switch is off, the registry is wrong, the policy is wrong."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class TasksTransport(Protocol):
    def list_tasks(self, list_id: str, page_token: Optional[str], max_results: int = 100,
                   show_completed: bool = True, show_hidden: bool = True) -> Tuple[List[dict], Optional[str]]: ...
    def insert_task(self, list_id: str, task: dict) -> dict: ...
    def complete_task(self, list_id: str, task_id: str) -> None: ...


class MailPort(Protocol):
    def read_head(self) -> Optional[dict]: ...
    def ack(self, call_id: str) -> dict: ...
    def reply(self, call_id: str, caller_agent: str, payload: bytes) -> dict: ...


class Config(object):
    def __init__(self, db_path: str, tasks_list_id: str = DEFAULT_TASKS_LIST_ID,
                 max_per_hour: int = 30, max_per_day: int = 120, max_export_per_run: int = 10,
                 refuse_unexportable_with_reply: bool = True,
                 clock: Callable[[], float] = time.time):
        self.db_path = db_path
        self.tasks_list_id = tasks_list_id
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self.max_export_per_run = max_export_per_run
        self.refuse_unexportable_with_reply = refuse_unexportable_with_reply
        self.clock = clock


# --------------------------------------------------------------------------- ledger

SCHEMA = """
CREATE TABLE IF NOT EXISTS missions(
  cid TEXT PRIMARY KEY, source_island TEXT NOT NULL, source_agent TEXT NOT NULL,
  ref TEXT, sequence INTEGER, envelope_sha256 TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  notes_sha256 TEXT, state TEXT NOT NULL, task_id TEXT UNIQUE, detail TEXT,
  created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS answers(
  cid TEXT PRIMARY KEY, task_id TEXT, body BLOB NOT NULL, body_sha256 TEXT NOT NULL,
  origin TEXT NOT NULL, state TEXT NOT NULL, receipt_json TEXT, detail TEXT,
  letter_completed INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS refusals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, cid TEXT, code TEXT NOT NULL,
  notes_sha256 TEXT NOT NULL, first_seen REAL NOT NULL, UNIQUE(task_id, code, notes_sha256));
CREATE TABLE IF NOT EXISTS events(ts REAL NOT NULL, kind TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS owner_choices(
  cid TEXT PRIMARY KEY, task_id TEXT NOT NULL, note TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS owner_log(ts REAL NOT NULL, action TEXT NOT NULL, cid TEXT NOT NULL, note TEXT NOT NULL);
"""


class Ledger(object):
    def __init__(self, path: str, clock: Callable[[], float] = time.time):
        self.clock = clock
        self.path = os.path.abspath(path)
        parent = os.path.dirname(self.path)
        info = os.lstat(parent)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or
                stat.S_IMODE(info.st_mode) != 0o700 or os.path.realpath(parent) != parent):
            raise Refusal("ledger_parent_must_be_private_0700_directory")
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            os.close(os.open(self.path, flags, 0o600))
        except FileExistsError:
            st = os.lstat(self.path)
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or
                    st.st_nlink != 1 or st.st_mode & 0o077):
                raise Refusal("ledger_file_must_be_private_regular_file")
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=5.0)
        self.db.row_factory = sqlite3.Row
        if str(self.db.execute("PRAGMA journal_mode=PERSIST").fetchone()[0]).lower() != "persist":
            raise Refusal("ledger_journal_mode")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)

    # rate limits ------------------------------------------------------------
    def rate_check(self, kind: str, hourly: int, daily: int) -> None:
        now = self.clock()
        h = self.db.execute("SELECT count(*) FROM events WHERE kind=? AND ts>=?", (kind, now - 3600)).fetchone()[0]
        d = self.db.execute("SELECT count(*) FROM events WHERE kind=? AND ts>=?", (kind, now - 86400)).fetchone()[0]
        if h >= hourly or d >= daily:
            raise Refusal("rate_limit_reached")
        self.db.execute("INSERT INTO events(ts,kind) VALUES(?,?)", (now, kind))

    # missions ---------------------------------------------------------------
    def mission(self, cid: str) -> Optional[sqlite3.Row]:
        return self.db.execute("SELECT * FROM missions WHERE cid=?", (cid,)).fetchone()

    def add_mission(self, cid, source_island, source_agent, ref, sequence, env_sha, pay_sha, notes_sha, state, detail=None):
        now = self.clock()
        self.db.execute(
            "INSERT INTO missions(cid,source_island,source_agent,ref,sequence,envelope_sha256,payload_sha256,"
            "notes_sha256,state,detail,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, source_island, source_agent, ref, sequence, env_sha, pay_sha, notes_sha, state, detail, now, now))

    def set_mission(self, cid: str, state: str, task_id: Optional[str] = None, detail: Optional[str] = None) -> None:
        self.db.execute(
            "UPDATE missions SET state=?, task_id=COALESCE(?,task_id), detail=COALESCE(?,detail), updated=? WHERE cid=?",
            (state, task_id, detail, self.clock(), cid))

    # answers ----------------------------------------------------------------
    def answer(self, cid: str) -> Optional[sqlite3.Row]:
        return self.db.execute("SELECT * FROM answers WHERE cid=?", (cid,)).fetchone()

    def add_answer(self, cid: str, task_id: Optional[str], body: bytes, origin: str) -> None:
        now = self.clock()
        self.db.execute(
            "INSERT INTO answers(cid,task_id,body,body_sha256,origin,state,created,updated) VALUES(?,?,?,?,?,'admitting',?,?)",
            (cid, task_id, sqlite3.Binary(body), hashlib.sha256(body).hexdigest(), origin, now, now))

    def set_answer(self, cid: str, state: str, receipt: Optional[dict] = None, detail: Optional[str] = None) -> None:
        encoded = None if receipt is None else json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        self.db.execute(
            "UPDATE answers SET state=?, receipt_json=COALESCE(?,receipt_json), detail=COALESCE(?,detail), updated=? WHERE cid=?",
            (state, encoded, detail, self.clock(), cid))

    def mark_letter_completed(self, cid: str) -> None:
        self.db.execute("UPDATE answers SET letter_completed=1, updated=? WHERE cid=?", (self.clock(), cid))

    def admitting(self) -> List[sqlite3.Row]:
        return self.db.execute("SELECT * FROM answers WHERE state='admitting' ORDER BY created").fetchall()

    def admitted_needing_letter_completion(self) -> List[sqlite3.Row]:
        return self.db.execute(
            "SELECT a.cid AS cid, m.task_id AS task_id FROM answers a JOIN missions m ON m.cid=a.cid "
            "WHERE a.state='admitted' AND a.letter_completed=0 AND m.task_id IS NOT NULL ORDER BY a.created").fetchall()

    # refusals (recorded once per task+code+notes) ---------------------------
    def refuse_once(self, task_id: str, cid: Optional[str], code: str, notes: object) -> bool:
        digest = hashlib.sha256(notes.encode("utf-8", "replace") if isinstance(notes, str) else b"\x00none").hexdigest()
        try:
            self.db.execute("INSERT INTO refusals(task_id,cid,code,notes_sha256,first_seen) VALUES(?,?,?,?,?)",
                            (task_id, cid, code, digest, self.clock()))
            return True
        except sqlite3.IntegrityError:
            return False


# --------------------------------------------------------------------------- pure helpers

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pages(tasks: TasksTransport, list_id: str) -> Iterator[dict]:
    token = None
    seen = set()
    while True:
        rows, nxt = tasks.list_tasks(list_id, token, max_results=100, show_completed=True, show_hidden=True)
        for row in rows:
            yield row
        if not nxt:
            return
        if nxt in seen or nxt == token:
            raise Refusal("pagination_token_cycle")
        seen.add(nxt)
        token = nxt


def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key")
        out[key] = value
    return out


def parse_mission_payload(payload: bytes) -> Tuple[dict, bytes]:
    """Mirror of installed validate_mission_payload. Returns (request, trailing_body)."""
    if type(payload) is not bytes or len(payload) < 6 or len(payload) > MAX_MISSION_PAYLOAD_BYTES:
        raise Refusal("payload_size_invalid")
    size = int.from_bytes(payload[:4], "big")
    if size < 2 or size > MAX_REQUEST_BYTES or size > len(payload) - 4:
        raise Refusal("payload_request_length_invalid")
    raw = payload[4:4 + size]
    try:
        request = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
        canonical = json.dumps(request, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError):
        raise Refusal("payload_request_invalid")
    if (canonical != raw or type(request) is not dict or frozenset(request) != REQUEST_FIELDS or
            request["to"] != RECEIVER or request["purpose"] != "queue_task" or
            type(request["hop"]) is not int or request["hop"] != 1 or request["parent"] is not None or
            type(request["ref"]) is not str or not REPORT_REF_RE.fullmatch(request["ref"])):
        raise Refusal("payload_request_invalid")
    return request, payload[4 + size:]


def render_letter(cid: str, source_agent: str, ref: str, body_text: str) -> str:
    """Letter text shown to Gemini. Plain data; it grants no authority."""
    return ("CROSSROAD LETTER\nid: " + cid + "\nfrom: " + source_agent + "\nref: " + ref +
            "\npurpose: queue_task\n--\n" + body_text)


def fenced_notes(text: str) -> str:
    notes = "```text\n" + text + "\n```"
    if len(notes) > MAX_NOTES_CHARS:
        raise Refusal("letter_exceeds_8192_notes_chars")
    return notes


def parse_answer_notes(notes: object) -> bytes:
    """Strict: the notes are exactly one fenced block. Returns the exact body bytes."""
    if not isinstance(notes, str):
        raise Refusal("notes_missing")
    if len(notes) > MAX_NOTES_CHARS:
        raise Refusal("notes_exceed_8192_chars")
    if "\r" in notes:
        raise Refusal("notes_contain_carriage_return")
    if "\x00" in notes:
        raise Refusal("notes_contain_nul")
    match = FENCED.fullmatch(notes)
    if not match:
        raise Refusal("notes_not_one_fenced_body")
    body = match.group(1)
    if not body.strip():
        raise Refusal("answer_body_empty")
    try:
        data = body.encode("utf-8")
    except UnicodeEncodeError:
        raise Refusal("answer_not_valid_unicode")        # lone surrogate: JSON from Google can carry one
    if len(data) > MAX_RESULT_BYTES:
        raise Refusal("answer_exceeds_result_bytes")
    return data


def screen_letter_body(body_text: str) -> None:
    """D3/D6: refuse, never rewrite. These bytes are never sent to Google."""
    if "\x00" in body_text:
        raise Refusal("letter_body_contains_nul")
    if "\r" in body_text:
        raise Refusal("letter_body_contains_carriage_return")
    if any(ord(ch) < 0x20 and ch not in "\n\t" for ch in body_text):
        raise Refusal("letter_body_control_characters")
    if "```" in body_text:
        raise Refusal("letter_body_contains_fence")     # would close the fence Gemini is told to trust


def acquire_lock(path: str) -> int:
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        raise Refusal("another_run_holds_the_lock")
    return fd


# ---- owner actions: ledger only, no Tasks, no mail port. Each is logged. Nothing is deleted.
def _owner_log(ledger: "Ledger", action: str, cid: str, note: str) -> None:
    if not isinstance(note, str) or not note.strip():
        raise Refusal("owner_note_required")
    ledger.db.execute("INSERT INTO owner_log(ts,action,cid,note) VALUES(?,?,?,?)", (ledger.clock(), action, cid, note))


def owner_release_blocked(ledger: "Ledger", cid: str, note: str) -> None:
    """After a human looked at the Tasks list and saw no Letter task for this CID: allow ONE fresh insert."""
    row = ledger.mission(cid)
    if row is None or row["state"] != "blocked_ambiguous":
        raise Refusal("nothing_to_release")
    _owner_log(ledger, "release_blocked", cid, note)
    ledger.set_mission(cid, "claimed", detail="released by owner: " + note)


def owner_choose_answer(ledger: "Ledger", cid: str, task_id: str, note: str) -> None:
    """Pick which of several Answer tasks counts. Only before any answer for the CID is stored. Other tasks stay."""
    if ledger.mission(cid) is None or ledger.answer(cid) is not None or not task_id:
        raise Refusal("nothing_to_choose")
    _owner_log(ledger, "choose_answer:" + task_id, cid, note)
    ledger.db.execute("INSERT OR REPLACE INTO owner_choices(cid,task_id,note,created) VALUES(?,?,?,?)",
                      (cid, task_id, note, ledger.clock()))


def owner_reset_held(ledger: "Ledger", cid: str, note: str) -> None:
    """Put an answer held for the owner back into the retry queue (same stored bytes)."""
    row = ledger.answer(cid)
    if row is None or row["state"] != "held_for_owner":
        raise Refusal("nothing_to_reset")
    _owner_log(ledger, "reset_held", cid, note)
    ledger.set_answer(cid, "admitting", detail="reset by owner")


# --------------------------------------------------------------------------- bridge

class Bridge(object):
    def __init__(self, config: Config, tasks: TasksTransport, port: MailPort):
        if config.tasks_list_id != DEFAULT_TASKS_LIST_ID:
            raise Refusal("bridge_restricted_to_default_list")
        self.c = config
        self.tasks = tasks
        self.port = port
        self.ledger = Ledger(config.db_path, config.clock)
        self._lock_path = os.path.join(os.path.dirname(os.path.abspath(config.db_path)), "run.lock")
        self._lock_fd = None

    # -- single-runner lock (ledger parent is a private 0700 directory) -------
    def _acquire(self) -> None:
        self._lock_fd = acquire_lock(self._lock_path)

    def _release(self) -> None:
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None

    def run_once(self) -> dict:
        self._acquire()
        try:
            exported = self._export_pending()
            collected = self._collect_answers()
            return {"export": exported, "collect": collected}
        finally:
            self._release()

    def export_pending(self) -> List[dict]:
        self._acquire()
        try:
            return self._export_pending()
        finally:
            self._release()

    def collect_answers(self) -> List[dict]:
        self._acquire()
        try:
            return self._collect_answers()
        finally:
            self._release()

    # ===================================================================== export
    def _export_pending(self) -> List[dict]:
        results = []
        for _ in range(self.c.max_export_per_run):
            try:
                head = self.port.read_head()
            except PortError as exc:
                if exc.halt:
                    raise HaltRun(exc.code)
                results.append({"status": "port_error", "code": exc.code})
                break
            if head is None:
                break
            result = self._export_one(head)
            results.append(result)
            if result["status"] not in ("exported", "refused_letter_replied", "refused_letter_reply_pending"):
                break          # FIFO mailbox: a head that is not cleared blocks the letters behind it
        return results

    def _check_head(self, head: dict) -> None:
        if (not isinstance(head, dict) or not isinstance(head.get("call_id"), str) or
                not CALL_ID_RE.fullmatch(head["call_id"]) or head.get("destination_agent") != RECEIVER or
                not isinstance(head.get("source_agent"), str) or not NAME_RE.fullmatch(head["source_agent"]) or
                not isinstance(head.get("source_island"), str) or not NAME_RE.fullmatch(head["source_island"]) or
                not isinstance(head.get("payload"), bytes) or
                head.get("payload_sha256") != sha256_hex(head["payload"])):
            raise Refusal("head_letter_shape_invalid")

    def _ack(self, cid: str) -> Optional[dict]:
        """Returns None when acked, else a result dict (the head stays unacked and is retried)."""
        try:
            self.port.ack(cid)
        except PortError as exc:
            if exc.halt:
                raise HaltRun(exc.code)
            return {"cid": cid, "status": "ack_pending", "code": exc.code}
        return None

    def _export_one(self, head: dict) -> dict:
        try:
            self._check_head(head)
        except Refusal as exc:
            return {"cid": head.get("call_id") if isinstance(head, dict) else None,
                    "status": "invalid_head", "code": exc.code}
        cid = head["call_id"]
        env_sha = str(head.get("envelope_sha256") or "")
        pay_sha = head["payload_sha256"]
        old = self.ledger.mission(cid)
        if old is not None:
            if (old["source_agent"] != head["source_agent"] or old["source_island"] != head["source_island"] or
                    old["payload_sha256"] != pay_sha or old["envelope_sha256"] != env_sha):
                self.ledger.set_mission(cid, "conflict", detail="head letter differs from ledger")
                return {"cid": cid, "status": "conflict", "code": "head_differs_from_ledger"}
            return self._resume(cid, old, head)
        # new letter -----------------------------------------------------
        # The dropbox port flags what it could not verify or what is about to expire. Both are refused WITH a reply to the sender.
        if head.get("body_token_verified") is False:
            return self._refuse_unexportable(cid, head, env_sha, pay_sha, "letter_body_not_verifiable")
        if head.get("expired") is True:
            return self._refuse_unexportable(cid, head, env_sha, pay_sha, "mission_expired")
        try:
            request, notes = self._build(cid, head)
        except (Refusal, UnicodeError) as exc:
            code = exc.code if isinstance(exc, Refusal) else "body_not_utf8"
            return self._refuse_unexportable(cid, head, env_sha, pay_sha, code)
        try:
            self.ledger.rate_check("letter", self.c.max_per_hour, self.c.max_per_day)
        except Refusal as exc:
            return {"cid": cid, "status": "rate_limited", "code": exc.code}
        self.ledger.add_mission(cid, head["source_island"], head["source_agent"], request["ref"], head.get("sequence"),
                                env_sha, pay_sha, sha256_hex(notes.encode("utf-8")), "claimed")
        return self._resume(cid, self.ledger.mission(cid), head, notes=notes)

    def _build(self, cid: str, head: dict) -> Tuple[dict, str]:
        request, body = parse_mission_payload(head["payload"])
        body_text = body.decode("utf-8", "strict") if body else "(no body)"
        screen_letter_body(body_text)
        return request, fenced_notes(render_letter(cid, head["source_agent"], request["ref"], body_text))

    def _notes_for(self, cid: str, head: dict) -> str:
        return self._build(cid, head)[1]

    def _resume(self, cid: str, row: sqlite3.Row, head: dict, notes: Optional[str] = None) -> dict:
        state = row["state"]
        if state in ("conflict", "blocked_ambiguous"):
            return {"cid": cid, "status": state, "code": row["detail"] or state}
        if state in ("refused_unexportable", "refused_acked"):
            return self._finish_refusal(cid, row)
        if state == "acked":
            return {"cid": cid, "status": "conflict", "code": "ledger_says_acked_but_letter_is_still_head"}
        if notes is None:
            try:
                notes = self._notes_for(cid, head)
            except (Refusal, UnicodeError):
                return {"cid": cid, "status": "conflict", "code": "ledger_letter_not_renderable"}
        if sha256_hex(notes.encode("utf-8")) != row["notes_sha256"]:
            self.ledger.set_mission(cid, "conflict", detail="rendered letter differs from ledger")
            return {"cid": cid, "status": "conflict", "code": "rendered_letter_differs_from_ledger"}
        if state in ("claimed", "insert_attempted"):
            found = [t for t in pages(self.tasks, self.c.tasks_list_id) if t.get("title") == "Letter " + cid]
            matching = [t for t in found if t.get("notes") == notes]
            if len(found) > 1:
                self.ledger.set_mission(cid, "blocked_ambiguous", detail="several Letter tasks carry this id")
                return {"cid": cid, "status": "blocked_ambiguous", "code": "several_letter_tasks_for_one_cid"}
            if found and not matching:
                self.ledger.set_mission(cid, "blocked_ambiguous", detail="a Letter task with other notes exists")
                return {"cid": cid, "status": "blocked_ambiguous", "code": "letter_title_exists_with_other_notes"}
            if matching:
                self.ledger.set_mission(cid, "exported", task_id=matching[0]["id"])
            elif state == "insert_attempted":
                self.ledger.set_mission(cid, "blocked_ambiguous", detail="earlier insert outcome unknown and no task is visible")
                return {"cid": cid, "status": "blocked_ambiguous", "code": "earlier_insert_outcome_unknown"}
            else:
                self.ledger.set_mission(cid, "insert_attempted")          # durable BEFORE the call
                try:
                    task = self.tasks.insert_task(self.c.tasks_list_id, {"title": "Letter " + cid, "notes": notes, "status": "needsAction"})
                except NotSent as exc:
                    # nothing left the machine: safe to try again on the next run
                    self.ledger.set_mission(cid, "claimed", detail="insert not sent: " + type(exc).__name__)
                    return {"cid": cid, "status": "insert_not_sent", "code": type(exc).__name__}
                except Exception as exc:
                    # outcome unknown: the row stays insert_attempted; the next run looks first and never re-inserts blind
                    return {"cid": cid, "status": "insert_outcome_unknown", "code": type(exc).__name__}
                self.ledger.set_mission(cid, "exported", task_id=task["id"])
        pending = self._ack(cid)
        if pending is not None:
            return pending
        self.ledger.set_mission(cid, "acked")
        return {"cid": cid, "status": "exported", "task_id": self.ledger.mission(cid)["task_id"]}

    def _refuse_unexportable(self, cid: str, head: dict, env_sha: str, pay_sha: str, code: str) -> dict:
        if not self.c.refuse_unexportable_with_reply:
            return {"cid": cid, "status": "unexportable_head_blocks_queue", "code": code}
        self.ledger.add_mission(cid, head["source_island"], head["source_agent"], None, head.get("sequence"),
                                env_sha, pay_sha, None, "refused_unexportable", detail=code)
        return self._finish_refusal(cid, self.ledger.mission(cid))

    def _finish_refusal(self, cid: str, row: sqlite3.Row) -> dict:
        if row["state"] == "refused_unexportable":
            pending = self._ack(cid)
            if pending is not None:
                return pending
            self.ledger.set_mission(cid, "refused_acked")
        if self.ledger.answer(cid) is None:
            text = "GEMINI_COULD_NOT_RECEIVE_LETTER\nreason: " + str(row["detail"]) + "\n"
            self.ledger.add_answer(cid, None, text.encode("utf-8"), "export_refusal")
        outcome = self._admit(cid)
        status = "refused_letter_replied" if outcome["status"] == "admitted" else "refused_letter_reply_pending"
        return {"cid": cid, "status": status, "code": row["detail"], "reply": outcome["status"]}

    def owner_release_blocked(self, cid: str, owner_note: str) -> None:
        owner_release_blocked(self.ledger, cid, owner_note)

    def owner_choose_answer(self, cid: str, task_id: str, owner_note: str) -> None:
        owner_choose_answer(self.ledger, cid, task_id, owner_note)

    def owner_reset_held(self, cid: str, owner_note: str) -> None:
        owner_reset_held(self.ledger, cid, owner_note)

    # ==================================================================== collect
    def _collect_answers(self) -> List[dict]:
        results: List[dict] = []
        # 0. D1: a pickup whose acknowledgement committed but whose answer was lost must not strand the CID
        self._reconcile_acks(results)
        # A. retry admissions that are durable but unconfirmed (no Tasks read needed)
        for row in self.ledger.admitting():
            results.append(self._guard(row["cid"], lambda row=row: self._admit(row["cid"])))
        # B. read the list once and judge every Answer task on its own
        by_cid: Dict[str, List[dict]] = {}
        for task in pages(self.tasks, self.c.tasks_list_id):
            title = task.get("title")
            if not isinstance(title, str):
                continue
            match = ANSWER_TITLE.fullmatch(title)
            if match:
                by_cid.setdefault(match.group(1), []).append(task)
            elif NEAR_MISS_ANSWER.match(title) and not LETTER_TITLE.fullmatch(title):
                tid = str(task.get("id"))
                if self.ledger.refuse_once(tid, None, "answer_title_not_exact", task.get("notes")):
                    results.append({"task_id": tid, "status": "refused", "code": "answer_title_not_exact"})
        for cid, group in by_cid.items():
            # D2: whatever one item does, the others still run (a run-wide HaltRun is the only exception)
            result = self._guard(cid, lambda cid=cid, group=group: self._judge(cid, group))
            results.extend(result if isinstance(result, list) else [result])
        # C. mark Letter tasks completed once their answer is durably admitted
        for row in self.ledger.admitted_needing_letter_completion():
            try:
                self.tasks.complete_task(self.c.tasks_list_id, row["task_id"])
            except Exception as exc:
                results.append({"cid": row["cid"], "status": "letter_completion_pending", "code": type(exc).__name__})
                continue
            self.ledger.mark_letter_completed(row["cid"])
            results.append({"cid": row["cid"], "status": "letter_completed"})
        return results

    def _guard(self, cid: str, action):
        try:
            return action()
        except HaltRun:
            raise
        except Exception as exc:
            return {"cid": cid, "status": "item_error", "code": type(exc).__name__}

    def _reconcile_acks(self, results: List[dict]) -> None:
        """FIFO fact: only the head can be acknowledged, so a CID that was exported and is no longer the head was picked up.
        Covers an ack that committed while its answer was lost (port_exception, timeout)."""
        rows = self.ledger.db.execute(
            "SELECT m.cid AS cid, m.state AS state FROM missions m LEFT JOIN answers a ON a.cid=m.cid "
            "WHERE m.state IN ('exported','refused_unexportable') OR (m.state='refused_acked' AND a.cid IS NULL) "
            "ORDER BY m.created").fetchall()
        if not rows:
            return
        try:
            head = self.port.read_head()
        except PortError as exc:
            if exc.halt:
                raise HaltRun(exc.code)
            return
        head_cid = head.get("call_id") if isinstance(head, dict) else None
        for row in rows:
            cid, state = row["cid"], row["state"]
            if head_cid == cid:
                pending = self._ack(cid)          # still at the head: the earlier ack did not commit; try again
                if pending is not None:
                    results.append(pending)
                    continue
            if state == "exported":
                self.ledger.set_mission(cid, "acked")
                results.append({"cid": cid, "status": "pickup_reconciled"})
            else:
                if state == "refused_unexportable":
                    self.ledger.set_mission(cid, "refused_acked")
                results.append(self._guard(cid, lambda cid=cid: self._finish_refusal(cid, self.ledger.mission(cid))))

    def _refuse(self, task: dict, cid: Optional[str], code: str) -> dict:
        tid = str(task.get("id"))
        fresh = self.ledger.refuse_once(tid, cid, code, task.get("notes"))
        return {"cid": cid, "task_id": tid, "status": "refused", "code": code, "new": fresh}

    def _judge(self, cid: str, group: List[dict]) -> List[dict]:
        out: List[dict] = []
        mission = self.ledger.mission(cid)
        if mission is None or mission["state"] not in ("exported", "acked"):
            return [self._refuse(t, cid, "unknown_cid") for t in group]
        known = self.ledger.answer(cid)
        if len(group) > 1:
            keep = [t for t in group if known is not None and known["task_id"] == t.get("id")]
            if not keep and known is None:           # D5: the owner may have named the one that counts
                choice = self.ledger.db.execute("SELECT task_id FROM owner_choices WHERE cid=?", (cid,)).fetchone()
                if choice is not None:
                    keep = [t for t in group if t.get("id") == choice["task_id"]]
            for t in group:
                if t not in keep:
                    out.append(self._refuse(t, cid, "duplicate_answer" if keep else "ambiguous_duplicate_answers"))
            if not keep:
                return out
            group = keep
        task = group[0]
        try:
            data = parse_answer_notes(task.get("notes"))
        except (Refusal, UnicodeError) as exc:
            code = exc.code if isinstance(exc, Refusal) else "answer_not_valid_unicode"
            out.append(self._refuse(task, cid, code))
            if known is None:
                out.extend(self._reply_answer_refused(cid, task, code, mission))
            return out
        if known is not None:
            if known["task_id"] != task.get("id"):
                out.append(self._refuse(task, cid, "answer_task_replaced"))
            elif known["body_sha256"] != sha256_hex(data):
                out.append(self._refuse(task, cid, "answer_changed_after_receipt"))
            return out
        if mission["state"] != "acked":
            out.append({"cid": cid, "status": "waiting_pickup_ack"})
            return out
        try:
            self.ledger.rate_check("admission", self.c.max_per_hour, self.c.max_per_day)
        except Refusal as exc:
            out.append({"cid": cid, "status": "rate_limited", "code": exc.code})
            return out
        self.ledger.add_answer(cid, task["id"], data, "gemini_task")          # exact bytes durable BEFORE the call
        out.append(self._admit(cid))
        return out

    # The caller must not be left waiting: a content refusal of Gemini's Answer sends the original caller ONE refusal reply
    # through the normal reply path (fixed code, none of Gemini's text), and the Letter is then completed so Gemini stops.
    ANSWER_REFUSAL_CODES = {"answer_exceeds_result_bytes": "gemini_answer_too_long", "notes_exceed_8192_chars": "gemini_answer_too_long"}

    def _reply_answer_refused(self, cid: str, task: dict, code: str, mission: sqlite3.Row) -> List[dict]:
        if mission["state"] != "acked":
            return [{"cid": cid, "status": "waiting_pickup_ack"}]
        try:
            self.ledger.rate_check("admission", self.c.max_per_hour, self.c.max_per_day)
        except Refusal as exc:
            return [{"cid": cid, "status": "rate_limited", "code": exc.code}]
        reply_code = self.ANSWER_REFUSAL_CODES.get(code, "gemini_answer_invalid")
        text = "GEMINI_ANSWER_REFUSED\nreason: " + reply_code + "\n"
        self.ledger.add_answer(cid, str(task.get("id")), text.encode("utf-8"), "answer_refusal")        # durable BEFORE the call
        outcome = self._admit(cid)
        return [dict(outcome, via_refusal_reply=reply_code)]

    def _admit(self, cid: str) -> dict:
        row = self.ledger.answer(cid)
        mission = self.ledger.mission(cid)
        if row is None or mission is None:
            return {"cid": cid, "status": "refused", "code": "no_ledger_row"}
        if row["state"] == "admitted":
            return {"cid": cid, "status": "admitted", "replay": "ledger"}
        if row["state"] != "admitting":
            return {"cid": cid, "status": row["state"], "code": row["detail"]}
        try:
            out = self.port.reply(cid, mission["source_agent"], bytes(row["body"]))
        except PortError as exc:
            if exc.halt:
                raise HaltRun(exc.code)
            if exc.retryable:
                self.ledger.set_answer(cid, "admitting", detail=exc.code)
                return {"cid": cid, "status": "retry_later", "code": exc.code}
            if exc.permanent:
                self.ledger.set_answer(cid, "rejected", detail=exc.code)
                return {"cid": cid, "status": "rejected_by_core", "code": exc.code}
            # D4: a code this packet does not know is not proof the answer is bad. Keep the bytes, stop retrying, ask the owner.
            self.ledger.set_answer(cid, "held_for_owner", detail=exc.code)
            return {"cid": cid, "status": "held_for_owner", "code": exc.code}
        except Exception as exc:                                              # unknown outcome: keep bytes, retry
            self.ledger.set_answer(cid, "admitting", detail="port_exception:" + type(exc).__name__)
            return {"cid": cid, "status": "retry_later", "code": "port_exception"}
        if not (isinstance(out, dict) and out.get("status") == "result_admitted" and out.get("call_id") == cid):
            self.ledger.set_answer(cid, "admitting", detail="reply_receipt_invalid")
            return {"cid": cid, "status": "retry_later", "code": "reply_receipt_invalid"}
        self.ledger.set_answer(cid, "admitted", receipt=out)
        return {"cid": cid, "status": "admitted", "replay": out.get("replay"),
                "original_source_agent": mission["source_agent"], "original_source_island": mission["source_island"],
                "via": "gemini", "channel_claim": "Google Tasks"}
