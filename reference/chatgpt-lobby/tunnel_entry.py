"""Entry point of the ChatGPT TUNNEL container. DRAFT, NOT INSTALLED.

Same pattern as the Gemini bridge container: starts as root INSIDE the container (cap_drop ALL, cap_add SETUID + SETGID only),
reads the root-only credential from the read-only mount, drops to the container uid/gid, runs the vendor self-check, then runs
`tunnel-client run` as a CHILD and watches the lobby.
The key goes into the child's environment only (the profile says api_key: env:CONTROL_PLANE_API_KEY). It is never printed,
logged or written. Nothing is deleted.

Why a watchdog (review item 1): this container shares the network namespace of the lobby container (compose network_mode:
service:...). If the lobby container restarts, docker gives it a NEW namespace and this container keeps the dead one: the
client's own /healthz stays green while nothing reaches the lobby. So every PROBE_INTERVAL seconds this process asks
127.0.0.1:$LOBBY_PORT/health; PROBE_FAILS failures in a row = stop the client and exit 4, and docker's restart policy starts this
container again, which joins the lobby's CURRENT namespace. The container healthcheck probes the same lobby URL as well.

Mounts (compose): /secrets (ro, root-delivered), /vendor (ro, vendor tunnel client), /profiles (ro), /state (rw, container user).
"""
import http.client
import json
import os
import signal
import subprocess
import sys
import time

KEY_FILE = "/secrets/CONTROL_PLANE_API_KEY"
CLIENT = "/vendor/tunnel-client"
PROFILES = "/profiles"
PROFILE = "chatgpt-lobby"
RUN_AS = 1000                      # example value: your container user id
LOBBY = ("127.0.0.1", int(os.environ["LOBBY_PORT"]), "/health")      # LOBBY_PORT is set in the compose file
PROBE_INTERVAL = 10
PROBE_FAILS = 3
STOP_GRACE = 10


def say(obj):
    print(json.dumps(obj, sort_keys=True, separators=(",", ":")), flush=True)


def lobby_alive():
    try:
        connection = http.client.HTTPConnection(LOBBY[0], LOBBY[1], timeout=3)
        connection.request("GET", LOBBY[2])
        status = connection.getresponse().status
        connection.close()
        return status == 200
    except Exception:
        return False


def stop_child(child):
    child.terminate()
    try:
        child.wait(STOP_GRACE)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()


def supervise(child, probe=lobby_alive, sleep=time.sleep):
    """Return the exit code. 4 = the lobby stopped answering (stale namespace or dead lobby); else the client's own code."""
    fails = 0
    while True:
        code = child.poll()
        if code is not None:
            say({"event": "client_exited", "rc": code})
            return code if code else 1
        if probe():
            fails = 0
        else:
            fails += 1
            if fails >= PROBE_FAILS:
                say({"event": "lobby_unreachable_restarting", "failures": fails})
                stop_child(child)
                return 4
        sleep(PROBE_INTERVAL)


def main():
    if os.geteuid() != 0:
        say({"event": "must_start_as_root_in_container"})
        return 2
    try:
        with open(KEY_FILE, "rb") as handle:
            raw = handle.read(8193)
    except OSError:
        say({"event": "credential_source_missing"})
        return 2
    key = raw.split(b"\n", 1)[0].decode("utf-8", "strict").strip() if len(raw) <= 8192 else ""
    if not key:
        say({"event": "credential_source_invalid"})
        return 2
    os.setgroups([])
    os.setgid(RUN_AS)
    os.setuid(RUN_AS)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/state", "CONTROL_PLANE_API_KEY": key}
    doctor = [CLIENT, "doctor", "--profile", PROFILE, "--profile-dir", PROFILES]
    try:
        done = subprocess.run(doctor, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired):
        say({"event": "doctor_not_run"})
        return 3
    if done.returncode != 0:
        say({"event": "vendor_doctor_refused", "rc": done.returncode})
        return 3
    say({"event": "tunnel_starting", "profile": PROFILE})
    child = subprocess.Popen([CLIENT, "run", "--profile", PROFILE, "--profile-dir", PROFILES], env=env)

    def on_term(_signum, _frame):
        stop_child(child)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, on_term)
    return supervise(child)


if __name__ == "__main__":
    raise SystemExit(main())
