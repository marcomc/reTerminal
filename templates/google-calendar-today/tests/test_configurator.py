"""Isolated lifecycle/security tests: no live account writes or installed settings."""

import copy
import hashlib
import http.client
import io
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest.mock import patch

TEMPLATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TEMPLATE))
from configurator.config import (
    BOOLS,
    ENUMS,
    THEMES,
    Store,
    atomic_json,
    defaults,
    validate,
)
from configurator.errors import AppError
from configurator.renderer import approved_artwork
from configurator.server import bind, open_browser
from configurator.service import Service
from configurator.transport import PNG, Transport


def agenda():
    result = defaults()
    result["calendars"] = [
        {
            "id": "calendar-a",
            "name": "Sample calendar",
            "initials": "AA",
            "color": "#123456",
        }
    ]
    return result


def layout(url="https://assets.example.test/agenda.html#config=old"):
    return {
        "stageSize": {"width": 800, "height": 480},
        "editorMetadata": {"retain": True},
        "stageElements": [
            {
                "id": "group",
                "children": [
                    {"id": "native-agenda", "htmlConfig": {"htmlUrl": url}},
                    {"id": "native-battery"},
                    {"id": "editor-note"},
                ],
            }
        ],
    }


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.uploads = []
        self.account = "account-a"
        self.auth = True
        self.session = True
        self.network = False
        self.upload_fail = False
        self.create_timeout = False
        self.save_timeout = False
        self.deploy_fail = False
        self.snapshot_bad = False
        self.assign = True
        self.created = 0
        self.page = {
            "id": "page-a",
            "name": "Sample agenda",
            "data": json.dumps(layout()),
            "resolution": "800x480",
            "dither": 3,
            "description": "keep",
            "tags": ["safe"],
        }
        self.pages_data = [self.page]

    def request(self, route, payload=None, method=None, **kwargs):
        self.calls.append((route.split("?")[0], method, copy.deepcopy(payload)))
        if self.network:
            raise AppError("network", 503, True)
        if route == "/api/v2/auth/profile":
            if not self.auth:
                raise AppError("key_invalid", 401)
            key = kwargs.get("key")
            return {
                "user": {
                    "user_id": "account-b" if key == "new-account-key" else self.account
                }
            }
        if not self.auth:
            raise AppError("key_invalid", 401)
        if route.startswith("/api/v2/calendar/list"):
            if not self.session or "invalid-session" in route:
                raise AppError("google_expired", 401)
            return {
                "calendarList": [
                    {
                        "id": "calendar-a",
                        "summary": "Sample calendar",
                        "accessRole": "owner",
                        "primary": True,
                    },
                    {
                        "id": "calendar-b",
                        "summary": "Subscribed",
                        "accessRole": "reader",
                    },
                ]
            }
        if route == "/api/v2/user/device/list":
            return [
                {
                    "id": "device-a",
                    "device_name": "Sample display",
                    "mac_address": "sample-mac",
                    "board": {"type": "reterminal_e1002"},
                    "online_status": "online",
                },
                {"id": "unsupported", "board": {"type": "unknown"}},
            ]
        if route.startswith("/api/v2/calendar/authorize"):
            return {
                "auth_url": "https://accounts.google.com/o/oauth2/auth?state=provider-owned"
            }
        if route.startswith("/api/v2/user/page/detail"):
            if "kind=snapshot" in route and self.snapshot_bad:
                return dict(self.page, data="{}")
            return copy.deepcopy(self.page)
        if route.startswith("/api/v2/user/page?"):
            return {
                "total": len(self.pages_data),
                "pages": copy.deepcopy(self.pages_data),
            }
        if route == "/render/preview":
            return PNG + b"fixture"
        if route == "/api/v2/user/page" and method == "POST":
            self.created += 1
            self.page = dict(payload["pages"][0], id="page-created")
            self.pages_data.append(self.page)
            if self.create_timeout:
                self.create_timeout = False
                raise AppError("network", 503, True)
            return {"ids": [self.page["id"]]}
        if route == "/api/v2/user/page" and method == "PUT":
            self.page.update(payload)
            if self.save_timeout:
                self.save_timeout = False
                raise AppError("network", 503, True)
            return None  # A successful write may omit result.
        if route == "/api/v2/user/device/deploy":
            if self.deploy_fail:
                raise AppError("network", 503, True)
            return None
        if route.startswith("/api/v2/user/device/playlist"):
            return {
                "pages": [
                    {
                        "id": "snapshot-a",
                        "source_page_id": self.page["id"],
                        "kind": "snapshot",
                    }
                ]
                if self.assign
                else []
            }
        raise AssertionError(route)

    def upload(self, raw, name, kind):
        self.uploads.append((name, kind, raw))
        if self.upload_fail:
            raise AppError("network", 503, True)
        return "https://assets.example.test/" + name

    def cities(self, text, language):
        return [
            {
                "id": 1,
                "name": "Sample city",
                "country": "Example",
                "latitude": 1,
                "longitude": 2,
                "timezone": "UTC",
            }
        ]


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root, use_environment=False)
        self.fake = FakeTransport()
        self.store.write_connection(
            {
                "api_key": "sample-private-key",
                "session_id": "sample-private-session",
                "resources": {"page_id": "page-a", "device_id": "device-a"},
            }
        )
        self.app = Service(self.store, self.fake)
        self.app.origin = "http://127.0.0.1:8765"

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def run_job(self, kind="publish", settings=None):
        result = self.app.start_job(kind, settings or agenda(), "device-a")
        self.app.close()
        return self.app.job(result["job_id"])


class StorageTests(BaseCase):
    def test_fresh_install_default_and_permissions(self):
        fresh = Store(self.root / "fresh", use_environment=False)
        self.assertEqual(fresh.preferences()["calendars"], [])
        self.assertEqual(fresh.connections()["resources"], {})
        for path in (fresh.config, fresh.connection):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_migration_preserves_legacy_and_existing_bindings(self):
        root = self.root / "legacy"
        root.mkdir()
        atomic_json(
            root / "sensecraft.local.json",
            {
                "agenda": dict(
                    agenda(),
                    session_id="old-session",
                    batteryBinding={"apiKey": "old-key"},
                ),
                "resources": {"page_id": "old-page", "device_id": "old-device"},
                "extra": {"preserved": True},
            },
        )
        atomic_json(
            root / "sensecraft.connection.local.json",
            {
                "resources": {"device_id": "existing-device"},
                "session_id": "existing-session",
            },
        )
        (root / ".env").write_text(
            'export SENSECRAFT_API_KEY="legacy-key"\nDONT_RUN=$(false)\n'
        )
        migrated = Store(root, use_environment=False)
        self.assertEqual(migrated.connections()["api_key"], "legacy-key")
        self.assertEqual(migrated.connections()["session_id"], "existing-session")
        self.assertEqual(migrated.connections()["resources"]["page_id"], "old-page")
        self.assertEqual(
            migrated.connections()["resources"]["device_id"], "existing-device"
        )
        self.assertNotIn("session_id", migrated.preferences())
        self.assertNotIn("batteryBinding", migrated.preferences())
        self.assertEqual(
            json.loads(migrated.config.read_text())["extra"], {"preserved": True}
        )

    def test_atomic_failure_keeps_previous_contents_and_removes_temp(self):
        before = self.store.connection.read_bytes()
        with (
            patch("configurator.config.os.replace", side_effect=OSError("injected")),
            self.assertRaises(OSError),
        ):
            atomic_json(self.store.connection, {"broken": True})
        self.assertEqual(self.store.connection.read_bytes(), before)
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_private_reconstruction_retains_journal_cache_and_preferences(self):
        self.run_job()
        conn = self.store.connections()
        pref = self.store.preferences()
        shutil.rmtree(self.store.state)
        restarted = Store(self.root, use_environment=False)
        self.assertEqual(restarted.connections(), conn)
        self.assertEqual(restarted.preferences(), pref)
        self.assertTrue(restarted.meta()["uploads"])
        self.assertTrue(restarted.meta()["last_published"])

    def test_environment_override(self):
        store = Store(self.root, use_environment=False)
        store.use_environment = True
        with patch.dict(os.environ, {"SENSECRAFT_API_KEY": "override"}):
            self.assertEqual(store.key(), "override")
        self.assertEqual(store.key(), "sample-private-key")

    def test_interrupted_migration_retries_without_losing_session(self):
        original = dict(agenda(), session_id="legacy-session")
        atomic_json(
            self.store.config,
            {"agenda": original, "resources": {"page_id": "legacy-page"}},
        )
        self.store.connection.unlink()
        from configurator import config as config_module

        write = config_module.atomic_json

        def fail_preferences(path, value):
            if path == self.store.config:
                raise OSError("injected preference failure")
            return write(path, value)

        with (
            patch.object(config_module, "atomic_json", side_effect=fail_preferences),
            self.assertRaises(OSError),
        ):
            self.store.migrate()
        self.store.migrate()
        self.assertEqual(self.store.connections()["session_id"], "legacy-session")
        self.assertEqual(
            self.store.connections()["resources"]["page_id"], "legacy-page"
        )


class ProcessLockTests(BaseCase):
    def child(self, code):
        return subprocess.Popen(
            [sys.executable, "-u", "-c", code, str(self.root), str(TEMPLATE)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_shared_process_operation_is_busy_then_recovers(self):
        code = """
import sys
sys.path.insert(0, sys.argv[2])
from configurator.config import Store
s = Store(sys.argv[1], use_environment=False)
print('ready', flush=True)
for line in sys.stdin:
    acquired = s.operation.acquire(blocking=False)
    print('acquired' if acquired else 'busy', flush=True)
    if acquired:
        s.set_meta('child_completed', True)
        s.operation.release()
"""
        child = self.child(code)
        try:
            self.assertEqual(child.stdout.readline().strip(), "ready")
            self.app.operation.acquire()
            try:
                child.stdin.write("check\n")
                child.stdin.flush()
                self.assertEqual(child.stdout.readline().strip(), "busy")
            finally:
                self.app.operation.release()
            child.stdin.write("check\n")
            child.stdin.flush()
            self.assertEqual(child.stdout.readline().strip(), "acquired")
            child.stdin.close()
            child.wait(timeout=10)
            self.assertTrue(self.store.meta()["child_completed"])
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
            child.stdout.close()
            child.stderr.close()

    def test_initialization_refuses_shared_active_operation(self):
        self.app.operation.acquire()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.path.insert(0, sys.argv[2]); from configurator.config import Store; from configurator.errors import AppError\ntry: Store(sys.argv[1], use_environment=False)\nexcept AppError as e: print(e.code)",
                    str(self.root),
                    str(TEMPLATE),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            self.assertEqual(result.stdout.strip(), "busy")
            self.assertEqual(result.stderr, "")
        finally:
            self.app.operation.release()

    def test_cross_process_read_modify_write_preserves_every_update(self):
        code = """
import sys
sys.path.insert(0, sys.argv[2])
from configurator.config import Store
s = Store(sys.argv[1], use_environment=False)
print('ready', flush=True)
sys.stdin.readline()
for _ in range(100):
    s.change_connection(lambda c: c.__setitem__('counter', c.get('counter', 0) + 1))
"""
        children = []
        try:
            for _ in range(2):
                child = self.child(code)
                children.append(child)
                self.assertEqual(child.stdout.readline().strip(), "ready")
            for child in children:
                child.stdin.write("start\n")
                child.stdin.flush()
                child.stdin.close()
            for child in children:
                self.assertEqual(child.wait(timeout=15), 0)
            self.assertEqual(self.store.connections()["counter"], 200)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=10)
                child.stdout.close()
                child.stderr.close()


class ValidationTests(BaseCase):
    def test_all_approved_options(self):
        for key, values in dict(ENUMS, theme=THEMES).items():
            for value in values:
                config = agenda()
                config[key] = value
                self.assertEqual(validate(config)[key], value)
        for key in BOOLS:
            for value in (True, False):
                config = agenda()
                config[key] = value
                validate(config)
        for intensity in range(101):
            config = agenda()
            config["intensity"] = intensity
            validate(config)
        for count in (1, 10):
            config = agenda()
            config["calendars"] = [
                dict(config["calendars"][0], id=f"calendar-{i}") for i in range(count)
            ]
            validate(config)

    def test_invalid_options_and_secret_injection(self):
        invalid = [
            ("intensity", True),
            ("intensity", 1.1),
            ("intensity", 101),
            ("latitude", float("nan")),
            ("latitude", 91),
            ("longitude", True),
            ("timezone", "invalid"),
            ("showMoon", "true"),
            ("titleSize", 24),
            ("city", ""),
            ("theme", "other"),
            ("language", []),
            ("session_id", "injected"),
        ]
        for key, value in invalid:
            config = agenda()
            config[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(AppError):
                validate(config)
        for key, value in (
            ("initials", "ABCDE"),
            ("initials", " "),
            ("color", "red"),
            ("id", ""),
            ("name", ""),
        ):
            config = agenda()
            config["calendars"][0][key] = value
            with self.assertRaises(AppError):
                validate(config)
        for records in ([], agenda()["calendars"] * 2, agenda()["calendars"] * 11):
            with self.assertRaises(AppError):
                validate(dict(agenda(), calendars=records))

    def test_unknown_calendar_or_unsupported_device_refused(self):
        with self.assertRaises(AppError):
            self.app.save(
                dict(
                    agenda(), calendars=[dict(agenda()["calendars"][0], id="unknown")]
                ),
                "device-a",
            )
        with self.assertRaises(AppError):
            self.app.save(agenda(), "unsupported")

    def test_city_search_validation(self):
        self.assertEqual(self.app.cities("Sample")["cities"][0]["timezone"], "UTC")
        for query in ("", "a", "a" * 101):
            with self.assertRaises(AppError):
                self.app.cities(query)


class LifecycleTests(BaseCase):
    def test_thread_start_failure_releases_lock_and_registration(self):
        with (
            patch(
                "configurator.service.threading.Thread.start",
                side_effect=RuntimeError("private failure"),
            ),
            self.assertRaises(AppError) as caught,
        ):
            self.app.start_job("preview", agenda(), "device-a")
        self.assertEqual(caught.exception.code, "internal")
        self.assertEqual(self.app.jobs, {})
        self.assertEqual(self.app.threads, [])
        self.app.close()
        self.assertEqual(self.run_job("preview")["status"], "succeeded")

    def test_shutdown_racing_registration_never_leaks_unstarted_thread(self):
        original = self.app.checkpoint
        calls = 0

        def stop_before_registration():
            nonlocal calls
            calls += 1
            if calls == 2:
                self.app.stopping.set()
            original()

        with (
            patch.object(self.app, "checkpoint", side_effect=stop_before_registration),
            self.assertRaises(AppError) as caught,
        ):
            self.app.start_job("preview", agenda(), "device-a")
        self.assertEqual(caught.exception.code, "stopped")
        self.app.close(stop=True)
        self.assertEqual(self.app.threads, [])
        self.assertTrue(self.app.operation.acquire(blocking=False))
        self.app.operation.release()

    def test_active_job_state_supports_browser_rejoin(self):
        entered, release = threading.Event(), threading.Event()
        preflight = self.app.preflight

        def paused(*args, **kwargs):
            entered.set()
            release.wait(5)
            return preflight(*args, **kwargs)

        with patch.object(self.app, "preflight", side_effect=paused):
            try:
                result = self.app.start_job("preview", agenda(), "device-a")
                self.assertTrue(entered.wait(5))
                active = self.app.state()["active_job"]
                self.assertEqual(active["job_id"], result["job_id"])
                self.assertEqual(active["agenda"], agenda())
                self.assertNotIn("request", self.app.job(result["job_id"]))
            finally:
                release.set()
                self.app.close()
        self.assertIsNone(self.app.state()["active_job"])

    def test_busy_state_preserves_validated_resource_choices_without_network(self):
        previous = self.app.state()
        calls = len(self.fake.calls)
        self.app.operation.acquire()
        try:
            current = self.app.state()
            for name in ("calendars", "devices", "pages"):
                self.assertEqual(current[name], previous[name])
                self.assertTrue(current[name])
            self.assertEqual(len(self.fake.calls), calls)
        finally:
            self.app.operation.release()

    def test_preview_unsaved_never_promotes_or_mutates_page(self):
        before = self.store.config.read_bytes()
        conn = self.store.connections()
        settings = dict(agenda(), intensity=73)
        job = self.run_job("preview", settings)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual(self.store.config.read_bytes(), before)
        self.assertEqual(self.store.connections()["resources"], conn["resources"])
        self.assertFalse(self.store.meta().get("last_published"))
        self.assertFalse(
            any(
                method in ("PUT", "POST") and "/user/" in route
                for route, method, _ in self.fake.calls
            )
        )
        self.assertTrue(job["result"]["preview_url"].endswith(".png"))
        html = next(
            raw for _, kind, raw in self.fake.uploads if kind == "document"
        ).decode()
        self.assertNotIn("sample-private-key", html)
        self.assertNotIn("sample-private-session", html)
        self.assertNotIn("testing", html)
        self.assertNotIn("syntheticEvents", html)
        preview = next(
            payload
            for route, _, payload in self.fake.calls
            if route == "/render/preview"
        )
        result = preview["layout"]
        self.assertEqual(result["editorMetadata"], {"retain": True})
        self.assertEqual(result["stageElements"][0]["children"][1]["id"], "editor-note")

    def test_save_only_is_offline_after_known_resource_validation(self):
        self.app.calendars()
        self.app.devices()
        self.fake.calls.clear()
        self.fake.network = True
        result = self.app.save(agenda(), "device-a")
        self.assertTrue(result["saved"])
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(self.fake.uploads, [])
        self.assertFalse(self.store.meta().get("journal"))

    def test_existing_publish_readback_assignment_snapshot_and_recovery(self):
        job = self.run_job()
        self.assertEqual(job["status"], "succeeded", job)
        self.assertTrue(job["result"]["snapshot_verified"])
        self.assertEqual(
            json.loads((self.store.state / "persisted-private.json").read_text()),
            json.loads(self.fake.page["data"]),
        )
        self.assertFalse(job["result"]["physical_delivery_confirmed"])
        self.assertEqual(self.fake.created, 0)
        self.assertEqual(self.fake.page["description"], "keep")
        self.assertFalse(
            any(
                "template" in route or "public" in route
                for route, _, _ in self.fake.calls
            )
        )
        self.app.save(dict(agenda(), intensity=1), "device-a")
        calls = len(self.fake.calls)
        self.assertTrue(self.app.recover()["restored"])
        self.assertEqual(self.store.preferences()["intensity"], 50)
        self.assertEqual(len(self.fake.calls), calls)

    def test_fresh_install_creates_once_and_rebuild_reuses_uploads(self):
        self.store.change_connection(lambda conn: conn["resources"].pop("page_id"))
        self.assertEqual(self.run_job()["status"], "succeeded")
        uploads = len(self.fake.uploads)
        self.assertEqual(self.fake.created, 1)
        self.assertEqual(self.fake.page["name"], "Google Calendar Today")
        shutil.rmtree(self.store.state)
        self.assertEqual(self.run_job()["status"], "succeeded")
        self.assertEqual(self.fake.created, 1)
        self.assertEqual(len(self.fake.uploads), uploads)

    def test_unknown_upload_stops_retry_without_duplication(self):
        self.fake.upload_fail = True
        job = self.run_job("preview")
        self.assertEqual(job["error"]["code"], "uncertain_upload")
        self.fake.upload_fail = False
        self.assertEqual(self.run_job("preview")["error"]["code"], "uncertain_upload")
        self.assertEqual(len(self.fake.uploads), 1)

    def test_confirmed_uncertain_upload_recovery_preserves_completed_uploads(self):
        self.fake.upload_fail = True
        self.run_job("preview")
        with self.assertRaises(AppError):
            self.app.recover_uploads(False)
        self.assertEqual(self.app.recover_uploads(True)["cleared"], 1)
        self.assertTrue(self.store.meta()["upload_uncertainty_history"])
        self.fake.upload_fail = False
        self.assertEqual(self.run_job("preview")["status"], "succeeded")
        completed = self.store.meta()["uploads"]
        self.assertEqual(self.app.recover_uploads(True)["cleared"], 0)
        self.assertEqual(self.store.meta()["uploads"], completed)

    def test_legacy_content_addressed_upload_cache_import(self):
        raw = b"sample-asset"
        digest = hashlib.sha256(raw).hexdigest()
        atomic_json(
            self.store.state / "uploads.json",
            {
                "sample.png|" + digest: {
                    "url": "https://assets.example.test/prior.png",
                    "sha256": digest,
                }
            },
        )
        url = self.app.renderer.upload(raw, "sample.png", "image")
        self.assertEqual(url, "https://assets.example.test/prior.png")
        self.assertEqual(self.fake.uploads, [])
        self.assertTrue(self.store.meta()["uploads"])

    def test_restarted_publication_resumes_durable_journal(self):
        self.fake.deploy_fail = True
        self.assertEqual(self.run_job()["status"], "failed")
        uploads = len(self.fake.uploads)
        self.fake.deploy_fail = False
        self.app = Service(Store(self.root, use_environment=False), self.fake)
        self.assertEqual(self.run_job()["status"], "succeeded")
        self.assertEqual(len(self.fake.uploads), uploads)

    def test_shutdown_stops_before_upload_and_keeps_retryable_error(self):
        self.app.stopping.set()
        with self.assertRaises(AppError) as caught:
            self.app.start_job("publish", agenda(), "device-a")
        self.assertEqual(caught.exception.code, "stopped")
        self.assertEqual(self.fake.uploads, [])

    def test_ongoing_job_refuses_parallel_mutation(self):
        self.app.operation.acquire()
        try:
            with self.assertRaises(AppError) as caught:
                self.app.start_job("preview", agenda(), "device-a")
            self.assertEqual(caught.exception.code, "busy")
            self.assertEqual(self.app.state()["devices"], [])
        finally:
            self.app.operation.release()

    def test_short_calendar_display_name_does_not_trigger_false_privacy_error(self):
        settings = agenda()
        settings["calendars"][0]["name"] = "A"
        self.assertEqual(self.run_job("preview", settings)["status"], "succeeded")

    def test_create_timeout_reconciles_page_without_duplicate(self):
        self.store.change_connection(lambda conn: conn["resources"].pop("page_id"))
        self.fake.create_timeout = True
        self.assertEqual(self.run_job()["error"]["code"], "uncertain_create")
        self.assertEqual(self.run_job()["status"], "succeeded")
        self.assertEqual(self.fake.created, 1)
        self.assertEqual(self.fake.page["name"], "Google Calendar Today")

    def test_fresh_rename_timeout_reconciles_without_another_create_or_put(self):
        self.store.change_connection(lambda conn: conn["resources"].pop("page_id"))
        self.fake.save_timeout = True
        self.assertEqual(self.run_job()["status"], "failed")
        self.assertEqual(self.run_job()["status"], "succeeded")
        self.assertEqual(self.fake.created, 1)
        self.assertEqual(self.fake.page["name"], "Google Calendar Today")
        self.assertEqual(sum(method == "PUT" for _, method, _ in self.fake.calls), 1)

    def test_create_timeout_missing_result_preserves_uncertainty(self):
        self.store.change_connection(lambda conn: conn["resources"].pop("page_id"))
        self.fake.create_timeout = True
        self.run_job()
        self.fake.pages_data = []
        self.assertEqual(self.run_job()["error"]["code"], "uncertain_create")
        self.assertEqual(self.fake.created, 1)

    def test_put_timeout_reconciles_before_repeat_and_retains_upload_cache(self):
        self.fake.save_timeout = True
        self.assertEqual(self.run_job()["status"], "failed")
        uploads = len(self.fake.uploads)
        self.assertEqual(self.run_job()["status"], "succeeded")
        puts = [route for route, method, _ in self.fake.calls if method == "PUT"]
        self.assertEqual(len(puts), 1)
        self.assertEqual(len(self.fake.uploads), uploads)

    def test_partial_deploy_failure_keeps_last_published_and_refuses_new_draft(self):
        self.run_job()
        before = self.store.meta()["last_published"]
        self.fake.deploy_fail = True
        self.assertEqual(
            self.run_job(settings=dict(agenda(), intensity=73))["status"], "failed"
        )
        self.assertEqual(self.store.meta()["last_published"], before)
        self.assertEqual(
            self.run_job(settings=dict(agenda(), intensity=74))["error"]["code"], "busy"
        )
        self.fake.deploy_fail = False
        self.assertEqual(
            self.run_job(settings=dict(agenda(), intensity=73))["status"], "succeeded"
        )

    def test_assignment_and_snapshot_failures_are_not_promoted(self):
        for attribute in ("assign", "snapshot_bad"):
            setattr(self.fake, attribute, attribute == "snapshot_bad")
            self.assertEqual(self.run_job()["error"]["code"], "readback")
            self.assertFalse(self.store.meta().get("last_published"))
            setattr(self.fake, attribute, attribute == "assign")

    def test_missing_invalid_and_expired_connections(self):
        self.store.change_connection(lambda conn: conn.pop("api_key"))
        self.assertEqual(self.run_job("preview")["error"]["code"], "key_missing")
        self.store.change_connection(
            lambda conn: conn.__setitem__("api_key", "sample-private-key")
        )
        self.fake.auth = False
        self.assertEqual(self.run_job("preview")["error"]["code"], "key_invalid")
        self.fake.auth = True
        self.fake.session = False
        self.assertEqual(self.run_job("preview")["error"]["code"], "google_expired")
        self.store.change_connection(lambda conn: conn.pop("session_id"))
        self.assertEqual(self.run_job("preview")["error"]["code"], "google_missing")


class AuthTests(BaseCase):
    def test_page_list_empty_data_is_resolved_through_detail(self):
        self.fake.pages_data = [dict(self.fake.page, data="")]
        records = self.app.page_choices()
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["agenda"])
        self.assertEqual(self.store.meta()["pages"], records)
        self.assertTrue(
            any(route == "/api/v2/user/page/detail" for route, _, _ in self.fake.calls)
        )

    def test_invalid_key_is_not_saved(self):
        before = self.store.connection.read_bytes()
        self.fake.auth = False
        with self.assertRaises(AppError):
            self.app.set_key("invalid-key")
        self.assertEqual(self.store.connection.read_bytes(), before)

    def test_same_account_rotation_reuses_session_and_other_account_segregates(self):
        self.app.set_key("rotated-same-account")
        self.assertEqual(
            self.store.connections()["session_id"], "sample-private-session"
        )
        self.assertEqual(self.store.connections()["resources"]["page_id"], "page-a")
        self.app.set_key("new-account-key")
        conn = self.store.connections()
        self.assertNotIn("session_id", conn)
        self.assertEqual(conn["resources"], {})
        self.assertEqual(
            conn["_account_history"][0]["session_id"], "sample-private-session"
        )
        self.assertFalse(any(method for _, method, _ in self.fake.calls))

    def test_key_write_failure_is_atomic(self):
        before = self.store.connection.read_bytes()
        with (
            patch("configurator.config.os.replace", side_effect=OSError("injected")),
            self.assertRaises(OSError),
        ):
            self.app.set_key("new-account-key")
        self.assertEqual(self.store.connection.read_bytes(), before)

    def test_environment_override_switch_is_validated_and_segregated(self):
        self.store.use_environment = True
        with patch.dict(os.environ, {"SENSECRAFT_API_KEY": "new-account-key"}):
            with self.assertRaises(AppError) as caught:
                self.app.set_key("different-key")
            self.assertEqual(caught.exception.code, "environment_override")
            self.app.check_override()
            self.assertEqual(self.store.connections()["resources"], {})
            self.assertNotIn("session_id", self.store.connections())
            self.assertEqual(self.store.connections()["api_key"], "new-account-key")

    def test_authorization_failure_uses_guided_native_fallback(self):
        original = self.fake.request

        def fail_authorize(route, *args, **kwargs):
            if route.startswith("/api/v2/calendar/authorize"):
                raise AppError("upstream", 502)
            return original(route, *args, **kwargs)

        with patch.object(self.fake, "request", side_effect=fail_authorize):
            result, _ = self.app.google_start(True)
        self.assertEqual(result["status"], "guided")
        self.assertIsNone(result["authorize_url"])

    def test_numeric_selected_resource_ids_are_normalized_for_ui(self):
        self.store.change_connection(
            lambda conn: conn["resources"].__setitem__("device_id", 123)
        )
        self.assertEqual(self.app.state()["device_id"], "123")

    def test_existing_session_reused_without_authorization_request(self):
        self.assertEqual(self.app.google_start()["status"], "valid")
        self.assertFalse(any("authorize" in route for route, _, _ in self.fake.calls))

    def test_oauth_nonce_cookie_expiry_session_and_replay(self):
        response, cookie = self.app.google_start(True)
        self.assertEqual(response["status"], "authorize")
        nonce = self.app.oauth["nonce"]
        for state, browser in (("wrong", cookie), (nonce, "wrong")):
            with self.assertRaises(AppError):
                self.app.oauth_callback(
                    {"state": state, "session_id": "new-session"}, browser
                )
        with self.assertRaises(AppError):
            self.app.oauth_callback(
                {"state": nonce, "session_id": "invalid-session"}, cookie
            )
        self.assertEqual(
            self.store.connections()["session_id"], "sample-private-session"
        )
        self.app.oauth_callback({"state": nonce, "session_id": "new-session"}, cookie)
        self.assertEqual(self.store.connections()["session_id"], "new-session")
        with self.assertRaises(AppError):
            self.app.oauth_callback(
                {"state": nonce, "session_id": "new-session"}, cookie
            )
        self.app.google_start(True)
        self.app.oauth["expires"] = 0
        with self.assertRaises(AppError):
            self.app.oauth_callback(
                {"state": self.app.oauth["nonce"], "session_id": "new-session"},
                self.app.oauth["browser"],
            )

    def test_guided_native_import_validates_session_without_editing_page(self):
        url = "https://assets.example.test/agenda.html#" + urllib.parse.urlencode(
            {"config": json.dumps({"session_id": "imported-session"})}
        )
        self.fake.page["data"] = json.dumps(layout(url))
        self.assertEqual(self.app.import_google("page-a")["status"], "valid")
        self.assertEqual(self.store.connections()["session_id"], "imported-session")
        self.assertFalse(any(method for _, method, _ in self.fake.calls))

    def test_state_masks_secrets_and_exposes_choices_and_errors(self):
        state = self.app.state()
        text = json.dumps(state)
        self.assertNotIn("sample-private-key", text)
        self.assertNotIn("sample-private-session", text)
        self.assertNotIn("sample-mac", text)
        self.assertEqual(state["connection"]["key"], "valid")
        self.assertEqual(state["connection"]["google"], "valid")
        self.assertEqual(len(state["calendars"]), 2)
        self.fake.session = False
        self.assertEqual(self.app.state()["connection"]["google"], "expired")


class HTTPTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.server = bind(self.app, 0)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        super().tearDown()

    def request(self, route="/api/state", method="GET", data=None, headers=None):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=10
        )
        body = json.dumps(data) if data is not None else None
        defaults = {
            "Origin": self.app.origin,
            "X-CSRF-Token": self.app.csrf,
            "Content-Type": "application/json",
        }
        defaults.update(headers or {})
        conn.request(method, route, body=body, headers=defaults)
        response = conn.getresponse()
        raw = response.read()
        result = (
            json.loads(raw)
            if response.getheader("Content-Type") == "application/json"
            else raw
        )
        conn.close()
        return response.status, result, dict(response.getheaders())

    def test_cross_site_csrf_and_host_refusal(self):
        cases = [
            {"Origin": "https://other.test"},
            {"Origin": ""},
            {"X-CSRF-Token": "bad"},
            {"Host": "localhost:" + str(self.server.server_port)},
            {"Sec-Fetch-Site": "cross-site"},
            {"Content-Type": "text/plain"},
        ]
        for headers in cases:
            status, _, _ = self.request(
                "/api/save",
                "POST",
                {"agenda": agenda(), "device_id": "device-a"},
                headers,
            )
            self.assertEqual(status, 403, headers)
        self.assertEqual(self.request(headers={"Host": "evil.test"})[0], 403)
        self.assertEqual(self.request(method="OPTIONS")[0], 403)

    def test_save_and_publish_confirmation_and_async_result(self):
        request = {"agenda": agenda(), "device_id": "device-a"}
        self.assertEqual(self.request("/api/save", "POST", request)[0], 200)
        self.assertEqual(self.request("/api/publish", "POST", request)[0], 400)
        self.assertEqual(
            self.request("/api/publish", "POST", dict(request, confirm=False))[0], 400
        )
        status, job, _ = self.request("/api/preview", "POST", request)
        self.assertEqual(status, 202)
        self.app.close()
        status, result, _ = self.request(job["status_url"])
        self.assertEqual(result["status"], "succeeded")
        status, raw, headers = self.request(result["result"]["preview_url"])
        self.assertEqual(status, 200)
        self.assertTrue(raw.startswith(PNG))
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_static_and_artifact_path_traversal_refused(self):
        for route in (
            "/api/artifacts/../../sensecraft.connection.local.json",
            "/assets/../manifest.json",
            "/assets/%2e%2e/manifest.json",
            "/../sensecraft.connection.local.json",
            "/api/jobs/missing",
        ):
            self.assertEqual(self.request(route)[0], 404, route)
        asset = next(iter(approved_artwork()))
        self.assertEqual(self.request("/assets/" + asset)[0], 200)
        self.assertEqual(self.request("/")[0], 200)

    def test_internal_exception_redacted(self):
        with patch.object(
            self.app,
            "state",
            side_effect=RuntimeError("secret-session private-account"),
        ):
            status, result, _ = self.request()
        self.assertEqual(status, 500)
        self.assertNotIn("secret-session", json.dumps(result))

    def test_oauth_browser_cookie_http_callback_and_no_session_response(self):
        status, _result, headers = self.request(
            "/api/google/start", "POST", {"reconnect": True}
        )
        self.assertEqual(status, 200)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        route = "/oauth/callback?" + urllib.parse.urlencode(
            {"state": self.app.oauth["nonce"], "session_id": "http-session"}
        )
        status, body, headers = self.request(
            route,
            headers={"Cookie": cookie, "Origin": "", "Sec-Fetch-Site": "cross-site"},
        )
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/?google=connected")
        self.assertNotIn("http-session", str(body) + str(headers))


class TransportTests(unittest.TestCase):
    def response(self, raw):
        stream = io.BytesIO(raw)
        return stream

    def test_application_error_and_http_error_classification(self):
        transport = Transport(lambda: "sample-key")
        for raw, google, code in (
            (b'{"code":401}', False, "key_invalid"),
            (b'{"code":401}', True, "google_expired"),
            (b"not json", False, "protocol"),
            (b'{"code":500}', False, "upstream"),
        ):
            with (
                patch.object(transport.opener, "open", return_value=self.response(raw)),
                self.assertRaises(AppError) as caught,
            ):
                transport.request("/test", google=google)
            self.assertEqual(caught.exception.code, code)
        with (
            patch.object(
                transport.opener,
                "open",
                side_effect=urllib.error.HTTPError(
                    "secret-url", 401, "private", {}, None
                ),
            ),
            self.assertRaises(AppError) as caught,
        ):
            transport.request("/test")
        self.assertEqual(caught.exception.code, "key_invalid")
        self.assertNotIn("secret-url", str(caught.exception))

    def test_png_and_empty_write_result(self):
        transport = Transport(lambda: "sample-key")
        with patch.object(
            transport.opener, "open", return_value=self.response(PNG + b"sample")
        ):
            self.assertTrue(
                transport.request("/render/preview", {}, binary=True).startswith(PNG)
            )
        with patch.object(
            transport.opener, "open", return_value=self.response(b'{"code":200}')
        ):
            self.assertIsNone(transport.request("/test", {}, "PUT"))


class LauncherTests(unittest.TestCase):
    def test_occupied_port_falls_back_to_loopback(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Service(Store(directory, use_environment=False), FakeTransport())
            occupied = socket.socket()
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            server = bind(app, port)
            try:
                self.assertNotEqual(server.server_port, port)
                self.assertEqual(server.server_address[0], "127.0.0.1")
                self.assertEqual(app.origin, f"http://127.0.0.1:{server.server_port}")
            finally:
                server.server_close()
                occupied.close()

    def test_browser_success_false_and_exception(self):
        output = io.StringIO()
        self.assertTrue(open_browser("http://127.0.0.1:1234", lambda url: True, output))
        self.assertFalse(
            open_browser("http://127.0.0.1:1234", lambda url: False, output)
        )
        self.assertFalse(
            open_browser(
                "http://127.0.0.1:1234",
                lambda url: (_ for _ in ()).throw(OSError()),
                output,
            )
        )
        self.assertIn("manually", output.getvalue())

    def test_cli_prints_url_and_clean_sigterm_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(
                os.environ,
                SENSECRAFT_AGENDA_CONFIG=str(root / "preferences.json"),
                SENSECRAFT_AGENDA_CONNECTION=str(root / "connection.json"),
                SENSECRAFT_AGENDA_STATE_DIR=str(root / "state"),
            )
            env.pop("SENSECRAFT_API_KEY", None)
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(TEMPLATE / "configurator"),
                    "--port",
                    "0",
                    "--no-browser",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                url = process.stdout.readline().strip()
                self.assertTrue(url.startswith("http://127.0.0.1:"), url)
                process.send_signal(signal.SIGTERM)
                stdout, stderr = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, stderr)
                self.assertIn("Configurator stopped", stdout)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()


if __name__ == "__main__":
    unittest.main()
