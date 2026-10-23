#!/usr/bin/env python3
"""Grep the site for phrases that must be gone after a fix round. Read-only, standard library only.

Phrases file: one phrase per line; blank lines and lines starting with # are ignored. A line may start with
"re:" to be treated as a regular expression (case-insensitive), otherwise it is a plain, case-sensitive
substring. See templates/phrases.example.txt.

Usage:
  python3 check_old_phrases.py critiques/final/phrases-hu.txt --root site/hu
  python3 check_old_phrases.py phrases.txt --root site --ext .html .js
Prints file:line and the phrase for every hit. Exit code 1 if anything is found.
"""
import argparse
import os
import re
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('phrases', help='phrases file')
    ap.add_argument('--root', required=True, nargs='+', help='folder(s) or file(s) to search')
    ap.add_argument('--ext', nargs='*', default=['.html', '.js', '.json', '.md', '.txt'], help='file extensions to search')
    a = ap.parse_args()

    pats = []
    for line in open(a.phrases, encoding='utf8'):
        s = line.rstrip('\n')
        if not s.strip() or s.lstrip().startswith('#'):
            continue
        if s.startswith('re:'):
            pats.append((s, re.compile(s[3:], re.I)))
        else:
            pats.append((s, None))
    files = []
    for r in a.root:
        if os.path.isfile(r):
            files.append(r)
            continue
        for dp, dn, fn in os.walk(r):
            dn[:] = [d for d in dn if d not in ('node_modules', '.git', '__pycache__')]
            files += [os.path.join(dp, f) for f in fn if os.path.splitext(f)[1] in a.ext]
    hits = 0
    for f in sorted(files):
        try:
            lines = open(f, encoding='utf8').read().split('\n')
        except UnicodeDecodeError:
            continue
        for i, L in enumerate(lines, 1):
            for raw, rx in pats:
                if (rx and rx.search(L)) or (not rx and raw in L):
                    hits += 1
                    print(f'{f}:{i}: [{raw}] {L.strip()[:160]}')
    print(f'{len(pats)} phrases, {len(files)} files, {hits} hits')
    sys.exit(1 if hits else 0)


if __name__ == '__main__':
    main()
