"""Smoke tests for the ChatGPT lobby reference: adapter over a synthetic tray, launcher pin check, config and compose shape.
Standard library only. Run once from this folder:  python3 -I -B tests/test_smoke.py
Fixtures are created exclusively under tests/retained/ and are never cleaned up. No file is deleted.
The island bridge is played by the test: it writes <cid>.mission.md and <cid>.answered.txt by hand."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import unittest
import uuid

HERE = pathlib.Path(__file__).resolve().parent
LOBBY = HERE.parent
REF = LOBBY.parent
for entry in (LOBBY, REF / "dropbox-port", REF / "gemini-tasks-mailbox"):
    sys.path.insert(0, str(entry))

import dropbox_lobby_adapter as adapter_mod  # noqa: E402
import lobby_main as launcher  # noqa: E402
from dropbox_port import answer_names, render_mission  # noqa: E402

RETAINED = HERE / "retained"
ME = os.geteuid()
CID = "20261016T020000Z_a1b2c3"
MISSION_REF = "xx261016a_Letter_Test.md"


def fixture(prefix):
    RETAINED.mkdir(mode=0o700, exist_ok=True)
    path = RETAINED / (prefix + "-" + uuid.uuid4().hex)
    path.mkdir(mode=0o700)
    return path


def make_adapter():
    root = fixture("tray")
    agent_dir = root / "dropbox" / "chatgpt"
    (agent_dir / "in").mkdir(parents=True, mode=0o755)
    (agent_dir / "out").mkdir(mode=0o755)
    (root / "state").mkdir(mode=0o700)
    port = adapter_mod.LobbyDropboxPort(str(root / "dropbox"), str(root / "state"), inbox_owner_uid=ME,
                                        agent="chatgpt", required_uid=ME, mission_ttl_seconds=10 ** 9)
    config = {"agent": "chatgpt", "dropbox_root": str(root / "dropbox"), "inbox_owner_uid": ME, "state_dir": str(root / "state")}
    (root / "adapter.json").write_text(json.dumps(config))
    return agent_dir, adapter_mod.LobbyDropboxAdapter(str(root / "adapter.json"), port=port)


def deliver(agent_dir, cid=CID, body="Say hello."):
    (agent_dir / "in" / (cid + ".mission.md")).write_bytes(render_mission(cid, "agent-a", "pc1", "chatgpt", MISSION_REF, body))


class AdapterTests(unittest.TestCase):
    def test_list_read_reply_and_bridge_confirmation(self):
        agent_dir, adapter = make_adapter()
        deliver(agent_dir)
        pending = adapter.list_pending()
        self.assertEqual([(m["call_id"], m["source_agent"]) for m in pending], [(CID, "agent-a")])
        one = adapter.read_one(CID)
        self.assertEqual((one["payload"], one["status"]), (b"Say hello.", "captured"))
        first = adapter.reply(CID, b"Hello.")
        self.assertEqual(first["status"], "reply_submitted")                       # written; the bridge has not confirmed yet
        self.assertEqual(adapter.reply(CID, b"Hello.")["replay"], "true")          # same bytes again: a no-op
        self.assertEqual([s["status"] for s in adapter.captured_statuses()], ["reply_pending"])
        ref, request_name, _ = answer_names(CID, "chatgpt", "agent-a")
        self.assertEqual((agent_dir / "out" / ref).read_bytes(), b"Hello.")
        self.assertTrue((agent_dir / "out" / request_name).exists())
        (agent_dir / "in" / (CID + ".answered.txt")).write_bytes(b"answered\n")
        self.assertEqual(adapter.reply(CID, b"Hello.")["status"], "result_admitted")
        self.assertEqual(adapter.captured_statuses(), [])                          # finished work is not listed
        self.assertEqual(adapter.list_pending(), [])

    def test_other_bytes_are_a_coded_refusal_and_the_lobby_can_see_the_code(self):
        agent_dir, adapter = make_adapter()
        deliver(agent_dir)
        adapter.reply(CID, b"first")
        with self.assertRaises(adapter_mod.AdapterRefusal) as ctx:
            adapter.reply(CID, b"second")
        self.assertEqual(str(ctx.exception.code), "id_collision")

    def test_bad_input_is_refused_with_fixed_codes(self):
        _agent_dir, adapter = make_adapter()
        for call in (lambda: adapter.read_one("not-a-call-id"), lambda: adapter.reply(CID, b""), lambda: adapter.reply(CID, "text")):
            with self.assertRaises(adapter_mod.AdapterRefusal):
                call()


class LauncherPinTests(unittest.TestCase):
    def test_pins_must_match_the_files_and_fail_closed(self):
        deploy = fixture("deploy")
        sources = {"lobby_server.py": LOBBY, "dropbox_lobby_adapter.py": LOBBY,
                   "dropbox_port.py": REF / "dropbox-port", "gemini_p2.py": REF / "gemini-tasks-mailbox"}
        for name, folder in sources.items():
            (deploy / name).write_bytes((folder / name).read_bytes())
        self.assertEqual(launcher.verify(str(deploy)), "PINS.json")                # no pins file: refuse
        namespace = {"__name__": "make_pins"}
        exec(compile((LOBBY / "make_pins.py").read_text(), "make_pins.py", "exec"), namespace)
        self.assertEqual(namespace["main"](["make_pins.py", str(deploy)]), 0)
        self.assertIsNone(launcher.verify(str(deploy)))
        with open(str(deploy / "lobby_server.py"), "ab") as handle:
            handle.write(b"\n# one extra byte\n")
        self.assertEqual(launcher.verify(str(deploy)), "lobby_server.py")


class ShapeTests(unittest.TestCase):
    def test_lobby_config_has_four_tools_and_no_send_mail(self):
        config = json.loads((LOBBY / "config" / "lobby-config.json").read_text())
        self.assertEqual(config["enabled_tools"], ["check_mail", "read_mail", "reply", "job_status"])
        self.assertEqual(config["listen"]["host"], "127.0.0.1")
        self.assertIsNone(config["callers"]["chatgpt"]["token_hash"])

    def test_compose_publishes_no_port_and_drops_capabilities(self):
        text = (LOBBY / "chatgpt.compose.example.yml").read_text()
        code = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        self.assertFalse(any(line.strip().startswith("ports:") for line in code))
        self.assertEqual(sum(1 for line in code if "cap_drop: [ALL]" in line), 2)
        self.assertIn("no-new-privileges:true", text)
        self.assertIn('network_mode: "service:crossroad-chatgpt-lobby"', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
