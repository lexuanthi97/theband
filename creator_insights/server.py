"""Máy chủ cục bộ: mở dashboard và tra cứu từ khóa bất kỳ theo thời gian thực.

    python -m creator_insights serve   ->  http://localhost:8765
"""

from __future__ import annotations

import json
import urllib.parse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from . import analyzer
from .collect import DATA_DIR, load_config, load_history, VN_TZ
from .sources import Fetcher, google_suggest, tiktok_suggest

import datetime as dt

WEB_DIR = DATA_DIR.parent


def lookup(query: str, config: dict) -> dict:
    query = analyzer.normalize(query)[:80]
    region, lang = config.get("region", "VN"), config.get("language", "vi")
    fetcher = Fetcher(delay=0.3, max_requests=12)
    classifier = analyzer.Classifier(config)
    sugs = []
    for mod in config.get("modifiers", [""]):
        sugs += tiktok_suggest(fetcher, (query + mod).strip(), region, lang)
    sugs += google_suggest(fetcher, query, lang)
    sugs += google_suggest(fetcher, query, lang, youtube=True)
    agg = analyzer.aggregate(sugs, classifier, {}, filter_relevant=False)
    related = {query: [analyzer.normalize(s.keyword) for s in sugs if s.source == "tiktok" and s.seed == query]}
    today = dt.datetime.now(VN_TZ).strftime("%Y-%m-%d")
    history = load_history(DATA_DIR, today, config.get("history_days", 30))
    rows = analyzer.build_report(agg, related, classifier, history, today)
    return {"query": query, "requests": fetcher.count, "keywords": rows}


class Handler(SimpleHTTPRequestHandler):
    config: dict = {}

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/lookup":
            q = urllib.parse.parse_qs(parsed.query).get("q", [""])[0].strip()
            if not q:
                return self._json({"error": "Thiếu từ khóa (?q=...)"}, 400)
            try:
                return self._json(lookup(q, self.config))
            except Exception as exc:  # trả lỗi rõ ràng cho giao diện
                return self._json({"error": f"Không tra cứu được: {exc}"}, 502)
        if parsed.path == "/api/ping":
            return self._json({"ok": True})
        return super().do_GET()

    def _json(self, payload: dict, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(port: int = 8765) -> None:
    Handler.config = load_config()
    handler = partial(Handler, directory=str(WEB_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Mở trình duyệt: http://localhost:{port}  (Ctrl+C để dừng)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
