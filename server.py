from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from parser import parse_optional_price, search_olx


class OlxHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/search":
            return super().do_GET()

        params = parse_qs(parsed.query)
        query = params.get("query", [""])[0]
        sort = params.get("sort", ["asc"])[0]

        try:
            items = search_olx(
                query=query,
                min_price=parse_optional_price(params.get("min_price", [""])[0]),
                max_price=parse_optional_price(params.get("max_price", [""])[0]),
                sort=sort if sort in {"asc", "desc"} else "asc",
            )
            self._json({"items": items})
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    address = ("127.0.0.1", 8000)
    server = ThreadingHTTPServer(address, OlxHandler)
    print(f"OLX Parser running at http://{address[0]}:{address[1]}")
    server.serve_forever()


if __name__ == "__main__":
    main()
