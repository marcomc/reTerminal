"""Verify later renders, ten-calendar reads and the deployed snapshot."""

import argparse
import hashlib
import json
import urllib.parse
import urllib.request

from paths import ROOT, load_api_key, load_config, load_settings

BASE = "https://sensecraft-hmi-api.seeed.cc"
KEY = load_api_key()


def save(name, data):
    p = ROOT / name
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    p.chmod(0o600)


def get(route):
    r = urllib.request.Request(BASE + route, headers={"api-key": KEY})
    with urllib.request.urlopen(r, timeout=45) as f:
        v = json.load(f)
    if v.get("code") != 200:
        raise RuntimeError("SenseCraft API request failed")
    return v


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--ten-calendars", action="store_true", help="also verify a ten-calendar API read"
)
arguments = parser.parse_args()
cfg = load_config()
settings = load_settings()
cal = get(
    "/api/v2/calendar/list?" + urllib.parse.urlencode({"session_id": cfg["session_id"]})
)["result"]["calendarList"]
if not all(c["id"] in {r["id"] for r in cal} for c in cfg["calendars"]):
    raise ValueError("Configured calendar is absent from the connected Google list")
selected = [calendar["id"] for calendar in cfg["calendars"]]
if not selected:
    raise ValueError("At least one configured calendar is required")
configured_events = get(
    "/api/v2/calendar/events?"
    + urllib.parse.urlencode(
        {
            "session_id": cfg["session_id"],
            "calendar_ids": ",".join(selected),
            "type": 2,
            "time_zone": cfg["timezone"],
        }
    )
)["result"]["events"]
if not all(event["calendarId"] in selected for event in configured_events):
    raise ValueError("Configured calendar query returned an unexpected calendar")
print("Configured-calendar event read verified", flush=True)
ten_calendar_events = []
if arguments.ten_calendars:
    ten_selection = [c["id"] for c in cal[:10]]
    if len(set(ten_selection)) != 10:
        raise ValueError(
            "Connected Google list does not contain ten distinct calendars"
        )
    u = "/api/v2/calendar/events?" + urllib.parse.urlencode(
        {
            "session_id": cfg["session_id"],
            "calendar_ids": ",".join(ten_selection),
            "type": 2,
            "time_zone": cfg["timezone"],
        }
    )
    ten_calendar_events = get(u)["result"]["events"]
    if not all(event["calendarId"] in ten_selection for event in ten_calendar_events):
        raise ValueError("Ten-calendar query returned an unexpected calendar")
    print("Ten-calendar API read verified", flush=True)
print("Configured-calendar reconciliation passed", flush=True)
d = next(
    x
    for x in get("/api/v2/user/device/list")["result"]
    if x["id"] == settings["device_id"]
)
save("verified-device.json", d)
a = get(
    "/api/v2/user/device/playlist?"
    + urllib.parse.urlencode({"mac_address": d["mac_address"], "type": "all"})
)
save("verified-assignment.json", a)
pages = [
    p
    for p in a["result"]["pages"]
    if p.get("source_page_id") == settings["page_id"] or p["id"] == settings["page_id"]
]
if len(pages) != 1:
    raise ValueError("Expected exactly one deployed private page")
p = pages[0]
snapshot = get(
    "/api/v2/user/page/detail?"
    + urllib.parse.urlencode({"page_id": p["id"], "kind": p.get("kind", "layout")})
)["result"]
save("verified-snapshot.json", snapshot)
expectation = ROOT / "persisted-private.json"
if not expectation.exists():
    raise ValueError(
        "Missing persisted expectation; save the private page before verifying"
    )
expected = json.loads(expectation.read_text())
if json.loads(snapshot["data"]) != expected:
    raise RuntimeError("Deployed snapshot does not match the persisted private page")
r = urllib.request.Request(
    BASE + "/render/preview",
    data=json.dumps(
        {
            "layout": json.loads(snapshot["data"]),
            "resolution": "800x480",
            "dither": 3,
            "img_format": "png",
        }
    ).encode(),
    headers={"api-key": KEY, "Content-Type": "application/json"},
)
with urllib.request.urlopen(r, timeout=60) as f:
    raw = f.read()
if not raw.startswith(b"\x89PNG"):
    raise RuntimeError("Snapshot preview did not return PNG data")
(ROOT / "verified-snapshot-preview.png").write_bytes(raw)
# The API's device_image is service-provided evidence; do not call it a physical screenshot.
url = d.get("device_image", "")
imageMeta = {"present": bool(url)}
if url:
    host = urllib.parse.urlsplit(url).hostname
    if host != "sensecraft-hmi-api.seeed.cc":
        raise ValueError("Service device image is not hosted by SenseCraft")
    r = urllib.request.Request(url, headers={"api-key": KEY})
    with urllib.request.urlopen(r, timeout=45) as f:
        media = f.read()
        imageMeta.update(
            {
                "content_type": f.headers.get("Content-Type"),
                "bytes": len(media),
                "sha256": hashlib.sha256(media).hexdigest(),
            }
        )
    if media.startswith(b"\x89PNG"):
        (ROOT / "service-device-image.png").write_bytes(media)
    else:
        (ROOT / "service-device-image.bin").write_bytes(media)
save(
    "live-verification-report.json",
    {
        "ten_calendar_read": arguments.ten_calendars,
        "ten_calendar_event_count": (
            len(ten_calendar_events) if arguments.ten_calendars else None
        ),
        "ten_calendar_returned_subset": arguments.ten_calendars,
        "configured_calendars_reconciled": True,
        "configured_calendar_event_count": len(configured_events),
        "snapshot_exact_layout": True,
        "device_online": d.get("online_status") == 1,
        "device_last_seen": d.get("last_seen"),
        "device_current_app_present": d.get("current_app") is not None,
        "service_image": imageMeta,
        "physical_delivery_confirmed": False,
    },
)
print(
    "Deployed snapshot equals saved layout; later preview and service image captured",
    flush=True,
)
