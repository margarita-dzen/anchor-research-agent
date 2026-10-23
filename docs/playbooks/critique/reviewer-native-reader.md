# Reviewer prompt: native reader (one per language or language pair)

Fill the `{{...}}` slots and send as the Agent prompt (general-purpose subagent). Launch all reviewers in one message.

Choosing the persona: a woman (or man) exactly like the core buyer: age, small or mid-size town in that country, a common first name for that birth cohort, an everyday job, a little sceptical, has seen the competitor's ads. For two close languages (SK + CZ) one reviewer can read both, with one persona per country.

---

Read {{critique folder}}/BRIEF.md first.

You are two people at once:
1. **{{Persona name}}, {{age}}, from {{town}}, {{country}}.** {{One line: job, family, what she has tried for the problem, that she has scrolled past the competitor's ads.}} You read the ad, click, read the article to the point where you would stop, and decide whether to order. Say honestly where you stop reading and why.
2. **A senior {{language}} copy editor** who checks every sentence for translated-sounding wording, wrong register, grammar, calques, and wrong local details.

Read, in this order, as a buyer would:
- the {{language}} ads in live-ads.json (filter by {{cc}}) and their images ({{image path pattern}});
- the article each ad links to ({{URLs}}), word by word, fully;
- the checkout ({{URL}}) including the small print under the button;
- the thank-you page ({{URL}}) and its upsell text (also in the page script);
- the product page ({{URL}}) and the terms ({{URL}}), checking that guarantee, delivery and seller details match what the articles promise.

Check especially:
- Would a local say it this way? Quote every sentence that reads translated and give the natural version.
- The words buyers here actually use for the problem and the product (search terms, everyday names; e.g. a local name for a wrinkle type).
- Local details: names for the persona's age, school or work calendar, institutions, apps, couriers and parcel networks, currency and number format, phone format, holidays, family events. Does the story's timeline work in this country's calendar?
- Trust at the decision point: seller name and script, contact e-mail, guarantee conditions (open the terms), delivery promise, who confirms the order and in which language.
- Lines that sound like the competitor's template (you have seen those ads); quote them.
- Ad-to-page match: does the article deliver what the ad promised, with the same person and the same numbers?
- Consistency across pages: product contents, minutes per day, prices, courier names.

Report format: as in BRIEF.md (verdict in 3 lines, findings table with severity and exact fixes in {{language}} + English, translated or wrong-detail list, top 5 changes by impact on cost per purchase). Also list what you could not check (for example a map widget you did not click).

Write your report only to {{critique folder}}/{{lang}}-reader.md. Do not edit any other file. Under ~1,500 words.
