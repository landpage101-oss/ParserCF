# HANDOFF — agent-parser, Phase 6: TODO sweep (CSS normalization, resolve_vf generic, CRLF fix)

## Дата

2026-06-04

## TL;DR

Сессия закрыла все 5 открытых TODO из Phase 5. Три PR (CSS seed normalization, generic
`resolve_vf.py`, `.gitattributes`), одна data migration на `canonical_records` (вне git),
два TODO закрыты без кода (408 — phantom, timeout monitor — данных нет).
DB не изменилась: **80 canonical**, 0 unresolved `validation_failed`.

## Что merged в этой сессии

| Branch | Commit | Title |
|---|---|---|
| `fix/mdn-css-seed-url-normalization` | `a147478` | `fix(mdn): normalize CSS seed URLs to modern Web/CSS/<prop> format` |
| `feat/scripts-resolve-vf-generic` | `bfa08ea` | `feat(scripts): add generic resolve_vf.py for validation_failed resolution` |
| `chore/add-gitattributes-line-endings` | `eb67212` | `chore: add .gitattributes to normalize line endings to LF` |

`main` на `eb67212`.

## Детали по каждому PR

### `fix/mdn-css-seed-url-normalization`

Три старых MDN CSS seed URL использовали путь `/Reference/Properties/<prop>` — legacy
формат, которого MDN давно нет в современной навигации. `parse_id` честно стрипал
`_BASE` и возвращал `Web/CSS/Reference/Properties/<prop>`, что расходилось с
актуальным MDN-каноном и приводило к 1 лишнему attempted вместо skip в каждом батче.

Изменения:
- `src/sources/developer_mozilla_org.py`: три OLD URL → современные (`Web/CSS/z-index`,
  `Web/CSS/flex-wrap`, `Web/CSS/justify-content`).
- `tests/sources/test_developer_mozilla_org.py`: обновлён первый assert в
  `test_parse_id_strips_prefix_and_extension` под новый URL-формат.

`parse_id` не трогался — логика не менялась.

Сопутствующая **data migration** (вне git, оператор руками, после merge PR, до
следующего batch):
```sql
UPDATE canonical_records SET source_id = 'Web/CSS/z-index'
  WHERE source = 'developer_mozilla_org' AND source_id = 'Web/CSS/Reference/Properties/z-index';
UPDATE canonical_records SET source_id = 'Web/CSS/flex-wrap'
  WHERE source = 'developer_mozilla_org' AND source_id = 'Web/CSS/Reference/Properties/flex-wrap';
UPDATE canonical_records SET source_id = 'Web/CSS/justify-content'
  WHERE source = 'developer_mozilla_org' AND source_id = 'Web/CSS/Reference/Properties/justify-content';
```

`raw_content` и `change_history` не трогались — аудит. Verify после migration:
`python scripts/check_db_state.py --source developer_mozilla_org --show-ids` показал
34 canonical, все CSS-записи в новом формате.

### `feat/scripts-resolve-vf-generic`

Заменяет паттерн разовых `resolve_vf<N>.py` (использовался в Phase 5 для vf #4)
универсальным CLI-инструментом.

```
python scripts/resolve_vf.py --vf-id N --resolution <fixed|discarded|source_changed> --reason "..."
python scripts/resolve_vf.py --vf-id N --dry-run
```

Обёртка над `resolve_validation_failure()` из `src.db.store`: fetches и отображает
запись до применения, guard на unknown/already-resolved id, commit после резолюции,
readback `resolved_at` как подтверждение. `--dry-run` — показ без записи.

Тесты не добавлялись — обёртка над уже протестированным helper'ом. Baseline 155 держится.

### `chore/add-gitattributes-line-endings`

Добавлен `.gitattributes` с `* text=auto eol=lf` в корень репо. Устраняет
phantom-дифф на Windows: 55 файлов показывались как Modified с чистыми CRLF-заменами
после `git config --global core.autocrlf` отсутствовал.

Порядок исправления в сессии:
1. `git config --global core.autocrlf true` — сброс phantom-дифа в рабочем дереве.
2. `git checkout -- .` — очистка working tree.
3. PR с `.gitattributes` + `git add --renormalize .` — только 1 файл в diff (renormalize
   ничего не добавил, дерево уже было чистым).

## Закрытые TODO из Phase 5

| TODO | Решение |
|---|---|
| #1 CSS source_id normalization | PR + data migration — закрыт |
| #2 `resolve_vf.py` generic | PR — закрыт |
| #3 MDN timeout monitor | Monitor — 0 батчей с тех пор, данных нет, следующий батч покажет |
| #4 408 retry policy | Phantom — 0 наблюдений в трейсах за всю историю проекта; `except Exception` достаточен |
| #5 CRLF / `.gitattributes` | PR — закрыт |

## Текущее состояние репо

DB (`data/scraped.db`, gitignored):

- `developer_mozilla_org`: **34 canonical**, 0 unresolved vf
- `docs_python_org`: **27 canonical**, 0 unresolved vf
- `anthropic_news`: **19 canonical**, 0 unresolved vf
- **TOTAL: 80 canonical**, 0 unresolved validation_failed

Tests: **155 total** (130 unit + 25 eval), ruff + mypy --strict чистые.

`config/sources.yaml`: без изменений (3 источника).

## Открытые TODO

1. **TODO #3 (MDN timeout monitor)** — переведён в «monitor». Те же 3 URL
   (`Promise`, `Fetch_API/Using_Fetch`, `Headers/Cache-Control`) под наблюдением.
   Порог эскалации: >1/3 батчей подряд с timeout'ами → `wait_for=1500` или подъём
   `timeout` в `extract.py`. Следующий MDN-батч — первая точка данных после Phase 5.

## Заметки для следующей сессии

- **CSS source_ids нормализованы.** Все 34 MDN canonical используют единый формат.
  Следующий batch должен skip все 34 как fresh (если `--max-age-days=7` не истёк).
- **`scripts/resolve_vf.py` — стандартный инструмент для vf-резолюций.** Больше
  не нужны разовые `resolve_vf<N>.py`.
- **`.gitattributes` в репо.** CRLF-шум устранён на репо-уровне. `core.autocrlf=true`
  дополнительно выставлен у оператора глобально.
- **Pre-existing lint ошибки в `scripts/check_mdn_state.py`** — зафиксированы в Phase 6,
  не блокируют (acceptance chain проверяет файлы точечно, не весь `scripts/`). Отдельный
  TODO если понадобится.
- Run-time роли неизменны: `/investigate-failed`, `/onboard-source`, `/query`.
- Следующий осмысленный шаг — новый источник (`/onboard-source`) или MDN-батч для
  закрытия TODO #3.
