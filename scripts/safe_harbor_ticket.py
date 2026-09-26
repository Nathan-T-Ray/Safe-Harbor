#!/usr/bin/env python3
"""Visible cooperative GitHub ticket claims. No credentials are stored."""
import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = 'Nathan-T-Ray/Safe-Harbor'
ROOT = Path(__file__).resolve().parents[1]


def gh(*args):
    return subprocess.run(['gh', *args], check=True, text=True, capture_output=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['claim', 'release', 'show'])
    parser.add_argument('ticket')
    parser.add_argument('--owner')
    parser.add_argument('--branch')
    parser.add_argument('--paths', nargs='+')
    args = parser.parse_args()
    ident = args.ticket.removeprefix('SH-')
    manifest = json.loads((ROOT / 'docs/safe-harbor/github-issues.json').read_text())
    if ident not in manifest['tickets']:
        parser.error('Unknown Safe Harbor ticket ID')
    number = str(manifest['tickets'][ident]['number'])
    issue = json.loads(gh('issue', 'view', number, '--repo', REPO, '--json', 'title,body,state,labels,assignees,url'))
    if args.action == 'show':
        print(json.dumps(issue, indent=2)); return
    if not args.owner:
        parser.error('--owner is required')
    if issue['state'] != 'OPEN':
        parser.error('Ticket is closed; do not claim accepted work')
    marker = re.search(r'<!-- claim-owner: (.*?) -->', issue['body'])
    current_owner = marker.group(1) if marker else 'UNCLAIMED'
    claimed = any(x['name'] == 'status:claimed' for x in issue['labels'])
    if args.action == 'claim' and (claimed or current_owner != 'UNCLAIMED'):
        parser.error(f'Already owned by {current_owner}; coordinate instead of stealing the claim')
    if args.action == 'release' and current_owner != args.owner:
        parser.error(f'Only current owner {current_owner} can release this claim')
    if args.action == 'claim' and (not args.branch or not args.paths):
        parser.error('Claims require --branch and --paths')
    login = gh('api', 'user', '--jq', '.login')
    if args.action == 'release' and login not in [a['login'] for a in issue['assignees']]:
        parser.error('Only the assigned GitHub account can release this claim')
    owner = args.owner if args.action == 'claim' else 'UNCLAIMED'
    status = f'CLAIMED — {owner}' if args.action == 'claim' else 'AVAILABLE — UNCLAIMED'
    block = '\n'.join([
        '<!-- claim-start -->', f'<!-- claim-owner: {owner} -->',
        f'## {status}', f'**Owner:** {owner}',
        f'**GitHub operator:** @{login}' if args.action == 'claim' else '**GitHub operator:** unassigned',
        f'**Branch:** `{args.branch}`' if args.action == 'claim' else '**Branch:** unassigned',
        f'**Reserved paths:** {", ".join(args.paths or [])}' if args.action == 'claim' else '**Reserved paths:** none',
        f'**Updated:** {datetime.now(timezone.utc).isoformat()}',
        'Do not edit these paths without coordinating with the owner.' if args.action == 'claim' else 'Read dependencies and overlapping path claims before claiming.',
        '<!-- claim-end -->',
    ])
    body = re.sub(r'<!-- claim-start -->.*?<!-- claim-end -->', lambda _: block, issue['body'], flags=re.S)
    if body == issue['body'] and '<!-- claim-start -->' not in issue['body']:
        parser.error('Missing claim block; ask integrator to repair issue')
    title = re.sub(r'^\[(CLAIMED: [^\]]+|AVAILABLE)\]\s*', '', issue['title'])
    title = (f'[CLAIMED: {owner}] ' if args.action == 'claim' else '[AVAILABLE] ') + title
    label = 'status:claimed' if args.action == 'claim' else 'status:available'
    remove = ','.join(x['name'] for x in issue['labels'] if x['name'].startswith('status:') and x['name'] != label)
    with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False) as stream:
        stream.write(body); path = stream.name
    try:
        # Recheck immediately before mutation. GitHub issues have no compare-and-swap claim API.
        check = json.loads(gh('issue', 'view', number, '--repo', REPO, '--json', 'body'))
        if check['body'] != issue['body']:
            parser.error('Issue changed while claiming; refresh and coordinate')
        gh('issue', 'edit', number, '--repo', REPO, '--title', title, '--body-file', path,
           '--add-label', label, *(['--remove-label', remove] if remove else []),
           '--add-assignee' if args.action == 'claim' else '--remove-assignee', login)
    finally:
        Path(path).unlink(missing_ok=True)
    updated = json.loads(gh('issue', 'view', number, '--repo', REPO, '--json', 'title,body,labels,url'))
    if f'<!-- claim-owner: {owner} -->' not in updated['body']:
        raise RuntimeError('Claim changed concurrently; do not start work before resolving ownership')
    print(updated['title']); print(updated['url'])
    print('Refresh current claims before editing. GitHub is authoritative; the committed board is a snapshot.')


if __name__ == '__main__':
    main()
