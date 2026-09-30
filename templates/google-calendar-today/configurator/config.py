"""Durable root storage, migration and strict display preference validation."""

import copy
import json
import math
import os
import re
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import AppError
from .locking import FileMutex, FileRLock

TEMPLATE = Path(__file__).resolve().parents[1]
PROJECT = TEMPLATE.parents[1]
ENUMS = {
    "language": ["it", "en", "fr", "de", "es"],
    "markerMode": ["initials_and_dot", "initials_only", "dot_only", "none"],
    "backgroundMode": ["automatic", "manual"],
    "cadence": ["months", "seasons"],
    "mode": ["light", "dark"],
    "hemisphere": ["auto", "north", "south"],
    "carnivalRule": ["shrove_tuesday", "none"],
}
BOOLS = [
    "showTimezone",
    "showSunrise",
    "showSunset",
    "showMoon",
    "showBattery",
    "autoDark",
    "specialDates",
    "excludeBirthdays",
]
THEMES = [
    "white",
    "dark",
    "floral",
    "unicorn",
    "lgbtq",
    "spring",
    "summer",
    "autumn",
    "winter",
    "easter",
    "christmas",
    "epiphany",
    "halloween",
    "carnival",
] + [f"month-{i:02}" for i in range(1, 13)]


def defaults():
    value = json.loads((TEMPLATE / "examples/config.example.json").read_text())
    # The source example uses a different historical envelope on some checkouts.
    value = value.get("agenda", value)
    value.pop("session_id", None)
    value.pop("batteryBinding", None)
    value["calendars"] = []
    return value


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def read_json(path, fallback=None):
    if not path.exists():
        return copy.deepcopy(fallback)
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise TypeError
        return value
    except (ValueError, TypeError, OSError) as exc:
        raise AppError("validation") from exc


class Store:
    def __init__(self, project=PROJECT, *, use_environment=True):
        self.project = Path(project).resolve()
        self.config = Path(
            os.environ.get(
                "SENSECRAFT_AGENDA_CONFIG", self.project / "sensecraft.local.json"
            )
            if use_environment
            else self.project / "sensecraft.local.json"
        ).resolve()
        self.connection = Path(
            os.environ.get(
                "SENSECRAFT_AGENDA_CONNECTION",
                self.project / "sensecraft.connection.local.json",
            )
            if use_environment
            else self.project / "sensecraft.connection.local.json"
        ).resolve()
        self.state = Path(
            os.environ.get(
                "SENSECRAFT_AGENDA_STATE_DIR", self.project / ".private/native-agenda"
            )
            if use_environment
            else self.project / ".private/native-agenda"
        ).resolve()
        for path in (self.config, self.connection, self.state):
            if path == TEMPLATE or TEMPLATE in path.parents:
                raise AppError("validation")
        self.use_environment = use_environment
        self.operation = FileMutex(self.connection.with_suffix(".json.operation.lock"))
        self.lock = FileRLock(self.connection.with_suffix(".json.transaction.lock"))
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.migrate()

    def migrate(self):
        if not self.operation.acquire(blocking=False):
            raise AppError("busy", 409, True)
        try:
            self._migrate()
        finally:
            self.operation.release()

    def _migrate(self):
        with self.lock:
            pref = read_json(self.config, {"agenda": defaults()})
            conn = read_json(self.connection, {"resources": {}})
            if not isinstance(pref.get("agenda"), dict) or not isinstance(
                conn.get("resources", {}), dict
            ):
                raise AppError("validation")
            conn.setdefault("resources", {})
            session = pref["agenda"].pop("session_id", None)
            pref["agenda"].pop("batteryBinding", None)
            if session and not conn.get("session_id"):
                conn["session_id"] = session
            for key, value in pref.pop("resources", {}).items():
                if not conn["resources"].get(key):
                    conn["resources"][key] = value
            if not conn.get("api_key"):
                envfile = self.project / ".env"
                if envfile.exists():
                    for line in envfile.read_text().splitlines():
                        key, sep, value = (
                            line.strip().removeprefix("export ").partition("=")
                        )
                        if sep and key.strip() == "SENSECRAFT_API_KEY":
                            conn["api_key"] = value.strip().strip("\"'")
            # Connection first: interrupted migration must retain legacy bindings.
            atomic_json(self.connection, conn)
            atomic_json(self.config, pref)

    def preferences(self):
        with self.lock:
            return read_json(self.config)["agenda"]

    def connections(self):
        with self.lock:
            return read_json(self.connection)

    def write_connection(self, conn):
        with self.lock:
            atomic_json(self.connection, conn)

    def change_connection(self, update):
        with self.lock:
            conn = self.connections()
            update(conn)
            self.write_connection(conn)

    def meta(self):
        return self.connections().get("_configurator", {})

    def set_meta(self, key, value):
        self.change_connection(
            lambda conn: conn.setdefault("_configurator", {}).__setitem__(key, value)
        )

    def key(self):
        key = (
            os.environ.get("SENSECRAFT_API_KEY") if self.use_environment else None
        ) or self.connections().get("api_key")
        if not key or key.startswith("REPLACE_"):
            raise AppError("key_missing")
        return key

    def save(self, agenda, device_id):
        with self.lock:
            pref = read_json(self.config)
            pref["agenda"] = copy.deepcopy(agenda)
            self.change_connection(
                lambda conn: conn["resources"].__setitem__("device_id", device_id)
            )
            atomic_json(self.config, pref)


def validate(agenda):
    expected = set(defaults())
    if not isinstance(agenda, dict) or set(agenda) != expected:
        raise AppError("validation")
    try:
        for key, choices in ENUMS.items():
            if agenda[key] not in choices:
                raise ValueError
        if agenda["theme"] not in THEMES:
            raise ValueError
        if any(type(agenda[key]) is not bool for key in BOOLS):
            raise ValueError
        if type(agenda["intensity"]) is not int or not 0 <= agenda["intensity"] <= 100:
            raise ValueError
        if (
            any(type(agenda[key]) is not int for key in ("titleSize", "minTitleSize"))
            or not 24 <= agenda["minTitleSize"] <= agenda["titleSize"] <= 32
        ):
            raise ValueError
        for key, limit in (("latitude", 90), ("longitude", 180)):
            if (
                type(agenda[key]) not in (int, float)
                or not math.isfinite(agenda[key])
                or abs(agenda[key]) > limit
            ):
                raise ValueError
        if (
            not isinstance(agenda["city"], str)
            or not 1 <= len(agenda["city"].strip()) <= 200
        ):
            raise ValueError
        if not isinstance(agenda["timezone"], str):
            raise TypeError
        ZoneInfo(agenda["timezone"])
        calendars = agenda["calendars"]
        if not isinstance(calendars, list) or not 1 <= len(calendars) <= 10:
            raise ValueError
        ids = set()
        for item in calendars:
            if not isinstance(item, dict) or set(item) != {
                "id",
                "name",
                "initials",
                "color",
            }:
                raise ValueError
            if not all(isinstance(value, str) for value in item.values()):
                raise ValueError
            if not 1 <= len(item["id"]) <= 1024 or item["id"] in ids:
                raise ValueError
            ids.add(item["id"])
            if (
                not 1 <= len(item["name"]) <= 200
                or not 1 <= len(item["initials"].strip()) <= 4
                or len(item["initials"]) > 4
            ):
                raise ValueError
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", item["color"]):
                raise ValueError
    except (ValueError, TypeError, KeyError, ZoneInfoNotFoundError) as exc:
        raise AppError("validation") from exc
    return copy.deepcopy(agenda)
