"""Launcher of the ChatGPT lobby on VPS1 (a container-fleet island). DRAFT, NOT INSTALLED.

1. Checks the sha256 of every file the lobby runs from (pins in PINS.json, written by make_pins.py at build time).
   A different byte = exit 2, `pin_mismatch`, nothing started.
2. Makes the reviewed lobby_server.py use the dropbox backend WITHOUT editing it: lobby_server does
   `from saas_adapter import SaasAdapter` inside Lobby.__init__ (when the v3 config has `host_adapter_config`). This launcher
   registers dropbox_lobby_adapter under that module name, so the import resolves to LobbyDropboxAdapter. The PC1 adapter, the PC1 CLI
   guard and the PC1 source pins are NOT shipped and cannot load.
3. Runs lobby_server.main(argv) unchanged.

Run as:  python3 -I -B /app/lobby_main.py --config /config/lobby-config.json     (as the container user, inside the container)
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PINS_FILE = "PINS.json"          # written by make_pins.py at build time: {"file name": "sha256 hex", ...} for FILES below
FILES = ("lobby_server.py", "dropbox_port.py", "gemini_p2.py", "dropbox_lobby_adapter.py")


def verify(directory=HERE):
    try:
        with open(os.path.join(directory, PINS_FILE), "rb") as handle:
            pins = json.loads(handle.read(65537).decode("utf-8"))
    except (OSError, ValueError):
        return PINS_FILE
    if type(pins) is not dict or set(pins) != set(FILES):
        return PINS_FILE
    for name, expected in pins.items():
        try:
            with open(os.path.join(directory, name), "rb") as handle:
                actual = hashlib.sha256(handle.read()).hexdigest()
        except OSError:
            return name
        if actual != expected:
            return name
    return None


def main(argv=None):
    bad = verify()
    if bad is not None:
        print(json.dumps({"status": "refused", "code": "pin_mismatch", "file": bad}, sort_keys=True), file=sys.stderr)
        return 2
    sys.path.insert(0, HERE)
    import dropbox_lobby_adapter
    sys.modules["saas_adapter"] = dropbox_lobby_adapter
    import lobby_server
    return lobby_server.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
