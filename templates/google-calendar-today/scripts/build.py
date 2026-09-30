"""Build native SenseCraft media and private/portable candidates; no page writes."""

import hashlib
import json
import sys
import urllib.parse
import urllib.request
import uuid

from paths import (
    ARTWORK,
    ROOT,
    SOURCE,
    load_api_key,
    load_config,
    load_settings,
)

BASE = "https://sensecraft-hmi-api.seeed.cc"
KEY = load_api_key()


def save(name, data):
    p = ROOT / name
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    p.chmod(0o600)


def upload(p, kind):
    boundary = "agenda-" + uuid.uuid4().hex
    mime = "text/html" if kind == "document" else "image/png"
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\n{kind}\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{p.name}"\r\nContent-Type: {mime}\r\n\r\n'
        ).encode()
        + p.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    r = urllib.request.Request(
        BASE + "/api/v1/oss/file/upload",
        data=body,
        headers={
            "api-key": KEY,
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
    )
    with urllib.request.urlopen(r, timeout=55) as f:
        v = json.load(f)
    if v.get("code") != 200:
        raise RuntimeError("SenseCraft asset upload failed")
    return v["result"]["file_url"]


cachefile = ROOT / "uploads.json"
cache = json.loads(cachefile.read_text()) if cachefile.exists() else {}
assets = {}
source = ARTWORK
manifestfile = source / "manifest.json"
decorations = {
    entry["path"]: entry
    for entry in (
        json.loads(manifestfile.read_text())["decorations"]
        if manifestfile.exists()
        else []
    )
}
for p in sorted((source / "monthly").glob("*.png")) + sorted(
    (source / "themes").glob("*.png")
):
    if p.stem in ["white", "dark"]:
        continue
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    decoration = decorations.get(p.relative_to(source).as_posix())
    if decoration is not None and decoration["sha256"] != digest:
        raise ValueError(f"Asset hash does not match manifest: {p.name}")
    k = p.name + "|" + digest
    if k not in cache:
        cache[k] = {"url": upload(p, "image"), "sha256": digest}
        save("uploads.json", cache)
        print("Uploaded decoration", p.stem, flush=True)
    if p.parent.name == "monthly":
        name = "month-" + p.name[:2]
        if p.stem.endswith("-dark"):
            name += "-dark"
    else:
        name = p.stem
    assets[name] = {
        "url": cache[k]["url"],
        "mockup": (
            decoration["mockup_crop"]
            if decoration is not None
            else p.parent.name == "themes"
        ),
    }
for name in list(assets):
    if name.endswith("-dark") and name[:-5] in assets:
        assets[name[:-5]]["darkUrl"] = assets[name]["url"]
        assets[name[:-5]]["darkMockup"] = assets[name]["mockup"]
html = SOURCE.read_text().replace(
    "/* ASSET_MANIFEST */{}", json.dumps(assets, separators=(",", ":"))
)
if "--production" in sys.argv:
    start = html.index("const params=new URLSearchParams(location.search);")
    end = html.index("\nfunction parts", start)
    html = html[:start] + "let now=new Date();" + html[end:]
    start = html.index("function syntheticEvents()")
    end = html.index("\nfunction batteryPercentage(", start)
    html = html[:start] + html[end:]
    start = html.index("const w=testing?")
    end = html.index("):fetch(weatherUrl", start) + 2
    html = html[:start] + "const w=" + html[end:]
    html = html.replace(
        "let ev;if(testing)ev=Promise.resolve(syntheticEvents());else if", "let ev;if"
    )
    html = html.replace(
        "const b=testing?Promise.resolve(78):readBattery();", "const b=readBattery();"
    )
    if "testing" in html or "syntheticEvents" in html:
        raise ValueError("Production document contains test-only code")
settings = load_settings()
config = load_config()
if not 1 <= len(config["calendars"]) <= 10:
    raise ValueError("Private build requires 1–10 calendars")
if len({calendar["id"] for calendar in config["calendars"]}) != len(
    config["calendars"]
):
    raise ValueError("Private build requires distinct calendar IDs")
if not isinstance(config["intensity"], int) or not 0 <= config["intensity"] <= 100:
    raise ValueError("Private build requires intensity 0–100")
forbidden = [KEY, config.get("session_id", "")]
for calendar in config["calendars"]:
    forbidden.extend([calendar.get("id", ""), calendar.get("name", "")])
if any(secret and secret in html for secret in forbidden):
    raise ValueError("Compiled source contains private configuration")
compiled = ROOT / "agenda-upload.html"
compiled.write_text(html)
digest = hashlib.sha256(compiled.read_bytes()).hexdigest()
k = "agenda-upload.html|" + digest
if k not in cache:
    cache[k] = {"url": upload(compiled, "document"), "sha256": digest}
    save("uploads.json", cache)
    print("Uploaded native agenda document", flush=True)
private_config = dict(config)
if config["showBattery"]:
    private_config["batteryBinding"] = {
        "deviceId": settings["device_id"],
        "apiKey": KEY,
    }
else:
    private_config.pop("batteryBinding", None)
base = cache[k]["url"]
privateUrl = (
    base
    + "#"
    + urllib.parse.urlencode(
        {
            "config": json.dumps(
                private_config, separators=(",", ":"), ensure_ascii=False
            )
        }
    )
)
main = {
    "id": "native-agenda",
    "type": "html",
    "x": 0,
    "y": 0,
    "width": 800,
    "height": 480,
    "htmlConfig": {"htmlUrl": privateUrl},
}
# Battery now shares HTML styling; its credential stays in the private fragment.
layout = {
    "stageSize": {"width": 800, "height": 480},
    "dither": 3,
    "stageElements": [
        {
            "id": "__device_container_group__",
            "type": "group",
            "x": 0,
            "y": 0,
            "width": 800,
            "height": 480,
            "fill": "#ffffff",
            "strokeWidth": 0,
            "children": [main],
        }
    ],
}
save("candidate-private.json", layout)
publicConfig = {
    k: v
    for k, v in private_config.items()
    if k not in ["session_id", "calendars", "batteryBinding"]
}
publicConfig["showBattery"] = False
publicConfig["calendars"] = []
portable = json.loads(json.dumps(layout))
portable["stageElements"][0]["children"] = [
    dict(
        main,
        htmlConfig={
            "htmlUrl": base
            + "#"
            + urllib.parse.urlencode(
                {
                    "config": json.dumps(
                        publicConfig, separators=(",", ":"), ensure_ascii=False
                    )
                }
            )
        },
    )
]
save("candidate-portable.json", portable)
# Assert private values are absent from both the portable export and uploaded source.
encoded = json.dumps(portable, ensure_ascii=False) + compiled.read_text()
for secret in (
    [KEY, private_config["session_id"]]
    + [calendar["id"] for calendar in private_config["calendars"]]
    + [calendar["name"] for calendar in private_config["calendars"]]
):
    if secret and secret in encoded:
        raise ValueError("Portable candidate contains private configuration")
save(
    "build-report.json",
    {
        "html_sha256": digest,
        "asset_count": len(assets),
        "private_calendar_count": len(config["calendars"]),
        "portable_privacy_check": True,
        "configuration": {
            k: config[k]
            for k in [
                "language",
                "timezone",
                "backgroundMode",
                "cadence",
                "specialDates",
                "autoDark",
                "intensity",
                "markerMode",
            ]
        },
        "html_url": base,
        "production": "--production" in sys.argv,
    },
)
print("Built private and portable native candidates; privacy check passed", flush=True)
