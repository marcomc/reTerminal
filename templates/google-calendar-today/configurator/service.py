"""Application lifecycle, native OAuth, asynchronous preview and private publication."""

import copy
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.parse

from .config import BOOLS, ENUMS, THEMES, atomic_json, validate
from .errors import AppError, safe_error
from .renderer import Renderer, runtime
from .transport import PNG, Transport

NATIVE_URL = "https://sensecraft.seeed.cc/hmi"
KEY_URL = NATIVE_URL + "/account"


def query(route, **params):
    return route + "?" + urllib.parse.urlencode(params)


def identifier(value):
    if type(value) not in (str, int) or not str(value) or len(str(value)) > 1024:
        raise AppError("validation")
    return str(value)


class Service:
    def __init__(self, store, transport=None, renderer=None):
        self.store = store
        self.stopping = threading.Event()
        self.transport = transport or Transport(store.key)
        self.renderer = renderer or Renderer(store, self.transport, self.checkpoint)
        self.operation = store.operation
        self.lifecycle_lock = threading.Lock()
        self.jobs_lock = threading.Lock()
        self.jobs = {}
        self.artifacts = {}
        self.threads = []
        self.oauth = None
        self.oauth_lock = threading.Lock()
        self.origin = None
        self.csrf = secrets.token_urlsafe(32)

    def connection_status(self):
        conn = self.store.connections()
        try:
            self.store.key()
            key = "configured"
        except AppError:
            key = "missing"
        return {
            "key": key,
            "key_masked": "••••" if key != "missing" else None,
            "google": "configured" if conn.get("session_id") else "missing",
            "page": "existing" if conn["resources"].get("page_id") else "new",
            "key_management_url": KEY_URL,
            "native_url": NATIVE_URL,
        }

    def calendars(self, session=None):
        self.check_override()
        self.store.key()
        session = session or self.store.connections().get("session_id")
        if not session:
            raise AppError("google_missing", 401)
        result = self.transport.request(
            query("/api/v2/calendar/list", session_id=session), google=True
        )
        if not isinstance(result, dict) or not isinstance(
            result.get("calendarList"), list
        ):
            raise AppError("protocol", 502)
        try:
            records = [
                {
                    "id": identifier(item["id"]),
                    "name": item.get("summary") or "Calendar",
                    "access_role": item.get("accessRole"),
                    "primary": item.get("primary") is True,
                    "timezone": item.get("timeZone"),
                }
                for item in result["calendarList"]
            ]
        except (TypeError, KeyError) as exc:
            raise AppError("protocol", 502) from exc
        if session == self.store.connections().get("session_id"):
            self.store.set_meta("calendars", records)
        return records

    def devices(self):
        self.check_override()
        result = self.transport.request("/api/v2/user/device/list")
        if not isinstance(result, list):
            raise AppError("protocol", 502)
        records = []
        for item in result:
            board = item.get("board") or {}
            model = board.get("type")
            # This renderer is validated for E1002's 800x480 color display only.
            compatible = model in ("E1002", "reTerminal E1002", "reterminal_e1002")
            records.append(
                {
                    "id": identifier(item["id"]),
                    "name": item.get("device_name")
                    or item.get("name")
                    or model
                    or "Device",
                    "model": model,
                    "resolution": "800x480" if compatible else item.get("resolution"),
                    "compatible": compatible,
                    "online": item.get("online_status", item.get("online")),
                }
            )
        self.store.set_meta("devices", records)
        self.store.set_meta(
            "device_bindings",
            {identifier(item["id"]): item.get("mac_address") for item in result},
        )
        return records

    def pages(self):
        self.check_override()
        records = []
        page = 1
        while True:
            result = self.transport.request(
                query("/api/v2/user/page", page=page, page_size=100, types="layout")
            )
            if not isinstance(result, dict) or not isinstance(
                result.get("pages"), list
            ):
                raise AppError("protocol", 502)
            records.extend(result["pages"])
            if len(records) >= result.get("total", len(records)):
                return records
            if not result["pages"] or page >= 1000:
                raise AppError("protocol", 502)
            page += 1

    def page_choices(self):
        result = []
        for page in self.pages():
            if not page.get("data"):
                # The account list may return an empty data placeholder; inspect detail.
                page = self.detail(identifier(page["id"]))
            try:
                layout = json.loads(page.get("data", "{}"))
                agenda = (
                    runtime.find_element(
                        layout.get("stageElements", []), "native-agenda"
                    )
                    is not None
                )
            except (ValueError, TypeError, AttributeError):
                agenda = False
            result.append(
                {
                    "id": identifier(page["id"]),
                    "name": page.get("name") or "Page",
                    "resolution": page.get("resolution"),
                    "agenda": agenda,
                }
            )
        self.store.set_meta("pages", result)
        return result

    def detail(self, page_id, kind=None):
        self.check_override()
        params = {"page_id": page_id}
        if kind:
            params["kind"] = kind
        page = self.transport.request(query("/api/v2/user/page/detail", **params))
        if (
            not isinstance(page, dict)
            or not page.get("id")
            or not isinstance(page.get("data"), str)
        ):
            raise AppError("protocol", 502)
        return page

    def state(self):
        acquired = self.operation.acquire(blocking=False)
        try:
            return self._state(acquired)
        finally:
            if acquired:
                self.operation.release()

    def _state(self, refresh):
        status = self.connection_status()
        cached = self.store.meta()
        resources = {
            name: copy.deepcopy(cached.get(name, []))
            for name in ("calendars", "devices", "pages")
        }
        errors = []
        # Avoid network reads while a publication is changing remote/local state.
        if refresh and status["key"] != "missing":
            for name, fetch in (
                ("devices", self.devices),
                ("calendars", self.calendars),
                ("pages", self.page_choices),
            ):
                try:
                    resources[name] = fetch()
                    if name == "devices":
                        status["key"] = "valid"
                    elif name == "calendars":
                        status["google"] = "valid"
                except AppError as exc:
                    errors.append(dict(resource=name, **exc.public()))
                    if exc.code == "key_invalid":
                        status["key"] = "invalid"
                    elif exc.code == "google_expired":
                        status["google"] = "expired"
                    elif exc.code in ("network", "upstream", "protocol"):
                        status["google" if name == "calendars" else "key"] = (
                            "unavailable"
                        )
        # Refresh may have reconciled an explicit override to another account.
        current = self.connection_status()
        status["page"] = current["page"]
        status["google"] = (
            "missing" if current["google"] == "missing" else status["google"]
        )
        meta = self.store.meta()
        journal = meta.get("journal") or {}
        with self.jobs_lock:
            active = next(
                (
                    copy.deepcopy(item)
                    for item in self.jobs.values()
                    if item["status"] in ("queued", "running")
                ),
                None,
            )
        return dict(
            agenda=self.store.preferences(),
            device_id=str(self.store.connections()["resources"]["device_id"])
            if self.store.connections()["resources"].get("device_id") is not None
            else None,
            connection=status,
            **resources,
            resource_errors=errors,
            csrf_token=self.csrf,
            active_job={
                "job_id": active["job_id"],
                "kind": active["kind"],
                **active["request"],
            }
            if active
            else None,
            capabilities={
                "enums": ENUMS,
                "themes": THEMES,
                "booleans": BOOLS,
                "calendar_min": 1,
                "calendar_max": 10,
                "intensity": {"min": 0, "max": 100, "step": 1},
                "oauth_callback": "requested; provider completion requires live verification",
                "preview": "native",
                "physical_delivery": False,
            },
            publication={
                "recover_available": bool(meta.get("last_published")),
                "pending": bool(journal and journal.get("phase") != "complete"),
                "phase": journal.get("phase"),
                "published_at": meta.get("last_published", {}).get("published_at"),
                "uncertain_uploads": sum(
                    not item.get("url") for item in meta.get("uploads", {}).values()
                ),
            },
        )

    def check_override(self):
        explicit = (
            os.environ.get("SENSECRAFT_API_KEY") if self.store.use_environment else None
        )
        if explicit and explicit != self.store.connections().get("api_key"):
            self.set_key(explicit)

    @staticmethod
    def account_identity(profile):
        if not isinstance(profile, dict):
            raise AppError("protocol", 502)
        profile = profile.get("user", profile)
        if not isinstance(profile, dict):
            raise AppError("protocol", 502)
        value = profile.get("id") or profile.get("user_id") or profile.get("uid")
        if value is None:
            raise AppError("protocol", 502)
        return hashlib.sha256(str(value).encode()).hexdigest()

    def set_key(self, key):
        if (
            not isinstance(key, str)
            or not 1 <= len(key.strip()) <= 4096
            or any(ord(char) < 33 for char in key.strip())
        ):
            raise AppError("validation")
        key = key.strip()
        explicit = (
            os.environ.get("SENSECRAFT_API_KEY") if self.store.use_environment else None
        )
        if explicit and explicit != key:
            raise AppError("environment_override", 409)
        profile = self.transport.request("/api/v2/auth/profile", key=key)
        account = self.account_identity(profile)
        conn = self.store.connections()
        old_account = conn.get("account_identity")
        old_key = conn.get("api_key")
        if old_account is None and old_key:
            try:
                old_account = self.account_identity(
                    self.transport.request("/api/v2/auth/profile", key=old_key)
                )
            except AppError:
                old_account = None
        same = (old_key == key) or (old_account == account)
        if not same and (old_key or conn.get("session_id") or conn["resources"]):
            # Preserve prior account bindings for recovery without reusing them under a new key.
            history = conn.get("_account_history", [])
            history.append({k: v for k, v in conn.items() if k != "_account_history"})
            conn = {"resources": {}, "_account_history": history}
        conn["api_key"] = key
        conn["account_identity"] = account
        self.store.write_connection(conn)
        with self.oauth_lock:
            self.oauth = None
        status = self.connection_status()
        status["key"] = "valid"
        return {"connection": status}

    def google_start(self, reconnect=False):
        self.check_override()
        if type(reconnect) is not bool:
            raise AppError("validation")
        if not reconnect and self.store.connections().get("session_id"):
            try:
                return {
                    "status": "valid",
                    "calendars": self.calendars(),
                    "authorize_url": None,
                    "native_url": NATIVE_URL,
                    "expires_in": 0,
                }
            except AppError as exc:
                if exc.code != "google_expired":
                    raise
        self.store.key()
        nonce = secrets.token_urlsafe(32)
        browser = secrets.token_urlsafe(32)
        with self.oauth_lock:
            self.oauth = {
                "nonce": nonce,
                "browser": browser,
                "expires": time.monotonic() + 600,
            }
        redirect = (
            self.origin + "/oauth/callback?" + urllib.parse.urlencode({"state": nonce})
        )
        fallback = {
            "status": "guided",
            "authorize_url": None,
            "native_url": NATIVE_URL,
            "instructions": "Open SenseCraft, connect Google Calendar in a private page editor, save that page, then select it here to import the validated connection.",
            "expires_in": 600,
        }
        try:
            result = self.transport.request(
                query("/api/v2/calendar/authorize", redirect_uri=redirect)
            )
            url = result.get("auth_url") if isinstance(result, dict) else None
            parsed = urllib.parse.urlsplit(url or "")
            if (
                parsed.scheme != "https"
                or parsed.hostname != "accounts.google.com"
                or parsed.username
                or parsed.password
            ):
                raise AppError("protocol", 502)
            fallback.update(status="authorize", authorize_url=url)
        except AppError as exc:
            if exc.code in ("key_invalid", "key_missing"):
                raise
        return fallback, browser

    def oauth_callback(self, params, browser):
        with self.oauth_lock:
            pending = self.oauth
            if (
                not pending
                or pending["expires"] <= time.monotonic()
                or not secrets.compare_digest(params.get("state", ""), pending["nonce"])
                or not secrets.compare_digest(browser or "", pending["browser"])
            ):
                raise AppError("forbidden", 403)
            session = params.get("session_id")
            if not isinstance(session, str) or not session or len(session) > 4096:
                raise AppError("validation")
            records = self.calendars(session)
            self.store.change_connection(
                lambda conn: conn.__setitem__("session_id", session)
            )
            self.store.set_meta("calendars", records)
            self.oauth = None

    def import_google(self, page_id):
        page = self.detail(identifier(page_id))
        try:
            layout = json.loads(page["data"])
        except ValueError as exc:
            raise AppError("protocol", 502) from exc
        sessions = set()

        def visit(value):
            if isinstance(value, dict):
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
            elif isinstance(value, str) and value.startswith("https://"):
                parsed = urllib.parse.urlsplit(value)
                if (
                    parsed.hostname == "sensecraft-hmi-api.seeed.cc"
                    and parsed.path == "/api/v2/calendar/events"
                ):
                    session = urllib.parse.parse_qs(parsed.query).get(
                        "session_id", [None]
                    )[0]
                    if session:
                        sessions.add(session)
                config = urllib.parse.parse_qs(parsed.fragment).get("config", [None])[0]
                if config:
                    try:
                        session = json.loads(config).get("session_id")
                        if isinstance(session, str) and session:
                            sessions.add(session)
                    except (ValueError, AttributeError):
                        pass

        visit(layout)
        if len(sessions) != 1:
            raise AppError("google_missing", 401)
        session = sessions.pop()
        records = self.calendars(session)
        self.store.change_connection(
            lambda conn: conn.__setitem__("session_id", session)
        )
        self.store.set_meta("calendars", records)
        return {"status": "valid", "calendars": records}

    def select_page(self, page_id):
        page_id = identifier(page_id)
        page = self.detail(page_id)
        layout = json.loads(page["data"])
        if page.get("resolution") != "800x480" or not runtime.find_element(
            layout.get("stageElements", []), "native-agenda"
        ):
            raise AppError("validation")
        if self.store.meta().get("journal", {}).get("phase") not in (None, "complete"):
            raise AppError("busy", 409)
        self.store.change_connection(
            lambda conn: conn["resources"].__setitem__("page_id", page_id)
        )
        return {"page_id": page_id}

    def cities(self, text, language="it"):
        if (
            not isinstance(text, str)
            or not 2 <= len(text.strip()) <= 100
            or language not in ENUMS["language"]
        ):
            raise AppError("validation")
        records = self.transport.cities(text.strip(), language)
        return {
            "cities": [
                {
                    key: item.get(key)
                    for key in (
                        "id",
                        "name",
                        "country",
                        "admin1",
                        "latitude",
                        "longitude",
                        "timezone",
                    )
                }
                for item in records
            ]
        }

    def preflight(self, agenda, device_id, *, fresh=True):
        self.check_override()
        agenda = validate(agenda)
        device_id = identifier(device_id)
        meta = self.store.meta()
        calendars = (
            self.calendars()
            if fresh or not meta.get("calendars")
            else meta["calendars"]
        )
        devices = (
            self.devices() if fresh or not meta.get("devices") else meta["devices"]
        )
        allowed = {item["id"] for item in calendars}
        if any(item["id"] not in allowed for item in agenda["calendars"]):
            raise AppError("validation")
        device = next(
            (
                item
                for item in devices
                if item["id"] == device_id and item["compatible"]
            ),
            None,
        )
        if device is None:
            raise AppError("validation")
        return agenda, device_id

    def save(self, agenda, device_id):
        agenda, device_id = self.preflight(agenda, device_id, fresh=False)
        self.store.save(agenda, device_id)
        return {"saved": True, "agenda": agenda, "device_id": device_id}

    def recover(self):
        self.check_override()
        published = self.store.meta().get("last_published")
        if not published:
            raise AppError("not_found", 404)
        self.store.save(published["agenda"], published["device_id"])
        return {
            "restored": True,
            "agenda": published["agenda"],
            "device_id": published["device_id"],
            "remote_changed": False,
        }

    def recover_uploads(self, confirm):
        if confirm is not True:
            raise AppError("validation")
        self.check_override()
        cache = self.store.meta().get("uploads", {})
        pending = {key: entry for key, entry in cache.items() if not entry.get("url")}
        if not pending:
            return {
                "cleared": 0,
                "remote_changed": False,
                "possible_orphan_upload": False,
            }
        history = self.store.meta().get("upload_uncertainty_history", [])
        history.append({"acknowledged_at": time.time(), "pending": pending})
        self.store.set_meta("upload_uncertainty_history", history)
        self.store.set_meta(
            "uploads", {key: entry for key, entry in cache.items() if entry.get("url")}
        )
        return {
            "cleared": len(pending),
            "remote_changed": False,
            "possible_orphan_upload": True,
        }

    def phase(self, job_id, phase):
        self.checkpoint()
        with self.jobs_lock:
            self.jobs[job_id]["phase"] = phase

    def checkpoint(self):
        if self.stopping.is_set():
            raise AppError("stopped", 503, True)

    def start_job(self, kind, agenda, device_id):
        self.checkpoint()
        # Validate form synchronously; ownership/network checks belong to the job.
        agenda = validate(agenda)
        device_id = identifier(device_id)
        if not self.operation.acquire(blocking=False):
            raise AppError("busy", 409)
        job_id = secrets.token_hex(16)
        with self.lifecycle_lock:
            thread = None
            try:
                self.checkpoint()
                with self.jobs_lock:
                    self.jobs[job_id] = {
                        "job_id": job_id,
                        "kind": kind,
                        "status": "queued",
                        "phase": "preflight",
                        "result": None,
                        "error": None,
                        "request": {"agenda": agenda, "device_id": device_id},
                    }
                thread = threading.Thread(
                    target=self._run_job,
                    args=(job_id, kind, agenda, device_id),
                    name="agenda-" + kind,
                    daemon=False,
                )
                self.threads.append(thread)
                thread.start()
            except BaseException as exc:
                if thread in self.threads:
                    self.threads.remove(thread)
                with self.jobs_lock:
                    self.jobs.pop(job_id, None)
                self.operation.release()
                if isinstance(exc, Exception):
                    raise safe_error(exc) from exc
                raise
        return {
            "job_id": job_id,
            "status": "queued",
            "status_url": "/api/jobs/" + job_id,
        }

    def _run_job(self, job_id, kind, agenda, device_id):
        try:
            with self.jobs_lock:
                self.jobs[job_id]["status"] = "running"
            agenda, device_id = self.preflight(agenda, device_id)
            if kind == "publish":
                result = self.publish(job_id, agenda, device_id)
            else:
                self.phase(job_id, "build")
                candidate = self.renderer.build(agenda, device_id)
                page_id = self.store.connections()["resources"].get("page_id")
                if page_id:
                    candidate = runtime.merge_candidate(
                        json.loads(self.detail(page_id)["data"]), candidate
                    )
                self.phase(job_id, "preview")
                raw = self.preview(candidate)
                preview_url = self.save_preview(job_id, raw)
                result = {"preview_url": preview_url}
            with self.jobs_lock:
                self.jobs[job_id].update(
                    status="succeeded", phase="complete", result=result
                )
        except Exception as exc:  # noqa: BLE001 - job boundary must redact any unexpected failure
            with self.jobs_lock:
                self.jobs[job_id].update(
                    status="failed", error=safe_error(exc).public()
                )
        finally:
            self.operation.release()

    def preview(self, layout):
        raw = self.transport.request(
            "/render/preview",
            {
                "layout": layout,
                "resolution": "800x480",
                "dither": 3,
                "img_format": "png",
            },
            binary=True,
        )
        if not isinstance(raw, bytes) or not raw.startswith(PNG):
            raise AppError("protocol", 502)
        return raw

    def save_preview(self, job_id, raw):
        directory = self.store.state / "configurator-previews"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / (job_id + ".png")
        path.write_bytes(raw)
        path.chmod(0o600)
        self.artifacts[job_id + ".png"] = path
        return "/api/artifacts/" + job_id + ".png"

    def publish(self, job_id, agenda, device_id):
        self.checkpoint()
        digest = hashlib.sha256(
            json.dumps(
                {"agenda": agenda, "device_id": device_id}, sort_keys=True
            ).encode()
        ).hexdigest()
        journal = self.store.meta().get("journal")
        if (
            journal
            and journal.get("phase") != "complete"
            and journal.get("digest") != digest
        ):
            raise AppError("busy", 409)
        if not journal or journal.get("phase") == "complete":
            journal = {
                "digest": digest,
                "phase": "build",
                "agenda": agenda,
                "device_id": device_id,
                "name": "Google Calendar Today " + secrets.token_hex(8),
            }
            self.store.set_meta("journal", journal)
        self.store.save(agenda, device_id)
        if "layout" not in journal:
            self.phase(job_id, "build")
            candidate = self.renderer.build(agenda, device_id)
            page_id = self.store.connections()["resources"].get("page_id")
            if page_id:
                before = self.detail(page_id)
                atomic_json(
                    self.store.state / ("before-page-" + job_id + ".json"), before
                )
                candidate = runtime.merge_candidate(
                    json.loads(before["data"]), candidate
                )
                journal["page_id"] = page_id
                journal["metadata"] = {
                    key: before[key]
                    for key in (
                        "name",
                        "type",
                        "resolution",
                        "dither",
                        "description",
                        "tags",
                    )
                    if key in before
                }
            journal["layout"] = candidate
            self.store.set_meta("journal", journal)
        layout = journal["layout"]
        if "thumbnail" not in journal:
            self.phase(job_id, "preview")
            raw = self.preview(layout)
            self.save_preview(job_id, raw)
            journal["thumbnail"] = self.renderer.upload(
                raw, "agenda-preview.png", "thumbnail"
            )
            self.store.set_meta("journal", journal)
        self.phase(job_id, "save_page")
        if not journal.get("page_id"):
            self.checkpoint()
            if journal.get("creation_attempted"):
                matches = [
                    item for item in self.pages() if item.get("name") == journal["name"]
                ]
                if len(matches) != 1:
                    raise AppError("uncertain_create", 409, True)
                page = self.detail(matches[0]["id"])
                if json.loads(page["data"]) != layout:
                    raise AppError("readback", 409, True)
                journal["page_id"] = identifier(page["id"])
            else:
                journal.update(creation_attempted=True, phase="create")
                self.store.set_meta("journal", journal)
                body = {
                    "name": journal["name"],
                    "type": "layout",
                    "data": json.dumps(
                        layout, separators=(",", ":"), ensure_ascii=False
                    ),
                    "thumbnail": journal["thumbnail"],
                    "resolution": "800x480",
                    "dither": 3,
                }
                try:
                    result = self.transport.request(
                        "/api/v2/user/page", {"pages": [body]}, "POST"
                    )
                    ids = result.get("ids") if isinstance(result, dict) else None
                    if not isinstance(ids, list) or len(ids) != 1:
                        raise AppError("protocol", 502)
                    journal["page_id"] = identifier(ids[0])
                except AppError as exc:
                    if (
                        exc.code in ("key_invalid", "key_missing", "upstream")
                        and not exc.retryable
                    ):
                        journal.pop("creation_attempted", None)
                        self.store.set_meta("journal", journal)
                        raise
                    raise AppError("uncertain_create", 409, True) from exc
            self.store.set_meta("journal", journal)
            self.store.change_connection(
                lambda conn: conn["resources"].__setitem__(
                    "page_id", journal["page_id"]
                )
            )
        page_id = journal["page_id"]
        # Reconcile readback before any repeat PUT: upstream may have applied it.
        page = self.detail(page_id)
        expected_name = journal.get("metadata", {}).get("name", "Google Calendar Today")
        if json.loads(page["data"]) != layout or page.get("name") != expected_name:
            self.checkpoint()
            payload = dict(
                journal.get("metadata", {}),
                id=page_id,
                name=expected_name,
                data=json.dumps(layout, separators=(",", ":"), ensure_ascii=False),
                thumbnail=journal["thumbnail"],
            )
            journal["phase"] = "save_page"
            self.store.set_meta("journal", journal)
            self.transport.request("/api/v2/user/page", payload, "PUT")
            page = self.detail(page_id)
        if json.loads(page["data"]) != layout or page.get("name") != expected_name:
            raise AppError("readback", 409, True)
        journal["phase"] = "deploy"
        self.store.set_meta("journal", journal)
        self.phase(job_id, "deploy")
        mac = self.store.meta().get("device_bindings", {}).get(device_id)
        if not mac:
            raise AppError("validation")
        # Refresh is repeatable: it updates an existing assignment without creating pages/uploads.
        self.transport.request(
            "/api/v2/user/device/deploy",
            {"mode": "refresh", "page_ids": [page_id], "mac_addresses": [mac]},
            "POST",
        )
        self.phase(job_id, "verify")
        assignment = self.transport.request(
            query("/api/v2/user/device/playlist", mac_address=mac, type="all")
        )
        pages = assignment.get("pages", []) if isinstance(assignment, dict) else []
        entry = next(
            (
                item
                for item in pages
                if str(item.get("source_page_id") or item.get("id")) == str(page_id)
            ),
            None,
        )
        if not entry:
            raise AppError("readback", 409, True)
        snapshot_verified = False
        if entry.get("kind") == "snapshot":
            snapshot = self.detail(entry["id"], "snapshot")
            if (
                json.loads(snapshot["data"]) != layout
                or snapshot.get("resolution") != "800x480"
                or snapshot.get("dither") != 3
            ):
                raise AppError("readback", 409, True)
            snapshot_verified = True
        # A fresh source readback is also checked after deployment.
        page = self.detail(page_id)
        if (
            json.loads(page["data"]) != layout
            or page.get("resolution") != "800x480"
            or page.get("dither") != 3
        ):
            raise AppError("readback", 409, True)
        atomic_json(self.store.state / "persisted-private.json", layout)
        self.store.set_meta(
            "last_published",
            {
                "agenda": agenda,
                "device_id": device_id,
                "page_id": page_id,
                "published_at": time.time(),
            },
        )
        journal["phase"] = "complete"
        self.store.set_meta("journal", journal)
        return {
            "published": True,
            "page_exact_readback": True,
            "assignment_verified": True,
            "snapshot_verified": snapshot_verified,
            "physical_delivery_confirmed": False,
        }

    def job(self, job_id):
        with self.jobs_lock:
            if job_id not in self.jobs:
                raise AppError("not_found", 404)
            return {
                key: copy.deepcopy(value)
                for key, value in self.jobs[job_id].items()
                if key != "request"
            }

    def close(self, *, stop=False):
        with self.lifecycle_lock:
            if stop:
                self.stopping.set()
            threads = tuple(self.threads)
        for thread in threads:
            thread.join()
