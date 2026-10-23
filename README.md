# Anchor Research Agent

Рисърч на ъгли, фунии и реклами за бранд по продукт и ниша, клониране на избраните фунии и реклами към тях, по един и същ процес за всеки клиент.
Изграден от автоматизациите за halo. (`~/halo-patches/research`) и So Simple мехлемите (`~/so-simple-ointments-research`). Скилът е `SKILL.md`. Текстовете минават през отделния скил `skills/copy-masters`.

## Пускане
```bash
python3 agent/run.py runs/<име>/run.json            # етапите и състоянието
python3 agent/run.py runs/<име>/run.json next       # следващият етап (автоматичен или инструкция за Claude)
python3 agent/run.py runs/<име>/run.json done <етап>
```
`run.json` на продукта (пример: `runs/so_simple_acne/run.json`) + конфигурация за свалянето (`harvest_config`, пример: `runs/example/run.json`).

## Етапи
| # | Етап | Как | Код / документ |
|---|---|---|---|
| 1 | Сваляне на рекламите | авто | `agent/adlib/harvest.py` (заявки + `--top-pages`), `docs/adlib.md` |
| 2 | Обединяване, визии, EU обхват, крайни URL-и | авто | `agent/adlib/consolidate.py`, `thumbs.py`, `eu_reach.py`, `resolve_urls.py` |
| 3 | Сила на доказателствата | авто | `agent/evidence.py`, `docs/evidence-scale.md` |
| 4 | Чистене от теми извън продукта | авто | `agent/fit.py relevance` |
| 5 | Банка с истински отзиви | авто | `agent/collect_reviews.py` (Judge.me / WooCommerce), `agent/review_bank.py` |
| 6 | Ъгли и хукове | Claude | `docs/stages.md#ъгли`, creative-strategy, copy-masters/schwartz |
| 7 | Разбор на фуниите | Claude | `docs/stages.md#фунии`, `agent/qa/capture.py`, `agent/clone_mode.py` |
| 8 | Пасване + крайна оценка (60/40) + местни конкуренти | авто | `agent/fit.py funnels` |
| 9 | **Контролна точка 1:** избор | Валентин | артефакт Да / Може би / Не (`docs/stages.md#избор`) |
| 10 | Клониране | Claude | `docs/absolute-clone.md` (чеклист §8), `docs/design-skills.md`, `docs/rules.md`; числата и твърденията: `agent/review_stats.py`, `agent/claims.py rank/stock` |
| 11 | Текстове | Claude | `skills/copy-masters` (авторът в `utm_content`) |
| 12 | Реклами | Claude | anchor-creative-playbook, `agent/credits.py start/end` |
| 13 | QA с праг | авто + Claude | `agent/qa/run_qa.py` (сходство, копи, отзиви, снимки през `check_media.py`); `done qa` не минава под прага без записана причина |
| 14 | **Контролна точка 2:** преглед | Валентин | `templates/review/README.md` (Shelly шаблоните) |
| 15 | Резултати и учене | авто, седмично | `agent/weekly.py` → `results.py`, `snapshot_diff.py`, `calibrate.py`, `feedback.py` |

## Качество
- Еталон: `python3 agent/golden.py goldens/*.json` след всяка промяна в оценките.
- Тестове: `python3 -m unittest discover -s tests`.
- Научени проверки от прегледите: `docs/learned-checks.md` (`agent/feedback.py`).
- Кредити: `python3 agent/credits.py balance | need <N> | report runs/<име>`.
