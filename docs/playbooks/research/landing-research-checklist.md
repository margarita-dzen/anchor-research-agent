# Landing-page research checklist

Goal: learn how the longest-running competitors turn ad clicks into orders, find the gaps on our own pages, and end with a page blueprint. Save the result as `<project>-landing.md`.

## 1. Pick the pages

- Start from `landing-targets.json` (made by `digest.py ads`). It ranks landing URLs by how long their ads have run and how many new ads point at them.
- Take the top 10 to 15 that sell something comparable to our product. Skip clinics and services when we sell a product, pet products when we sell for people, and anything that lands on Facebook / Instagram / WhatsApp.
- Add our own current ad destinations (the page each live ad sends to), so the gaps are concrete.
- Note for each page the ad that sends traffic to it: days running and ad id. That is the proof the page converts well enough to keep paying for.

## 2. Capture

1. Run `python3 scripts/fetch_pages.py --targets landing-targets.json --top 15 --skip "clinic|pet"`. It saves `pages/<name>.txt` with headings, buttons, prices, form fields, signal flags and full text.
2. Any page marked **LOW TEXT** is built in JavaScript. Open it in a browser (Playwright MCP) instead:
   - Mobile viewport (390 x 844), iPhone user agent.
   - **Block `facebook.net`, `connect.facebook.net` and `facebook.com/tr`** before loading, so we never fire a competitor's pixel or pollute our own.
   - Scroll to the bottom slowly so lazy sections load, then take a text snapshot. One full-page screenshot only if the visual style matters.
3. Follow the funnel one step further where it is free: product page to cart, advertorial to the page its button opens, quiz to its first result. **Never place an order, never submit a form with real data, never start a checkout payment.**
4. If the page shows a different offer per country, capture each market version you care about.

## 3. What to note per page

| Item | What to write down |
|---|---|
| Page type | Advertorial (article), product page (PDP), listicle, quiz, webinar sign-up, lead form, collection grid |
| Ad days | Days the ad pointing here has run, plus ad id |
| Above the fold | Headline verbatim + Gloss; what is visible before scrolling |
| Section order | The full order of blocks top to bottom (problem, story, mechanism, product, proof, offer, FAQ, guarantee) |
| Offer | Price, compare-at price, bundles (1 / 2 / 3), which option is preselected, gifts, free shipping threshold |
| Guarantee | Money back, days, conditions ("no return needed"), where on the page it sits |
| Payment | Cash on delivery offered? Default? Card / BLIK / PayPal / Klarna? Fee for COD? |
| Delivery | Promised time, courier names, office pickup, free shipping rule |
| Proof | Review count and source (Trustpilot, Judge.me), named experts, customer count, press, study citations (note if invented or unverifiable) |
| Urgency | Countdown, stock counter, "last copies", and whether it looks honest |
| Checkout | Steps, fields, order bumps, upsells shown, thank-you page offer if visible without ordering |
| Platform | Shopify, WooCommerce, funnel builder (fetch_pages.py detects most) |
| Distinctive move | The one thing this page does that others do not |
| Red flags | Fake reviews, invented doctors, fake countdowns, medical claims. Note them so we never copy them |

## 4. Patterns

After all pages, write the patterns that repeat across the long runners, each with the pages it comes from. Typical ones:
1. Problem in the headline, not the spec sheet.
2. A big real review number above the fold.
3. A multi-pack preselected, framed for the buyer's life.
4. Risk reversal in one line next to the button.
5. Named expert proof (name, role, city) beats "recommended by doctors".
6. Comparison block: the usual fix vs ours.
7. Reviews that repeat the angle in the customer's words.
8. FAQ that answers real doubts honestly.
9. Delivery speed and cash on delivery visible near the button (in COD markets).
10. Urgency is common but the longest runners use little of it.

## 5. Gaps on our pages

Table: | # | Gap | Where (URL) | What the winners do | Fix |
Be specific: quote the wrong line, name the section, give the fix. Include broken things (wrong FAQ answers, contradicting specs, broken review counters, sold-out items on ad destinations) and claims that break the copy rules.

Also list what our pages already do well and must keep.

## 6. Blueprint

One or two page blueprints (for example "problem advertorial" and "problem-first product page"):
- Block order, top to bottom, with what each block says.
- Offer box: bundles, preselected option, guarantee line, payment and delivery line.
- Proof plan: which real reviews, expert, or demo we have or must collect. Mark missing items as [to be sourced].
- Design notes: brand look, readable font sizes on mobile, no text over images, CTAs as text links in advertorials.

## 7. Open items before building

Facts to confirm with the owner: real review count, guarantee policy, delivery times, COD availability per market, product specs, which testimonials have consent.

## Rules

- Competitor numbers and claims are theirs. Quote them as "they claim".
- Never copy their reviews, doctors, studies, photos or before/after images.
- Our copy follows the pack's copy rules: no fake reviews, no invented studies or numbers, no medical claims, no body-shaming hooks, honest urgency only.
