"""Container healthcheck: HTTP GET on loopback for each URL given, exit 0 only if EVERY one answers 200. Used by both containers
(same bytes). The tunnel container passes two URLs: the lobby (http://127.0.0.1:LOBBY_PORT/health) and its own client
(http://127.0.0.1:CLIENT_HEALTH_PORT/healthz), so a tunnel that holds a dead copy of the lobby's network namespace is unhealthy.
Usage: python3 -I -B http_health.py http://127.0.0.1:LOBBY_PORT/health [more URLs]
No redirect following, 5 s timeout per URL, prints a fixed word only."""
import http.client
import sys
import urllib.parse


def one(raw):
    url = urllib.parse.urlsplit(raw)
    if url.scheme != "http" or url.hostname != "127.0.0.1" or url.port is None:
        return None
    try:
        connection = http.client.HTTPConnection("127.0.0.1", url.port, timeout=5)
        connection.request("GET", url.path or "/")
        status = connection.getresponse().status
        connection.close()
    except Exception:
        return False
    return status == 200


def main(argv):
    if len(argv) < 2:
        return 64
    results = [one(raw) for raw in argv[1:]]
    if any(r is None for r in results):
        return 64
    ok = all(results)
    print("up" if ok else "down")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
