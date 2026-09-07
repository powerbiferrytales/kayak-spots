"""
enrich_osm_access.py

Re-queries Overpass API for full tag data on all kayak/canoe spots, then
stamps each OSM spot in kayak_spots.js with an 'access' field:

  "public"   — explicitly open (access=public/yes/permissive, or put_in points)
  "club"     — club or members-only (club=*, access=members, leisure=sports_centre)
  "private"  — restricted (access=private/no)
  "unknown"  — no access tags present

Wiki and personal spots are set to "public" (they are curated for public access).

Run from the same folder as kayak_spots.js:
  python enrich_osm_access.py
"""

import json, re, time, sys, pathlib

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Run:  pip install requests")

JS_FILE      = pathlib.Path("kayak_spots.js")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
EUROPE_BBOX  = (34, -12, 72, 45)


def classify_access(tags: dict) -> str:
    access  = tags.get("access", "")
    club    = tags.get("club", "")
    leisure = tags.get("leisure", "")
    waterway = tags.get("waterway", "")

    if access in ("private", "no"):
        return "private"

    if access == "members" or club or leisure == "sports_centre":
        return "club"

    if access in ("public", "yes", "permissive") or waterway == "put_in":
        return "public"

    return "unknown"


def fetch_osm_tags() -> dict:
    """Fetch full tags for all kayak/canoe OSM elements. Returns {type/id: tags}."""
    s, w, n, e = EUROPE_BBOX
    query = f"""
[out:json][timeout:120][bbox:{s},{w},{n},{e}];
(
  node["leisure"="slipway"]["canoe"~"^(yes|designated|permissive)$"];
  node["leisure"="slipway"]["kayak"~"^(yes|designated|permissive)$"];
  node["sport"="canoe"];
  node["waterway"="put_in"];
  node["canoe"~"^(yes|designated|permissive)$"]["leisure"!="swimming_pool"];
  node["kayak"~"^(yes|designated|permissive)$"]["leisure"!="swimming_pool"];
  way["leisure"="slipway"]["canoe"~"^(yes|designated|permissive)$"];
  way["leisure"="slipway"]["kayak"~"^(yes|designated|permissive)$"];
  way["sport"="canoe"];
  way["waterway"="put_in"];
);
out center tags;
"""
    print("Querying Overpass API for full tag data (30–120 s)…")
    session = requests.Session()
    session.headers["User-Agent"] = (
        "KayakSpotResearch/6.0 (non-commercial; github.com/powerbiferrytales)"
    )

    for attempt in range(3):
        try:
            r = session.post(OVERPASS_URL, data={"data": query}, timeout=150)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as exc:
            print(f"  Attempt {attempt + 1} failed: {exc}")
            if attempt == 2:
                sys.exit("Overpass API unavailable — try again later.")
            time.sleep(10)

    result = {}
    for el in data.get("elements", []):
        key = f"{el['type']}/{el['id']}"
        result[key] = el.get("tags", {})

    print(f"  -> {len(result)} OSM elements retrieved")
    return result


def main():
    if not JS_FILE.exists():
        sys.exit(f"Not found: {JS_FILE} — run the scraper first.")

    text = JS_FILE.read_text(encoding="utf-8")
    m = re.search(r"var KAYAK_SPOTS\s*=\s*(\[.*?\]);", text, re.DOTALL)
    if not m:
        sys.exit("Could not parse kayak_spots.js")
    spots = json.loads(m.group(1))

    osm_tags = fetch_osm_tags()

    counts = {"public": 0, "club": 0, "private": 0, "unknown": 0, "non_osm": 0}

    for spot in spots:
        if spot.get("source") != "osm":
            spot["access"] = "public"
            counts["non_osm"] += 1
            continue

        source_url = spot.get("source_url", "")
        osm_m = re.search(r"openstreetmap\.org/(node|way)/(\d+)", source_url)

        if osm_m:
            osm_key = f"{osm_m.group(1)}/{osm_m.group(2)}"
            tags    = osm_tags.get(osm_key, {})
            access  = classify_access(tags)
        else:
            access = "unknown"

        spot["access"] = access
        counts[access] += 1

    JS_FILE.write_text(
        "var KAYAK_SPOTS = " + json.dumps(spots, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )

    osm_total = counts["public"] + counts["club"] + counts["private"] + counts["unknown"]
    print(f"\nDone — {len(spots)} spots updated:")
    print(f"  public   : {counts['public'] + counts['non_osm']}  "
          f"(incl. {counts['non_osm']} wiki/personal, {counts['public']} OSM)")
    print(f"  club     : {counts['club']}")
    print(f"  private  : {counts['private']}")
    print(f"  unknown  : {counts['unknown']}")
    print(f"  OSM total: {osm_total}")


if __name__ == "__main__":
    main()
