"""Save verified candidates and deploy; back up private state before mutation."""

import datetime
import hashlib
import json
import os
import urllib.parse
import urllib.request
import uuid

from paths import ARTWORK, ROOT, load_config, load_settings

BASE = "https://sensecraft-hmi-api.seeed.cc"
KEY = os.environ["SENSECRAFT_API_KEY"]
settings = load_settings()


def save(name, data):
    p = ROOT / name
    if name.startswith("before-") and p.exists():
        p = ROOT / (
            p.stem
            + "-"
            + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
            + p.suffix
        )
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    p.chmod(0o600)


def request(route, payload=None, method=None):
    r = urllib.request.Request(
        BASE + route,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"api-key": KEY, "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(r, timeout=60) as f:
        raw = f.read()
    if raw.startswith(b"\x89PNG"):
        return raw
    v = json.loads(raw)
    if v.get("code") != 200:
        raise RuntimeError(
            "SenseCraft application code "
            + str(v.get("code"))
            + " for "
            + route.split("?")[0]
        )
    return v


def upload_thumbnail(p):
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    cachefile = ROOT / "thumbnail-uploads.json"
    cache = json.loads(cachefile.read_text()) if cachefile.exists() else {}
    if digest in cache:
        return cache[digest]
    b = "agenda-" + uuid.uuid4().hex
    body = (
        (
            f'--{b}\r\nContent-Disposition: form-data; name="type"\r\n\r\nthumbnail\r\n--{b}\r\nContent-Disposition: form-data; name="file"; filename="agenda-preview.png"\r\nContent-Type: image/png\r\n\r\n'
        ).encode()
        + p.read_bytes()
        + f"\r\n--{b}--\r\n".encode()
    )
    r = urllib.request.Request(
        BASE + "/api/v1/oss/file/upload",
        data=body,
        headers={"api-key": KEY, "Content-Type": "multipart/form-data; boundary=" + b},
    )
    with urllib.request.urlopen(r, timeout=55) as f:
        v = json.load(f)
    assert v["code"] == 200
    cache[digest] = v["result"]["file_url"]
    save("thumbnail-uploads.json", cache)
    return cache[digest]


report = json.loads((ROOT / "build-report.json").read_text())
assert report["production"]
private = json.loads((ROOT / "candidate-private.json").read_text())
portable = json.loads((ROOT / "candidate-portable.json").read_text())
assert "synthetic" not in (ROOT / "agenda-upload.html").read_text()
# Read every target now; do not use historical account identifiers alone.
page = request(
    "/api/v2/user/page/detail?"
    + urllib.parse.urlencode({"page_id": settings["page_id"]})
)["result"]
save("before-page.json", page)
devices = request("/api/v2/user/device/list")["result"]
device = next(d for d in devices if d["id"] == settings["device_id"])
save("before-device.json", device)
templates = []
pagenum = 1
while True:
    envelope = request(
        "/api/v2/user/template?"
        + urllib.parse.urlencode({"page": pagenum, "page_size": 100})
    )["result"]
    rows = envelope.get("templates", [])
    templates.extend(rows)
    if len(rows) < 100:
        break
    pagenum += 1
    assert pagenum <= 30
original = next(t for t in templates if t["id"] == settings["template_id"])
save("before-template.json", original)
assignment = request(
    "/api/v2/user/device/playlist?"
    + urllib.parse.urlencode({"mac_address": device["mac_address"], "type": "all"})
)
save("before-assignment.json", assignment)
print("Fresh targets verified; original account state backed up", flush=True)
# Save a live preview of the actual production document before page mutation.
raw = request(
    "/render/preview",
    {"layout": private, "resolution": "800x480", "dither": 3, "img_format": "png"},
)
assert isinstance(raw, bytes)
(ROOT / "production-before-save.png").write_bytes(raw)
thumb = upload_thumbnail(ARTWORK / "thumbnail.png")
private_thumb = upload_thumbnail(ROOT / "production-before-save.png")
# Preserve metadata; replace only the requested agenda layout and its preview.
payload = {
    "id": page["id"],
    "name": page["name"],
    "type": "layout",
    "data": json.dumps(private, separators=(",", ":"), ensure_ascii=False),
    "resolution": "800x480",
    "dither": 3,
    "thumbnail": private_thumb,
    "description": page.get("description", ""),
    "tags": page.get("tags", []),
}
save("page-update-payload.json", payload)
request("/api/v2/user/page", payload, "PUT")
after = request(
    "/api/v2/user/page/detail?" + urllib.parse.urlencode({"page_id": page["id"]})
)["result"]
save("after-page.json", after)
assert json.loads(after["data"]) == private
assert after["resolution"] == "800x480" and after["dither"] == 3
print("Workspace layout saved and read back exactly", flush=True)
# Update the existing reusable template. Never issue a marketplace create/publish request.
fields = [
    "name",
    "description",
    "images",
    "device_models",
    "resolutions",
    "dithers",
    "tags",
]
tp = {k: original.get(k) for k in fields}
tp.update(
    {
        "id": original["id"],
        "thumbnail": thumb,
        "data": json.dumps(portable, separators=(",", ":"), ensure_ascii=False),
        "api_data": json.dumps(
            {
                "platforms": {"googleCalendar": {"included": True, "sanitized": True}},
                "installation": {
                    "requires_calendar_mapping": True,
                    "battery_per_device": True,
                },
            },
            separators=(",", ":"),
        ),
        "category_ids": [
            v["id"] if isinstance(v, dict) else v
            for v in original.get("category_ids", [])
        ],
    }
)
tp["images"] = [thumb]
save("template-update-payload.json", tp)
request("/api/v2/user/template", tp, "PUT")
readback = request(
    "/api/v2/user/template?" + urllib.parse.urlencode({"page": 1, "page_size": 100})
)["result"]["templates"]
aftertemplate = next(t for t in readback if t["id"] == original["id"])
save("after-template.json", aftertemplate)
assert json.loads(aftertemplate["data"]) == portable
encoded = json.dumps(aftertemplate, ensure_ascii=False)
config = load_config()
for secret in (
    [KEY, config["session_id"]]
    + [c["id"] for c in config["calendars"]]
    + [c["name"] for c in config["calendars"]]
):
    if secret:
        assert secret not in encoded
print("Reusable template updated; portable privacy/readback checks passed", flush=True)
deploy = {
    "mode": "refresh",
    "page_ids": [page["id"]],
    "mac_addresses": [device["mac_address"]],
}
save("deploy-payload.json", deploy)
response = request("/api/v2/user/device/deploy", deploy)
save("deploy-response.json", response)
assignment_after = request(
    "/api/v2/user/device/playlist?"
    + urllib.parse.urlencode({"mac_address": device["mac_address"], "type": "all"})
)
save("after-assignment.json", assignment_after)
devices_after = request("/api/v2/user/device/list")["result"]
device_after = next(d for d in devices_after if d["id"] == device["id"])
save("after-device.json", device_after)
save(
    "persistence-report.json",
    {
        "page_exact_readback": True,
        "portable_exact_readback": True,
        "portable_privacy_check": True,
        "deploy_code": response["code"],
        "template_audit_status": aftertemplate.get("audit_status"),
        "device_field_names": sorted(device_after),
        "physical_delivery_confirmed": False,
    },
)
print("Refresh deploy accepted; assignment and device state captured", flush=True)
