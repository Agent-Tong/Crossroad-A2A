"""Smoke tests for DropboxPort on a synthetic tray. Standard library only.
Run once from this folder:  python3 -I -B tests/test_smoke.py
Fixtures are created exclusively under tests/retained/ and are never cleaned up. No file is deleted.
The island bridge is played by the test itself: it writes <cid>.mission.md and <cid>.answered.txt by hand."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import unittest
import unittest.mock
import uuid

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "gemini-tasks-mailbox"))      # gemini_p2 (core types) lives in the sibling folder

import dropbox_port  # noqa: E402
from dropbox_port import DropboxPort, answer_names, render_mission  # noqa: E402
from gemini_p2 import PortError  # noqa: E402

RETAINED = HERE / "retained"
ME = os.geteuid()
CID = "20261016T020000Z_a1b2c3"
CID2 = "20261016T020100Z_b2c3d4"
REF = "xx261016a_Letter_Test.md"


def fixture(prefix):
    RETAINED.mkdir(mode=0o700, exist_ok=True)
    path = RETAINED / (prefix + "-" + uuid.uuid4().hex)
    path.mkdir(mode=0o700)
    return path


def make_tray():
    root = fixture("tray")
    agent_dir = root / "dropbox" / "gemini"
    (agent_dir / "in").mkdir(parents=True, mode=0o755)
    (agent_dir / "out").mkdir(mode=0o755)
    state = root / "state"
    state.mkdir(mode=0o700)
    port = DropboxPort(str(root / "dropbox"), str(state), inbox_owner_uid=ME, required_uid=ME, mission_ttl_seconds=10 ** 9)
    return agent_dir, port


def deliver(agent_dir, cid, caller="agent-a", body="Please compare options A and B."):
    raw = render_mission(cid, caller, "pc1", "gemini", REF, body)
    (agent_dir / "in" / (cid + ".mission.md")).write_bytes(raw)
    return raw


class DropboxPortSmoke(unittest.TestCase):
    def test_read_ack_reply_then_bridge_confirms(self):
        agent_dir, port = make_tray()
        deliver(agent_dir, CID)
        head = port.read_head()
        self.assertEqual((head["call_id"], head["source_agent"], head["destination_agent"]), (CID, "agent-a", "gemini"))
        self.assertTrue(head["body_token_verified"])
        self.assertEqual(port.ack(CID)["status"], "picked_up")
        self.assertIsNone(port.read_head())                                  # acked letters are not offered again
        with self.assertRaises(PortError) as ctx:
            port.reply(CID, "agent-a", b"Option A.")
        self.assertEqual(ctx.exception.code, "post_transport_uncertain")     # written, not yet confirmed by the bridge
        ref, request_name, request_bytes = answer_names(CID, "gemini", "agent-a")
        self.assertEqual((agent_dir / "out" / ref).read_bytes(), b"Option A.")
        self.assertEqual((agent_dir / "out" / request_name).read_bytes(), request_bytes)
        self.assertEqual(json.loads(request_bytes)["parent"], CID)
        (agent_dir / "in" / (CID + ".answered.txt")).write_bytes(b"answered\n")    # the bridge signs, posts, then writes this
        done = port.reply(CID, "agent-a", b"Option A.")
        self.assertEqual(done["status"], "result_admitted")
        self.assertEqual(port.reply(CID, "agent-a", b"Option A.")["replay"], "true")

    def test_other_bytes_for_the_same_call_are_refused_and_nothing_is_rewritten(self):
        agent_dir, port = make_tray()
        deliver(agent_dir, CID)
        port.ack(CID)
        with self.assertRaises(PortError):
            port.reply(CID, "agent-a", b"first")
        ref = answer_names(CID, "gemini", "agent-a")[0]
        with self.assertRaises(PortError) as ctx:
            port.reply(CID, "agent-a", b"second")
        self.assertEqual(ctx.exception.code, "id_collision")
        self.assertEqual((agent_dir / "out" / ref).read_bytes(), b"first")

    def test_a_tampered_mission_is_skipped_and_does_not_block_the_next_one(self):
        agent_dir, port = make_tray()
        raw = deliver(agent_dir, CID)
        (agent_dir / "in" / (CID + ".mission.md")).write_bytes(raw.replace(b"at most 8000 bytes", b"at most 9999 bytes"))
        deliver(agent_dir, CID2, body="Second letter.")
        head = port.read_head()
        self.assertEqual(head["call_id"], CID2)
        self.assertEqual(port.skipped(), {CID: "render_mismatch"})

    def test_an_edited_body_is_flagged_as_not_token_verified(self):
        agent_dir, port = make_tray()
        raw = deliver(agent_dir, CID)
        (agent_dir / "in" / (CID + ".mission.md")).write_bytes(raw.replace(b"options A", b"options Z"))
        self.assertFalse(port.read_head()["body_token_verified"])      # the consumer (gemini_p2) refuses such a letter with a reply

    def test_caps_and_caller_checks(self):
        agent_dir, port = make_tray()
        deliver(agent_dir, CID)
        port.ack(CID)
        with self.assertRaises(PortError) as ctx:
            port.reply(CID, "agent-a", b"x" * 8001)
        self.assertEqual(ctx.exception.code, "result_oversize")
        with self.assertRaises(PortError) as ctx:
            port.reply(CID, "someone-else", b"x")
        self.assertEqual(ctx.exception.code, "wrong_caller")
        with self.assertRaises(PortError) as ctx:
            port.reply(CID, "agent-a", b"\xff\xfe")
        self.assertEqual(ctx.exception.code, "payload_invalid")


class ConcurrentCreateControl(unittest.TestCase):
    """Control for the check-then-rename race. Another writer creates the final name in the gap between the port's last
    look and its publish. The port must publish nothing, keep the other writer's file untouched, and keep its staged bytes.
    The gap is simulated on the real file system by a hook that fires once, just before (or just after the check for) the
    publish step. The hook is attached to every step an implementation could use (existence check, os.rename, os.link,
    the no-replace primitive), so the test does not depend on which one is used; `fired` proves the gap really happened.
    A check-then-os.rename implementation FAILS this test (it replaces the other writer's file)."""

    FOREIGN = b"foreign writer bytes"

    def run_with_gap_writer(self, agent_dir, port, reply_bytes=b"Option A."):
        ref = answer_names(CID, "gemini", "agent-a")[0]
        out_dir = str(agent_dir / "out")
        final = os.path.join(out_dir, ref)
        state = {"fired": False, "busy": False}
        real_lexists_early = os.path.lexists

        def gap():
            # fires only once the port has staged its temp file, i.e. inside the commit step
            if state["busy"] or state["fired"]:
                return
            state["busy"] = True
            try:
                staged = any(n.startswith(".part-") for n in os.listdir(out_dir))
                if staged and not real_lexists_early(final):
                    state["fired"] = True
                    fd = os.open(final, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
                    os.write(fd, self.FOREIGN)
                    os.close(fd)
            finally:
                state["busy"] = False

        real_lexists, real_rename, real_link = os.path.lexists, os.rename, os.link
        real_noreplace = getattr(dropbox_port, "_rename_noreplace", None)

        def lexists_then_gap(path):
            result = real_lexists(path)
            if os.fspath(path) == final and not result:
                gap()                                   # the check just said "free"; now the other writer arrives
            return result

        def rename_after_gap(src, dst, *a, **k):
            gap()
            return real_rename(src, dst, *a, **k)

        def link_after_gap(src, dst, *a, **k):
            gap()
            return real_link(src, dst, *a, **k)

        patches = [unittest.mock.patch.object(os.path, "lexists", lexists_then_gap),
                   unittest.mock.patch.object(os, "rename", rename_after_gap),
                   unittest.mock.patch.object(os, "link", link_after_gap)]
        if real_noreplace is not None:
            def noreplace_after_gap(src, dst):
                gap()
                return real_noreplace(src, dst)
            patches.append(unittest.mock.patch.object(dropbox_port, "_rename_noreplace", noreplace_after_gap))
        for patch in patches:
            patch.start()
        try:
            with self.assertRaises(PortError) as ctx:
                port.reply(CID, "agent-a", reply_bytes)
        finally:
            for patch in patches:
                patch.stop()
        return ctx.exception.code, state["fired"], final

    def test_a_writer_that_creates_the_final_name_in_the_gap_is_never_replaced(self):
        agent_dir, port = make_tray()
        deliver(agent_dir, CID)
        port.ack(CID)
        code, fired, final = self.run_with_gap_writer(agent_dir, port)
        self.assertTrue(fired, "the simulated writer never ran: the control proved nothing")
        self.assertEqual(code, "id_collision")
        with open(final, "rb") as handle:
            self.assertEqual(handle.read(), self.FOREIGN)                       # the other writer's file is intact
        parts = [n for n in os.listdir(agent_dir / "out") if n.startswith(".part-")]
        self.assertEqual(len(parts), 1)                                          # our staged bytes are kept, not lost
        with open(agent_dir / "out" / parts[0], "rb") as handle:
            self.assertEqual(handle.read(), b"Option A.")

    def test_no_atomic_no_replace_operation_means_nothing_is_published(self):
        agent_dir, port = make_tray()
        deliver(agent_dir, CID)
        port.ack(CID)
        with unittest.mock.patch.object(dropbox_port, "_NOREPLACE", None):
            with self.assertRaises(PortError) as ctx:
                port.reply(CID, "agent-a", b"Option A.")
        self.assertEqual(ctx.exception.code, "storage_failure")                  # fail closed
        ref = answer_names(CID, "gemini", "agent-a")[0]
        self.assertFalse(os.path.lexists(agent_dir / "out" / ref))
        self.assertEqual(len([n for n in os.listdir(agent_dir / "out") if n.startswith(".part-")]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
