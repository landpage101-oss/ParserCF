# agent-parser

Universal scraper agent on Claude Code + Firecrawl with safety perimeter.

## Quick start

```bash
git clone <repo>
cd agent-parser
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
cp .env.example .env  # заполните FIRECRAWL_API_KEY и ANTHROPIC_API_KEY
pytest tests/
```

## Документы

- `docs/PROJECT_OVERVIEW.md` — цели и не-цели.
- `docs/ARCHITECTURE.md` — шесть слоёв архитектуры.
- `docs/TECH_STACK.md` — что чем строится.
- `docs/CURRENT_STATUS.md` — текущая фаза.
- `agent_parser_secure_v2.md` — полная техническая инструкция.
- `evals_and_ci.md` — eval-набор и CI.
- `IMPLEMENTATION_ROADMAP.md` — пошаговая инструкция реализации.
- `ERRATA.md` — баги в проектной документации (применены на Этапе 0).
