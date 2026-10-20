#!/usr/bin/env python3
"""Serve the TV launcher and bridge its actions to the TV."""
import json
import os
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backend_rpc

ROOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/tvsite"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
HIDDEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apps_hidden.json")
SHOWN = ["Netflix", "YouTube", "Prime Video", "Plex", "TV Browser"]


def hidden_apps():
    try:
        with open(HIDDEN_FILE) as f:
            return {n.strip().lower() for n in json.load(f).get("hidden", [])}
    except Exception:
        return {"hisensebar"}


def apps():
    r = backend_rpc.handle("apps", None)
    if not r.get("ok"):
        return r
    hidden = hidden_apps()
    names = {a["name"].strip().lower(): a["name"] for a in r["data"] if a["name"].strip().lower() not in hidden}
    return {"ok": True, "data": [names[n.lower()] for n in SHOWN if n.lower() in names]}


def sources():
    r = backend_rpc.handle("sources", None)
    if not r.get("ok"):
        return r
    data = [{"id": s.get("sourceid"), "name": s.get("displayname") or s.get("sourcename"),
             "signal": s.get("is_signal") == "1"} for s in r["data"]]
    return {"ok": True, "data": data}


def switch_source(sid):
    r = backend_rpc.handle("sources", None)
    if not r.get("ok"):
        return r
    for s in r["data"]:
        if s.get("sourceid") == sid or (s.get("sourcename") or "").lower() == sid.lower():
            return backend_rpc.handle("source", s)
    return {"ok": False, "error": f"unknown source {sid!r}"}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        if self.path.endswith(".html") or self.path == "/" or self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        if u.path == "/_log":
            self.send_response(204)
            self.end_headers()
            return
        if u.path == "/api/apps":
            return self._json(apps())
        if u.path == "/api/sources":
            return self._json(sources())
        if u.path == "/api/launch":
            return self._json(backend_rpc.handle("launch", q.get("name", "")))
        if u.path == "/api/source":
            return self._json(switch_source(q.get("id", "")))
        if u.path == "/api/state":
            return self._json(backend_rpc.handle("state", None))
        return super().do_GET()


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
