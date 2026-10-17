"""Build tool: writes PINS.json (sha256 of the four files the lobby launcher checks) into a deploy directory.
Usage: python3 -I -B make_pins.py /abs/path/to/deploy_dir
The deploy directory must already hold the four files (copy lobby_server.py and dropbox_lobby_adapter.py from this folder,
dropbox_port.py from ../dropbox-port/ and gemini_p2.py from ../gemini-tasks-mailbox/). Writes one file, deletes nothing."""
import hashlib
import json
import os
import sys

FILES = ("lobby_server.py", "dropbox_port.py", "gemini_p2.py", "dropbox_lobby_adapter.py")


def main(argv):
    if len(argv) != 2 or not os.path.isabs(argv[1]):
        print("usage: make_pins.py /abs/deploy_dir", file=sys.stderr)
        return 64
    pins = {}
    for name in FILES:
        with open(os.path.join(argv[1], name), "rb") as handle:
            pins[name] = hashlib.sha256(handle.read()).hexdigest()
    with open(os.path.join(argv[1], "PINS.json"), "x", encoding="utf-8") as out:     # "x": never overwrite
        out.write(json.dumps(pins, sort_keys=True, indent=1) + "\n")
    print("PINS.json written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
