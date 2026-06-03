# HANDOFF — agent-parser, Phase 4: MDN expansion + eval pipeline hygiene

## Дата

2026-06-02

## TL;DR

Эта сессия закрыла открытый TODO «MDN coverage expansion» из
`HANDOFF_PHASE3_COMPLETE.md`, разобрала ежедневный flake в `eval-live-smoke`
cron, починила корневую причину false-drift'а в `capture_fixture.py` и
архивировала зависшие phase-3 artefacts. Суммарный coverage по трём
источникам — **67 canonical** (было 54), 0 unresolved validation_failed.

## Что merged в этой сессии

| Branch                                | Title                                                                              |
|---------------------------------------|------------------------------------------------------------------------------------|
| `feat/mdn-seeds-expansion`            | `feat(sources): expand developer_mozilla_org seeds from 8 to 34 URLs`              |
| `chore/eval-fixtures-refresh`         | `chore(eval): refresh live fixtures (PSF 3.14.5, MDN template)`                    |
| `fix/eval-capture-fixture-idempotent` | `fix(eval): make capture_fixture idempotent`                                       |
| `chore/archive-phase3-artefacts`      | `chore: archive phase3 artefacts + add db-state diag tool`                         |

Каждый PR — отдельная ветка, один коммит, rebase-and-merge.

## Детали по каждому PR

### MDN seeds expansion (8 → 34)

Категории (+26 URL):

- **CSS Properties** (+7): `display`, `position`, `grid-template-columns`,
  `flex`, `transform`, `transition`, `gap`.
- **JS Built-in Objects** (+8): `Array/map`, `Array/reduce`, `Promise`,
  `Promise/all`, `Object/keys`, `JSON/parse`, `Map`, `Set`.
- **Web API** (+5): `Fetch_API/Using_Fetch`, `WebSocket`,
  `IntersectionObserver`, `History_API`, `Web_Storage_API`.
- **HTTP** (+6): `Methods/POST`, `Methods/PUT`, `Status/200`, `Status/404`,
  `CORS`, `Headers/Cache-Control`.

Метод: manual curation (0 Firecrawl credits). Для MDN `firecrawl_map`
избыточен — статичный reference-сайт, ручной выбор лучше фильтрации
десятков тысяч URL.

URL-формат: новые CSS-seed'ы используют современный канонический path
`Web/CSS/<prop>` вместо `Web/CSS/Reference/Properties/<prop>` у трёх
исходных. Несогласованность в `parse_id` допустима — разные source_id
в `canonical_records`. Нормализация старых трёх — отдельный PR при
необходимости, не делалось.

Side-fix: ASCII `->` вместо Unicode `→` в комментарии `parse_id`
(паттерн RUF003, как в `anthropic_news.py`).

### Eval fixtures refresh

Live drift, обнаруженный `eval-live-smoke` cron:

- **`08_python_json`** — PSF выкатил **3.14.5** (был 3.14.5rc1) + уточнение
  описания параметра `indent` в `json.dumps`.
- **`09_mdn_get`** — MDN изменил template: link «Report problems» теперь
  embed'ит полный GitHub issue URL с metadata вместо `#`. Page content
  unchanged.
- **`17_arxiv_abstract`** — `captured_content_hash` **не изменился**.
  Diff был чистый шум от `capture_fixture` (timestamp + JSON re-format).

`pytest tests/eval/ -q` — 25 passed с обновлёнными фикстурами.

### `capture_fixture` idempotent fix

Корневая причина ежедневного fail'а `eval-live-smoke` cron:
`tests/eval/tools/capture_fixture.py` безусловно обновлял `captured_at` +
`captured_content_hash` + перезаписывал `.captured.md` без trailing newline.
То есть **каждый** прогон давал non-empty diff даже без content drift.

Фикс:

- `_normalise_body()` приводит body к одному trailing `\n`.
- Hash считается один раз в начале.
- `.captured.md` пишется только если bytes реально отличаются.
- `.expected.json` обновляется только если hash сменился (тогда же
  advance `captured_at`).
- JSON пишется с trailing `\n` для clean diffs.
- Per-fixture progress (`[md]`, `[meta]`, `[stub]`) показывает что
  тронуто.

Поведение для новых фикстур не тронуто. После merge: следующий cron
будет молчать пока реальный content drift не появится.

### Phase 3 artefacts archive + diag tool

Закоммичено из untracked:

- `HANDOFF_PHASE3_COMPLETE.md` — handoff прошлой сессии (audit trail).
- `reports/investigation_core_views_phase1.txt` — investigation notes по
  `core-views-on-ai-safety` flake.
- `scripts/investigate_core_views.py` — reusable repro script.
- `scripts/check_db_state.py` — generalised read-only diag tool
  (заменил throwaway `check_mdn_state.py`). Принимает `--source <name>`
  и опциональный `--show-ids`. Использует `sqlite3 -readonly`.
- `.gitignore`: `scripts/discovered_*.txt` (выходы discovery-скриптов,
  regenerable).

## Текущее состояние репо

DB (`data/scraped.db`, gitignored):

- `developer_mozilla_org`: **21 canonical**, 0 unresolved vf
- `docs_python_org`: **27 canonical**, 0 unresolved vf
- `anthropic_news`: **19 canonical**, 0 unresolved vf
- **TOTAL: 67 canonical**

`config/sources.yaml`: без изменений (3 источника).

Tests: ~140 unit + 25 eval, ruff + mypy --strict чистые на `main`.

## Production batch результаты — MDN

Первый прогон против 34 seeds:

| Категория | Записано | Не записано | Причина |
|---|---|---|---|
| CSS (10)   | 10 | 0 | — |
| JS (10)    | 8  | 2 | timeout (`Promise`, `Set`) |
| Web API (7)| 2  | 5 | CostGate |
| HTTP (7)   | 1  | 6 | CostGate |

Батч упёрся в CostGate (~115 cr) после URL `Web/API/View_Transition_API`.
Транспортные timeouts не пишутся в `validation_failed` — просто logged
и skipped (`logger.exception` per PR `4a67fd1`).

## Открытые TODO

1. **Добор 13 MDN seeds** (5 Web API tail + 6 HTTP tail + 2 timeout JS).
   Варианты:
   - bump cost cap на одну сессию + повторный batch (но он перепрогонит
     все 21 успешных, до incremental refresh).
   - точечный re-scrape 13 URL через одноразовый скрипт (~65 cr).
   - подождать incremental refresh.

2. **Incremental refresh** (`docs/tickets/TODO_incremental_refresh.md`) —
   skip-if-fresh в `run.py`. Стал актуальнее: без него добор хвоста MDN
   стоит повторного прогона всего seed-листа.

3. **MDN `Promise` / `Set` timeout** — same class что `core-views-on-ai-safety`
   (большие JS-страницы, 30s timeout мало). Accepted infra-flake. Если
   станет систематикой (>1/3 запусков) — добавить `wait_for=1500` для MDN
   или поднять `timeout` в `extract.py`.

4. **408 retry policy** — открытый TODO с Phase 3, не сработал ещё на
   систематику.

5. **CRLF noise на Windows-машине разработчика** — лечится
   `git config --global core.autocrlf true`. Это user-side, не требует
   изменений в репо. Альтернатива — добавить `.gitattributes` с
   `* text=auto eol=lf` (отдельный PR, не сделано).

## Заметки для следующей сессии

- Run-time роли проекта: только `/investigate-failed`, `/onboard-source`,
  `/query`. Расширение seeds существующего адаптера — design-time work
  по явному запросу.
- Edit/Write tools в этой сессии обрезали запись на ~1200 байт. Все
  правки > этой границы делались через bash heredoc на Linux mount path.
  Если повторится — bash heredoc остаётся надёжным fallback.
- Скрипт `python scripts/check_db_state.py --source <name>` — быстрая
  read-only sanity-проверка состояния DB по любому источнику.
