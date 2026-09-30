"""Verify later renders, ten-calendar reads and the deployed snapshot."""

import hashlib
import json
import os
import urllib.parse
import urllib.request

from paths import ROOT, load_config, load_settings

BASE = "https://sensecraft-hmi-api.seeed.cc"
KEY = os.environ["SENSECRAFT_API_KEY"]


def save(name, data):
    p = ROOT / name
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    p.chmod(0o600)


def get(route):
    r = urllib.request.Request(BASE + route, headers={"api-key": KEY})
    with urllib.request.urlopen(r, timeout=45) as f:
        v = json.load(f)
    assert v["code"] == 200
    return v


cfg = load_config()
settings = load_settings()
cal = get(
    "/api/v2/calendar/list?" + urllib.parse.urlencode({"session_id": cfg["session_id"]})
)["result"]["calendarList"]
assert all(c["id"] in {r["id"] for r in cal} for c in cfg["calendars"])
selection = [c["id"] for c in cal[:10]]
assert len(set(selection)) == 10
u = "/api/v2/calendar/events?" + urllib.parse.urlencode(
    {
        "session_id": cfg["session_id"],
        "calendar_ids": ",".join(selection),
        "type": 2,
        "time_zone": cfg["timezone"],
    }
)
events = get(u)["result"]["events"]
assert all(e["calendarId"] in selection for e in events)
print(
    "Ten-calendar API read verified; selected-calendar reconciliation passed",
    flush=True,
)
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
assert len(pages) == 1
p = pages[0]
snapshot = get(
    "/api/v2/user/page/detail?"
    + urllib.parse.urlencode({"page_id": p["id"], "kind": p.get("kind", "layout")})
)["result"]
save("verified-snapshot.json", snapshot)
expected = json.loads((ROOT / "candidate-private.json").read_text())
assert json.loads(snapshot["data"]) == expected
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
assert raw.startswith(b"\x89PNG")
(ROOT / "verified-snapshot-preview.png").write_bytes(raw)
# The API's device_image is service-provided evidence; do not call it a physical screenshot.
url = d.get("device_image", "")
imageMeta = {"present": bool(url)}
if url:
    host = urllib.parse.urlsplit(url).hostname
    assert host == "sensecraft-hmi-api.seeed.cc"
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
        "ten_calendar_read_code": 200,
        "ten_calendar_event_count": len(events),
        "ten_calendar_returned_subset": True,
        "configured_calendars_reconciled": True,
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
