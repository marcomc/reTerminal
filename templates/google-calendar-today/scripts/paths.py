"""Paths and private configuration for the Google Calendar Today helpers.

``sensecraft.local.json`` holds display preferences. Connections are separate
so deleting generated ``.private`` state never removes durable local state.
"""

import json
import os
import tempfile
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1]
PROJECT = TEMPLATE.parents[1]
ROOT = (
    Path(
        os.environ.get(
            "SENSECRAFT_AGENDA_STATE_DIR", PROJECT / ".private/native-agenda"
        )
    )
    .expanduser()
    .resolve()
)
CONFIG = (
    Path(os.environ.get("SENSECRAFT_AGENDA_CONFIG", PROJECT / "sensecraft.local.json"))
    .expanduser()
    .resolve()
)
CONNECTION = (
    Path(
        os.environ.get(
            "SENSECRAFT_AGENDA_CONNECTION", PROJECT / "sensecraft.connection.local.json"
        )
    )
    .expanduser()
    .resolve()
)
SOURCE = TEMPLATE / "src/agenda.html"
ARTWORK = TEMPLATE / "assets"

if ROOT == TEMPLATE or TEMPLATE in ROOT.parents:
    raise ValueError("Installation state must be outside the template source tree")
ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
for local_path in (CONFIG, CONNECTION):
    if local_path == TEMPLATE or TEMPLATE in local_path.parents:
        raise ValueError("Local configuration must be outside the template source tree")


def _read_object(path, label):
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ValueError(f"Missing {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {label}: {path}") from exc
    if not isinstance(data, dict):
        raise TypeError(f"{label} must contain a JSON object")
    return data


def _write_json(path, data, *, private=False):
    """Atomically write local JSON without leaving a partial configuration."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary)
    try:
        os.fchmod(fd, 0o600 if private else 0o644)
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(path)
        if private:
            path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _legacy_env_api_key():
    """Read only SENSECRAFT_API_KEY from .env; never execute its contents."""
    legacy_env = PROJECT / ".env"
    if not legacy_env.exists():
        return None
    for line in legacy_env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        if name.strip() != "SENSECRAFT_API_KEY" or not separator:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        return value or None
    return None


def _migrate_if_needed():
    """Split the historical unified root configuration once, without data loss."""
    preferences = _read_object(CONFIG, "preferences configuration")
    agenda = preferences.get("agenda")
    resources = preferences.get("resources")
    if not isinstance(agenda, dict):
        raise TypeError("Preferences configuration requires an agenda object")
    if CONNECTION.exists():
        connection = _read_object(CONNECTION, "connection configuration")
        if not isinstance(connection.get("resources"), dict):
            raise ValueError("Connection configuration requires a resources object")
        migrated_agenda = dict(agenda)
        migrated_connection = dict(connection)
        changed = False
        session_id = migrated_agenda.pop("session_id", None)
        if session_id:
            changed = True
            if not migrated_connection.get("session_id"):
                migrated_connection["session_id"] = session_id
        if isinstance(resources, dict):
            changed = True
            merged_resources = dict(resources)
            for name, value in migrated_connection["resources"].items():
                if value not in (None, ""):
                    merged_resources[name] = value
            migrated_connection["resources"] = merged_resources
        if not migrated_connection.get("api_key"):
            api_key = _legacy_env_api_key()
            if api_key:
                migrated_connection["api_key"] = api_key
                changed = True
        if changed:
            _write_json(CONNECTION, migrated_connection, private=True)
            _write_json(CONFIG, {"agenda": migrated_agenda}, private=True)
            return {"agenda": migrated_agenda}, migrated_connection
        return preferences, connection
    if not isinstance(resources, dict):
        raise TypeError("Legacy preferences configuration requires a resources object")

    migrated_agenda = dict(agenda)
    session_id = migrated_agenda.pop("session_id", None)
    connection = {"resources": dict(resources)}
    if session_id:
        connection["session_id"] = session_id
    api_key = _legacy_env_api_key()
    if api_key:
        connection["api_key"] = api_key
    _write_json(CONNECTION, connection, private=True)
    _write_json(CONFIG, {"agenda": migrated_agenda}, private=True)
    return {"agenda": migrated_agenda}, connection


def load_local():
    """Return separated preferences and connections, migrating legacy root JSON."""
    preferences, connection = _migrate_if_needed()
    return {"agenda": preferences["agenda"], "connection": connection}


def load_config():
    """Return preferences plus the Google session expected by existing helpers."""
    local = load_local()
    config = dict(local["agenda"])
    session_id = local["connection"].get("session_id")
    if session_id:
        config["session_id"] = session_id
    return config


def load_settings():
    """Return SenseCraft resource identifiers from the private connection file."""
    return dict(load_local()["connection"]["resources"])


def load_api_key():
    """Resolve key: explicit environment, private connection, then legacy .env."""
    explicit = os.environ.get("SENSECRAFT_API_KEY")
    if explicit:
        return explicit
    connection = load_local()["connection"]
    key = connection.get("api_key") or _legacy_env_api_key()
    if not key:
        raise ValueError(
            "Missing SenseCraft API key; set SENSECRAFT_API_KEY or configure "
            "sensecraft.connection.local.json"
        )
    return key


def save_config(config):
    """Save display preferences and preserve private connections/resources."""
    local = load_local()
    preferences = {
        k: v for k, v in config.items() if k not in {"batteryBinding", "session_id"}
    }
    connection = dict(local["connection"])
    if config.get("session_id"):
        connection["session_id"] = config["session_id"]
    _write_json(CONNECTION, connection, private=True)
    _write_json(CONFIG, {"agenda": preferences}, private=True)
