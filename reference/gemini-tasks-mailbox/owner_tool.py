"""Owner actions on the bridge ledger. Ledger only: no Tasks call, no mail call. Nothing is deleted. Each action is logged.

  python3 -I -B owner_tool.py --ledger /abs/path/ledger.sqlite3 status
  python3 -I -B owner_tool.py --ledger ... status --dropbox-root /abs/dropbox --port-state-dir /abs/state   # adds the read-only dropbox port view
  python3 -I -B owner_tool.py --ledger ... release-blocked CID --note "looked at the list, no Letter task"
  python3 -I -B owner_tool.py --ledger ... choose-answer CID --task-id TASKID --note "why this one"
  python3 -I -B owner_tool.py --ledger ... reset-held CID --note "why it is safe to retry"
It takes the same run.lock as the bridge, so it refuses while a run is in progress.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import gemini_p2 as g  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(prog="owner_tool")
    parser.add_argument("--ledger", required=True)
    sub = parser.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("status")
    st.add_argument("--dropbox-root")
    st.add_argument("--port-state-dir")
    st.add_argument("--agent", default=g.RECEIVER)
    for name in ("release-blocked", "reset-held"):
        p = sub.add_parser(name)
        p.add_argument("cid")
        p.add_argument("--note", required=True)
    p = sub.add_parser("choose-answer")
    p.add_argument("cid")
    p.add_argument("--task-id", required=True)
    p.add_argument("--note", required=True)
    args = parser.parse_args(argv)
    if not os.path.isabs(args.ledger):
        print(json.dumps({"ok": False, "code": "ledger_path_must_be_absolute"}))
        return 2
    try:
        fd = g.acquire_lock(os.path.join(os.path.dirname(args.ledger), "run.lock"))
    except g.Refusal as exc:
        print(json.dumps({"ok": False, "code": exc.code}))
        return 2
    try:
        ledger = g.Ledger(args.ledger)
        if args.cmd == "status":
            rows = {
                "missions_not_final": [dict(r) for r in ledger.db.execute(
                    "SELECT cid,state,detail FROM missions WHERE state NOT IN ('acked','refused_acked')")],
                "answers_not_final": [dict(r) for r in ledger.db.execute(
                    "SELECT cid,state,detail FROM answers WHERE state NOT IN ('admitted')")],
            }
            if args.dropbox_root or args.port_state_dir:
                # READ-ONLY view of the dropbox port: phases, the bridge-took-it-but-never-confirmed case, orphan temp files.
                try:
                    import dropbox_port
                    if not (args.dropbox_root and args.port_state_dir):
                        raise ValueError("both")
                    rows["dropbox_port"] = dropbox_port.port_status(args.dropbox_root, args.port_state_dir, args.agent)
                except (ImportError, ValueError):
                    rows["dropbox_port"] = {"ok": False, "code": "dropbox_port_unavailable_or_args_incomplete"}
            print(json.dumps({"ok": True, **rows}, sort_keys=True))
            return 0
        if args.cmd == "release-blocked":
            g.owner_release_blocked(ledger, args.cid, args.note)
        elif args.cmd == "reset-held":
            g.owner_reset_held(ledger, args.cid, args.note)
        else:
            g.owner_choose_answer(ledger, args.cid, args.task_id, args.note)
        print(json.dumps({"ok": True, "action": args.cmd, "cid": args.cid}))
        return 0
    except g.Refusal as exc:
        print(json.dumps({"ok": False, "code": exc.code}))
        return 2
    finally:
        os.close(fd)


if __name__ == "__main__":
    raise SystemExit(main())
