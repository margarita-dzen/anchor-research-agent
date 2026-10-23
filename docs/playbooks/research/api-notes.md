# API notes: Scrape Creators and TrendTrack

Everything here was learned on real research runs. Read it before you plan a sweep or call an endpoint by hand.

## Keys

| API | Env var | Fallback | Auth |
|---|---|---|---|
| Scrape Creators | `SCRAPECREATORS_API_KEY` | line `SCRAPECREATORS_API_KEY=...` in `~/.env` | header `x-api-key: <key>` |
| TrendTrack | `TRENDTRACK_API_KEY` | line `TRENDTRACK_API_KEY=...` in `~/.env` | header `Authorization: Bearer <key>` |

Never paste a key into a chat, a report, a doc or a script. If one ends up in a chat, tell the owner once that it should be rotated, then carry on.

## Which tool for what

| Question | Use | Why |
|---|---|---|
| "Which ads on this problem have run longest in big EU markets?" | TrendTrack `/v1/ads/query`, `sortBy: longestRunning`, `minDaysRunning: 60` | Sorts by days running and filters by age; carries reach, spend estimate and video transcripts |
| "Who advertises this in BG / RO / PL right now?" | Scrape Creators FB Ad Library search with `country` | Exact country filter, 1 credit per page, cheap |
| "Show me all ads of competitor X" | Scrape Creators `company/ads` (by page id) or TrendTrack advertiser ads | SC is cheap but capped at ~40 ads; TT costs ~3 credits per ad |
| "What do people say about this problem?" | Scrape Creators TikTok / YouTube / FB page post comments | Ad comments are not reachable, organic comments are |
| "Which local creators own this topic?" | Scrape Creators TikTok / Instagram / YouTube search | Sort by views, filter by region and language |

## Scrape Creators

Base `https://api.scrapecreators.com`. Every endpoint is GET with query parameters. **1 credit per request** on every endpoint used so far. Responses include `credits_charged` and `credits_remaining`; `sc.py` writes both to `run.log`.

### Endpoints used

| Purpose | Path | Params | Result key |
|---|---|---|---|
| Credit balance (free) | `/v1/credit-balance` | none | |
| FB Ad Library keyword search | `/v1/facebook/adLibrary/search/ads` | `query`, `country` (BG, DE, ... or omit for all), `status=ACTIVE`, `trim=true`, `cursor`, optional `sort_by=relevancy_monthly_grouped` (newer ads) | `searchResults`, `searchResultsCount`, `cursor` |
| FB Ad Library: all ads of a page | `/v1/facebook/adLibrary/company/ads` | `pageId`, `status=ACTIVE`, `trim=true`, `cursor` | `results`, `cursor` |
| FB Ad Library: find a page id by name | `/v1/facebook/adLibrary/search/companies` | `query` | `searchResults[].page_id` |
| FB Ad Library: one ad in detail | `/v1/facebook/adLibrary/ad` | `id` (ad archive id) | `snapshot` |
| FB page organic posts | `/v1/facebook/profile/posts` | `url` (page URL) | `posts[]` (with `commentCount`, `topComments`) |
| FB post comments | `/v1/facebook/post/comments` | `url` (post URL), `cursor` | `comments[]` |
| TikTok keyword search | `/v1/tiktok/search/keyword` | `query` | `search_item_list[].aweme_info` |
| TikTok hashtag search | `/v1/tiktok/search/hashtag` | `hashtag` | `aweme_list` |
| TikTok video comments | `/v1/tiktok/video/comments` | `url`, `cursor` (20, 40, ...) | `comments[]` |
| Instagram reels search | `/v2/instagram/reels/search` | `query` | `reels[]` |
| YouTube search | `/v1/youtube/search` | `query` | `videos[]`, `shorts[]` |
| YouTube video comments | `/v1/youtube/video/comments` | `url`, `order=top` | `comments[]` |
| Google search | `/v1/google/search` | `query`, `region` (BG, PL, ...) | `results[]` |
| Reddit search / post comments | `/v1/reddit/search`, `/v1/reddit/post/comments` | `query` / `url` | `posts[]` / `comments[]` |

Other endpoints exist (TikTok / YouTube / Instagram transcripts, profiles, Instagram post comments). They were not used in a real run, so test one call first and check the response shape before you loop over them.

### Gotchas
- **Ad Library is capped at about 40 ads per query.** Page 1 returns up to 30, page 2 up to about 10, then it stops. Same for `company/ads`. So "40 ads" in a digest means "at least 40". To see more, split the query into narrower terms or search per country.
- **POST variants return 404.** Use GET with `cursor` for paging. A 404 on a GET usually means a typo in the path.
- **TikTok, Instagram and YouTube search are not geo-filtered.** Search in the local language, then keep only results whose TikTok `region` matches, or whose author and language are local. `digest.py social --region BG,RO` does the TikTok part.
- **Ad comments cannot be reached.** Ad details carry no post id. For objections, pull comments from the advertiser's organic page posts (`profile/posts` then `post/comments`) and from popular TikTok / YouTube videos on the topic.
- **The credit-balance endpoint can lag** behind a top-up (it once showed 100 while real calls showed about 7,100 left). Trust `credits_remaining` on a real call.
- `start_date` is a Unix timestamp. Days running = today minus start date. `collation_count` = how many copies of the same creative run (more copies = being scaled).
- `targeted_or_reached_countries` is often empty in keyword search; the country you searched is then the best market signal.
- Dynamic product ads put `{{product.name}}` in the body; the real text is in `snapshot.cards[0].body`. `digest.py` handles this.

## TrendTrack

Base `https://api.trendtrack.io`. Bearer key. Cost is reported in response headers `x-usage-cost` and `x-credits-remaining`. **1,000 credits = 1 USD.**

### Endpoints used

| Purpose | Call | Cost |
|---|---|---|
| Account, plan | `GET /v1/me` | free |
| Credits used / left | `GET /v1/usage` | free |
| Find an advertiser by domain | `GET /v1/lookup?q=<domain>&type=auto` | free |
| Search ads by ad text | `POST /v1/ads/query` with JSON body (below) | about 1.5 credits per ad returned (25 ads = 38) |
| All ads of one advertiser | `GET /v1/advertisers/{id}/ads?status=active&sortBy=longestRunning` | about 3 credits per ad |

Query body that worked:
```json
{"search": ["<term>"], "searchType": "adCopy", "platforms": ["facebook"], "status": "active",
 "sortBy": "longestRunning", "order": "desc", "limit": 25, "minDaysRunning": 60}
```

### Gotchas
- **Data is Facebook only and effectively EU only** (it comes from Meta's EU transparency data). `countries: ["US"]` is ignored and you get no US ads. To learn "what works abroad", use the big EU markets: DE, FR, NL, the Nordic countries, plus UK where present.
- **`minDaysRunning` works** and is the best "proven abroad" filter. 60 days is a good default for foreign markets. Leave it at 0 for your own markets so new competitors show up.
- **429 Too Many Requests:** wait the number of seconds in `retry-after` and try again. The scripts do this and also pause about 1.2 s between calls.
- A search returns at most `limit` ads; zero results cost zero. Literal words cause noise: "plaque" returns door plaques, "braces" returns knee braces. Plan to filter (`digest.py ads --exclude`).
- English searches in TrendTrack still return EU advertisers (UK, IE, Nordic countries in English, international shops), which is useful.
- Every ad has `daysRunning`, `metrics.reach`, `metrics.estimatedSpend`, `metrics.duplicates`, `content.landingPageUrl` and often `content.transcript` (what the video says). Reach and spend are estimates; days running is the stronger signal.

## Reading the numbers

- **Days running is the main proof that an ad pays.** Nobody keeps paying for a losing ad for months. 60+ days = likely profitable. 300+ days = evergreen.
- **Many new ads on the same landing URL in the last 7 to 30 days** = the advertiser is scaling it right now. `landing-targets.json` scores both.
- **Variants / duplicates** = the same creative in several ad sets or languages. High counts mean it is being pushed.
- Reach and spend are rough. Use them to compare, never quote them as facts in client material.
