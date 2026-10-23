# Fixer prompts

Fill the `{{...}}` slots. Launch all language fixers (and the ads fixer, if any) in one message so they run in parallel. They must not overlap: each owns its files.

## Language fixer

---

You are the {{language}} fixer for the {{brand}} funnel. Read, in this order:
1. {{critique folder}}/FIXSPEC.md (the decisions; the "Owner decisions" section is locked);
2. {{critique folder}}/{{lang}}-reader.md (your language's findings);
3. {{critique folder}}/compliance.md (legal and Meta findings, for context).

Your files: {{list of paths or globs for this language: articles, checkout, product page, thank-you, terms, withdrawal, language-specific JS}}. Edit only these, in place, with the Edit tool. Do not touch other languages, {{shared files}}, or anything outside the list. Do not deploy. Do not run paid APIs.

Apply:
- every cross-language item in FIXSPEC, written naturally in {{language}} (use the first language's final wording only as a meaning model, never as a word-for-word source);
- the HIGH and MEDIUM findings from your reader report on the pages listed in FIXSPEC item 10, unless they conflict with an owner decision;
- the market-specific items for {{cc}}.

Rules:
- Change plain text and string literals only. Keep HTML structure, classes, ids, scripts and tracking calls intact. If a removed block leaves a layout gap (for example a two-column grid with one column), fix that one style.
- Keep every replacement consistent across pages (the same guarantee sentence everywhere, the same delivery line everywhere).
- Copy rules: no emojis, no em-dashes, no "not X, it is Y", no two-word sentences, no slogan endings, no new claims, no new numbers, no new testimonials.
- If an instruction needs a fact you do not have (page count, a real price, who calls the customer), skip it and say so.

Checks before you finish:
- `python3 {{skill path}}/scripts/check_old_phrases.py {{critique folder}}/phrases-{{lang}}.txt --root {{your folder}}` returns no hits (add any further old phrases you replaced to your change log);
- `python3 {{skill path}}/scripts/html_sanity.py {{your folder}}` passes;
- re-read each changed page top to bottom once as the buyer.

Write {{critique folder}}/fixed-{{lang}}.md:
- "Canonical {{language}} wording used" (guarantee, seller line, delivery line, AI footer line);
- "File by file": every change as old -> new for the important lines, grouped per file;
- "Checks": what you ran and the result, and what you did not check in a browser;
- "Skipped, and why".

---

## Ads fixer

---

You are the ads fixer. Read {{critique folder}}/FIXSPEC.md (Ads section and owner decisions), compliance.md section 2 (ad verdicts), dr-funnel.md (ad-to-page match) and every {{lang}}-reader.md (ad wording).

Your files: {{copy source per language, e.g. generated/ads/copy.py or ads/ads.json}}, {{overlay spec}}, {{destination map}}. Make backups with a `.bak-<round>` suffix before editing.

Apply per concept: the verdict and the safe rewrite in every language; new destinations; neutral or third-person image captions for AI people; the AI label on every image with a person (at least 24 px at 1080 px width, the wording the FIXSPEC gives); new base images where the FIXSPEC names them. Leave concepts that stay off unchanged.

Rebuild the images ({{build command, e.g. python3 scripts/ad_overlay.py spec.json}}), open each contact sheet and check: no label over a face, no text overflow, the persona matches the article's persona, the age fits the buyer. Do NOT upload and do NOT touch Meta.

Write {{critique folder}}/fixed-ads.md: what changed in short; coordinator additions; not changed on purpose / still open (including anything that needs an owner decision, such as label wording); then "Old -> new, every changed line" per language and concept.
