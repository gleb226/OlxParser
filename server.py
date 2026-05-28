from __future__ import annotations

import json
import os
import socket
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

from parser import parse_optional_price, search_olx


class OlxHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._json({"ok": True, "service": "olx-parser", "version": 4})
            return

        if parsed.path == "/api/image":
            self._proxy_image(parse_qs(parsed.query).get("url", [""])[0])
            return

        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if parsed.path != "/api/search":
            return super().do_GET()

        params = parse_qs(parsed.query)
        query = params.get("query", [""])[0]
        sort = params.get("sort", ["asc"])[0]
        seller_type = params.get("seller_type", ["all"])[0]
        category = params.get("category", ["all"])[0]
        city = params.get("city", ["all"])[0]
        city_query = params.get("city_query", [""])[0]
        price_currency = params.get("price_currency", ["UAH"])[0].upper()

        try:
            items = search_olx(
                query=query,
                min_price=parse_optional_price(params.get("min_price", [""])[0]),
                max_price=parse_optional_price(params.get("max_price", [""])[0]),
                sort=sort if sort in {"asc", "desc"} else "asc",
                seller_type=seller_type if seller_type in {"all", "private", "business"} else "all",
                category=category,
                city=city,
                city_query=city_query,
                price_currency=price_currency if price_currency in {"UAH", "USD", "EUR"} else "UAH",
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

    def _proxy_image(self, image_url: str) -> None:
        url = unquote(image_url).strip()
        if not url.startswith(("https://", "http://")) or "olxcdn.com" not in url:
            self.send_error(400, "Bad image URL")
            return

        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "Referer": "https://www.olx.ua/",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/jpeg,image/png",
            },
        )

        try:
            with urlopen(request, timeout=14) as response:
                body = response.read()
                content_type = response.headers.get("Content-Type", "image/jpeg")
        except Exception:
            self.send_error(404, "Image not available")
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _requested_port() -> int | None:
    raw_port = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PORT")
    if raw_port is None:
        return None

    try:
        port = int(raw_port)
    except ValueError as exc:
        raise SystemExit("Port must be a number.") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("Port must be between 1 and 65535.")
    return port


def _is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _create_server() -> tuple[ThreadingHTTPServer, tuple[str, int]]:
    requested = _requested_port()
    ports = [requested] if requested is not None else [8000, 5000, 8212, 8080, 3000, 3001, 3002]

    for port in ports:
        if not _is_port_available(port):
            if requested is not None:
                raise SystemExit(f"Port {port} is already in use.")
            continue

        address = ("127.0.0.1", port)
        try:
            return ThreadingHTTPServer(address, OlxHandler), address
        except OSError:
            if requested is not None:
                raise

    raise SystemExit("No free local port found.")


def main(open_browser: bool = False) -> None:
    server, address = _create_server()
    url = f"http://{address[0]}:{address[1]}"
    print(f"OLX Smart Search running at {url}")

    if open_browser:
        webbrowser.open(url)

    server.serve_forever()


if __name__ == "__main__":
    main()
