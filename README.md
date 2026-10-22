# Anchor Research Agent

Рисърч на ъгли, фунии и реклами за бранд по продукт и ниша, по един и същ процес за всеки клиент.
Изграден от автоматизациите за halo. (`~/halo-patches/research`) и So Simple мехлемите (`~/so-simple-ointments-research`).

## Процес
| # | Етап | Състояние |
|---|---|---|
| 1 | Ключови думи по продукт × пазар, теми, белези, правила за продукт | **готово: `runs/<име>/run.json` (пример: `runs/example/run.json` = So Simple), `agent/adlib/runconfig.py`**; самите думи още се пишат ръчно |
| 2 | Сваляне на рекламите от Meta Ad Library (headless) | **готово: `agent/adlib/harvest.py` + `scrape.py` (заявки или `--top-pages`/`--pages` = всички реклами на рекламодателя), `eu_reach.py` (EU обхват за топ кандидатите), `docs/adlib.md`** |
| 3 | Обединяване по collation_id, визии, крайни URL-и, снимки във времето | **готово: `agent/adlib/consolidate.py`, `thumbs.py`, `resolve_urls.py` (→ `evidence.py --resolved`), `snapshot_diff.py`** |
| 4 | **Сила на доказателствата по лендинг** | **готово: `agent/evidence.py`, `docs/evidence-scale.md`** |
| 5 | Ъгли и хукове (подагент, фиксирана схема) | предстои |
| 6 | Гласът на клиента (отзиви) | **готово: `agent/collect_reviews.py` (Judge.me, всички продукти + снимки) → `agent/review_bank.py` (+ Drive CSV/xlsx, без имейли/IP)** |
| 7 | Разбор на фуниите + оценка за пасване | `FUNNEL_AGENT_BRIEF.md`, `funnel_capture.py`, предстои |
| 8 | Артефакт за избор (Да / Може би / Не) | шаблон в `so-simple-ointments-research/acne_pick/`, предстои |
| 9 | Клон → реклами → хъб → Drive | режим „абсолютно клониране“: `docs/absolute-clone.md`, `agent/clone_mode.py` (бранд или дизайнът на примера), източници `agent/config/clients.json` |

## Бързо
```bash
python3 agent/adlib/harvest.py runs/example/run.json --limit 1 --scrolls 2   # проба; целият поток: docs/adlib.md
python3 agent/adlib/consolidate.py runs/example/run.json
python3 agent/evidence.py <ads_all.json> --product acne --traffic traffic.json --out landing_evidence.json
python3 -m unittest discover -s tests
```
