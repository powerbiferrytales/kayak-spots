"""
Fetch open GitHub issues labelled 'new-spot', add them to my_spots.csv,
run the merge script, and close each processed issue.

Setup:
    Create a file called .env in this folder containing:
        GITHUB_TOKEN=ghp_your_token_here

    Then run:
        python process_new_spots.py

Requirements: Python 3.6+, no external packages needed.
"""

import csv, json, os, pathlib, re, subprocess, sys, urllib.request, urllib.error

REPO         = 'powerbiferrytales/kayak-spots'
LABEL        = 'new-spot'
CSV_FILE     = pathlib.Path('my_spots.csv')
MERGE_SCRIPT = pathlib.Path('merge_my_spots.py')

def load_token():
    env_file = pathlib.Path('.env')
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith('GITHUB_TOKEN='):
                return line.split('=', 1)[1].strip()
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        return token
    sys.exit('No GITHUB_TOKEN found. Create a .env file with GITHUB_TOKEN=your_token')

def gh_get(path, token):
    url = f'https://api.github.com{path}'
    req = urllib.request.Request(url, headers={
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'kayak-spots-processor/1.0',
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def gh_patch(path, token, data):
    url = f'https://api.github.com{path}'
    req = urllib.request.Request(url, method='PATCH',
        data=json.dumps(data).encode(),
        headers={
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'User-Agent': 'kayak-spots-processor/1.0',
        })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def parse_body(body):
    """Parse GitHub issue form body into a dict of field -> value."""
    fields = {}
    current = None
    for line in body.splitlines():
        heading = re.match(r'^###\s+(.+)', line)
        if heading:
            current = heading.group(1).strip()
            fields[current] = ''
        elif current is not None:
            stripped = line.strip()
            if stripped and stripped not in ('_No response_',):
                fields[current] = (fields[current] + ' ' + stripped).strip()
    return fields

def fetch_issues(token):
    issues = gh_get(f'/repos/{REPO}/issues?labels={LABEL}&state=open&per_page=50', token)
    return issues

def load_csv():
    if not CSV_FILE.exists():
        return []
    with open(CSV_FILE, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def save_csv(rows):
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['name','lat','lng','notes','region','country'])
        writer.writeheader()
        writer.writerows(rows)

def main():
    token = load_token()
    print(f'Fetching open issues labelled "{LABEL}" from {REPO}…')
    issues = fetch_issues(token)

    if not issues:
        print('No new spot issues found.')
        return

    print(f'Found {len(issues)} issue(s).')
    existing = load_csv()
    added = []

    for issue in issues:
        number = issue['number']
        title  = issue['title']
        print(f'\n  Issue #{number}: {title}')

        fields = parse_body(issue.get('body') or '')

        try:
            lat = float(fields.get('Latitude', '').replace(',', '.'))
            lng = float(fields.get('Longitude', '').replace(',', '.'))
        except ValueError:
            print(f'    Skipping — could not parse lat/lng from issue body')
            continue

        name    = title.strip()
        region  = fields.get('Region', '').strip()
        country = fields.get('Country', '').strip()
        notes   = fields.get('Notes', '').strip()
        access  = fields.get('Access type', '').strip()
        if access and access != 'Public (anyone can use)':
            notes = f'[{access}] {notes}'.strip()

        row = {'name': name, 'lat': lat, 'lng': lng,
               'notes': notes, 'region': region, 'country': country}
        existing.append(row)
        added.append((number, name, lat, lng))
        print(f'    Added: {name} ({lat}, {lng})')

        gh_patch(f'/repos/{REPO}/issues/{number}', token, {'state': 'closed'})
        print(f'    Issue #{number} closed.')

    if not added:
        print('\nNothing to add.')
        return

    save_csv(existing)
    print(f'\nSaved {len(added)} new spot(s) to {CSV_FILE}')

    if MERGE_SCRIPT.exists():
        print('Running merge script…')
        subprocess.run([sys.executable, str(MERGE_SCRIPT)], check=True)
    else:
        print(f'Note: {MERGE_SCRIPT} not found — run it manually to update kayak_spots.js')

if __name__ == '__main__':
    main()
