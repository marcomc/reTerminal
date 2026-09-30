"""Build native SenseCraft media and private/portable candidates; no page writes."""

import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
import uuid

from paths import ARTWORK, ROOT, SOURCE, load_config, load_settings, save_config

BASE = "https://sensecraft-hmi-api.seeed.cc"
KEY = os.environ["SENSECRAFT_API_KEY"]


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
    assert v["code"] == 200
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
    assert "testing" not in html and "syntheticEvents" not in html
compiled = ROOT / "agenda-upload.html"
compiled.write_text(html)
digest = hashlib.sha256(compiled.read_bytes()).hexdigest()
k = "agenda-upload.html|" + digest
if k not in cache:
    cache[k] = {"url": upload(compiled, "document"), "sha256": digest}
    save("uploads.json", cache)
    print("Uploaded native agenda document", flush=True)
settings = load_settings()
config = load_config()
assert 1 <= len(config["calendars"]) <= 10
assert len({c["id"] for c in config["calendars"]}) == len(config["calendars"])
assert isinstance(config["intensity"], int) and 0 <= config["intensity"] <= 100
if config["showBattery"]:
    config["batteryBinding"] = {"deviceId": settings["device_id"], "apiKey": KEY}
else:
    config.pop("batteryBinding", None)
save_config(config)
base = cache[k]["url"]
privateUrl = (
    base
    + "#"
    + urllib.parse.urlencode(
        {"config": json.dumps(config, separators=(",", ":"), ensure_ascii=False)}
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
    for k, v in config.items()
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
    [KEY, config["session_id"]]
    + [c["id"] for c in config["calendars"]]
    + [c["name"] for c in config["calendars"]]
):
    if secret:
        assert secret not in encoded
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
