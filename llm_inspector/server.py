"""Tiny dependency-free HTTP server that serves the viewer and the saved runs."""
from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATIC = Path(__file__).parent / "static"
ID_RE = re.compile(r"^[\w.\-]+$")


def _summary(path: Path) -> dict | None:
    try:
        d = json.loads(path.read_text())
    except Exception:
        return None
    calls = d.get("calls", [])
    inp = sum(c.get("input_tokens") or 0 for c in calls)
    read = sum(c.get("cache_read") or 0 for c in calls)
    return {
        "id": d.get("id", path.stem),
        "started": d.get("started"),
        "ended": d.get("ended"),
        "command": d.get("command"),
        "calls": len(calls),
        "invocations": len({c.get("root_run_id") for c in calls}),
        "input_tokens": inp,
        "output_tokens": sum(c.get("output_tokens") or 0 for c in calls),
        "cache_read": read,
        "hit_rate": (read / inp) if inp else 0,
        "mtime": path.stat().st_mtime,
    }


def make_handler(run_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            if path == "/api/executions":
                rows = [s for p in run_dir.glob("*.json") if (s := _summary(p))]
                rows.sort(key=lambda r: r.get("started") or 0, reverse=True)
                return self._send(200, json.dumps(rows).encode())
            m = re.match(r"^/api/executions/(.+)$", path)
            if m and ID_RE.match(m.group(1)):
                f = run_dir / f"{m.group(1)}.json"
                if f.is_file():
                    return self._send(200, f.read_bytes())
            self._send(404, b'{"error":"not found"}')

        def do_DELETE(self):
            m = re.match(r"^/api/executions/(.+)$", self.path)
            if m and ID_RE.match(m.group(1)):
                f = run_dir / f"{m.group(1)}.json"
                if f.is_file():
                    f.unlink()
                    return self._send(200, b'{"ok":true}')
            self._send(404, b'{"error":"not found"}')

    return Handler


def serve(run_dir: Path, host="127.0.0.1", port=8765, open_browser=False):
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        srv = ThreadingHTTPServer((host, port), make_handler(run_dir))
    except OSError as exc:
        raise SystemExit(f"[llm_inspector] cannot listen on {host}:{port} ({exc}). Try --port <other>.")
    print(f"[llm_inspector] reading runs from {run_dir}")
    print(f"[llm_inspector] viewer at http://{host}:{port}")
    if open_browser:
        import webbrowser
        webbrowser.open(f"http://{host}:{port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
