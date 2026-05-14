# Правило: onboard-source

Расширение для `/onboard-source <domain>`. Загружается в контекст при вызове команды.

## Цель роли

Design-time онбординг нового источника: ты пишешь ЧЕРНОВИК Python-адаптера, тесты под него и предлагаешь запись для allow-list. Финальное решение — за человеком на PR-review. Это единственная роль, где тебе разрешено создавать новый код источника.

## Предусловия (проверить до любого Firecrawl-вызова)

1. Домен ещё не в `config/sources.yaml` — иначе останови, источник уже онбординг-нут.
2. `is_allowed()` для корня домена возвращает `True` — иначе останови, robots.txt запрещает.
3. Домен прошёл ручную legal-проверку человеком — если подтверждения в задаче не видно, спроси прежде чем продолжать.

## Контракт адаптера

Файл `src/sources/<machine_name>.py`, класс `<CamelCase>Adapter`, по `src/sources/_base.py::SourceAdapter`:
- атрибуты: `domain: str`, `name: str`, `page_type: str` (один из `article|docs|product|reference`)
- `list_urls(self, since: str | None = None) -> Iterable[str]` — на старте фиксированный набор seed-URL (5-10 штук), `since` пока игнорируется
- `parse_id(self, url: str) -> str` — канонический ID на источнике

## Тесты

`tests/sources/test_<machine_name>.py`, минимум три кейса: `test_list_urls_returns_seeds`, `test_parse_id_strips_prefix_and_extension`, `test_page_type_is_<type>`.

## Cost discipline

- `firecrawl_map` — один вызов, cost cap 5 кредитов.
- `firecrawl_scrape` — не более 3 вызовов, суммарный cap 15 кредитов.
- Если для понимания структуры нужно больше — останови, опиши в отчёте, что осталось неясным. Не жги кредиты на «ещё посмотреть».

## allow-list запись — НЕ редактировать файл

`config/sources.yaml` под CODEOWNERS-review и в `settings.json` deny. Ты НЕ редактируешь его. Вместо этого — выдаёшь предлагаемую запись как fenced YAML-блок в финальном сообщении, человек применяет её при merge. Поля записи — по `src/compliance/sources_config.py::SourceConfig`.

## Границы

- Только `Write(src/sources/**)` и `Write(tests/sources/**)`.
- НЕ трогай `src/safety/**`, `src/db/**`, `config/**`, `.github/**`, `.claude/**`.
- Адаптер — это черновик. В summary явно скажи, что нужно от человека: legal-review, проверка seed-URL, прогон тестов, заполнение `sources.yaml`.
