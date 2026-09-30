"""Loopback-only stdlib HTTP UI with exact-origin mutation protection."""

import argparse
import errno
import http.cookies
import json
import mimetypes
import secrets
import signal
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import TEMPLATE, Store
from .errors import AppError, safe_error
from .renderer import approved_artwork
from .service import Service

MAX_BODY = 64 * 1024
LANDING = b"<!doctype html><meta charset=utf-8><title>Google Calendar Today</title><h1>Google Calendar Today</h1><p>The local backend is running. The configuration interface will appear here when installed.</p>"


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, service):
        if address[0] != "127.0.0.1":
            raise AppError("validation")
        self.service = service
        super().__init__(address, Handler)
        self.service.origin = f"http://127.0.0.1:{self.server_port}"


class Handler(BaseHTTPRequestHandler):
    server_version = "AgendaLocal"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, format, *args):
        # HTTP request targets include OAuth session values. Never log them.
        pass

    def respond(self, status, body, content_type="application/json", headers=None):
        if content_type == "application/json":
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        self.send_header("Connection", "close")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def guard(self, mutation=False):
        expected = urllib.parse.urlsplit(self.server.service.origin).netloc
        if self.headers.get_all("Host") != [expected]:
            raise AppError("forbidden", 403)
        origin = self.headers.get("Origin")
        if origin and origin != self.server.service.origin:
            raise AppError("forbidden", 403)
        if self.headers.get(
            "Sec-Fetch-Site"
        ) == "cross-site" and not self.path.startswith("/oauth/callback?"):
            raise AppError("forbidden", 403)
        if mutation and (
            self.headers.get_all("Origin") != [self.server.service.origin]
            or self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            != "application/json"
            or not secrets.compare_digest(
                self.headers.get("X-CSRF-Token", ""), self.server.service.csrf
            )
        ):
            raise AppError("forbidden", 403)

    def body(self):
        if (
            self.headers.get("Transfer-Encoding")
            or len(self.headers.get_all("Content-Length") or []) != 1
        ):
            raise AppError("validation")
        try:
            size = int(self.headers["Content-Length"])
            if not 0 < size <= MAX_BODY:
                raise ValueError
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError
            value = json.loads(
                raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError())
            )
            if not isinstance(value, dict):
                raise TypeError
            return value
        except (ValueError, TypeError, UnicodeError) as exc:
            raise AppError("validation") from exc

    def do_GET(self):
        try:
            self.guard()
            route = urllib.parse.urlsplit(self.path)
            path = route.path
            params = urllib.parse.parse_qs(route.query)
            app = self.server.service
            if path == "/api/state":
                return self.respond(200, app.state())
            if path == "/api/calendars":
                return self.respond(
                    200, self.read_operation(lambda: {"calendars": app.calendars()})
                )
            if path == "/api/devices":
                return self.respond(
                    200, self.read_operation(lambda: {"devices": app.devices()})
                )
            if path == "/api/pages":
                return self.respond(
                    200, self.read_operation(lambda: {"pages": app.page_choices()})
                )
            if path == "/api/cities":
                return self.respond(
                    200,
                    app.cities(
                        params.get("q", [""])[0], params.get("language", ["it"])[0]
                    ),
                )
            if path.startswith("/api/jobs/"):
                return self.respond(200, app.job(path.removeprefix("/api/jobs/")))
            if path.startswith("/api/artifacts/"):
                name = path.removeprefix("/api/artifacts/")
                artifact = app.artifacts.get(name)
                if artifact is None or not artifact.is_file():
                    raise AppError("not_found", 404)
                return self.respond(200, artifact.read_bytes(), "image/png")
            if path == "/oauth/callback":
                if any(len(values) != 1 for values in params.values()):
                    raise AppError("forbidden", 403)
                cookie = http.cookies.SimpleCookie()
                cookie.load(self.headers.get("Cookie", ""))
                browser = cookie.get("agenda_oauth")
                if not app.operation.acquire(blocking=False):
                    raise AppError("busy", 409)
                try:
                    app.oauth_callback(
                        {key: values[0] for key, values in params.items()},
                        browser.value if browser else None,
                    )
                finally:
                    app.operation.release()
                return self.respond(
                    303,
                    b"",
                    "text/plain",
                    {
                        "Location": "/?google=connected",
                        "Set-Cookie": "agenda_oauth=; HttpOnly; SameSite=Lax; Path=/oauth/callback; Max-Age=0",
                    },
                )
            if path.startswith("/assets/"):
                relative = urllib.parse.unquote(path.removeprefix("/assets/"))
                if relative not in approved_artwork():
                    raise AppError("not_found", 404)
                asset = (TEMPLATE / "assets" / relative).resolve()
                if (TEMPLATE / "assets").resolve() not in asset.parents:
                    raise AppError("not_found", 404)
                return self.respond(200, asset.read_bytes(), "image/png")
            if path.startswith("/api/"):
                raise AppError("not_found", 404)
            static = TEMPLATE / "configurator/static"
            relative = urllib.parse.unquote(path.lstrip("/")) or "index.html"
            target = (static / relative).resolve()
            if static.resolve() not in target.parents:
                raise AppError("not_found", 404)
            if target.is_file() and target.suffix in (
                ".html",
                ".css",
                ".js",
                ".svg",
                ".png",
                ".ico",
            ):
                return self.respond(
                    200,
                    target.read_bytes(),
                    mimetypes.guess_type(target.name)[0] or "application/octet-stream",
                )
            if path == "/":
                return self.respond(200, LANDING, "text/html; charset=utf-8")
            raise AppError("not_found", 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # noqa: BLE001 - HTTP boundary must redact any unexpected failure
            error = safe_error(exc)
            self.respond(error.status, {"error": error.public()})

    def do_POST(self):
        app = self.server.service
        acquired = False
        try:
            self.guard(mutation=True)
            data = self.body()
            path = urllib.parse.urlsplit(self.path).path
            if path in ("/api/preview", "/api/publish"):
                allowed = {"agenda", "device_id"} | (
                    {"confirm"} if path == "/api/publish" else set()
                )
                if set(data) != allowed or (
                    path == "/api/publish" and data.get("confirm") is not True
                ):
                    raise AppError("validation")
                return self.respond(
                    202,
                    app.start_job(
                        "publish" if path == "/api/publish" else "preview",
                        data["agenda"],
                        data["device_id"],
                    ),
                )
            if not app.operation.acquire(blocking=False):
                raise AppError("busy", 409)
            acquired = True
            if path == "/api/key" and set(data) == {"api_key"}:
                result = app.set_key(data["api_key"])
            elif path == "/api/google/start" and set(data) <= {"reconnect"}:
                result = app.google_start(data.get("reconnect", False))
                if isinstance(result, tuple):
                    result, browser = result
                    return self.respond(
                        200,
                        result,
                        headers={
                            "Set-Cookie": f"agenda_oauth={browser}; HttpOnly; SameSite=Lax; Path=/oauth/callback; Max-Age=600"
                        },
                    )
            elif path == "/api/google/import" and set(data) == {"page_id"}:
                result = app.import_google(data["page_id"])
            elif path == "/api/page" and set(data) == {"page_id"}:
                result = app.select_page(data["page_id"])
            elif path == "/api/save" and set(data) == {"agenda", "device_id"}:
                result = app.save(data["agenda"], data["device_id"])
            elif path == "/api/recover" and not data:
                result = app.recover()
            elif path == "/api/uploads/recover" and set(data) == {"confirm"}:
                result = app.recover_uploads(data["confirm"])
            else:
                raise AppError("not_found", 404)
            self.respond(200, result)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # noqa: BLE001 - HTTP boundary must redact any unexpected failure
            error = safe_error(exc)
            self.respond(error.status, {"error": error.public()})
        finally:
            if acquired:
                app.operation.release()

    def do_OPTIONS(self):
        self.respond(403, {"error": AppError("forbidden").public()})

    def read_operation(self, callback):
        app = self.server.service
        if not app.operation.acquire(blocking=False):
            raise AppError("busy", 409)
        try:
            return callback()
        finally:
            app.operation.release()


def bind(service, port=8765):
    if not 0 <= port <= 65535:
        raise AppError("validation")
    try:
        return LocalServer(("127.0.0.1", port), service)
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE:
            raise
        return LocalServer(("127.0.0.1", 0), service)


def open_browser(url, opener=None, output=None):
    output = output or sys.stdout
    try:
        opened = (opener or webbrowser.open)(url)
    except OSError:
        opened = False
    if not opened:
        print(
            "Browser opening failed. Open the printed URL manually.",
            file=output,
            flush=True,
        )
    return bool(opened)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the local Google Calendar Today configurator."
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    app = Service(Store())
    server = bind(app, args.port)
    print(app.origin + "/", flush=True)
    if not args.no_browser:
        open_browser(app.origin + "/")

    def shutdown(signum, frame):
        app.stopping.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    previous = {
        sig: signal.signal(sig, shutdown) for sig in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        # Finish outstanding durable jobs before exiting; transport requests are bounded.
        app.close(stop=True)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        print("Configurator stopped.", flush=True)
