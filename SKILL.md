---
name: anchor-research-agent
description: Use when researching competitor ads, angles, advertorials and funnels for a brand by product and niche (Meta Ad Library, landing pages, TrendTrack), when choosing which landing pages or funnels to clone, and whenever the user asks for an "absolute"/1:1 clone of a funnel. Triggers on "рисърч", "проучване на конкуренти", "ъгли", "фунии за клониране", "кои лендинги", "клонирай абсолютно", "1:1 клон".
---

# Anchor Research Agent

Процесът и състоянието на етапите са в `README.md`. Преди работа прочети нужния документ в `docs/`.

## Преди всичко
Прочети `docs/rules.md` (правилата на клиентите на едно място, вкл. кой kie ключ, страници за преглед, RO пазар).

## Избор на лендинги и фунии (ВИНАГИ)
Никога не избирай фунии само по трафик или само по дни на въртене. Пусни скалата за сила на доказателствата:
```bash
python3 ~/anchor-research-agent/agent/evidence.py <ads_all.json> [--product X] [--traffic traffic.json] --out landing_evidence.json
```
Правилата и теглата са в `docs/evidence-scale.md`. За разбор на фунии вземай само минали URL-и и ги подреждай по сила. След снимките добави оценка за пасване. Крайната оценка = 60% сила + 40% пасване. В артефакта за избор показвай двете отделно.

## Абсолютно клониране
При всяко „клонирай“ (с или без „абсолютно“ / „1:1“) следвай `docs/absolute-clone.md` стъпка по стъпка. Вече клонираните фунии са в `cloned` на `runs/<x>/run.json`. Първо снимай целия оригинал и направи списъка на секциите. Режимът на дизайна го решава `python3 ~/anchor-research-agent/agent/clone_mode.py funnels.json`: на основния домейн значи бранд бук на клиента, на външен хост значи дизайнът на примера. Материалите на клиента (сайт, отзиви, Drive библиотека, локални папки, Instagram, експерти) са в `agent/config/clients.json`. Отзивите и медийната лента пазят броя и формата на примера, но се пълнят с истински материали на клиента. Сравнявай едно до друго, преди да кажеш „готово“.

## Преглед и одобрение
Когато клонингът, рекламите и текстовете са готови, строи прегледа по `templates/review/README.md`: реклами като във фийда (образец shelly-ads-wave2) + страница за одобрение на всичко (образец shellyx-advertorials /review). Одобренията се пазят в db на артефакта. Shelly файловете са само за структурата, не се публикуват.

## Дизайн скилове
Клон = без редизайн; адаптация към бранда = дизайн скилове; проверка = audit скилове; оферта = CRO. Подробно: `docs/design-skills.md`.

## Текстове
`copy-masters` (отделен скил): Schwartz решава какво казва текстът, водещият автор е по задача, авторът отива в `utm_content`.

## Единно пускане, правила, учене
- `python3 agent/run.py runs/<x>/run.json [next|done <етап>]`: етапите и 2-те контролни точки. Етапите за Claude: `docs/stages.md`.
- Всички правила на клиентите на едно място: `docs/rules.md`. Прочети преди клон, копи и реклами.
- Преди да покажеш нещо за преглед: проверките от `docs/learned-checks.md` (научени от прегледите) и `agent/qa/run_qa.py` (праг). Под прага не се показва.
- След всеки преглед: `agent/feedback.py ingest` (отказите стават данни). Всяка седмица: `agent/weekly.py`.
- След промяна в evidence.py / fit.py: `python3 agent/golden.py goldens/*.json`. Ако еталонът падне, промяната е лоша.
