"""Keep reusable sources separate from ignored installation state."""

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
SOURCE = TEMPLATE / "src/agenda.html"
ARTWORK = TEMPLATE / "assets"

# Never let installation data be written into the versionable template tree.
if ROOT == TEMPLATE or TEMPLATE in ROOT.parents:
    raise ValueError("Installation state must be outside the template source tree")
ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)

if CONFIG == TEMPLATE or TEMPLATE in CONFIG.parents:
    raise ValueError("Local configuration must be outside the template source tree")


def load_local():
    """Read the root configuration without using historical state as fallback."""
    data = json.loads(CONFIG.read_text())
    if not isinstance(data, dict) or not all(
        isinstance(data.get(section), dict) for section in ("agenda", "resources")
    ):
        raise ValueError("Local configuration requires agenda and resources objects")
    return data


def load_config():
    return load_local()["agenda"]


def load_settings():
    return load_local()["resources"]


def save_config(config):
    """Save preferences atomically while preserving target-resource metadata."""
    data = load_local()
    # The battery key is supplied by the environment during preview/build/save.
    data["agenda"] = {k: v for k, v in config.items() if k != "batteryBinding"}
    fd, temporary = tempfile.mkstemp(
        dir=CONFIG.parent, prefix=".sensecraft.local.", suffix=".tmp"
    )
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(CONFIG)
    finally:
        temporary.unlink(missing_ok=True)
