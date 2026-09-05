"""
Check whether each spot in kayak_spots.js is near a body of water.

Uses the Overpass API (free, no key needed) to query OSM for water
features within RADIUS metres of each coordinate.

Results are cached in water_check_cache.json so the script is resumable
if interrupted — just run it again and it picks up where it left off.

Flagged spots (not near water) are written to water_flagged.csv.

Usage:
    python check_water_proximity.py [--radius 150] [--delay 1.5]
"""

import json, re, csv, time, argparse, pathlib, urllib.request, urllib.error, urllib.parse

SPOTS_FILE  = pathlib.Path('kayak_spots.js')
CACHE_FILE  = pathlib.Path('water_check_cache.json')
OUTPUT_FILE = pathlib.Path('water_flagged.csv')

OVERPASS_URL = 'https://overpass-api.de/api/interpreter'

WATER_QUERY = """
[out:json][timeout:10];
(
  way(around:{r},{lat},{lng})[natural=water];
  way(around:{r},{lat},{lng})[waterway];
  way(around:{r},{lat},{lng})[natural=coastline];
  relation(around:{r},{lat},{lng})[natural=water];
  node(around:{r},{lat},{lng})[natural=water];
);
out count;
"""

def load_spots():
    text = SPOTS_FILE.read_text(encoding='utf-8')
    m = re.search(r'var KAYAK_SPOTS\s*=\s*(\[.*?\]);', text, re.DOTALL)
    if not m:
        raise SystemExit('Could not parse kayak_spots.js')
    return json.loads(m.group(1))

def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding='utf-8'))
    return {}

def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')

def has_water_nearby(lat, lng, radius):
    query = WATER_QUERY.format(r=radius, lat=lat, lng=lng)
    params = urllib.parse.urlencode({'data': query})
    url = OVERPASS_URL + '?' + params
    req = urllib.request.Request(url, headers={'User-Agent': 'kayak-spots-checker/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            total = result.get('elements', [{}])[0].get('tags', {}).get('total', '0')
            return int(total) > 0
    except Exception as e:
        print(f'    API error: {e}')
        return None  # None = unknown, don't cache

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--radius', type=int, default=150,
                        help='metres to search for water (default 150)')
    parser.add_argument('--delay', type=float, default=1.5,
                        help='seconds between API calls (default 1.5)')
    args = parser.parse_args()

    spots = load_spots()
    cache = load_cache()
    flagged = []

    print(f'Checking {len(spots)} spots  |  radius={args.radius}m  |  delay={args.delay}s')
    print(f'Cached results: {len(cache)}  |  Remaining: {len(spots) - len(cache)}')
    print()

    for i, s in enumerate(spots, 1):
        key = f"{s['lat']:.6f},{s['lng']:.6f}"
        name = (s.get('name') or s.get('section') or s.get('region') or '?').strip()

        if key in cache:
            near = cache[key]
            status = 'CACHED-OK' if near else 'CACHED-FLAG'
        else:
            print(f'[{i}/{len(spots)}] Checking: {name[:50]}')
            near = has_water_nearby(s['lat'], s['lng'], args.radius)
            if near is not None:
                cache[key] = near
                save_cache(cache)
            status = 'OK' if near else ('FLAG' if near is not None else 'ERROR')
            time.sleep(args.delay)

        if not cache.get(key, True):
            flagged.append({
                'name':       name,
                'lat':        s['lat'],
                'lng':        s['lng'],
                'region':     s.get('region', ''),
                'country':    s.get('country', ''),
                'source_url': s.get('source_url', ''),
                'maps_url':   s.get('maps_url', ''),
            })
            if 'FLAG' not in status:
                status = 'FLAG'

        if i % 50 == 0:
            print(f'  ... {i}/{len(spots)} done, {len(flagged)} flagged so far')

    # Write output
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['name','lat','lng','region','country','source_url','maps_url'])
        writer.writeheader()
        writer.writerows(flagged)

    print()
    print(f'Done. {len(flagged)} spots flagged out of {len(spots)} total.')
    print(f'Results written to: {OUTPUT_FILE}')

if __name__ == '__main__':
    main()
