# FIXSPEC template

Copy to `critiques/<round>/FIXSPEC.md`. Each cross-language item is an exact instruction a fixer can apply without a judgment call. Give the English meaning and, where you have it, the first language's final wording as the model.

---

# Fix spec after the {{round}} critique round ({{date}})

Reports this spec is based on (read the one for your language, plus compliance.md): {{list of report files}} (all in this folder). Site root: {{path}} (edit files in place with the Edit tool; do NOT deploy; do NOT touch other languages' files; do NOT touch {{shared files: API, shared JS, catalog, hosting config}}).

## Owner decisions that are fixed (do not reverse them)
- {{e.g. No captions under article images and no ad strip at the top of articles.}}
- {{e.g. No pre-order wording anywhere. No phone number.}}
- {{e.g. The expert narrates; no new narrator. Keep the story structure, but rewrite the formulaic lines listed below.}}
- {{e.g. Keep the AI women in the photos; disclose AI in the footer line (item 7).}}

## Cross-language decisions to apply in EVERY language's pages
1. **Guarantee** (articles, product page, checkout, thank-you page, JS strings in the page, terms page): new promise = "{{exact English sentence}}". Write it naturally in the language. In the terms page, change the guarantee clause to match ({{conditions}}). Do NOT change the separate statutory 14-day withdrawal section.
2. **Seller name** on all non-legal pages (footers, checkout, thank-you): Latin script only: "{{Company, City, Country (reg. no.)}}" with local spelling of the city and country. In the terms page keep the registered name, Latin form first, original script in brackets.
3. **Delivery wording:** delete every "{{arrives in a few days}}" promise. Under the order button add: "{{Delivery: at the latest 30 days from order confirmation; after dispatch the courier delivers in 1-3 working days.}}" Use the same sentence in the delivery FAQ. Never mention {{printing / pre-order}}.
4. **Composite story** ({{persona names per language}}):
   - composite note: name AND place changed;
   - replace "{{she wrote everything down for me}}" with "{{I put the details together from my students' messages}}";
   - remove dates from message captions and quotes;
   - delete the word-of-mouth chain sentence;
   - fix the timeline: {{exact calendar}}; keep local details correct;
   - rewrite the lines that copy the competitor's formula ({{reader report}} lists them; the same lines exist translated in every language). Keep the meaning, change wording and rhythm.
5. **Remove blocks:** {{e.g. the "If you close this page now" column in every article; keep "If you order now".}}
6. **Claims:** {{e.g. a1: replace "often looks fresher after 2-3 weeks" with "after 2-3 weeks it is worth comparing your weekly photos for the first time".}}
7. **Footer AI line:** "{{The photos in this article are AI-generated illustrations.}}" (local language).
8. **Product page:** {{e.g. remove the expert's country; narrow the muscle claim to what the study measured; remove the unverified blinding claim; keep the study numbers.}}
9. **Thank-you upsell:** {{e.g. remove "only now" urgency.}}
10. **Your language's report:** apply the HIGH and MEDIUM language findings from YOUR reader report (wrong words, translated-sounding sentences, grammar, local terms) on {{pages}}. Skip anything that conflicts with the owner decisions above.
11. **Market-specific:** {{e.g. PL only: add the locker payment sentence; fix the invoice wording.}}

## Ads (one ads fixer, not the language fixers)
- {{Per concept: verdict, new copy per language or the rule to apply, new destination, image changes (base image, label text and size).}}
- Concepts that stay off: {{list}}. Do not edit or resubmit rejected ads.
- Rebuild images, check the contact sheets by eye, do not upload. The creative swap on PAUSED ads happens only after the owner's OK.

## Out of scope (do not guess; list in your change log)
- {{e.g. the real table of contents (needs the printed book); page count and format; price changes in the backend; who confirms orders and in which language.}}

## Decisions for the owner (not for fixers)
- {{Conflicts between a legal finding and an owner decision, with the reviewer's reasoning and the options.}}

## Done means
- Every change above applied in your language's files; `python3 scripts/check_old_phrases.py phrases-<lang>.txt --root <your folder>` returns nothing.
- HTML still valid (`scripts/html_sanity.py`), page scripts untouched except plain string literals.
- A short change log at {{critique folder}}/fixed-<lang>.md: canonical wording used, what changed file by file, checks run, anything skipped and why.
