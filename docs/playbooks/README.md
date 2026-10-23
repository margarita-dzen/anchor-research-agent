# Компонентите от Anchor Playbooks (Вальо, 23.10.2026)

Пренесени от плъгина `anchor-playbooks` (FaceLab/Shelly), за да е агентът самостоятелен. Оригиналите остават в `~/anchor-playbooks`; при обновяване на плъгина сравни и пренеси наново. Всички скриптове са само стандартна библиотека (освен `qa_pages.py`/`verify_cart.py` с playwright и `watch_video.py` с yt-dlp/ffmpeg/whisper). Ключовете се четат от env или `~/.env`, никога от репото. Платените скриптове по подразбиране са сухо пускане (`--go` харчи).

| Компонент | Откъде | Къде в агента | Етап |
|---|---|---|---|
| `trendtrack.py`, `sc.py`, `run_queries.py` | competitor-ad-research | `agent/playbooks/research/` | доказателства от TrendTrack |
| `digest.py` (+ `ads.json`, `landing-targets.json`) | competitor-ad-research | `agent/playbooks/research/` → `agent/adlib/import_playbook_ads.py` | доказателства → evidence |
| `watch_video.py` | competitor-ad-research | `agent/playbooks/research/` | ъгли |
| `fetch_pages.py`, `landing-research-checklist.md`, `angles-report-template.md`, `api-notes.md` | competitor-ad-research | `agent/playbooks/research/`, `docs/playbooks/research/` | ъгли, фунии |
| формулата от `ad_velocity.py` | cod-funnel-launch | `agent/evidence.py` (`velocity`, `new_ads_7d`, `scaling_now`, само за показване) | evidence |
| `link_check.py`, `qa_pages.py` | cod-funnel-launch | `agent/playbooks/qa/` | критика (повторна проверка) |
| `verify_cart_paths.py` | shopify-offer-funnel | `agent/playbooks/cart/`, вика се от `agent/qa/verify_cart.py` | qa |
| `collect_findings.py`, `check_old_phrases.py`, `html_sanity.py` + промптовете | funnel-critique-round | `agent/playbooks/critique/`, `docs/playbooks/critique/` | критика |

Не са пренесени: `meta-ads-bulk-upload` и `meta_launch.py` (качването на реклами е извън агента, рекламите винаги PAUSED), `ai-ad-creatives/gen.py` (визиите са през скила anchor-ad-images), COD checkout шаблоните.

## Където правилата се разминават
Плейбуците на Вальо са писани за клиенти без решенията на Валентин. В агента важат решенията на Валентин (`docs/rules.md`, `docs/absolute-clone.md`): емоджита в лентите са позволени, етикетът „Рекламна публикация“ се маха, не се слага „събирателен образ“ (разказвачът е истински човек на клиента), сроковете, недостигът и „№1“ са позволени, когато са проверени с данни. Общото и в двата свята: без измислени отзиви, лекари, числа и проучвания, без медицински твърдения, без тирета.
