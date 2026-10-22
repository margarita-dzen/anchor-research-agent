---
name: anchor-research-agent
description: Use when researching competitor ads, angles, advertorials and funnels for a brand by product and niche (Meta Ad Library, landing pages, TrendTrack), when choosing which landing pages or funnels to clone, and whenever the user asks for an "absolute"/1:1 clone of a funnel. Triggers on "рисърч", "проучване на конкуренти", "ъгли", "фунии за клониране", "кои лендинги", "клонирай абсолютно", "1:1 клон".
---

# Anchor Research Agent

Процесът и състоянието на етапите са в `README.md`. Преди работа прочети нужния документ в `docs/`.

## Избор на лендинги и фунии (ВИНАГИ)
Никога не избирай фунии само по трафик или само по дни на въртене. Пусни скалата за сила на доказателствата:
```bash
python3 ~/anchor-research-agent/agent/evidence.py <ads_all.json> [--product X] [--traffic traffic.json] --out landing_evidence.json
```
Правилата и теглата са в `docs/evidence-scale.md`. За разбор на фунии вземай само минали URL-и и ги подреждай по сила. След снимките добави оценка за пасване. Крайната оценка = 60% сила + 40% пасване. В артефакта за избор показвай двете отделно.

## Абсолютно клониране
При „клонирай абсолютно точно“ / „1:1“ следвай `docs/absolute-clone.md` стъпка по стъпка. Първо снимай целия оригинал и направи списъка на секциите. Сравнявай едно до друго, преди да кажеш „готово“.
