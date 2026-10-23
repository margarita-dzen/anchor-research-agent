#!/usr/bin/env python3
"""Quick sanity check of HTML files after hand edits. Read-only, standard library (+ Node if installed).

Per file:
  - tag balance: reports closing tags without an opener and non-void tags left open at the end
  - inline <script> blocks (no src, JavaScript type): syntax check with `node --check` when Node is on PATH
  - leftover placeholders: [Bracketed text starting with a capital], {{slots}}, TODO
Usage: python3 html_sanity.py site/hu [more folders or files] [--no-placeholders]
Exit code 1 if any file has a problem.
"""
import argparse
import html.parser
import os
import re
import shutil
import subprocess
import sys
import tempfile

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
OPTIONAL_CLOSE = {'p', 'li', 'dt', 'dd', 'tr', 'td', 'th', 'thead', 'tbody', 'tfoot', 'option', 'colgroup', 'html', 'head', 'body'}


class Check(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.scripts = [], [], []
        self._in_script, self._script_ok, self._buf = False, False, []

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        self.stack.append((tag, self.getpos()[0]))
        if tag == 'script':
            d = dict(attrs)
            t = (d.get('type') or 'text/javascript').lower()
            self._in_script = True
            self._script_ok = 'src' not in d and ('javascript' in t or t == 'module')
            self._buf = []

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag == 'script' and self._in_script:
            if self._script_ok:
                self.scripts.append((self.getpos()[0], ''.join(self._buf)))
            self._in_script = False
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for t, ln in self.stack[i + 1:]:
                    if t not in OPTIONAL_CLOSE:
                        self.errors.append(f'line {ln}: <{t}> not closed before </{tag}> (line {self.getpos()[0]})')
                del self.stack[i:]
                return
        self.errors.append(f'line {self.getpos()[0]}: </{tag}> without an opening tag')

    def handle_data(self, data):
        if self._in_script:
            self._buf.append(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--no-placeholders', action='store_true', help='skip the placeholder check')
    a = ap.parse_args()
    node = shutil.which('node')
    files = []
    for p in a.paths:
        if os.path.isfile(p):
            files.append(p)
        else:
            for dp, dn, fn in os.walk(p):
                dn[:] = [d for d in dn if d not in ('node_modules', '.git')]
                files += [os.path.join(dp, f) for f in fn if f.endswith('.html')]
    bad = 0
    for f in sorted(files):
        src = open(f, encoding='utf8').read()
        c = Check()
        c.feed(src)
        c.close()
        errs = list(c.errors)
        errs += [f'line {ln}: <{t}> never closed' for t, ln in c.stack if t not in OPTIONAL_CLOSE]
        if node:
            for ln, code in c.scripts:
                with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as t:
                    t.write(code)
                r = subprocess.run([node, '--check', t.name], capture_output=True, text=True)
                os.unlink(t.name)
                if r.returncode:
                    msg = [x for x in r.stderr.splitlines() if 'SyntaxError' in x]
                    errs.append(f'inline script ending line {ln}: {msg[0] if msg else r.stderr.strip()[:200]}')
        if not a.no_placeholders:
            # outside <script>/<style>: [Bracketed text starting with a capital], {{slots}}, TODO
            text = re.sub(r'<(script|style)\b.*?</\1>', lambda m: '\n' * m.group(0).count('\n'), src, flags=re.S | re.I)
            found = [(text.count('\n', 0, m.start()) + 1, m.group(0))
                     for m in re.finditer(r'\[[A-Z][^\]\n="\'<>]{2,80}\]|\{\{[^}]+\}\}|\bTODO\b', text)]
            # inside scripts: only string literals that are a whole placeholder, e.g. '[SKU]'
            found += [(src.count('\n', 0, m.start()) + 1, m.group(0))
                      for m in re.finditer(r'(?<=[\'"])\[[A-Z][^\]\'"\n]{1,80}\](?=[\'"])', src)]
            for ln, g in sorted(found):
                errs.append(f'line {ln}: placeholder {g[:60]}')
        if errs:
            bad += 1
            print(f'PROBLEM {f}')
            for e in errs[:12]:
                print('   ', e)
    print(f'{len(files)} files, {bad} with problems' + ('' if node else ' (Node not found: inline scripts not syntax-checked)'))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
