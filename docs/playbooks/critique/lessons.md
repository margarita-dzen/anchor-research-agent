# Lessons from the first critique round (5 languages, COD book funnel)

Six reviewers (four native readers covering five languages, one direct-response, one compliance) found these. Use the list as a pre-check before the next round, and give it to reviewers as "known failure modes" only after they have written their first pass (so they still look with fresh eyes).

## What each reviewer type catches best

| Reviewer | Typical catches |
|---|---|
| Native reader (as the buyer) | Calques and translated sentences (about 15 per long article even after careful translation); wrong everyday terms; impossible calendar in the story; trust killers at the decision point (foreign-script seller name, numbered webmail address, a guarantee whose terms require a cross-border return); lines recognised from the competitor's ads; where she stops reading |
| Direct-response | Checkout friction (7 required inputs vs the competitor's 4 on the default path); offer box with nothing to weigh (no visible contents, no inside photo); ads routed to the wrong article; persona age in images below the buyer's age; the bump not making shipping free; three different "what's inside" lists across pages |
| Compliance | Bait advertising (taking orders with no shipping plan); guarantee vs terms omission; second-person appearance hooks (likely rejects); composite persons presented as real in ads; AI people unlabelled; UTMs in localStorage before consent; claims beyond the study; "only now" urgency; the cause of past rejections (news-card format) and a launch order that protects the account |

## Findings that recurred in every language

- Guarantee headline promised a full refund; the terms required a return at the buyer's cost to another country. Fixed with a no-return refund, terms updated to match.
- Seller name in a foreign script and a double legal form; fixed with one Latin-script name on all non-legal pages.
- "The parcel arrives in a few days" while the plan was not to ship yet; replaced with the statutory "at the latest 30 days" line and flagged to the owner.
- Composite story contradicted its own disclosure: dated messages, "she wrote me everything", a chain of colleagues who asked; all removed, disclosure now says name AND place changed.
- The story's 21 days could not fit the school calendar of a teacher; the timeline was rebuilt so the plan ends before the result photo.
- Sentences that mirrored the competitor's advertorial formula, in the same order; rewritten in our own rhythm.
- An "If you close this page now" column that told the reader she will keep looking bad; removed (Meta negative self-perception on the landing page).
- A timing claim ("often looks fresher after 2-3 weeks") with no evidence; replaced with a process line.
- The product page said the expert teaches in one country while the persona story used another country's details; resolved by the "place changed" disclosure and by removing the country from the expert line.
- "Only now" on the thank-you upsell; removed.

## Ad findings

- Second-person "you look tired" ads (2 concepts x 5 languages) rated LIKELY REJECT; rewritten neutral.
- A persona quote in an ad ("This is what <persona> wrote to me") for a person who does not exist; rewritten as "the question I get most often from students over 50".
- An ad promising the persona's morning routine with a tool pointed to the persona story, where she does something else; re-pointed to the routine article, persona name removed.
- A woman of about 35 in an ad for a 45 to 65 audience; new base image of a woman about 52.
- Three different women labelled with the same persona name across ads; use the article's identity reference for every persona ad.
- Article-card ads ("news" look) were rejected even without any appearance angle: the format is the trigger. Keep them off, never resubmit.
- One ad was rejected after a creative update; keep it off rather than fighting it.
- Label text "Illustration" at 22 px: compliance wanted "AI-generated illustration" at 24 px or larger. Record the owner's decision explicitly.

## Process lessons

- Put owner decisions at the top of the FIXSPEC. Reviewers will propose things the owner already rejected (an ad strip, captions, a domain e-mail); fixers must not apply them.
- Point each fixer at its own reader report for language items; the FIXSPEC holds only the cross-language decisions.
- Shared files (API, shared JS, catalog) belong to no language fixer. Assign each shared change to one named agent or do it yourself.
- Fixers must log what they skipped and why: missing facts (real table of contents, page count), price changes in the backend, decisions that conflict.
- Grep for the old phrases afterwards; a fix that landed on one page and not on the next is the most common miss.
- Every fixer checks HTML balance and inline script syntax; hand edits break pages silently.
- Re-run the full QA (pages, pixel stub, ad links) after fixes, before any deploy.
- What reviewers could not check (a map widget, the upsell flow in a real browser) must be listed and checked by hand.
