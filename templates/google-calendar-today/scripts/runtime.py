"""Pure production compilation and editor-preserving layout helpers."""

import copy
import json


def production_html(source, assets):
    html = source.replace(
        "/* ASSET_MANIFEST */{}", json.dumps(assets, separators=(",", ":"))
    )
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
    return html


def find_element(elements, identifier):
    for element in elements:
        if element.get("id") == identifier:
            return element
        found = find_element(element.get("children", []), identifier)
        if found is not None:
            return found
    return None


def remove_elements(elements, identifier):
    retained = []
    for element in elements:
        if element.get("id") == identifier:
            continue
        if "children" in element:
            element["children"] = remove_elements(element["children"], identifier)
        retained.append(element)
    return retained


def merge_candidate(page_layout, candidate_layout):
    merged = copy.deepcopy(page_layout)
    merged["stageElements"] = remove_elements(
        merged.get("stageElements", []), "native-battery"
    )
    current = find_element(merged.get("stageElements", []), "native-agenda")
    candidate = find_element(candidate_layout.get("stageElements", []), "native-agenda")
    if current is None or candidate is None:
        raise ValueError("Both page and candidate must contain native-agenda")
    url = candidate.get("htmlConfig", {}).get("htmlUrl")
    if not url:
        raise ValueError("Candidate native-agenda has no HTML URL")
    current.setdefault("htmlConfig", {})["htmlUrl"] = url
    return merged
