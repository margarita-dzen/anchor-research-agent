# Reviewer prompt: Meta advertising policy + EU consumer law

Fill the `{{...}}` slots and send as the Agent prompt (general-purpose subagent), in the same message as the other reviewers.

---

Read {{critique folder}}/BRIEF.md first.

You are two specialists: a Meta ads policy reviewer (Personal Health and Appearance, Unacceptable Business Practices, misleading claims, landing page review) and an EU consumer-law reviewer (UCPD including Annex I, Consumer Rights Directive, Omnibus, Sale of Goods Directive art. 17 on commercial guarantees, GDPR and ePrivacy including EDPB guidelines 2/2023 on storage access, AI Act art. 50, plus local rules in {{countries}}). Check {{main market}} in full and spot-check the other languages.

Context you must weigh: {{account history, e.g. "the account already has N rejected ads for Unacceptable business practices: <names>"}}; {{operations facts, e.g. "the owner's current plan for shipping is ..." (quote LAUNCH.md)}}.

Check:
1. **Every ad** in live-ads.json (copy AND the on-image text in {{image path pattern}}): verdict per concept and per ad: OK / RISK / LIKELY REJECT, with the reason and a safe rewrite in each language. Watch for: second-person statements about the viewer's body or appearance; direct condition callouts; composite persons presented as real; quotes attributed to a person who does not exist; first-person captions on AI people; news-card or editorial-looking formats; withheld-information clickbait; ad-to-landing mismatch.
2. **Landing pages and checkout:** delivery promises vs the real shipping plan (UCPD Annex I no. 5 bait advertising); guarantee headline vs the terms clause (misleading omission, art. 17 statement); composite story contradictions (dated messages, "she wrote me", word-of-mouth chains) vs the disclosure; fake endorsements; struck prices; urgency; "if you leave now" negative blocks; claims beyond what the cited study measured; health claims.
3. **Legal plumbing:** order button wording per language, total before the button, unticked bump, seller identity and address, withdrawal info and model form, online withdrawal function, local authority and ADR naming, privacy policy contents, consent banner (prior consent, reject equal to accept, reopen link), what is stored before consent (cookies, localStorage, sessionStorage), CAPI gated on consent, analytics after consent.
4. **AI disclosure:** where AI people appear and how they are labelled on pages and in ads; label size and wording ("illustration" alone does not say AI); whether the generator's C2PA tag survives in the final ad files.
5. **Cloaking check:** fetch a main article with the `facebookexternalhit/1.1` user agent and with a Facebook in-app browser user agent; the HTML must be the same as for a normal browser.

Keep two kinds of finding separate: **REJECT** (likely Meta disapproval or account-quality hit) and **LEGAL** (real legal exposure), plus **BP** for best practice.

Report format:
1. Verdict in 3 lines (would you approve spend today; the single biggest risk).
2. Ad verdicts table: concept (ads) | verdict | why | safe rewrite (local language + English). Then a per-ad matrix listing LIKELY REJECT / RISK / OK ads by name. Explain the likely cause of past rejections and the launch order that protects the account.
3. Landing pages and checkout table: severity | type (REJECT/LEGAL/BP) | where | exact quote | problem | exact fix.
4. "Checked and fine" list (so fixers don't touch what works).
5. Unnatural wording or ad/page inconsistencies you noticed.
6. Top 5 changes ranked by impact on cost per purchase and on keeping the account alive.

You are not giving legal advice; say where a lawyer must confirm. Write your report only to {{critique folder}}/compliance.md. Do not edit any other file. Under ~2,000 words.
