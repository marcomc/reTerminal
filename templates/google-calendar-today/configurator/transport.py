"""Bounded stdlib transport. No account data or URLs in public errors/logs."""

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .errors import AppError

BASE = "https://sensecraft-hmi-api.seeed.cc"
PNG = b"\x89PNG\r\n\x1a\n"
MAX_RESPONSE = 32 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # An account credential must never be forwarded to a redirect target.
        return None


class Transport:
    def __init__(self, key):
        self.key = key
        self.opener = urllib.request.build_opener(NoRedirect)

    def _request(
        self,
        url,
        *,
        body=None,
        method=None,
        content_type="application/json",
        account=True,
        google=False,
        binary=False,
    ):
        headers = {"Content-Type": content_type}
        if account:
            headers["api-key"] = self.key()
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=60) as response:
                raw = response.read(MAX_RESPONSE + 1)
        except urllib.error.HTTPError as exc:
            exc.close()
            if exc.code in (401, 403):
                raise AppError(
                    "google_expired" if google else "key_invalid", 401
                ) from exc
            raise AppError("upstream", 502, exc.code >= 500) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AppError("network", 503, True) from exc
        if len(raw) > MAX_RESPONSE:
            raise AppError("protocol", 502)
        if binary and raw.startswith(PNG):
            return raw
        # JSON errors returned from the render endpoint still need classification.
        try:
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise TypeError
        except (ValueError, TypeError, UnicodeError) as exc:
            raise AppError("protocol", 502) from exc
        if value.get("code") != 200:
            if value.get("code") in (401, 403):
                raise AppError("google_expired" if google else "key_invalid", 401)
            raise AppError("upstream", 502)
        if binary:
            raise AppError("protocol", 502)
        return value.get("result")

    def request(
        self, route, payload=None, method=None, *, google=False, binary=False, key=None
    ):
        if key is not None:
            return Transport(lambda: key).request(
                route, payload, method, google=google, binary=binary
            )
        if not route.startswith("/") or route.startswith("//"):
            raise AppError("validation")
        return self._request(
            BASE + route,
            body=None
            if payload is None
            else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(),
            method=method,
            google=google,
            binary=binary,
        )

    def upload(self, raw, name, kind):
        boundary = "agenda-" + uuid.uuid4().hex
        mime = "text/html" if kind == "document" else "image/png"
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\n{kind}\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
            + raw
            + f"\r\n--{boundary}--\r\n".encode()
        )
        value = self._request(
            BASE + "/api/v1/oss/file/upload",
            body=body,
            content_type="multipart/form-data; boundary=" + boundary,
        )
        if not isinstance(value, dict) or not isinstance(value.get("file_url"), str):
            raise AppError("protocol", 502)
        url = urllib.parse.urlsplit(value["file_url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise AppError("protocol", 502)
        return value["file_url"]

    def cities(self, query, language):
        url = (
            "https://geocoding-api.open-meteo.com/v1/search?"
            + urllib.parse.urlencode(
                {"name": query, "count": 10, "language": language, "format": "json"}
            )
        )
        try:
            with self.opener.open(url, timeout=30) as response:
                value = json.loads(response.read(1024 * 1024))
            return value.get("results", [])
        except (OSError, ValueError) as exc:
            raise AppError("network", 503, True) from exc
