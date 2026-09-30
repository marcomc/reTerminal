"""Reuse the original autonomous renderer; keep private binding in URL fragments."""

import hashlib
import importlib.util
import json
import urllib.parse

from .config import TEMPLATE, atomic_json
from .errors import AppError

spec = importlib.util.spec_from_file_location(
    "agenda_runtime", TEMPLATE / "scripts/runtime.py"
)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def approved_artwork():
    root = TEMPLATE / "assets"
    manifest = json.loads((root / "manifest.json").read_text())
    entries = {}
    for entry in manifest["decorations"]:
        path = (root / entry["path"]).resolve()
        if root.resolve() not in path.parents or path.suffix != ".png":
            raise AppError("validation")
        entries[entry["path"]] = entry
    return entries


class Renderer:
    def __init__(self, store, transport, checkpoint=None):
        self.store = store
        self.transport = transport
        self.checkpoint = checkpoint or (lambda: None)

    def upload(self, raw, name, kind):
        self.checkpoint()
        digest = hashlib.sha256(raw).hexdigest()
        cache_key = kind + "|" + digest
        cache = self.store.meta().get("uploads", {})
        entry = cache.get(cache_key)
        if entry and entry.get("url"):
            return entry["url"]
        if entry:
            raise AppError("uncertain_upload", 409)
        # Import content-addressed legacy cache from this installation only.
        # A key/account change clears bindings and disables this legacy import.
        if not self.store.connections().get("_account_history"):
            legacy = self.store.state / (
                "thumbnail-uploads.json" if kind == "thumbnail" else "uploads.json"
            )
            if legacy.exists():
                try:
                    old = json.loads(legacy.read_text())
                    value = (
                        old.get(digest)
                        if kind == "thumbnail"
                        else old.get(name + "|" + digest, {}).get("url")
                    )
                    parsed = urllib.parse.urlsplit(value or "")
                    if (
                        parsed.scheme == "https"
                        and parsed.hostname
                        and not parsed.username
                        and not parsed.password
                        and not parsed.fragment
                    ):
                        cache[cache_key] = {
                            "url": value,
                            "sha256": digest,
                            "status": "complete",
                        }
                        self.store.set_meta("uploads", cache)
                        return value
                except (ValueError, TypeError, AttributeError):
                    pass
        # Write intent before mutation. An interrupted request is never blindly repeated.
        cache[cache_key] = {"status": "pending", "name": name}
        self.store.set_meta("uploads", cache)
        try:
            url = self.transport.upload(raw, name, kind)
        except AppError as exc:
            if (
                exc.code in ("key_invalid", "key_missing", "upstream")
                and not exc.retryable
            ):
                cache.pop(cache_key, None)
                self.store.set_meta("uploads", cache)
                raise
            raise AppError("uncertain_upload", 409) from exc
        cache[cache_key] = {"url": url, "sha256": digest, "status": "complete"}
        self.store.set_meta("uploads", cache)
        return url

    def build(self, agenda, device_id):
        assets = {}
        for relative, entry in sorted(approved_artwork().items()):
            path = TEMPLATE / "assets" / relative
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise AppError("validation")
            if path.parent.name == "monthly":
                name = (
                    "month-"
                    + path.name[:2]
                    + ("-dark" if path.stem.endswith("-dark") else "")
                )
            else:
                name = path.stem
            assets[name] = {
                "url": self.upload(raw, path.name, "image"),
                "mockup": entry["mockup_crop"],
            }
        for name in list(assets):
            if name.endswith("-dark") and name[:-5] in assets:
                assets[name[:-5]]["darkUrl"] = assets[name]["url"]
                assets[name[:-5]]["darkMockup"] = assets[name]["mockup"]
        html = runtime.production_html(
            (TEMPLATE / "src/agenda.html").read_text(), assets
        )
        conn = self.store.connections()
        forbidden = [self.store.key(), conn.get("session_id", "")]
        if any(value and value in html for value in forbidden):
            raise AppError("validation")
        document = self.store.state / "agenda-upload.html"
        document.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        document.write_text(html)
        document.chmod(0o600)
        url = self.upload(html.encode(), "agenda-upload.html", "document")
        private = dict(agenda, session_id=conn["session_id"])
        if agenda["showBattery"]:
            private["batteryBinding"] = {
                "deviceId": device_id,
                "apiKey": self.store.key(),
            }
        url += "#" + urllib.parse.urlencode(
            {"config": json.dumps(private, separators=(",", ":"), ensure_ascii=False)}
        )
        candidate = {
            "stageSize": {"width": 800, "height": 480},
            "dither": 3,
            "stageElements": [
                {
                    "id": "__device_container_group__",
                    "type": "group",
                    "x": 0,
                    "y": 0,
                    "width": 800,
                    "height": 480,
                    "fill": "#ffffff",
                    "strokeWidth": 0,
                    "children": [
                        {
                            "id": "native-agenda",
                            "type": "html",
                            "x": 0,
                            "y": 0,
                            "width": 800,
                            "height": 480,
                            "htmlConfig": {"htmlUrl": url},
                        }
                    ],
                }
            ],
        }
        atomic_json(self.store.state / "candidate-private.json", candidate)
        return candidate
