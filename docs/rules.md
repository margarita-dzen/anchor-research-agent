# Правила на едно място (22.10.2026)

Събрани от паметта (`~/.claude/projects/-Users-magi/memory/`), за да не зависят от това дали терминалът е прочел правилната бележка. Източникът е в скобите. Ако правило в паметта се промени, обнови и тук.

## Винаги
- Само headless браузър (playwright, порт 9333 при Chrome). Никога прозорци в Chrome на потребителя. (feedback_never_open_chrome_windows, feedback_headless_render_never_open_chrome)
- Без em dash в текстовете за клиенти. (feedback_no_emdashes)
- Отзивите са дословни, с истинското име, от банката (`~/Clients/<клиент>/reviews/bank.json`). Не измисляме отзиви, имена, брой отзиви, лекари. (feedback_testimonial_verbatim_rule, feedback_absolute_clone_rules)
- Генерирани преди/след (и детски) се правят, но БЕЗ име, без срок и никога в карта на отзив. (feedback_absolute_clone_rules)
- Никога „илюстративна снимка“ / „Илюстрация“ / „Рекламна публикация“ / „Publicitate“: нито надпис, нито alt. (feedback_ba_no_illustrative_label, feedback_absolute_clone_rules)
- Офертният текст по визиите се НАБИРА в HTML, не се генерира. (feedback_offer_creative_typeset_not_generated)
- Един маркер за подарък на визия. (feedback_one_gift_marker_per_visual)
- Изрязаните продукти: непрозрачни, цели, без ореол, истински мащаб. (feedback_product_cutouts_opaque_uncropped)
- Грешка в генерация → прегенерирай, не кърпи пиксели. (feedback_no_pixel_patches_regenerate)
- Всяка страница се проверява на 390 и 1440 px. (feedback_funnel_qa_every_page_both_widths)
- План ≠ промяна на живо: питай „от сега или от датата?“. (feedback_plan_vs_live_changes)
- Един преглед на страница (review page), не много файлове. (feedback_single_review_page)
- Изборът на фунии винаги минава през скалата за сила на доказателствата + пасване. (docs/evidence-scale.md)

## Страници за преглед
- Новите страници се правят **непубликувани** до одобрение. Непубликувана страница дава 404 дори в preview темата, затова прегледът е на `https://<магазин>/pages/test?view=<template suffix>&preview_theme_id=<preview>`: шаблонът се показва върху вече публикуваната скрита страница, без промяна на живо. (BRIEF.md файловете, които казват isPublished=true, са по-стари.)
- Dawn скрива празните `div` (`div:empty{display:none}`). Кръгчетата и декорациите без съдържание трябва да имат `&nbsp;` или размер през `::before`.

## So Simple (Carina Precious)
- Офертите и гаранциите само след ОК от Елица. (feedback_so_simple_offers_confirm_elitsa)
- „Подбрани съставки“, не „100% натурални“ / „без химия“. (project_so_simple_greenwashing_2026_10)
- Всяка промяна по сайта → проверка и на sosimple.ro за кирилица. (feedback_so_simple_check_ro_on_every_site_change)
- BG видеа не отиват в RO. (feedback_no_bg_videos_in_ro)
- Комплектите са истински bundles. (feedback_shopify_packs_as_bundles)
- Козметика, не лекарство: без „лекува“, „спира възпалението“, „антисептично“, Accutane, %-успеваемост. „Кортикостероиди“ се споменават като контекст, не като обещание. (project_so_simple_ointments_research_2026_10)
- MAIN тема 202643046747 се пипа само след одобрение. Preview 203331305819.
- **RO пазар: всичко на румънски** (alt, мета, имейли, доставка, теми, метаполета, отзиви), без лева. Пикселите се зареждат винаги. RO версия на рекламите само ако фунията я има на sosimple.ro. (feedback_ro_market_all_romanian)
- Отзивите идват от банката `~/Clients/So-Simple/reviews/bank.json` (Shopify/Judge.me от 18.09). Старият WooCommerce адрес в anchor-ad-copy-formulas не важи.
- Отзив за друг продукт (напр. Pamela Petkova е към чая ACNE GONE, но говори и за стика) се ползва само с бележка за двата продукта („чай и стик“). В реклама за един продукт не се ползва.
- Описанията на продуктите още съдържат „100% натурални“ (чакат Ели). Не се копират в нови текстове.

## Nordics
- Образците от INA се ползват без разпознаваеми копия: само механиката, не фона, сцената, шрифта. (feedback_nordics_no_recognizable_ina_copies)
- Дизайните не са семпли. (feedback_nordics_designs_too_simple)
- Elena Ilieva („на пациентите си“) никога до снимката на д-р Балева. Експерти: д-р Юнуз, д-р Балева. (project_anchor_research_agent)

## INA Essentials
- Никъде „България“ / „българско семейство“. (feedback_ina_no_bulgaria_mention)
- Само NBP или GPT Image 2, без Higgsfield. (feedback_ina_only_nbp_or_gpt2, feedback_no_higgsfield_for_ina)
- Рекламите по метода на INA офертните уинъри, никога изрязване/лепене. (feedback_ads_ina_offer_method_only)

## Vitalaiz
- Ботокс, александрит, устни = лийдове към GHL, не сайт. Без изключване на аудитории. Премиум дизайн без serif, без името на марката, без цени. (project_vitalaiz_promo_styles_2026_10, feedback_vitalaiz_* в паметта)

## Криейтиви
- /creative-strategy преди всичко, после anchor-creative-playbook. 16 дизайн фамилии + Style Lab 30% винаги. Без повторени сцени в батч. (feedback_creative_strategy_skill_every_asset, feedback_diversification_taxonomy, feedback_style_lab_in_every_iteration, feedback_no_repeated_scenes_in_batch)
- Хедлайни: красота + клиничен довод, директен ъгъл, ALL CAPS. (feedback_beauty_plus_clinical_headlines, feedback_direct_angle_headline, feedback_headlines_all_caps)
- Процент, не цена, във визиите. Shelly: без цена. (feedback_percent_not_price_in_creatives, feedback_shelly_no_price_on_creative)
- Текстове: copy-masters (Schwartz → водещ автор по задача), авторът в utm_content.

## Генерации и кредити
- Преди батч: `python3 agent/credits.py need <N>`. Батчът наведнъж, не по 3. Отказаните „unsafe“ се таксуват → `--tries 1` и мек промпт. (feedback_parallel_generation, project_so_simple_ointments_research_2026_10)
- **Ключовете:** генерациите за всички клиенти вървят през основния ключ `KIE_AI_API_KEY`. Ключът `KIE_AI_API_KEY_PAVLOVA_VITALAIZ` (в паметта „ключът на Маргарита“) е за Павлова/УНИКАЛ и Vitalaiz. За друг клиент се ползва само при изрично разрешение за конкретната задача, с отчет преди/след. (reference_kie_key_pavlova_vitalaiz)
- Генерации само през kie runner-а (headless). Инструкцията в `~/ads-automation/SKILL.md` за Higgsfield в Chrome Canary (порт 9222) НЕ важи за агента. (feedback_never_open_chrome_windows)
- Style Lab 30%: смята се за целия батч (закръгляне нагоре), минимум 1 на фуния.
