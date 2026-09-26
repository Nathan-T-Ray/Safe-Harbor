#!/usr/bin/env python3
"""Refresh contributor snapshots from live issues without resetting claims."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/safe-harbor'
REPO = 'Nathan-T-Ray/Safe-Harbor'

def gh(*args):
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True).stdout

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true', help='Also refresh the central GitHub board body')
    args = parser.parse_args()
    manifest = json.loads((DOCS / 'github-issues.json').read_text())
    live = json.loads(gh('issue', 'list', '--repo', REPO, '--state', 'all', '--limit', '100', '--json', 'number,title,body,state,labels,assignees,url'))
    by_number = {issue['number']: issue for issue in live}
    specs = []
    for name in ['foundation','data','runtime','harness','ui','quality']:
        specs.extend(json.loads((DOCS/'ticket-specs'/f'{name}.json').read_text()))
    rows, claim_rows = [], []
    for spec in specs:
        ident = spec['id']
        issue = by_number[manifest['tickets'][ident]['number']]
        match = re.search(r'<!-- claim-owner: (.*?) -->', issue['body'])
        owner = match[1] if match else 'UNCLAIMED'
        statuses = [label['name'].removeprefix('status:') for label in issue['labels'] if label['name'].startswith('status:')]
        if len(statuses) != 1:
            raise RuntimeError(f'{ident}: expected exactly one live status label, found {statuses}')
        status = statuses[0].upper()
        label = f'**{status} — {owner}**' if owner != 'UNCLAIMED' else f'{status} — unclaimed'
        deps = ', '.join(f'[{d}]({manifest["tickets"][d]["url"]})' for d in spec['depends_on']) or 'none'
        rows.append(f'| [SH-{ident}]({issue["url"]}) | {spec["title"]} | {label} | {deps} |')
        if issue['state'] == 'OPEN' and owner != 'UNCLAIMED':
            paths = re.search(r'\*\*Reserved paths:\*\* (.*)', issue['body'])
            claim_rows.append(f'| [SH-{ident}]({issue["url"]}) | {owner} | {status} | {paths[1] if paths else "See issue"} |')
    timestamp = datetime.now(timezone.utc).isoformat()
    preamble = f'''# Safe Harbor — tickets and active claims

**60 bounded work packages. NO UNIT TESTS. NO COMPONENT TESTS. E2E ONLY.**

Standalone repository: https://github.com/{REPO}. Branch from `main`. Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. The previous project is not the working repository.

**Live issue titles, claim blocks and status labels are authoritative.** Snapshot refreshed {timestamp}. Claimed work stays reserved until released or accepted. An available ticket can still have unfinished dependencies.

Claim before editing: `python3 scripts/safe_harbor_ticket.py claim SH-ID --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`. Never overlap another owner's reserved paths. Only the integrator changes shared contracts, dependency locks and root startup.

Current implementation and verified limitations: [STATUS.md](https://github.com/{REPO}/blob/main/docs/safe-harbor/STATUS.md). Model-dependent acceptance remains pending until genuine provider runs are recorded. Deterministic operational runs do not establish model improvement.

| Ticket | Work | Status / owner | Dependencies |
|---|---|---|---|
'''
    board = preamble + '\n'.join(rows) + '\n'
    (DOCS/'TICKETS.md').write_text(board)
    (DOCS/'CLAIMS.md').write_text(f'# Current claims\n\nLive issue snapshot {timestamp}. Refresh before editing.\n\n| Ticket | Owner | Status | Reserved paths |\n|---|---|---|---|\n' + '\n'.join(claim_rows)+'\n')
    if args.publish:
        with tempfile.NamedTemporaryFile('w', suffix='.md') as stream:
            stream.write(board); stream.flush()
            gh('issue','edit',str(manifest['board']['number']),'--repo',REPO,'--body-file',stream.name)
    print(f'Refreshed {len(rows)} tickets and {len(claim_rows)} active claims; published={args.publish}')

if __name__ == '__main__':
    main()
