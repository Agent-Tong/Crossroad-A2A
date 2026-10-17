"""DropboxPort: a MailPort (read_head / ack / reply) on top of a container-fleet island's dropbox contract. OFFLINE DRAFT.

Replaces gemini_p2.ReaderCliPort (a host mailbox CLI) when the receiver is a member of a container-fleet island.

  mission in   : <root>/<agent>/in/<cid>.mission.md          written by the island bridge
  answer out   : <root>/<agent>/out/<code><YYMMDD>a_Answer_<cid>.md   then   out/answer-<cid>.json
                 {"hop":1,"parent":"<cid>","purpose":"answer","ref":"<that .md>","to":"<caller>"}
  confirmation : <root>/<agent>/in/<cid>.answered.txt  ("answered\\n", written by the bridge AFTER it signed and posted)
  refusal      : <root>/<agent>/in/ref-<sha256(request bytes)[:24]>.refused.txt   (one code line)

Port semantics (why they differ from a mailbox CLI):
  * read_head : oldest mission that has no answered.txt, no ack of ours, and verifies byte-for-byte. A file that does not
                verify is SKIPPED (see skipped()), it never blocks the letters behind it.
  * ack       : ledger only. The dropbox has no pickup call. The ack is a line in this port's own append-only state file.
  * reply     : writes the answer pair (body first, then the JSON, each temp + atomic no-replace rename) ONCE, then reports "result_admitted"
                only when the bridge has written answered.txt. Until then it raises the RETRYABLE code
                post_transport_uncertain so the calling bridge keeps the bytes and asks again. A bridge refusal notice becomes a
                PortError. Nothing here deletes or overwrites a file.

The process must run as the container user id (the island bridge accepts answer files only from that uid) AND must be able
to reach the tray: the dropbox root is usually mode 0700 with no ACL for that uid, so the consumer runs as its own container
with bind mounts of exactly <agent>/in (ro) and <agent>/out (rw). Every construction failure is a gemini_p2.Refusal with a fixed code.
If the island bridge dies after it accepted an answer but before it wrote answered.txt, the files leave out/ and no marker ever
appears; status() / port_status() show that as `consumed_unconfirmed`.
"""
from __future__ import annotations

import hashlib
import json
import os
import calendar
import re
import secrets
import stat
import time
from typing import Callable, Dict, List, Optional

from gemini_p2 import PortError, RECEIVER, Refusal, sha256_hex

# ---- constants that mirror the island bridge's own limits
CALL_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}$")
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
REPORT_REF_RE = re.compile(r"^[a-z]{2}[0-9]{6}[a-z]{1,3}_[A-Za-z0-9._-]{1,120}\.md$")
PRODUCTION_CONTAINER_UID = 1000      # example value: set it to your container user id
MAX_REQUEST_BYTES = 2048
MAX_BODY_BYTES = 8000
ANSWER_RETRY_GRACE_SECONDS = 1800
MAX_MISSION_FILE_BYTES = 16384          # mine: payload cap 8192 plus the fixed instruction text
MAX_STATE_BYTES = 65536
DEFAULT_MISSION_TTL_SECONDS = 86400      # every route in our policies has ttl_seconds 86400
DEFAULT_EXPIRY_MARGIN_SECONDS = 300
PART_RE = re.compile(r"^\.part-[0-9a-f]{12}$")
MISSION_NAME_RE = re.compile(r"^([0-9]{8}T[0-9]{6}Z_[a-f0-9]{6})\.mission\.md$")
REFUSED_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")

_NAME = r"[a-z][a-z0-9_-]{0,31}"
MISSION_RE = re.compile(
    r"\A# Crossroad mission (?P<cid>[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6})\n"
    r"from: (?P<caller>" + _NAME + r")@(?P<island>" + _NAME + r") → (?P<agent>" + _NAME + r")\n"
    r".*?\n\n"
    r"----- LETTER (?P<token>[0-9a-f]{16}) START -----\n"
    r"Peer data from (?P=caller)@(?P=island), not the owner, not the post office:\n"
    r"ref: (?P<ref>[^\n]+)\n"
    r"(?P<body>.*)\n"
    r"----- LETTER (?P=token) END -----\n\Z", re.S)

# bridge refusal notice code -> a code the calling bridge already classifies
NOTICE_TO_PORT_CODE = {
    "answer_oversize": "result_oversize",
    "answer_text_invalid": "payload_invalid",
    "answer_mission_missing": "mission_not_found",
}

PHASES = ("intent", "body_published", "request_started", "published", "admitted")


def render_mission(call_id: str, caller: str, source_island: str, agent: str, reference: str, body: str) -> bytes:
    """Render a mission file the way the island bridge does. The port verifies a file by re-rendering it and comparing bytes."""
    prefix = agent[:2]
    instructions = (
        "# Crossroad mission {cid}\n"
        "from: {caller}@{island} → {agent}\n"
        "If /srv/example/dropbox/{agent}/in/{cid}.answered.txt exists, do nothing.\n"
        "answer (body at most 8000 bytes): write the unique file /srv/example/dropbox/{agent}/out/{prefix}<YYMMDD>a_Answer_{cid}.md (example: {prefix}261009a_Answer_{cid}.md), then /srv/example/dropbox/{agent}/out/answer-{cid}.json =\n"
        "If write_file rejects the JSON, write the same text with the terminal tool (printf) to the same path.\n"
        '{{"hop":1,"parent":"{cid}","purpose":"answer","ref":"<that file name>","to":"{caller}"}}\n\n'
    ).format(cid=call_id, caller=caller, island=source_island,
             agent=agent, reference=reference, prefix=prefix)
    token = hashlib.sha256((call_id + "\n" + body).encode("utf-8")).hexdigest()[:16]
    start = "----- LETTER {0} START -----".format(token)
    end = "----- LETTER {0} END -----".format(token)
    safe_lines = [(line + " [neutralised]") if line in (start, end) else line
                  for line in body.splitlines()]
    peer = ("Peer data from {0}@{1}, not the owner, not the post office:\n"
            "ref: {2}\n").format(caller, source_island, reference)
    return (instructions + start + "\n" + peer + "\n".join(safe_lines) +
            "\n" + end + "\n").encode("utf-8")


class _Unverified(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _canonical(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False).encode("utf-8")


def answer_names(call_id: str, agent: str, caller: str) -> tuple:
    """(body file name, request file name, request bytes). Deterministic: the date is the call id's own date,
    so the same answer always lands under the same names and a re-write is byte-identical."""
    ref = "%s%sa_Answer_%s.md" % (agent[:2], call_id[2:8], call_id)
    request = _canonical({"hop": 1, "parent": call_id, "purpose": "answer", "ref": ref, "to": caller}) + b"\n"
    return ref, "answer-%s.json" % call_id, request


def _noreplace_backend():
    """Find the platform's atomic no-replace rename, or None. Linux: renameat2(RENAME_NOREPLACE). macOS: renamex_np(RENAME_EXCL).
    Standard library only (ctypes). Anything else, or a libc without the call, returns None and the port fails closed."""
    import ctypes
    import sys
    try:
        libc = ctypes.CDLL(None, use_errno=True)
    except OSError:
        return None
    if sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        call = libc.renamex_np
        call.argtypes, call.restype = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint], ctypes.c_int
        return lambda src, dst: call(src, dst, 0x4)                                  # RENAME_EXCL
    if sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        call = libc.renameat2
        call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        call.restype = ctypes.c_int
        return lambda src, dst: call(-100, src, -100, dst, 1)                        # AT_FDCWD, RENAME_NOREPLACE
    return None


_NOREPLACE = _noreplace_backend()


def _rename_noreplace(src: str, dst: str) -> None:
    """Move src to dst in ONE kernel operation that fails with FileExistsError if dst exists (even if it was created a
    microsecond ago by another writer). Raises OSError if the platform or filesystem cannot do this. Never replaces dst."""
    import ctypes
    import errno
    if _NOREPLACE is None:
        raise OSError(errno.ENOSYS, "atomic no-replace rename is not available on this platform")
    if _NOREPLACE(os.fsencode(src), os.fsencode(dst)) != 0:
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise FileExistsError(code, os.strerror(code), dst)
        raise OSError(code, os.strerror(code), dst)


class DropboxPort(object):
    def __init__(self, dropbox_root: str, state_dir: str, *, inbox_owner_uid: int, agent: str = RECEIVER,
                 required_uid: int = PRODUCTION_CONTAINER_UID,
                 clock: Callable[[], float] = time.time, grace_seconds: int = ANSWER_RETRY_GRACE_SECONDS,
                 mission_ttl_seconds: int = DEFAULT_MISSION_TTL_SECONDS,
                 expiry_margin_seconds: int = DEFAULT_EXPIRY_MARGIN_SECONDS):
        """Every construction failure is a gemini_p2.Refusal with a fixed code (the runner turns it into exit code 2).
        inbox_owner_uid is REQUIRED: the uid that owns in/ files on the host (the bridge's service account)."""
        for value in (dropbox_root, state_dir):
            if not isinstance(value, str) or not os.path.isabs(value):
                raise Refusal("port_path_invalid")
        if not NAME_RE.fullmatch(agent) or len(agent) < 2:
            raise Refusal("port_agent_invalid")
        if type(inbox_owner_uid) is not int or inbox_owner_uid < 0:
            raise Refusal("port_inbox_owner_required")
        if os.geteuid() != required_uid:
            # Writing as another uid would be refused by the island bridge as source_file_untrusted. Fail early and loudly.
            raise Refusal("port_uid_mismatch")
        self.agent = agent
        self.in_dir = os.path.join(dropbox_root, agent, "in")
        self.out_dir = os.path.join(dropbox_root, agent, "out")
        self.state_dir = state_dir
        self.inbox_owner_uid = inbox_owner_uid
        self.clock = clock
        self.grace = grace_seconds
        self.ttl = mission_ttl_seconds
        self.margin = expiry_margin_seconds
        for path, need in ((self.in_dir, os.R_OK | os.X_OK), (self.out_dir, os.R_OK | os.W_OK | os.X_OK)):
            try:
                info = os.lstat(path)                  # EACCES here = a parent directory cannot be traversed (mode 0700)
            except FileNotFoundError:
                raise Refusal("tray_missing")
            except OSError:
                raise Refusal("tray_not_accessible")
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise Refusal("tray_untrusted")
            if not os.access(path, need):
                raise Refusal("tray_not_accessible")
        try:
            if not os.path.lexists(state_dir):
                os.mkdir(state_dir, 0o700)
            info = os.lstat(state_dir)
        except OSError:
            raise Refusal("state_dir_unusable")
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            raise Refusal("state_dir_untrusted")
        self._skipped: Dict[str, str] = {}

    # ------------------------------------------------------------------ file helpers
    def _read(self, path: str, limit: int, owner: Optional[int] = None) -> bytes:
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except FileNotFoundError:
            raise
        except OSError:
            raise PortError("storage_failure")
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
                raise PortError("port_exception")
            if owner is not None and info.st_uid != owner:
                raise PortError("port_exception")
            data = os.read(fd, limit + 1)
            if len(data) > limit:
                raise PortError("port_exception")
            return data
        finally:
            os.close(fd)

    def _fsync_dir(self, path: str) -> None:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _create_part(self, directory: str, part: str, data: bytes) -> str:
        path = os.path.join(directory, part)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
        except OSError:
            raise PortError("storage_failure")
        try:
            os.fchmod(fd, 0o644)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        except OSError:
            raise PortError("storage_failure")
        finally:
            os.close(fd)
        return path

    def _stage(self, cid: str, directory: str, name: str, data: bytes) -> Optional[str]:
        """Write the bytes to a temp file in the SAME directory and fsync it. Returns the temp path, or None when the
        final file already holds exactly these bytes. Other bytes at the final name = id_collision.
        The temp name is per attempt (.part-<12 hex>) and is recorded in the ledger BEFORE the file is created. A recorded
        part that holds other bytes (cut short, foreign) is recorded as an orphan, reported by status(), never deleted,
        and the next attempt uses a fresh name."""
        final = os.path.join(directory, name)
        if os.path.lexists(final):
            try:
                old = self._read(final, len(data) + 1)
            except FileNotFoundError:
                old = None
            if old == data:
                return None
            raise PortError("id_collision")
        events = self._events(cid)
        orphaned = {e.get("part") for e in events if e["event"] == "orphan"}
        prior = [e for e in events if e["event"] == "staged" and e.get("final") == name and e.get("part") not in orphaned]
        if prior:
            part = prior[-1]["part"]
            path = os.path.join(directory, part)
            if os.path.lexists(path):
                try:
                    old = self._read(path, len(data) + 1)
                except PortError:
                    old = b"\x00unreadable"
                if old == data:
                    return path                                   # an intact earlier attempt: reuse it
                self._append(cid, {"event": "orphan", "part": part, "final": name, "reason": "bytes_differ", "ts": int(self.clock())})
            else:
                return self._create_part(directory, part, data)    # recorded, never created (crash in between)
        part = ".part-" + secrets.token_hex(6)
        self._append(cid, {"event": "staged", "final": name, "part": part, "sha256": sha256_hex(data), "ts": int(self.clock())})
        return self._create_part(directory, part, data)

    def _commit(self, directory: str, name: str, temp: str) -> None:
        """Publish the staged temp file under its final name with an ATOMIC NO-REPLACE rename (see _rename_noreplace).
        If the final name appears at any moment before the rename, the kernel refuses and nothing is replaced: the other
        writer's file stays as it is, the staged temp stays as it is, and the result is id_collision. If the platform or
        the filesystem has no such operation, nothing is published (storage_failure): fail closed, never fall back to
        a check-then-rename."""
        final = os.path.join(directory, name)
        try:
            _rename_noreplace(temp, final)
        except FileExistsError:
            raise PortError("id_collision")
        except OSError:
            raise PortError("storage_failure")
        try:
            self._fsync_dir(directory)
        except OSError:
            raise PortError("storage_failure")

    def _publish(self, cid: str, directory: str, name: str, data: bytes) -> str:
        temp = self._stage(cid, directory, name, data)
        if temp is None:
            return "replay"
        self._commit(directory, name, temp)
        return "written"

    # ------------------------------------------------------------------ state (append-only, one file per call id)
    def _state_path(self, cid: str) -> str:
        return os.path.join(self.state_dir, cid + ".jsonl")

    def _events(self, cid: str) -> List[dict]:
        path = self._state_path(cid)
        try:
            raw = self._read(path, MAX_STATE_BYTES)
        except FileNotFoundError:
            return []
        lines = raw.split(b"\n")
        torn = lines.pop()                    # text after the last newline is a torn write: ignored
        del torn
        events = []
        for line in lines:
            if not line:
                continue
            try:
                value = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeError):
                if not line.endswith(b"}"):
                    continue                  # a torn fragment (cut-short write) is never a complete JSON object: ignored
                raise PortError("reply_ledger_invalid")     # a complete-looking line that does not parse is corruption
            if type(value) is not dict or "event" not in value:
                raise PortError("reply_ledger_invalid")
            events.append(value)
        return events

    def _append(self, cid: str, event: dict) -> None:
        path = self._state_path(cid)
        created = not os.path.lexists(path)
        line = _canonical(event) + b"\n"
        try:
            if not created:
                with open(path, "rb") as handle:
                    handle.seek(0, os.SEEK_END)
                    if handle.tell() > 0:
                        handle.seek(-1, os.SEEK_END)
                        if handle.read(1) != b"\n":
                            line = b"\n" + line          # close a torn fragment so it cannot merge with this record
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                if os.write(fd, line) != len(line):
                    raise PortError("storage_failure")
                os.fsync(fd)
            finally:
                os.close(fd)
            if created:
                self._fsync_dir(self.state_dir)
        except OSError:
            raise PortError("storage_failure")

    @staticmethod
    def _find(events: List[dict], name: str) -> Optional[dict]:
        found = None
        for event in events:
            if event["event"] == name and found is None:
                found = event
        return found

    # ------------------------------------------------------------------ mission files
    def _mission_path(self, cid: str) -> str:
        return os.path.join(self.in_dir, cid + ".mission.md")

    def _answered(self, cid: str) -> bool:
        return os.path.lexists(os.path.join(self.in_dir, cid + ".answered.txt"))

    def _load_mission(self, cid: str) -> dict:
        """Read and verify one mission file. Verified = the file is byte-identical to what the island bridge
        mission_body() renders from the fields found in it. Raises FileNotFoundError or _Unverified."""
        raw = self._read(self._mission_path(cid), MAX_MISSION_FILE_BYTES, self.inbox_owner_uid)
        try:
            text = raw.decode("utf-8", "strict")
        except UnicodeError:
            raise _Unverified("not_utf8")
        match = MISSION_RE.fullmatch(text)
        if match is None:
            raise _Unverified("shape")
        if match.group("cid") != cid or match.group("agent") != self.agent:
            raise _Unverified("cid_or_agent_mismatch")
        ref = match.group("ref")
        if not REPORT_REF_RE.fullmatch(ref):
            raise _Unverified("ref_invalid")
        body = match.group("body")
        caller, island, token = match.group("caller"), match.group("island"), match.group("token")
        for candidate in (body, body + "\n"):       # the renderer drops one trailing newline of the original body
            if render_mission(cid, caller, island, self.agent, ref, candidate) == raw:
                return {"cid": cid, "caller": caller, "island": island, "ref": ref, "body": candidate,
                        "raw": raw, "file_sha256": sha256_hex(raw), "body_token_verified": True}
        # The bridge's renderer rewrites every line separator (CR, CRLF, U+2028 ...) to a newline AFTER it computed the
        # token from the original body, so such a letter can never match its token. Accept it when everything except the
        # token value matches, and say so: the body is then the sender's text with its line breaks normalised.
        for candidate in (body, body + "\n"):
            expected = render_mission(cid, caller, island, self.agent, ref, candidate)
            own = hashlib.sha256((cid + "\n" + candidate).encode("utf-8")).hexdigest()[:16]
            if expected.replace(own.encode(), token.encode()) == raw:
                return {"cid": cid, "caller": caller, "island": island, "ref": ref, "body": candidate,
                        "raw": raw, "file_sha256": sha256_hex(raw), "body_token_verified": False}
        raise _Unverified("render_mismatch")

    def _expired(self, cid: str, margin: int) -> bool:
        """The mission file carries no expiry; the bridge's ledger does and is private. Inferred: expires_at is the claim
        time (the call id's own timestamp) plus the route ttl, 86400 s in every route we use."""
        created = calendar.timegm(time.strptime(cid[:16], "%Y%m%dT%H%M%SZ"))
        return self.clock() - created > self.ttl - margin

    def skipped(self) -> Dict[str, str]:
        """Mission files read_head passed over because they did not verify (cid -> reason). For the owner; not a block."""
        return dict(self._skipped)

    def refused_notices(self) -> Dict[str, str]:
        """Bridge refusal notices in in/ (name -> code). Read-only."""
        out = {}
        for name in sorted(os.listdir(self.in_dir)):
            if re.fullmatch(r"ref-[a-f0-9]{24}\.refused\.txt", name):
                text = self._read(os.path.join(self.in_dir, name), 128).decode("ascii", "replace").strip()
                out[name] = text
        return out

    # ------------------------------------------------------------------ MailPort
    def read_head(self) -> Optional[dict]:
        try:
            names = sorted(os.listdir(self.in_dir))
        except OSError:
            raise PortError("storage_failure")
        for name in names:
            match = MISSION_NAME_RE.fullmatch(name)
            if match is None:
                continue
            cid = match.group(1)
            if self._answered(cid) or self._find(self._events(cid), "ack") is not None:
                continue
            try:
                mission = self._load_mission(cid)
            except _Unverified as exc:
                self._skipped[cid] = exc.reason
                continue
            except FileNotFoundError:
                continue
            self._skipped.pop(cid, None)
            request = _canonical({"hop": 1, "parent": None, "purpose": "queue_task", "ref": mission["ref"], "to": self.agent})
            payload = len(request).to_bytes(4, "big") + request + mission["body"].encode("utf-8")
            return {
                "call_id": cid, "source_agent": mission["caller"], "source_island": mission["island"],
                "destination_agent": self.agent, "destination_island": "vps1", "sequence": None,
                # not the Town Hall envelope (the dropbox does not carry it): the digest of the mission file itself
                "envelope_sha256": mission["file_sha256"],
                "body_token_verified": mission["body_token_verified"],      # gemini_p2 refuses a False here
                "expired": self._expired(cid, self.margin),                # gemini_p2 refuses with a reply
                "payload": payload, "payload_sha256": sha256_hex(payload),
            }
        return None

    def ack(self, call_id: str) -> dict:
        if not isinstance(call_id, str) or not CALL_ID_RE.fullmatch(call_id):
            raise PortError("call_id_invalid")
        try:
            mission = self._load_mission(call_id)
        except (_Unverified, FileNotFoundError):
            raise PortError("mission_not_found")
        prior = self._find(self._events(call_id), "ack")
        if prior is not None:
            if prior.get("mission_sha256") != mission["file_sha256"]:
                raise PortError("pickup_mismatch")
            return {"ok": True, "status": "picked_up", "call_id": call_id, "replay": "true"}
        self._append(call_id, {"event": "ack", "mission_sha256": mission["file_sha256"], "ts": int(self.clock())})
        return {"ok": True, "status": "picked_up", "call_id": call_id, "replay": "false"}

    def reply(self, call_id: str, caller_agent: str, payload: bytes) -> dict:
        if not isinstance(call_id, str) or not CALL_ID_RE.fullmatch(call_id):
            raise PortError("call_id_invalid")
        if not isinstance(caller_agent, str) or not NAME_RE.fullmatch(caller_agent):
            raise PortError("caller_invalid")
        if type(payload) is not bytes:
            raise PortError("payload_invalid")
        if len(payload) > MAX_BODY_BYTES:
            raise PortError("result_oversize")             # the dropbox cap is 8000 bytes, below the mailbox reader's 16384
        try:
            payload.decode("utf-8", "strict")
        except UnicodeError:
            raise PortError("payload_invalid")
        try:
            mission = self._load_mission(call_id)
        except (_Unverified, FileNotFoundError):
            raise PortError("mission_not_found")
        if mission["caller"] != caller_agent:
            raise PortError("wrong_caller")
        events = self._events(call_id)
        ack = self._find(events, "ack")
        if ack is None or ack.get("mission_sha256") != mission["file_sha256"]:
            raise PortError("pickup_mismatch")
        body_sha = sha256_hex(payload)
        ref, request_name, request_bytes = answer_names(call_id, self.agent, caller_agent)
        intent = self._find(events, "intent")
        if intent is not None:
            if intent.get("body_sha256") != body_sha or intent.get("request_sha256") != sha256_hex(request_bytes):
                raise PortError("id_collision")
        else:
            self._append(call_id, {"event": "intent", "body_sha256": body_sha, "ref": ref,
                                   "request_sha256": sha256_hex(request_bytes), "ts": int(self.clock())})
            events = self._events(call_id)
        have = {event["event"] for event in events} | {"intent"}
        # ---- terminal outcomes written by the island bridge
        if self._answered(call_id):
            if "request_started" not in have and "published" not in have:
                raise PortError("answer_exists")           # someone else answered this mission
            if "admitted" not in have:
                self._append(call_id, {"event": "admitted", "ts": int(self.clock())})
                return {"status": "result_admitted", "call_id": call_id, "replay": "false", "via": "dropbox"}
            return {"status": "result_admitted", "call_id": call_id, "replay": "true", "via": "dropbox"}
        notice = os.path.join(self.in_dir, "ref-" + sha256_hex(request_bytes)[:24] + ".refused.txt")
        if os.path.lexists(notice):
            code = self._read(notice, 128).decode("ascii", "replace").strip()
            if not REFUSED_CODE_RE.fullmatch(code):
                code = "port_exception"
            raise PortError(NOTICE_TO_PORT_CODE.get(code, code))
        # ---- publish, once
        if "published" not in have:
            if "request_started" not in have and self._expired(call_id, 0):
                raise PortError("answer_expired")               # the bridge would refuse it; write nothing (held_for_owner)
            if "body_published" not in have:
                self._publish(call_id, self.out_dir, ref, payload)
                self._append(call_id, {"event": "body_published", "ts": int(self.clock())})
            final = os.path.join(self.out_dir, request_name)
            if "request_started" not in have:
                temp = self._stage(call_id, self.out_dir, request_name, request_bytes)      # durable BEFORE the record below
                self._append(call_id, {"event": "request_started", "ts": int(self.clock())})
                if temp is not None:
                    self._commit(self.out_dir, request_name, temp)
            else:
                # An earlier run stopped between 'request_started' and 'published'. The JSON was staged before that record,
                # so one of three things is true: it is in place (done), still staged (finish the move), or already moved
                # and consumed by the bridge (done). It is never written a second time.
                if not os.path.lexists(final):
                    live = [e for e in self._events(call_id) if e["event"] == "staged" and e.get("final") == request_name]
                    orphaned = {e.get("part") for e in self._events(call_id) if e["event"] == "orphan"}
                    live = [e for e in live if e.get("part") not in orphaned]
                    temp = os.path.join(self.out_dir, live[-1]["part"]) if live else None
                    if temp is not None and os.path.lexists(temp):
                        if self._read(temp, len(request_bytes) + 1) != request_bytes:
                            raise PortError("port_exception")
                        self._commit(self.out_dir, request_name, temp)
            self._append(call_id, {"event": "published", "ts": int(self.clock())})
            raise PortError("post_transport_uncertain")      # written; the bridge confirms on its next cycle
        published = self._find(self._events(call_id), "published")
        if self.clock() - float(published.get("ts", 0)) > self.grace:
            raise PortError("answer_not_confirmed")          # bridge silent past its own retry grace: owner looks
        raise PortError("post_transport_uncertain")


def port_status(dropbox_root: str, state_dir: str, agent: str = RECEIVER, clock: Callable[[], float] = time.time,
                grace_seconds: int = ANSWER_RETRY_GRACE_SECONDS) -> dict:
    """READ-ONLY view for the owner (owner_tool status). Needs no particular uid, creates nothing, writes nothing."""
    port = DropboxPort.__new__(DropboxPort)
    port.agent, port.in_dir, port.out_dir = agent, os.path.join(dropbox_root, agent, "in"), os.path.join(dropbox_root, agent, "out")
    port.state_dir, port.inbox_owner_uid, port.clock, port.grace = state_dir, None, clock, grace_seconds
    port.ttl, port.margin, port._skipped = DEFAULT_MISSION_TTL_SECONDS, DEFAULT_EXPIRY_MARGIN_SECONDS, {}
    return port.status()


def _status(self) -> dict:
    now = self.clock()
    try:
        out_names = set(os.listdir(self.out_dir))
        state_names = sorted(os.listdir(self.state_dir))
    except OSError:
        return {"ok": False, "code": "tray_or_state_unreadable"}
    rows, staged_parts, orphaned, in_flight = [], set(), set(), set()
    for name in state_names:
        match = re.fullmatch(r"([0-9]{8}T[0-9]{6}Z_[a-f0-9]{6})\.jsonl", name)
        if match is None:
            continue
        cid = match.group(1)
        try:
            events = self._events(cid)
        except PortError as exc:
            rows.append({"cid": cid, "phase": "state_unreadable", "flags": [exc.code]})
            continue
        have = {e["event"] for e in events}
        phase = next((p for p in reversed(("ack",) + PHASES) if p in have), "none")
        intent = self._find(events, "intent")
        request_name = "answer-%s.json" % cid
        ref = intent.get("ref") if intent else None
        answered = self._answered(cid)
        notice = bool(intent) and os.path.lexists(os.path.join(self.in_dir, "ref-" + intent["request_sha256"][:24] + ".refused.txt"))
        present = sorted(n for n in (ref, request_name) if n and n in out_names)
        published = self._find(events, "published")
        age = int(now - float(published.get("ts", 0))) if published else None
        flags = []
        if phase == "published" and not answered and not notice:
            if not present:
                flags.append("consumed_unconfirmed")        # the bridge took the files but never wrote answered.txt
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
        for event in events:
            if event["event"] == "staged":
                staged_parts.add(event.get("part"))
            elif event["event"] == "orphan":
                orphaned.add(event.get("part"))
        if phase not in ("published", "admitted"):
            live = [e for e in events if e["event"] == "staged"]
            if live:
                in_flight.add(live[-1].get("part"))
        rows.append({"cid": cid, "phase": phase, "answered_txt": answered, "refused_notice": notice, "out_files": present,
                     "seconds_since_published": age, "flags": flags})
    parts = []
    for name in sorted(n for n in out_names if PART_RE.fullmatch(n)):
        if name in orphaned:
            parts.append({"part": name, "state": "orphan"})
        elif name in in_flight:
            parts.append({"part": name, "state": "in_flight"})
        elif name in staged_parts:
            parts.append({"part": name, "state": "leftover"})
        else:
            parts.append({"part": name, "state": "unrecorded"})
    return {"ok": True, "missions": rows, "part_files": parts,
            "orphan_parts": [p["part"] for p in parts if p["state"] != "in_flight"],
            "needs_owner": [r["cid"] for r in rows if set(r["flags"]) & {"consumed_unconfirmed", "bridge_silent_past_grace", "bridge_refused", "answered_by_someone_else", "state_unreadable"}]}


DropboxPort.status = _status


__all__ = ["DropboxPort", "port_status", "answer_names", "render_mission", "NOTICE_TO_PORT_CODE"]
