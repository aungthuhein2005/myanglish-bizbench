"""Minimal web demo and JSON API (standard library only).

    python -m app.server [--model GPT] [--port 8000]

    GET  /              demo page
    POST /api/analyze   {"message": "...", "context": "..."}  ->  analysis JSON
    GET  /health        {"ok": true, "model": "GPT"}

Binds to 127.0.0.1 only. Put it behind your own authentication before exposing it, since every
request spends API credit.
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

from app.analyzer import DEFAULT_MODEL, Analyzer
from src.evaluator import MODELS

ROOT = Path(__file__).resolve().parent.parent
PAGE = (Path(__file__).parent / "demo.html").read_bytes()
MAX_BODY = 4096


def make_handler(analyzer: Analyzer):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/":
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif self.path == "/health":
                self._send(200, {"ok": True, "model": analyzer.model})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/api/analyze":
                return self._send(404, {"error": "not found"})
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BODY:
                return self._send(413, {"error": f"body must be 1–{MAX_BODY} bytes"})
            try:
                req = json.loads(self.rfile.read(length))
                message = str(req["message"])
                context = req.get("context") or None
            except (ValueError, KeyError, TypeError):
                return self._send(400, {"error": 'send JSON like {"message": "..."}'})
            self._send(200, analyzer.analyze(message, context).to_dict())

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL, choices=list(MODELS))
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(Analyzer(args.model)))
    print(f"Myanglish analyzer ({args.model}) on http://127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
