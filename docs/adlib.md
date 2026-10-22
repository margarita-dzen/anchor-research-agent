# Събиране на реклами от Meta Ad Library (етапи 1-3, 22.10.2026)

Код: `agent/adlib/`. Всичко клиентско (заявки, теми, белези, правила за продукт, папка, дата) е в `runs/<име>/run.json`, ключовете са описани в `agent/adlib/runconfig.py`. Пример: `runs/example/run.json` = настройката на So Simple мехлемите (72 заявки, теми atopi/acne/herbal, белези mom/herbal).
Тестове: `python3 -m unittest discover -s tests` (`tests/test_adlib.py`, данни в `tests/fixtures/adlib/`).

## Поток
```bash
R=runs/<име>/run.json
python3 agent/adlib/harvest.py $R                      # заявките, по 2 паралелно, raw/*.json
python3 agent/adlib/consolidate.py $R                  # ads_all.json (по collation група)
python3 agent/adlib/thumbs.py $R                       # визиите ВЕДНАГА: fbcdn линковете изтичат
python3 agent/adlib/harvest.py $R --top-pages 5        # всички реклами на топ рекламодателите
python3 agent/adlib/consolidate.py $R                  # отново, с рекламите от страниците
python3 agent/adlib/eu_reach.py $R --top 100           # EU обхват за най-силните кандидати
python3 agent/adlib/resolve_urls.py runs/<име>/ads_all.json
python3 agent/evidence.py runs/<име>/ads_all.json --resolved runs/<име>/resolved.json --out landing_evidence.json
```
Проба с една заявка: `harvest.py $R --cat acne --country DE --limit 1 --scrolls 2`.
В git влиза само `run.json`; суровите файлове, визиите, кешовете и `ads_all.json` са в `.gitignore`.

## Капани на скрепъра
- Максимум 2 паралелни сваляния. При 4 FB пренасочва („page is navigating“) и връща 0 реклами. `runconfig.py` не пуска повече от 2, каквото и да пише в run.json.
- `content()` се повтаря до 10 пъти, докато страницата спре да се пренасочва.
- Файл с 0 реклами = пренасочване, не празен резултат: `harvest.py` го трие и пуска заявката отново (`scrape.retries` кръга, 20 с пауза).
- U+FFFD в текстовете чупи публикуването на artifact: `consolidate.py` го маха от заглавие, текст и бранд.
- Каталожните (DPA) реклами имат `{{product...}}` в тялото: текстът се взима от първата карта.
- Без API ключ: Ad Library API (`ads_archive`) не работи с нашите токени (грешка #10, 2332002). Всичко е headless Chromium, никога видим прозорец.

## run.json накратко
| Ключ | Какво |
|---|---|
| `queries` | `[{cat, country, q}]`: ключови думи по категория × пазар (замества `queries.tsv`) |
| `categories` | `{име: regex}` за темата на текста → поле `rel_<име>` |
| `flags` | `{име: regex}` за допълнителни белези → поле `<име>` (true/false) + списък `flags` |
| `exclude` | regex върху линк + страница (temu, amazon...) |
| `products` | правила, първото съвпадение печели: `cats` (поне една категория на заявката), `require` (всички теми), `exclude` (нито една тема) |
| `unmatched` | `drop` или име на продукт за останалите |
| `scrape_date` | дата на свалянето; `null` = от `raw/_meta.json` (пише го harvest), после днес |
| `pages` | пълно сваляне по страница: `country` (ALL), `scrolls`, `ids`, `products` за `--top-pages` |
| `thumbs`, `eu_reach` | колко визии / колко кандидата за EU обхват по продукт |

Рекламите от пълното сваляне по страница имат `cats: ["page"]` (плюс категориите на заявките, ако са хванати и там), затова в `products` трябват правила с `"cats": ["page"]` и тема, иначе отпадат.

## Пълно сваляне по страница
`harvest.py --pages <id,id>` или `--top-pages N` отваря `?view_all_page_id=<id>&search_type=page&country=ALL` (подредено по импресии) и сваля всички активни реклами на рекламодателя, не само тези с ключовата дума. Топ рекламодатели = брой активни реклами + дубликати на активните в `ads_all.json` (филтър `--product`). Файлове: `raw/page__<CC>__<page_id>.json`.
Проверено 22.10: Cloudless EU (page 528523063677895) → 40 реклами при 2 скрола, 32 записа след обединяване, 29 от тях търсенето „Akne Creme“ DE не е хванало.

## EU обхват (`eu_reach`)
**Работи.** Търсенето не го дава: във всичките 4 715 сурови реклами на So Simple (`~/so-simple-ointments-research/raw`) `reach_estimate`, `spend` и `targeted_or_reached_countries` са празни. Обхватът (DSA прозрачност) идва само от заявката `AdLibraryV3AdDetailsQuery`, която страницата пуска при „See ad details“: `transparency_by_location.eu_transparency` с `eu_total_reach`, `age_country_gender_reach_breakdown`, `location_audience`, `gender_audience`, `age_audience`. Работи без вход в акаунт.

Как го тегли `eu_reach.py`: една headless сесия отваря `?id=<реклама>`, натиска „See ad details“ и хваща истинската заявка (doc_id, lsd и другите токени се сменят, затова не са в кода). После праща същата заявка с `fetch` от страницата за всеки кандидат, като сменя само `adArchiveID` и `pageID`. ~0,6 с на реклама (5 реклами за 3,2 с при пробата), затова само за топ кандидатите (по дни + 15 × дубликати, активни). Кеш: `eu_reach_cache.json`; `consolidate.py` връща стойностите при всяко ново обединяване.

Полета в `ads_all.json`:
- `eu_reach`: уникални хора в ЕС за целия живот на рекламата (на представителя на collation групата, `meta_ad_id`). `null` = рекламата не е пускана в ЕС (САЩ, Великобритания).
- `eu_reach_countries`: държавите от разбивката, подредени по обхват. Пълната разбивка по държава е в кеша (`reach_by_country`).

Ограничения: обхватът е само за ЕС (Великобритания и САЩ нямат число); той е на една реклама, не на цялата група дубликати; при 5 поредни грешки скриптът спира (вероятно лимит от FB), кешът пази изтегленото. Още не влиза в скалата за сила: първо да се натрупа върху няколко клиента.
Проба 22.10, „Akne Creme“ DE: DERMASENCE 696 569 · Skinpicking.akne 201 997 · Bedrop 198 804 (DE, AT, IT, ES) · Cloudless tried-6-products 191 308.

## Крайни URL-и (`resolve_urls.py`)
Следва пренасочванията (HEAD, при грешка или 4xx GET, плюс `<meta refresh>`), разопакова `l.facebook.com/l.php?u=`, маха `utm_*`, `fbclid`, `gclid`, `shpxid` и др., `www.`, фрагмента и крайната `/`. Кеш `url_cache.json` (30 дни). `resolved.json` = `{landing_url: краен URL}` за `evidence.py --resolved`. Недостъпен адрес остава като оригинала без проследяване.
Проба 22.10: 34 URL-а → 31 крайни; английският линк на Bedrop пренасочва към немския продукт и двата се сливат, страницата минава прага (8 → 9 минали URL-а).

## Сравнение на снимки (`snapshot_diff.py`)
Две `ads_all.json` от едни и същи заявки в различни дни → по лендинг: `launched` (нови, пуснати след старата дата), `seen_late` (нови в снимката, но пуснати преди нея), `stopped` (активни → неактивни), `missing` (активни → липсват; по-слаб сигнал, може да е извън обхвата на свалянето), `running`, `net`. Изходът `snapshot-diff-v1` е за бъдещ сигнал в скалата „още пуска нови реклами“. Сравнявай само снимки със същите заявки и скролове, иначе `missing` е шум.
