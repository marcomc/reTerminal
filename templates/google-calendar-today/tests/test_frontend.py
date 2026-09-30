"""Frontend contract checks and optional isolated UI fixture server.

The fixture reuses the real HTTP backend with a simulated remote transport.
It never opens a real account or reads the installed root configuration.
Run this file with --serve-ui-fixture for manual cua_repl browser QA.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from configurator.config import BOOLS, ENUMS, defaults
from configurator.errors import AppError
from test_configurator import FakeTransport, Service, Store, agenda, bind, layout

TEMPLATE = Path(__file__).resolve().parents[1]
STATIC = TEMPLATE / "configurator/static"


class Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.fields = set()
        self.options = {}
        self.current_select = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            if attrs["id"] in self.ids:
                raise AssertionError("Duplicate control ID")
            self.ids.add(attrs["id"])
        if "data-setting" in attrs:
            self.fields.add(
                attrs.get("name") if attrs.get("type") == "radio" else attrs.get("id")
            )
        if tag == "select":
            self.current_select = attrs.get("id")
        if tag == "option" and self.current_select:
            self.options.setdefault(self.current_select, set()).add(attrs.get("value"))

    def handle_endtag(self, tag):
        if tag == "select":
            self.current_select = None


class FrontendContractTests(unittest.TestCase):
    def test_preferences_have_controls_or_explicit_compound_controls(self):
        controls = Controls()
        controls.feed((STATIC / "index.html").read_text())
        compound = {"city", "latitude", "longitude", "autoDark", "calendars", "theme"}
        self.assertEqual(set(defaults()), controls.fields | compound)
        self.assertLessEqual(set(BOOLS), controls.fields | compound)
        for field, values in ENUMS.items():
            if field != "backgroundMode":
                self.assertEqual(set(values), controls.options[field])

    def test_frontend_models_and_approved_asset_pairs(self):
        result = subprocess.run(
            ["node", str(TEMPLATE / "tests/check_frontend.js")],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("frontend model checks passed", result.stdout)

    def test_static_scripts_parse(self):
        for script in ("app.js", "model.js"):
            subprocess.run(["node", "--check", str(STATIC / script)], check=True)


class UITransport(FakeTransport):
    """Fictional account with twelve calendars, approved fictional PNG preview."""

    def __init__(self):
        super().__init__()
        self.slow = False
        self.fail_deploy_once = False
        self.page["data"] = json.dumps(
            layout(
                "https://assets.example.test/agenda.html#"
                + urllib.parse.urlencode(
                    {"config": json.dumps({"session_id": "fixture-session"})}
                )
            )
        )

    def request(self, route, payload=None, method=None, **kwargs):
        if route == "/api/v2/auth/profile" and kwargs.get("key") == "invalid":
            raise AppError("key_invalid", 401)
        if route == "/render/preview":
            if self.slow:
                time.sleep(5)
            return (TEMPLATE / "assets/thumbnail.png").read_bytes()
        if route == "/api/v2/user/device/deploy" and self.fail_deploy_once:
            self.fail_deploy_once = False
            raise AppError("network", 503, True)
        if route.startswith("/api/v2/calendar/list"):
            result = super().request(route, payload, method, **kwargs)
            result["calendarList"].extend(
                {
                    "id": f"calendar-{index}",
                    "summary": f"Calendario esempio {index}",
                    "accessRole": "reader",
                }
                for index in range(3, 13)
            )
            return result
        return super().request(route, payload, method, **kwargs)

    def cities(self, text, language):
        return [
            {
                "id": 1,
                "name": "Roma",
                "country": "Italia",
                "admin1": "Lazio",
                "latitude": 41.9,
                "longitude": 12.5,
                "timezone": "Europe/Rome",
            },
            {
                "id": 2,
                "name": "Sydney",
                "country": "Australia",
                "admin1": "New South Wales",
                "latitude": -33.87,
                "longitude": 151.21,
                "timezone": "Australia/Sydney",
            },
        ]


def serve_fixture(scenario):
    with tempfile.TemporaryDirectory(prefix="agenda-ui-fixture-") as directory:
        store = Store(Path(directory), use_environment=False)
        transport = UITransport()
        if scenario != "fresh":
            store.write_connection(
                {
                    "api_key": "fixture-key",
                    "session_id": "fixture-session",
                    "resources": {"page_id": "page-a", "device_id": "device-a"},
                }
            )
            store.save(agenda(), "device-a")
        if scenario == "expired":
            transport.session = False
        if scenario == "uncertain":
            store.set_meta("uploads", {"fixture-uncertain": {"url": None}})
        transport.slow = scenario == "slow"
        transport.fail_deploy_once = scenario == "deploy-fail"
        app = Service(store, transport)
        server = bind(app, 0)
        print(f"Isolated simulated UI ({scenario}): {app.origin}/", flush=True)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            app.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve-ui-fixture", action="store_true")
    parser.add_argument(
        "--scenario",
        choices=("connected", "fresh", "expired", "uncertain", "slow", "deploy-fail"),
        default="connected",
    )
    args, remaining = parser.parse_known_args()
    if args.serve_ui_fixture:
        serve_fixture(args.scenario)
    else:
        unittest.main(argv=[__file__, *remaining])
