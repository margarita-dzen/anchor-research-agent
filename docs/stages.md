# Етапите, които прави Claude

`agent/run.py` пуска автоматичните етапи и спира тук. След всеки етап: `python3 agent/run.py runs/<x>/run.json done <етап>`.

## доказателства от TrendTrack
По желание, между `consolidate` и `evidence` (`run.py` не спира на него). Ползва се, когато Ad Library дава малко за продукта или искаме доказателство от големи пазари (DE, FR, NL, Nordics) с реклами над 60 дни. Скриптовете са от competitor-ad-research на Вальо (`agent/playbooks/research/`, `docs/playbooks/README.md`).
1. Копирай `agent/playbooks/research/queries.example.json` в `runs/<x>/research/queries.json`: проблемите с думите на купувача, 1-2 думи (TrendTrack търси дословна фраза в текста на рекламата, многословните дават 0).
2. Сухо пускане (безплатно): `TRENDTRACK_API_KEY=$(cat ~/.config/trendtrack/key) python3 -I agent/playbooks/research/run_queries.py runs/<x>/research/queries.json`. Покажи сумата на Валентин в един ред и чакай ОК. Кредитите (TrendTrack ~38 на търсене от 25 реклами) се плащат само след ОК за тази сума. Scrape Creators ключ нямаме.
3. С ОК: същото + `--go`. Повторното пускане не плаща кешираното.
4. `python3 -I agent/playbooks/research/digest.py ads --raw runs/<x>/research/raw --exclude "<шум>" --out runs/<x>/research/digest.txt` (дава и `ads.json`, `landing-targets.json`).
5. `python3 agent/adlib/import_playbook_ads.py runs/<x>/research/ads.json --product <p> --into runs/<x>/ads/ads_all.json`, после `python3 agent/run.py runs/<x>/run.json done proof_sweep` и `evidence` наново.

## ъгли
Вход: `ads_all.json` (само relevant URL-и от `landing_ranked_<p>.json`) + банката с отзиви. Ако има TrendTrack, и `digest.txt` (чете се целият, дългите реклами се крият в малките групи).
1. Топ 30 реклами по сила: групирай по ъгъл (защо да купя), хук (първият ред), формат, аудитория.
2. Гласът на клиента от банката: желания, болки, възражения, дословни фрази (с име).
3. За всеки ъгъл: ниво на осъзнатост и етап на изтънченост (copy-masters/schwartz), колко силни реклами го носят, дали банката го доказва.
4. Видеата с най-дълъг живот се „гледат“: `python3 -I agent/playbooks/research/watch_video.py <url на видеото> --out runs/<x>/videos/<име>` (транскрипт + мрежа от кадри; нужни yt-dlp, ffmpeg, mlx-whisper). Чети `summary.txt` и `grid_01.jpg`.
5. Скалата за ранг на ъглите е по `docs/playbooks/research/angles-report-template.md`: първо дълго доказателство в чужбина, после празнината на нашия пазар, после пасването на продукта. Хуковете се пазят дословно на оригиналния език + превод.
6. Скоростта (`velocity`, `scaling_now` в `landing_evidence_<p>.json`) показва какво скалират СЕГА: отбележи го до ъгъла.
Изход: `analysis.json` {angles:[{name, why, evidence_ads, awareness, sophistication, proof_in_bank}], hooks:[...]}.

## фунии
Подагент по брифа (образец: `~/so-simple-ointments-research/FUNNEL_AGENT_BRIEF.md`), но с вход `landing_ranked_<p>.json`:
- топ 10-14 relevant URL-и по крайна оценка, без маркетплейси;
- снимки с `agent/qa/capture.py` (390 + 1440, вътрешен скрол се зашива), текст, контур на секциите;
- секции, оферта, техники, ъгъл, какво да не копираме; режим на дизайна от `agent/clone_mode.py`.
- по всяка страница попълни точките от `docs/playbooks/research/landing-research-checklist.md` (тип, над сгъвката, ред на секциите, оферта, гаранция, доставка, доказателства, спешност, checkout, отличителен ход, червени флагове). Бърз текстов вариант без браузър: `python3 -I agent/playbooks/research/fetch_pages.py --targets <landing-targets.json> --top 15`.
Изход: `funnels/funnels_<p>.json` (схемата от брифа). После автоматично `fit`.

## избор
Артефакт по шаблона `~/so-simple-ointments-research/acne_pick/` (template.html + data.json): ъгли, хукове, фунии с Да / Може би / Не + бележка. Фуниите показват **силата и пасването поотделно** + крайната оценка. Отделна секция „Местни конкуренти“ (нашият пазар) с топ 2 винаги, дори при ниска сила: Ad Library вижда малко от местните реклами. Изборите са в db колекция `picks`, четат се с ArtifactData list. **Фуниите задължително** се записват като `funnel-<папка>` (тест 22.10: в артефакта за ACNE имаше само ъгли и хукове). След избора: прехвърли „Да“ фуниите в `goldens/<клиент>_<продукт>.json`.

## клониране
Преди да избереш: виж `cloned` в `run.json`. Там са вече клонираните фунии и къде са. След клона: добави фунията там.
Всяка заявка „клонирай“ (с или без „абсолютно“/„1:1“) върви по `docs/absolute-clone.md`.

## реклами
anchor-creative-playbook + copy-masters. Преди генерации: `python3 agent/credits.py start runs/<x> ads`, след тях `end`. Всяка реклама: `utm_campaign=<продукт>_<тип>_<месец><год>`, `utm_content=<код>-<автор>`.

## критика
Кръгът критика от funnel-critique-round на Вальо, след `qa` и преди `review`. Целта: Валентин да вижда страници, по които читател, DR специалист и юрист вече са минали. Процес и промптове: `docs/playbooks/critique/` (`brief-template.md`, `reviewer-*.md`, `fixspec-template.md`, `fixer-prompt.md`, `lessons.md`).
1. Замрази клонингите. Папка `runs/<x>/critiques/<кръг>/`. BRIEF.md до ~60 реда: какво се продава, купувачът, оригиналът (конкурентската фуния) за сравнение, URL-ите, рекламите.
2. **Решенията на Валентин са заключени** и стоят първи в брифа и FIXSPEC: `docs/rules.md`, `docs/absolute-clone.md` §6, §8, §9 и решенията в `docs/learned-checks.md`. Където правилата на плейбука на Вальо се разминават с тях (емоджита в лентите, без етикет „Рекламна публикация“, без „събирателен образ“), важи решението на Валентин. Правна находка срещу такова решение не се „поправя“, а отива в „Решения за Валентин“.
3. Рецензенти паралелно (подагенти в едно съобщение): читател на езика на пазара в ролята на купувача (BG майка за детските четки, RO за sosimple.ro), DR рецензент срещу оригинала, Meta + ЕС рецензент с вердикт по реклама. Пишат само своя отчет.
4. `python3 -I agent/playbooks/critique/collect_findings.py runs/<x>/critiques/<кръг>/*.md --out .../findings-index.md`, после FIXSPEC по шаблона. Приоритет: решение на Валентин > правен BLOCKER > Meta REJECT > DR > езикова полировка. Всичко, което сменя офертата, гаранцията, доставката или цените, чака ОК (So Simple: Елица).
5. Поправки по FIXSPEC (подагент на фуния), всеки пише `fixed-<фуния>.md`.
6. Повторна проверка: `check_old_phrases.py phrases.txt --root <папка>`, `html_sanity.py <папка>`, `run_qa.py` наново, `verify_cart.py --page`, а линковете в рекламите: `python3 -I agent/playbooks/qa/link_check.py --ads-json <ads.json>`. После `done critique`.
