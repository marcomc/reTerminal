"""Standard-library tests for durable local configuration and private persistence."""

import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


class LocalConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name).resolve()
        self.config = self.root / "sensecraft.local.json"
        self.connection = self.root / "sensecraft.connection.local.json"
        self.state = self.root / ".private" / "native-agenda"
        self.env = patch.dict(
            os.environ,
            {
                "SENSECRAFT_AGENDA_CONFIG": str(self.config),
                "SENSECRAFT_AGENDA_CONNECTION": str(self.connection),
                "SENSECRAFT_AGENDA_STATE_DIR": str(self.state),
            },
            clear=False,
        )
        self.env.start()
        os.environ.pop("SENSECRAFT_API_KEY", None)
        sys.modules.pop("paths", None)
        self.paths = importlib.import_module("paths")
        self.paths.PROJECT = self.root

    def tearDown(self):
        self.env.stop()
        sys.modules.pop("paths", None)
        self.tempdir.cleanup()

    def write_legacy(self):
        self.config.write_text(
            json.dumps(
                {
                    "agenda": {"language": "it", "session_id": "session-value"},
                    "resources": {"page_id": "page-value", "device_id": "device-value"},
                }
            )
        )

    def test_migrates_unified_config_and_assembles_legacy_interfaces(self):
        self.write_legacy()
        (self.root / ".env").write_text(
            "SENSECRAFT_API_KEY=legacy-key\nDONT_EXECUTE=$(false)\n"
        )
        self.assertEqual(self.paths.load_config()["session_id"], "session-value")
        self.assertEqual(self.paths.load_settings()["page_id"], "page-value")
        self.assertEqual(self.paths.load_api_key(), "legacy-key")
        self.assertEqual(
            json.loads(self.config.read_text()), {"agenda": {"language": "it"}}
        )
        connection = json.loads(self.connection.read_text())
        self.assertEqual(connection["session_id"], "session-value")
        self.assertEqual(connection["resources"]["device_id"], "device-value")
        self.assertEqual(connection["api_key"], "legacy-key")
        self.assertEqual(self.connection.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)

    def test_migration_retries_after_preference_write_failure_without_data_loss(self):
        self.write_legacy()
        original_write = self.paths._write_json

        def fail_only_preferences(path, data, **kwargs):
            if path == self.config:
                raise OSError("injected preferences write failure")
            return original_write(path, data, **kwargs)

        with (
            patch.object(self.paths, "_write_json", side_effect=fail_only_preferences),
            self.assertRaisesRegex(OSError, "injected"),
        ):
            self.paths.load_local()
        self.assertEqual(
            json.loads(self.connection.read_text())["session_id"], "session-value"
        )
        self.assertEqual(self.paths.load_config()["session_id"], "session-value")
        self.assertEqual(self.paths.load_settings()["page_id"], "page-value")

    def test_existing_empty_connection_values_are_filled_from_legacy_config(self):
        self.write_legacy()
        self.connection.write_text(
            json.dumps(
                {
                    "session_id": None,
                    "resources": {"page_id": None, "device_id": "existing-device"},
                }
            )
        )
        self.assertEqual(self.paths.load_config()["session_id"], "session-value")
        self.assertEqual(self.paths.load_settings()["page_id"], "page-value")
        self.assertEqual(self.paths.load_settings()["device_id"], "existing-device")

    def test_explicit_environment_key_has_precedence(self):
        self.write_legacy()
        self.paths.load_local()
        with patch.dict(os.environ, {"SENSECRAFT_API_KEY": "explicit-key"}):
            self.assertEqual(self.paths.load_api_key(), "explicit-key")

    def test_private_state_can_be_removed_without_losing_durable_config(self):
        self.write_legacy()
        self.paths.load_local()
        shutil.rmtree(self.state)
        self.assertEqual(self.paths.load_config()["language"], "it")
        self.assertEqual(self.paths.load_settings()["device_id"], "device-value")


class PrivatePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name).resolve()
        self.state = self.root / "state"
        self.state.mkdir()
        config = self.root / "sensecraft.local.json"
        connection = self.root / "sensecraft.connection.local.json"
        config.write_text(json.dumps({"agenda": {"calendars": []}}))
        connection.write_text(
            json.dumps({"api_key": "test-key", "resources": {"page_id": "page-1"}})
        )
        self.env = patch.dict(
            os.environ,
            {
                "SENSECRAFT_AGENDA_CONFIG": str(config),
                "SENSECRAFT_AGENDA_CONNECTION": str(connection),
                "SENSECRAFT_AGENDA_STATE_DIR": str(self.state),
            },
            clear=False,
        )
        self.env.start()
        sys.modules.pop("paths", None)
        sys.modules.pop("persist", None)
        self.persist = importlib.import_module("persist")

    def tearDown(self):
        self.env.stop()
        sys.modules.pop("persist", None)
        sys.modules.pop("paths", None)
        self.tempdir.cleanup()

    def test_merge_candidate_preserves_editor_owned_elements(self):
        current = {
            "stageElements": [
                {
                    "id": "editor-group",
                    "children": [
                        {"id": "native-agenda", "htmlConfig": {"htmlUrl": "old"}},
                        {"id": "native-battery"},
                        {"id": "keep-me"},
                    ],
                }
            ],
            "editorMetadata": {"keep": True},
        }
        candidate = {
            "stageElements": [
                {
                    "id": "container",
                    "children": [
                        {"id": "native-agenda", "htmlConfig": {"htmlUrl": "new"}}
                    ],
                }
            ]
        }
        merged = self.persist.merge_candidate(current, candidate)
        self.assertEqual(merged["editorMetadata"], {"keep": True})
        self.assertEqual(merged["stageElements"][0]["children"][1]["id"], "keep-me")
        self.assertEqual(
            merged["stageElements"][0]["children"][0]["htmlConfig"]["htmlUrl"], "new"
        )

    def test_private_page_persistence_makes_no_template_request(self):
        page_layout = {
            "stageSize": {"width": 800, "height": 480},
            "editorMetadata": {"retain": "this"},
            "stageElements": [
                {
                    "id": "group",
                    "children": [
                        {"id": "native-agenda", "htmlConfig": {"htmlUrl": "old"}},
                        {"id": "native-battery"},
                        {"id": "editor-note"},
                    ],
                },
                {"id": "unrelated-root-node", "type": "text"},
            ],
        }
        candidate = {
            "stageElements": [
                {
                    "id": "candidate",
                    "children": [
                        {"id": "native-agenda", "htmlConfig": {"htmlUrl": "new"}}
                    ],
                }
            ]
        }
        (self.state / "build-report.json").write_text(json.dumps({"production": True}))
        (self.state / "candidate-private.json").write_text(json.dumps(candidate))
        (self.state / "agenda-upload.html").write_text("production")
        calls = []
        saved_layout = {}

        def fake_request(route, payload=None, method=None):
            calls.append(route)
            if route.startswith("/api/v2/user/page/detail"):
                return {
                    "result": {
                        "id": "page-1",
                        "name": "Agenda",
                        "data": json.dumps(saved_layout or page_layout),
                    }
                }
            if route == "/render/preview":
                return b"\x89PNGpreview"
            if route == "/api/v2/user/page":
                saved_layout.update(json.loads(payload["data"]))
                return {"code": 200}
            raise AssertionError(route)

        with (
            patch.object(self.persist, "request", side_effect=fake_request),
            patch.object(
                self.persist, "upload_thumbnail", return_value="thumbnail-url"
            ),
            patch.object(sys, "argv", ["persist.py"]),
        ):
            self.persist.main()
        self.assertFalse(any("/template" in route for route in calls))
        self.assertEqual(
            saved_layout["stageElements"][0]["children"][0]["htmlConfig"]["htmlUrl"],
            "new",
        )
        self.assertEqual(
            saved_layout["stageElements"][0]["children"][1]["id"], "editor-note"
        )
        self.assertEqual(saved_layout["editorMetadata"], {"retain": "this"})
        self.assertEqual(saved_layout["stageSize"], {"width": 800, "height": 480})
        self.assertEqual(saved_layout["stageElements"][1]["id"], "unrelated-root-node")
        self.assertEqual(
            json.loads((self.state / "persisted-private.json").read_text()),
            saved_layout,
        )

    def test_preview_only_never_uploads_thumbnail_or_mutates_page(self):
        page_layout = {
            "stageElements": [
                {
                    "id": "group",
                    "children": [
                        {"id": "native-agenda", "htmlConfig": {"htmlUrl": "old"}}
                    ],
                }
            ]
        }
        candidate = {
            "stageElements": [
                {
                    "id": "candidate",
                    "children": [
                        {"id": "native-agenda", "htmlConfig": {"htmlUrl": "new"}}
                    ],
                }
            ]
        }
        (self.state / "build-report.json").write_text(json.dumps({"production": True}))
        (self.state / "candidate-private.json").write_text(json.dumps(candidate))
        (self.state / "agenda-upload.html").write_text("production")
        calls = []

        def fake_request(route, payload=None, method=None):
            calls.append(route)
            if route.startswith("/api/v2/user/page/detail"):
                return {
                    "result": {
                        "id": "page-1",
                        "name": "Agenda",
                        "data": json.dumps(page_layout),
                    }
                }
            if route == "/render/preview":
                return b"\x89PNGpreview"
            raise AssertionError(route)

        with (
            patch.object(self.persist, "request", side_effect=fake_request),
            patch.object(self.persist, "upload_thumbnail") as upload,
            patch.object(sys, "argv", ["persist.py", "--preview-only"]),
        ):
            self.persist.main()
        upload.assert_not_called()
        self.assertNotIn("/api/v2/user/page", calls)
        self.assertFalse((self.state / "persisted-private.json").exists())

    def test_persist_rejects_page_missing_editor_metadata(self):
        (self.state / "build-report.json").write_text(json.dumps({"production": True}))
        (self.state / "candidate-private.json").write_text(
            json.dumps({"stageElements": []})
        )
        (self.state / "agenda-upload.html").write_text("production")
        with (
            patch.object(
                self.persist,
                "request",
                return_value={"result": {"id": "page-1", "name": "Agenda"}},
            ),
            patch.object(sys, "argv", ["persist.py"]),
            self.assertRaisesRegex(ValueError, "missing required metadata: data"),
        ):
            self.persist.main()

    def test_deploy_validates_device_before_page_mutation(self):
        connection = Path(os.environ["SENSECRAFT_AGENDA_CONNECTION"])
        connection.write_text(
            json.dumps(
                {
                    "api_key": "test-key",
                    "resources": {"page_id": "page-1", "device_id": "device-1"},
                }
            )
        )
        layout = {
            "stageElements": [
                {
                    "id": "group",
                    "children": [
                        {"id": "native-agenda", "htmlConfig": {"htmlUrl": "old"}}
                    ],
                }
            ]
        }
        candidate = {
            "stageElements": [
                {
                    "id": "candidate",
                    "children": [
                        {"id": "native-agenda", "htmlConfig": {"htmlUrl": "new"}}
                    ],
                }
            ]
        }
        (self.state / "build-report.json").write_text(json.dumps({"production": True}))
        (self.state / "candidate-private.json").write_text(json.dumps(candidate))
        (self.state / "agenda-upload.html").write_text("production")
        calls = []
        saved_layout = {}

        def fake_request(route, payload=None, method=None):
            calls.append(route)
            if route.startswith("/api/v2/user/page/detail"):
                return {
                    "result": {
                        "id": "page-1",
                        "name": "Agenda",
                        "data": json.dumps(saved_layout or layout),
                    }
                }
            if route == "/api/v2/user/device/list":
                return {"result": [{"id": "device-1", "mac_address": "mac"}]}
            if route.startswith("/api/v2/user/device/playlist"):
                return {"result": {"pages": []}}
            if route == "/render/preview":
                return b"\x89PNGpreview"
            if route == "/api/v2/user/page":
                saved_layout.update(json.loads(payload["data"]))
                return {"code": 200}
            if route == "/api/v2/user/device/deploy":
                return {"code": 200}
            raise AssertionError(route)

        with (
            patch.object(self.persist, "request", side_effect=fake_request),
            patch.object(
                self.persist, "upload_thumbnail", return_value="thumbnail-url"
            ),
            patch.object(sys, "argv", ["persist.py", "--deploy"]),
        ):
            self.persist.main()
        self.assertLess(
            calls.index("/api/v2/user/device/list"), calls.index("/api/v2/user/page")
        )


class OperationalGuardTests(unittest.TestCase):
    def test_operational_scripts_do_not_depend_on_assertions(self):
        for name in ("build.py", "configure.py", "verify-live.py"):
            source = (SCRIPTS / name).read_text()
            self.assertNotIn("assert ", source, name)


if __name__ == "__main__":
    unittest.main()
