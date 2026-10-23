#!/usr/bin/env python3
"""Merge the findings tables of several reviewer reports into one index grouped by severity.

Reads markdown reports, finds table rows whose first cell (or second, for compliance-style tables with a
type column) is a severity or verdict word, and writes a markdown index:
  ## BLOCKER / HIGH / MEDIUM / LOW / REJECT-type verdicts ...
  | source report | row cells ... |
Severity words recognised: BLOCKER, HIGH, MEDIUM, MED, LOW, LIKELY REJECT, RISK, OK (verdict tables).
The index is a map for writing the FIXSPEC; read the full reports too. Local files only, standard library only.

Usage: python3 collect_findings.py critiques/final/*-reader.md critiques/final/dr-funnel.md critiques/final/compliance.md --out critiques/final/findings-index.md
"""
import argparse
import os
import re

ORDER = ['BLOCKER', 'LIKELY REJECT', 'HIGH', 'RISK', 'MEDIUM', 'LOW', 'OK']
ALIAS = {'MED': 'MEDIUM'}


def sev_of(cell):
    c = re.sub(r'[*_`]', '', cell).strip().upper()
    c = ALIAS.get(c, c)
    for s in ORDER:
        if c == s or c.startswith(s + ' ') or c.startswith(s + ' ('):
            return s
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('reports', nargs='+')
    ap.add_argument('--out', default='findings-index.md')
    a = ap.parse_args()

    groups = {s: [] for s in ORDER}
    for path in a.reports:
        name = os.path.basename(path)
        if name in (os.path.basename(a.out), 'BRIEF.md', 'FIXSPEC.md') or name.startswith('fixed-'):
            continue
        for line in open(path, encoding='utf8'):
            if not line.lstrip().startswith('|') or re.match(r'^\s*\|[\s:|-]+\|\s*$', line):
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if not cells:
                continue
            sev = sev_of(cells[0])
            rest = cells[1:]
            if not sev and len(cells) > 1:
                sev = sev_of(cells[1])
                rest = [cells[0]] + cells[2:]
            if sev:
                groups[sev].append((name, rest))
    total = sum(len(v) for v in groups.values())
    with open(a.out, 'w', encoding='utf8') as f:
        f.write(f'# Findings index ({total} rows from {len(a.reports)} files)\n\n')
        f.write('Map for the FIXSPEC. Read the full reports for context and exact wording.\n\n')
        for s in ORDER:
            if not groups[s]:
                continue
            f.write(f'## {s} ({len(groups[s])})\n\n| source | finding |\n|---|---|\n')
            for name, rest in groups[s]:
                f.write(f'| {name} | ' + ' / '.join(x.replace('|', '/') for x in rest) + ' |\n')
            f.write('\n')
    print(f'{total} findings -> {a.out}: ' + ', '.join(f'{s} {len(v)}' for s, v in groups.items() if v))


if __name__ == '__main__':
    main()
