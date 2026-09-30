"""One-shot API configuration. Never runs periodically or hosts a service."""

import argparse
import json
import re
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from paths import ROOT, load_api_key, load_config, load_settings, save_config

BASE = "https://sensecraft-hmi-api.seeed.cc"
ENUMS = {
    "language": {"it", "en", "fr", "de", "es"},
    "markerMode": {"initials_and_dot", "initials_only", "dot_only", "none"},
    "backgroundMode": {"automatic", "manual"},
    "cadence": {"months", "seasons"},
    "mode": {"light", "dark"},
    "hemisphere": {"auto", "north", "south"},
    "carnivalRule": {"shrove_tuesday", "none"},
}
BOOLS = {
    "showTimezone",
    "showSunrise",
    "showSunset",
    "showMoon",
    "showBattery",
    "autoDark",
    "specialDates",
    "excludeBirthdays",
}
THEMES = {
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
} | {"month-" + str(i).zfill(2) for i in range(1, 13)}


def api_key():
    return load_api_key()


def save(name, v):
    p = ROOT / name
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2))
    p.chmod(0o600)


def api(route, data=None, method=None):
    r = urllib.request.Request(
        BASE + route,
        data=None if data is None else json.dumps(data).encode(),
        headers={
            "api-key": api_key(),
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(r, timeout=60) as f:
        raw = f.read()
    if raw.startswith(b"\x89PNG"):
        return raw
    v = json.loads(raw)
    if v.get("code") != 200:
        raise RuntimeError("SenseCraft application code " + str(v.get("code")))
    return v.get("result")


def upload_preview(raw):
    b = "agenda-" + uuid.uuid4().hex
    body = (
        (
            f'--{b}\r\nContent-Disposition: form-data; name="type"\r\n\r\nthumbnail\r\n--{b}\r\nContent-Disposition: form-data; name="file"; filename="agenda-configured-preview.png"\r\nContent-Type: image/png\r\n\r\n'
        ).encode()
        + raw
        + f"\r\n--{b}--\r\n".encode()
    )
    r = urllib.request.Request(
        BASE + "/api/v1/oss/file/upload",
        data=body,
        headers={
            "api-key": api_key(),
            "Content-Type": "multipart/form-data; boundary=" + b,
        },
    )
    with urllib.request.urlopen(r, timeout=45) as f:
        v = json.load(f)
    if v.get("code") != 200:
        raise RuntimeError("Thumbnail upload failed")
    return v.get("result")["file_url"]


def validate(c):
    if not 1 <= len(c["calendars"]) <= 10:
        raise ValueError("Select 1–10 calendars")
    if len({x["id"] for x in c["calendars"]}) != len(c["calendars"]):
        raise ValueError("Calendars must be distinct")
    for k, values in ENUMS.items():
        if c[k] not in values:
            raise ValueError("Invalid " + k)
    if c["theme"] not in THEMES:
        raise ValueError("Invalid theme")
    for k in BOOLS:
        if type(c[k]) is not bool:
            raise ValueError(k + " must be boolean")
    if type(c["intensity"]) is not int or not 0 <= c["intensity"] <= 100:
        raise ValueError("intensity must be an integer 0–100")
    ZoneInfo(c["timezone"])
    if (
        not -90 <= float(c["latitude"]) <= 90
        or not -180 <= float(c["longitude"]) <= 180
    ):
        raise ValueError("Invalid coordinates")
    if not 24 <= int(c["minTitleSize"]) <= int(c["titleSize"]) <= 32:
        raise ValueError("Invalid title font bounds")
    for x in c["calendars"]:
        if not x["initials"].strip() or len(x["initials"]) > 4:
            raise ValueError("Initials require 1–4 characters")
        if not re.fullmatch("#[0-9a-fA-F]{6}", x["color"]):
            raise ValueError("Use #RRGGBB colors")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list-calendars", action="store_true")
    p.add_argument(
        "--calendar",
        action="append",
        help="Fresh list index:INITIALS:#RRGGBB; repeat 1–10 times",
    )
    p.add_argument(
        "--set",
        action="append",
        default=[],
        help="Setting=value; JSON booleans/numbers or plain string",
    )
    p.add_argument(
        "--city",
        help="Geocode a city with the first-party Open-Meteo fallback provider",
    )
    p.add_argument("--city-index", type=int, default=1)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--save", action="store_true")
    p.add_argument("--deploy", action="store_true")
    p.add_argument("--check-only", action="store_true")
    a = p.parse_args()
    config = load_config()
    settings = load_settings()
    if a.deploy and not a.save:
        p.error("--deploy requires --save")
    if a.list_calendars or a.calendar or a.save:
        records = api(
            "/api/v2/calendar/list?"
            + urllib.parse.urlencode({"session_id": config["session_id"]})
        )["calendarList"]
        if a.list_calendars:
            for i, c in enumerate(records, 1):
                print(str(i) + ". " + c.get("summary", ""))
        if a.calendar:
            chosen = []
            for spec in a.calendar:
                index, initials, color = spec.split(":", 2)
                if not 1 <= int(index) <= len(records):
                    raise ValueError("Invalid calendar list index")
                record = records[int(index) - 1]
                chosen.append(
                    {
                        "id": record["id"],
                        "name": record.get("summary", ""),
                        "initials": initials,
                        "color": color,
                    }
                )
            config["calendars"] = chosen
        if a.save and not all(
            c["id"] in {r["id"] for r in records} for c in config["calendars"]
        ):
            raise ValueError("Selection no longer belongs to the connected Google list")
    editable = (
        set(ENUMS)
        | BOOLS
        | {
            "theme",
            "timezone",
            "latitude",
            "longitude",
            "city",
            "intensity",
            "titleSize",
            "minTitleSize",
        }
    )
    for assignment in a.set:
        name, value = assignment.split("=", 1)
        if name not in editable:
            p.error("Setting not editable: " + name)
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
        config[name] = value
    if a.city:
        url = (
            "https://geocoding-api.open-meteo.com/v1/search?"
            + urllib.parse.urlencode(
                {
                    "name": a.city,
                    "count": 10,
                    "language": config["language"],
                    "format": "json",
                }
            )
        )
        with urllib.request.urlopen(url, timeout=30) as f:
            geo = json.load(f).get("results", [])
        if not geo:
            raise ValueError("No matching city")
        if not 1 <= a.city_index <= len(geo):
            raise ValueError("Invalid city-index")
        city = geo[a.city_index - 1]
        config.update(
            {
                "city": city["name"],
                "latitude": city["latitude"],
                "longitude": city["longitude"],
                "timezone": city["timezone"],
            }
        )
    validate(config)
    if a.check_only:
        print("Configuration validation passed")
        return
    if not (a.preview or a.save):
        if a.set or a.city or a.calendar:
            save("config-draft.json", config)
            print("Validated draft saved privately; no account change")
        return
    if config["showBattery"]:
        config["batteryBinding"] = {
            "deviceId": settings["device_id"],
            "apiKey": api_key(),
        }
    else:
        config.pop("batteryBinding", None)
    page = api(
        "/api/v2/user/page/detail?"
        + urllib.parse.urlencode({"page_id": settings["page_id"]})
    )
    layout = json.loads(page["data"])
    children = layout["stageElements"][0]["children"]
    html = next(x for x in children if x["id"] == "native-agenda")
    url = urllib.parse.urldefrag(html["htmlConfig"]["htmlUrl"])[0]
    html["htmlConfig"]["htmlUrl"] = (
        url
        + "#"
        + urllib.parse.urlencode(
            {"config": json.dumps(config, separators=(",", ":"), ensure_ascii=False)}
        )
    )
    children[:] = [x for x in children if x["id"] != "native-battery"]
    if a.preview or a.save:
        raw = api(
            "/render/preview",
            {
                "layout": layout,
                "resolution": "800x480",
                "dither": 3,
                "img_format": "png",
            },
        )
        if not isinstance(raw, bytes):
            raise TypeError("SenseCraft preview did not return PNG data")
        (ROOT / "configured-preview.png").write_bytes(raw)
    if a.save:
        save("before-configure-page.json", page)
        api(
            "/api/v2/user/page",
            {
                "id": page["id"],
                "data": json.dumps(layout, separators=(",", ":"), ensure_ascii=False),
                "thumbnail": upload_preview(raw),
            },
            "PUT",
        )
        after = api(
            "/api/v2/user/page/detail?"
            + urllib.parse.urlencode({"page_id": page["id"]})
        )
        if json.loads(after["data"]) != layout:
            raise RuntimeError("Saved page did not read back exactly")
        save_config(config)
        save("candidate-private.json", layout)
        save("persisted-private.json", layout)
        print("Configuration saved and read back")
    if a.deploy:
        d = next(
            d
            for d in api("/api/v2/user/device/list")
            if str(d["id"]) == str(settings["device_id"])
        )
        api(
            "/api/v2/user/device/deploy",
            {
                "mode": "refresh",
                "page_ids": [page["id"]],
                "mac_addresses": [d["mac_address"]],
            },
        )
        print("Refresh accepted")


if __name__ == "__main__":
    main()
