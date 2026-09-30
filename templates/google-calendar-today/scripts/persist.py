"""Save a production candidate to one private SenseCraft page and optionally deploy.

This helper never creates, reads, updates, or publishes a reusable template.
"""

import argparse
import copy
import datetime
import hashlib
import json
import urllib.parse
import urllib.request
import uuid

from paths import ROOT, load_api_key, load_config, load_settings

BASE = "https://sensecraft-hmi-api.seeed.cc"


def save(name, data):
    path = ROOT / name
    if name.startswith("before-") and path.exists():
        path = ROOT / (
            path.stem
            + "-"
            + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
            + path.suffix
        )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    path.chmod(0o600)


def request(route, payload=None, method=None):
    key = load_api_key()
    response = urllib.request.Request(
        BASE + route,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"api-key": key, "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(response, timeout=60) as stream:
        raw = stream.read()
    if raw.startswith(b"\x89PNG"):
        return raw
    value = json.loads(raw)
    if value.get("code") != 200:
        raise RuntimeError(
            "SenseCraft application code "
            + str(value.get("code"))
            + " for "
            + route.split("?")[0]
        )
    return value


def upload_thumbnail(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    cachefile = ROOT / "thumbnail-uploads.json"
    cache = json.loads(cachefile.read_text()) if cachefile.exists() else {}
    if digest in cache:
        return cache[digest]
    boundary = "agenda-" + uuid.uuid4().hex
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\nthumbnail\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="agenda-preview.png"\r\nContent-Type: image/png\r\n\r\n'
        ).encode()
        + path.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    response = urllib.request.Request(
        BASE + "/api/v1/oss/file/upload",
        data=body,
        headers={
            "api-key": load_api_key(),
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
    )
    with urllib.request.urlopen(response, timeout=55) as stream:
        value = json.load(stream)
    if value.get("code") != 200:
        raise RuntimeError("Thumbnail upload failed")
    cache[digest] = value["result"]["file_url"]
    save("thumbnail-uploads.json", cache)
    return cache[digest]


def _find_element(elements, identifier):
    for element in elements:
        if element.get("id") == identifier:
            return element
        found = _find_element(element.get("children", []), identifier)
        if found is not None:
            return found
    return None


def _remove_elements(elements, identifier):
    """Remove obsolete owned elements while retaining every unrelated editor node."""
    retained = []
    for element in elements:
        if element.get("id") == identifier:
            continue
        if "children" in element:
            element["children"] = _remove_elements(element["children"], identifier)
        retained.append(element)
    return retained


def merge_candidate(page_layout, candidate_layout):
    """Keep editor metadata, update the agenda URL, and remove legacy battery."""
    merged = copy.deepcopy(page_layout)
    merged["stageElements"] = _remove_elements(
        merged.get("stageElements", []), "native-battery"
    )
    current = _find_element(merged.get("stageElements", []), "native-agenda")
    candidate = _find_element(
        candidate_layout.get("stageElements", []), "native-agenda"
    )
    if current is None or candidate is None:
        raise ValueError("Both page and candidate must contain native-agenda")
    url = candidate.get("htmlConfig", {}).get("htmlUrl")
    if not url:
        raise ValueError("Candidate native-agenda has no HTML URL")
    current.setdefault("htmlConfig", {})["htmlUrl"] = url
    return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deploy", action="store_true", help="refresh the configured device"
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="render and save the candidate preview without changing SenseCraft",
    )
    args = parser.parse_args()
    if args.deploy and args.preview_only:
        parser.error("--deploy cannot be combined with --preview-only")
    report = json.loads((ROOT / "build-report.json").read_text())
    if not report.get("production"):
        raise ValueError("Build a --production candidate before saving")
    candidate = json.loads((ROOT / "candidate-private.json").read_text())
    if "synthetic" in (ROOT / "agenda-upload.html").read_text():
        raise ValueError("Production document still contains synthetic test data")

    settings = load_settings()
    page_id = settings.get("page_id")
    if not page_id:
        raise ValueError("Connection configuration requires resources.page_id")
    page = request(
        "/api/v2/user/page/detail?" + urllib.parse.urlencode({"page_id": page_id})
    )["result"]
    missing = [field for field in ("id", "name", "data") if not page.get(field)]
    if missing:
        raise ValueError(
            "Private page is missing required metadata: " + ", ".join(missing)
        )
    save("before-page.json", page)
    device = None
    deployment = None
    if args.deploy:
        device_id = settings.get("device_id")
        if not device_id:
            raise ValueError("Connection configuration requires resources.device_id")
        devices = request("/api/v2/user/device/list")["result"]
        device = next((item for item in devices if item["id"] == device_id), None)
        if device is None:
            raise ValueError("Configured device is not available to this account")
        save("before-device.json", device)
        assignment = request(
            "/api/v2/user/device/playlist?"
            + urllib.parse.urlencode(
                {"mac_address": device["mac_address"], "type": "all"}
            )
        )
        save("before-assignment.json", assignment)
    page_layout = json.loads(page["data"])
    private = merge_candidate(page_layout, candidate)
    preview = request(
        "/render/preview",
        {"layout": private, "resolution": "800x480", "dither": 3, "img_format": "png"},
    )
    if not isinstance(preview, bytes):
        raise TypeError("SenseCraft preview did not return PNG data")
    (ROOT / "production-before-save.png").write_bytes(preview)
    if args.preview_only:
        print("Candidate preview saved; no SenseCraft page was changed", flush=True)
        return
    thumbnail = upload_thumbnail(ROOT / "production-before-save.png")

    payload = {
        "id": page["id"],
        "name": page["name"],
        "type": page.get("type", "layout"),
        "data": json.dumps(private, separators=(",", ":"), ensure_ascii=False),
        "resolution": page.get("resolution", "800x480"),
        "dither": page.get("dither", 3),
        "thumbnail": thumbnail,
        "description": page.get("description", ""),
        "tags": page.get("tags", []),
    }
    save("page-update-payload.json", payload)
    request("/api/v2/user/page", payload, "PUT")
    after = request(
        "/api/v2/user/page/detail?" + urllib.parse.urlencode({"page_id": page["id"]})
    )["result"]
    save("after-page.json", after)
    if json.loads(after["data"]) != private:
        raise RuntimeError("Saved private page did not read back exactly")
    save("persisted-private.json", private)
    print("Private page saved and read back exactly", flush=True)

    if args.deploy:
        deployment = {
            "mode": "refresh",
            "page_ids": [page["id"]],
            "mac_addresses": [device["mac_address"]],
        }
        save("deploy-payload.json", deployment)
        response = request("/api/v2/user/device/deploy", deployment)
        save("deploy-response.json", response)
        assignment_after = request(
            "/api/v2/user/device/playlist?"
            + urllib.parse.urlencode(
                {"mac_address": device["mac_address"], "type": "all"}
            )
        )
        save("after-assignment.json", assignment_after)
        print("Refresh deploy accepted; assignment captured", flush=True)

    config = load_config()
    save(
        "persistence-report.json",
        {
            "page_exact_readback": True,
            "private_calendar_count": len(config.get("calendars", [])),
            "deployment_requested": args.deploy,
            "deploy_code": deployment and 200,
            "physical_delivery_confirmed": False,
        },
    )


if __name__ == "__main__":
    main()
