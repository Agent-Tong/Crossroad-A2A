"""MailPort that drives a host mailbox reader entrypoint (receiver "gemini").

Argument vectors follow the mailbox reader guide of the host mail release. The reply body goes only through the
private stdin of that one invocation. Nothing is read from or written to the signing key here:
the path is passed through, the installed reply code opens it.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from typing import Callable, List, Optional, Tuple

from gemini_p2 import PortError, RECEIVER, sha256_hex

Runner = Callable[[List[str], Optional[bytes]], Tuple[int, bytes]]
CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
MAX_STDOUT = 262144


def subprocess_runner(timeout: int = 60) -> Runner:
    """No shell. argv is a list. A timeout is a retryable port error."""
    def run(argv: List[str], stdin: Optional[bytes]) -> Tuple[int, bytes]:
        try:
            done = subprocess.run(argv, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            raise PortError("port_exception")
        except OSError:
            raise PortError("port_exception")
        return done.returncode, done.stdout[:MAX_STDOUT]
    return run


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate")
        out[key] = value
    return out


def _parse(raw: bytes) -> dict:
    if not raw or len(raw) > MAX_STDOUT or not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise PortError("port_exception")
    try:
        value = json.loads(raw.decode("ascii", "strict"), object_pairs_hook=_unique)
    except (ValueError, UnicodeError):
        raise PortError("port_exception")
    if type(value) is not dict or type(value.get("ok")) is not bool:
        raise PortError("port_exception")
    return value


class ReaderCliPort(object):
    """Fields mirror the guide. All paths must be absolute; nothing is created here."""

    def __init__(self, python: str, reader_script: str, state_root: str, reply_state: str,
                 owner_config: str, result_signing_key: str, runner: Runner, agent: str = RECEIVER):
        for value in (python, reader_script, state_root, reply_state, owner_config, result_signing_key):
            if not isinstance(value, str) or not os.path.isabs(value):
                raise ValueError("all ReaderCliPort paths must be absolute")
        self.python = python
        self.reader_script = reader_script
        self.state_root = state_root
        self.reply_state = reply_state
        self.owner_config = owner_config
        self.key = result_signing_key
        self.runner = runner
        self.agent = agent

    def _base(self) -> List[str]:
        return [self.python, "-I", "-B", self.reader_script, "--state-root", self.state_root,
                "--agent", self.agent, "--mode", "mail"]

    def _call(self, tail: List[str], stdin: Optional[bytes] = None) -> dict:
        try:
            rc, raw = self.runner(self._base() + tail, stdin)
        except PortError:
            raise
        except Exception:
            raise PortError("port_exception")
        out = _parse(raw)
        if out["ok"] is not True:
            code = out.get("code")
            raise PortError(code if isinstance(code, str) and CODE_RE.fullmatch(code) else "port_exception")
        if rc != 0:
            raise PortError("port_exception")
        return out

    def read_head(self) -> Optional[dict]:
        try:
            out = self._call(["read-one"])
        except PortError as exc:
            if exc.code == "empty_inbox":
                return None
            raise
        meta = out.get("metadata")
        if type(meta) is not dict:
            raise PortError("port_exception")
        try:
            payload = base64.b64decode(out["payload_base64"], validate=True)
        except (KeyError, ValueError, TypeError):
            raise PortError("port_exception")
        if sha256_hex(payload) != meta.get("payload_sha256"):
            raise PortError("port_exception")
        head = dict(meta)
        head["payload"] = payload
        return head

    def ack(self, call_id: str) -> dict:
        return self._call(["ack", "--call-id", call_id])

    def reply(self, call_id: str, caller_agent: str, payload: bytes) -> dict:
        tail = ["reply", "--call-id", call_id, "--caller", caller_agent, "--reply-state", self.reply_state,
                "--config", self.owner_config, "--result-signing-key", self.key, "--payload-stdin"]
        return self._call(tail, payload)
