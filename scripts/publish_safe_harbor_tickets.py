#!/usr/bin/env python3
"""Publish the specified Safe Harbor work packages; resume without duplicate issues."""
import argparse
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = 'Nathan-T-Ray/Safe-Harbor'
BASE = f'https://github.com/{REPO}/blob/main'
DOCS = ROOT / 'docs/safe-harbor'
MANIFEST = DOCS / 'github-issues.json'
CLAIMS = {
    **{f'F{i:02}': 'codex-integrator' for i in range(1, 5)},
    **{f'D{i:02}': 'codex-data' for i in range(1, 5)},
    **{f'R{i:02}': 'codex-runtime' for i in range(1, 10)},
    **{f'U{i:02}': 'codex-ui' for i in [*range(1, 11), 12]},
}
LANES = {'F': 'integration', 'D': 'data', 'R': 'runtime', 'H': 'harness-evaluation', 'U': 'ui', 'Q': 'e2e'}


def gh(*args):
    return subprocess.run(['gh', *args], text=True, capture_output=True, check=True).stdout.strip()


def text_file_call(text, *args):
    with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False) as f:
        f.write(text); path = f.name
    try:
        return gh(*args, '--body-file', path)
    finally:
        Path(path).unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--account', help='Use an already authenticated gh account for this process only')
    p.add_argument('--local-only', action='store_true')
    args = p.parse_args()
    if args.account:
        os.environ['GH_TOKEN'] = gh('auth', 'token', '--hostname', 'github.com', '--user', args.account)
    tickets = []
    for name in ['foundation', 'data', 'runtime', 'harness', 'ui', 'quality']:
        tickets.extend(json.loads((DOCS / 'ticket-specs' / f'{name}.json').read_text()))
    assert len(tickets) == 60 and len({t['id'] for t in tickets}) == 60
    all_ids = {t['id'] for t in tickets}
    for t in tickets:
        assert set(t['depends_on']) <= all_ids, t['id']
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {'repository': REPO, 'branch': 'main', 'tickets': {}}
    now = datetime.now(timezone.utc).isoformat()
    for t in tickets:
        ident = t['id']; owner = CLAIMS.get(ident, 'UNCLAIMED')
        claimed = owner != 'UNCLAIMED'
        status = f'CLAIMED — {owner}' if claimed else 'AVAILABLE — UNCLAIMED'
        title = (f'[CLAIMED: {owner}] ' if claimed else '[AVAILABLE] ') + f'[SH-{ident}] {t["title"]}'
        deps = ', '.join(f'[SH-{d}]({BASE}/docs/safe-harbor/tickets/SH-{d}.md)' for d in t['depends_on']) or 'None'
        paths = ', '.join(f'`{x}`' for x in t['paths']) or 'Coordinate a distinct module with the integrator.'
        body = f'''<!-- claim-start -->
<!-- claim-owner: {owner} -->
## {status}
**Owner:** {owner}
**GitHub operator:** {'@Nathan-T-Ray' if claimed else 'unassigned'}
**Branch:** {'`main`' if claimed else 'unassigned — branch from `main`'}
**Reserved paths:** {paths if claimed else 'none; proposed scope listed below'}
**Updated:** {now}
{'Do not duplicate this work or edit reserved paths without coordinating with the owner.' if claimed else 'Available to claim. Dependencies still govern acceptance; check adjacent path owners first.'}
<!-- claim-end -->

# SH-{ident} — {t['title']}

**Lane:** {t['owner']}
**Dependencies:** {deps}
**Proposed file scope:** {paths}

## Work

{t['work']}

## Acceptance criteria

{t['done']}

## Required handoff

- Changed paths and commit/PR.
- What now works.
- Actual acceptance evidence.
- Remaining limitations.
- Next dependent ticket and owner.

## Shared boundaries

**NO UNIT TESTS. NO COMPONENT TESTS. E2E ONLY.** Build/type/syntax/schema/data-integrity checks are allowed. Use real coordinates, sequence, annotations and source tables. No fabricated biology, model runs or improvements. Distinguish mock, deterministic operational, real model and recorded replay.

Only the integrator edits shared contracts, root dependency manifests/locks and startup composition. Scientific tools return bounded typed data; runtime owns database writes; frontend derives no biological verdicts. At most two runtime workers, 24 nodes, three replans and one transient retry. Harness changes cannot alter criteria/evaluator/input data/model/budget/permissions.

Read [contribution and claim protocol]({BASE}/docs/safe-harbor/CONTRIBUTING.md), [specification]({BASE}/docs/safe-harbor/SPECIFICATION.md), [contracts]({BASE}/docs/safe-harbor/CONTRACTS.md), and [ticket board]({BASE}/docs/safe-harbor/TICKETS.md). Safe Harbor supersedes the old LA-* plan; do not assume inherited modules or old PRs satisfy this ticket.

Claim command: `python3 scripts/safe_harbor_ticket.py claim SH-{ident} --owner YOUR_MODEL --branch YOUR_BRANCH --paths YOUR_PATHS`
'''
        (DOCS / 'tickets' / f'SH-{ident}.md').write_text(body)
        assignment = f'''# Assignment: SH-{ident}

Implement [SH-{ident}: {t['title']}](../tickets/SH-{ident}.md) from `origin/main`.

Current publication-time status: **{status}**. Refresh the live GitHub issue before editing; this file is not the ownership authority.

Read AGENTS.md, docs/safe-harbor/CONTRIBUTING.md, SPECIFICATION.md and CONTRACTS.md. Claim first using scripts/safe_harbor_ticket.py. Work only in {paths}. Coordinate shared interfaces and overlapping files. Dependencies: {', '.join(t['depends_on']) or 'none'}.

Work: {t['work']}

Accept only when: {t['done']}

No unit/component tests; actual E2E and build/type/schema/data checks only. Return changed paths/commit, working behavior, measured acceptance evidence, limitations and next dependency. Do not fabricate results or claim acceptance from source code alone.
'''
        (DOCS / 'assignments' / f'SH-{ident}.md').write_text(assignment)
        t.update({'issue_title': title, 'issue_body': body, 'claimed_owner': owner})
    if not args.local_only:
        labels = [
            ('safe-harbor', '0969DA', 'Safe Harbor specification and implementation'),
            ('status:available', '2DA44E', 'Unclaimed; dependencies and path coordination still apply'),
            ('status:claimed', 'D29922', 'Actively owned; read title and claim block before editing'),
            ('status:review', '8250DF', 'Implementation handed off; acceptance review pending'),
            ('status:blocked', 'CF222E', 'Concrete blocker recorded; ownership retained'),
            ('status:done', '1A7F37', 'Acceptance evidence verified'),
            ('coordination', '5319E7', 'Contributor board and ownership coordination'),
        ] + [(f'lane:{v}', 'D4C5F9', f'Safe Harbor {v} work') for v in LANES.values()]
        for name, color, description in labels:
            gh('label', 'create', name, '--repo', REPO, '--color', color, '--description', description, '--force')
        existing = json.loads(gh('issue', 'list', '--repo', REPO, '--state', 'all', '--limit', '200', '--json', 'number,title,url'))
        if 'board' not in manifest:
            board = next((x for x in existing if '[SAFE HARBOR BOARD]' in x['title']), None)
            if board is None:
                url = text_file_call('''# Safe Harbor contributor board

The 60 F/D/R/H/U/Q implementation tickets are being published now. This board will be populated with direct links as each package is created.

**CLAIM BEFORE EDITING.** Claimed issues visibly name the model owner in title/body and carry `status:claimed`; available issues carry `status:available`. Shared contracts/dependencies are integrator-owned. New work branches from `main`. Old LA-* issues/PRs are legacy scope and are not Safe Harbor acceptance.

**NO UNIT TESTS. NO COMPONENT TESTS. E2E ONLY.** Real data, honest mode labels and measurable acceptance required.
''', 'issue', 'create', '--repo', REPO, '--title', '[SAFE HARBOR BOARD] Ticket index, active claims and contributor entry point', '--label', 'safe-harbor,coordination')
                board = {'number': int(url.rsplit('/', 1)[-1]), 'url': url}
            manifest['board'] = board; MANIFEST.write_text(json.dumps(manifest, indent=2)+'\n')
            print('BOARD', board['url'], flush=True)
        for t in tickets:
            ident = t['id']
            if ident in manifest['tickets']:
                continue
            found = next((x for x in existing if f'[SH-{ident}]' in x['title']), None)
            if found is None:
                labels = f'safe-harbor,lane:{LANES[ident[0]]},' + ('status:claimed' if ident in CLAIMS else 'status:available')
                extra = ['--assignee', 'Nathan-T-Ray'] if ident in CLAIMS else []
                url = text_file_call(t['issue_body'], 'issue', 'create', '--repo', REPO, '--title', t['issue_title'], '--label', labels, *extra)
                found = {'number': int(url.rsplit('/', 1)[-1]), 'url': url, 'title': t['issue_title']}
            manifest['tickets'][ident] = found
            MANIFEST.write_text(json.dumps(manifest, indent=2)+'\n')
            print(ident, found['url'], flush=True)
    rows = []
    for t in tickets:
        ident = t['id']; url = manifest['tickets'].get(ident, {}).get('url', f'tickets/SH-{ident}.md')
        status = f'**CLAIMED — {t["claimed_owner"]}**' if ident in CLAIMS else 'AVAILABLE — unclaimed'
        dep_links = ', '.join(f'[{d}]({manifest["tickets"].get(d,{}).get("url", f"tickets/SH-{d}.md")})' for d in t['depends_on']) or 'none'
        rows.append(f'| [SH-{ident}]({url}) | {t["title"]} | {status} | {dep_links} |')
    board_text = f'''# Safe Harbor — tickets and active claims

**60 bounded work packages. NO UNIT TESTS. NO COMPONENT TESTS. E2E ONLY.**

Start from [main](https://github.com/{REPO}/tree/main). Read the [specification]({BASE}/docs/safe-harbor/SPECIFICATION.md), [contracts]({BASE}/docs/safe-harbor/CONTRACTS.md), and [claim protocol]({BASE}/docs/safe-harbor/CONTRIBUTING.md).

**The live ticket's title, claim block, labels and assignee are authoritative.** This table is the initial ownership snapshot ({now}). [Current claimed tickets](https://github.com/{REPO}/issues?q=is%3Aopen+label%3Asafe-harbor+label%3Astatus%3Aclaimed) · [Available tickets](https://github.com/{REPO}/issues?q=is%3Aopen+label%3Asafe-harbor+label%3Astatus%3Aavailable).

Claim before editing: `python3 scripts/safe_harbor_ticket.py claim SH-H01 --owner YOUR_MODEL --branch YOUR_BRANCH --paths backend/safe_harbor/harness/`. A claim adds **CLAIMED: owner** to the title, records branch/paths/time in the body and assigns the GitHub operator. Never take a claimed ticket or overlap another owner's paths. Availability does not waive dependencies.

Active lanes: codex-integrator F01–F04; codex-data D01–D04 (delivered, acceptance review pending); codex-runtime R01–R09; codex-ui U01–U10/U12 (shared UI files reserved). Foundation claims remain open until actual acceptance. Runtime R10–R12 and all harness/evaluation packages are available with interface coordination. Data D05–D07 tools are the next vertical-slice need; D08–D09 need an independent evaluator. U11/cues, U13/presentation, U14/E2E must coordinate App integration with codex-ui.

Old LA-* issues and PRs remain intact for prior contributors; they are legacy scope, not the Safe Harbor queue. Do not assume their acceptance transfers. H01 interface requested by runtime: `safe_harbor.harness.get_harness(hash=None)` and `list_harnesses()`.

| Ticket | Work | Ownership | Dependencies |
|---|---|---|---|
''' + '\n'.join(rows) + '\n'
    (DOCS / 'TICKETS.md').write_text(board_text)
    (DOCS / 'CLAIMS.md').write_text('# Current claims\n\nGitHub live issues are authoritative. See [the ticket board](TICKETS.md) for the initial ownership snapshot and live filtered lists.\n\nDo not duplicate CLAIMED work. Use the claim helper before editing; it records owner, branch, paths and time visibly. Available means unclaimed, not dependency-complete.\n')
    if not args.local_only:
        text_file_call(board_text, 'issue', 'edit', str(manifest['board']['number']), '--repo', REPO)
        print('PUBLISHED', len(manifest['tickets']), 'tickets', manifest['board']['url'], flush=True)


if __name__ == '__main__':
    main()
