# Anchor Research Agent

Рисърч на ъгли, фунии и реклами за бранд по продукт и ниша, по един и същ процес за всеки клиент.
Изграден от автоматизациите за halo. (`~/halo-patches/research`) и So Simple мехлемите (`~/so-simple-ointments-research`).

## Процес
| # | Етап | Състояние |
|---|---|---|
| 1 | Ключови думи по продукт × пазар (`queries.tsv`) | ръчно, предстои генериране от `run.json` |
| 2 | Сваляне на рекламите от Meta Ad Library (headless) | `so-simple-ointments-research/scripts/adlib.py`, `harvest.py`, предстои пренасяне |
| 3 | Обединяване по collation_id, визии | `consolidate.py`, `thumbs.py`, предстои пренасяне |
| 4 | **Сила на доказателствата по лендинг** | **готово: `agent/evidence.py`, `docs/evidence-scale.md`** |
| 5 | Ъгли и хукове (подагент, фиксирана схема) | предстои |
| 6 | Гласът на клиента (отзиви) | **готово: `agent/collect_reviews.py` (Judge.me, всички продукти + снимки) → `agent/review_bank.py` (+ Drive CSV/xlsx, без имейли/IP)** |
| 7 | Разбор на фуниите + оценка за пасване | `FUNNEL_AGENT_BRIEF.md`, `funnel_capture.py`, предстои |
| 8 | Артефакт за избор (Да / Може би / Не) | шаблон в `so-simple-ointments-research/acne_pick/`, предстои |
| 9 | Клон → реклами → хъб → Drive | режим „абсолютно клониране“: `docs/absolute-clone.md`, `agent/clone_mode.py` (бранд или дизайнът на примера), източници `agent/config/clients.json` |

## Бързо
```bash
python3 agent/evidence.py <ads_all.json> --product acne --traffic traffic.json --out landing_evidence.json
python3 -m unittest discover -s tests
```
