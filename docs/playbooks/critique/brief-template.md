# Critique round brief template

Copy to `critiques/<round>/BRIEF.md`, replace every `{{...}}`, delete what does not apply. Keep it under about 60 lines: every reviewer reads it first.

---

# {{Round name}} critique round, {{Brand}} {{markets}} funnel ({{date}})

You are reviewing a LIVE paid-traffic funnel before real ad spend starts. Be a demanding, specific critic. Read every word as the real reader would. Quote exact text. Propose exact replacement text (in the page's language, with an English gloss). Rank findings: BLOCKER (fix before spending), HIGH, MEDIUM, LOW. Do not edit any files; write your report only to the path you are given.

## What is being sold
{{Product in one paragraph: what it is, format, the optional upgrade, payment method (e.g. cash on delivery only).}} Audience: {{who, age, countries}}. Narrator: {{expert name}} ({{documented facts only; "nothing else is known about her, do not invent facts"}}).
Benchmark: {{the competitor funnel, its shape (ad -> advertorial -> checkout), its best market and why it matters}}.

## Hard rules for any suggestion
- Only research that may be cited: {{citation with numbers}}. No other studies, no invented statistics.
- No before/after photos, no fake reviews or testimonials presented as real, no fake media logos, no "look X years younger" promises, no medical claims.
- {{Composite story rule: "The <persona> story is stated on the page to be a composite of several clients with the name changed."}}
- {{AI images rule: "The women in photos are AI-generated; the footer says so."}}
- Do not suggest a fake narrator, fake expert, or fake delivery promise.
- Owner decisions (do not argue against them; flag a legal problem if one exists): {{e.g. no phone number; no pre-order wording; no captions under images}}.

## Live URLs (fetch them; strip HTML to read; images are at the src paths)
Main articles the ads point to: {{list per language}}
Checkout / product page / thank-you / terms per language: {{list}}
Other pages that get no ad traffic: {{list, or "none"}}

## The ads (exact live copy)
{{path}}/live-ads.json: fields {{cc, name, primary, headline, desc, link, status}}. {{Which concepts stay off and why.}}
Ad images: {{path pattern}}. Look at them with the Read tool; the on-image text is part of the ad.

## Reference material
- Competitor advertorial, checkout, product page (text captures): {{paths}}
- Voice of customer: {{path}}; landing teardown: {{path}}; ads analysis: {{path}}
- Benchmark playbook (if any): {{path}}

## Report format (markdown)
1. Verdict in 3 lines: would you (as this reader / expert) buy / approve, and the single biggest reason why not.
2. Findings table: severity | where (URL + section or ad name) | exact quote | problem | exact fix (local language + English).
3. Anything that reads as machine-translated, unnatural, wrong register, wrong local detail (school system, currency, courier, names, holidays), or inconsistent between ad and page.
4. Top 5 changes ranked by expected impact on cost per purchase.
Keep it under ~1,500 words. Quote, don't paraphrase.
