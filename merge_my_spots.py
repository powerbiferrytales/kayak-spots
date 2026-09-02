"""
Merge my_spots.csv into kayak_spots.js.

CSV columns (only name/lat/lng required):
  name, lat, lng, notes, region, country

Run from the same folder as kayak_spots.js:
  python merge_my_spots.py
"""
import csv, json, re, pathlib, sys

CSV_FILE = pathlib.Path('my_spots.csv')
JS_FILE  = pathlib.Path('kayak_spots.js')

if not CSV_FILE.exists():
    sys.exit(f"Not found: {CSV_FILE}")
if not JS_FILE.exists():
    sys.exit(f"Not found: {JS_FILE}  — run the scraper first.")

# Load existing spots
text = JS_FILE.read_text(encoding='utf-8')
m = re.search(r'var KAYAK_SPOTS\s*=\s*(\[.*?\]);', text, re.DOTALL)
if not m:
    sys.exit("Could not parse kayak_spots.js")
existing = json.loads(m.group(1))

# Strip any previously merged personal spots so re-runs are idempotent
existing = [s for s in existing if s.get('source') != 'personal']

# Read CSV
personal = []
with open(CSV_FILE, newline='', encoding='utf-8-sig') as f:
    for i, row in enumerate(csv.DictReader(f), 1):
        name = row.get('name', '').strip()
        try:
            lat = float(row['lat'])
            lng = float(row['lng'])
        except (KeyError, ValueError):
            print(f"  Row {i}: skipping — missing or invalid lat/lng")
            continue
        maps_url = f"https://www.google.com/maps?q={lat},{lng}"
        personal.append({
            "name":       name,
            "lat":        lat,
            "lng":        lng,
            "region":     row.get('region', '').strip() or 'Personal',
            "section":    row.get('notes',  '').strip(),
            "country":    row.get('country','').strip() or 'Personal',
            "source":     "personal",
            "source_url": maps_url,
            "maps_url":   maps_url,
        })

if not personal:
    sys.exit("No valid rows found in my_spots.csv")

combined = existing + personal
JS_FILE.write_text(
    'var KAYAK_SPOTS = ' + json.dumps(combined, ensure_ascii=False, separators=(',', ':')) + ';',
    encoding='utf-8'
)
print(f"Done: {len(personal)} personal  +  {len(existing)} scraped  =  {len(combined)} total")
