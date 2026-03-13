# Эмпирические Бенчмарки (Eval Suite)

Контролируемые эксперименты: vanilla LLM vs abracadabra на одном и том же коде.

## Структура эксперимента

```
benchmarks/NNN_название/
├── BRIEF.md        ← задание (единый вход для обоих прогонов)
├── meta.yml        ← модель, версия, Ground Truth, ресурсы, метрики
├── baseline.md     ← результат vanilla-агента
├── abra.md         ← результат abra-агента
├── verdict.md      ← ослеплённый арбитраж
└── results/        ← мульти-модельные прогоны (bench runner)
    ├── COMPARISON.md           ← сводная таблица
    └── <model>_<kb>/           ← результаты по модели
        ├── baseline.md
        ├── abra.md
        ├── verdict.md
        └── metrics.yml
```

## Два способа запуска

### 1. Интерактивный (Claude Code / Cursor / Zed)

```
abra bench NNN
```

Self-contained — не требует предварительного `abra init`.

**Что происходит:**

1. **Baseline + Init (параллельно)** — субагент в чистом контексте (без `.rules`, `.cursorrules`, `CLAUDE.md`). Параллельно `abra init`.
2. **Abra audit** — полный конвейер (Пре-чеклист → Фазы 0–6 → Октагон) → `abra.md`.
3. **Verdict (ослепление, GT-free)** — рандомные метки «Report A» / «Report B», верификация каждой находки по коду, деанонимизация в финале.

### 2. Bench Runner (мульти-модельный, API)

```bash
pip install -r bench/requirements.txt

# Одна модель — три фазы
python -m bench.runner 003 --model gemini/gemini-3.1-pro-preview --tag test
python -m bench.runner 003 --model gemini/gemini-3.1-pro-preview --abra --tag test
python -m bench.runner 003 --verdict --verdict-model gemini/gemini-2.5-flash --tag test

# Массовый прогон + сводная таблица
python -m bench.compare 003
python -m bench.compare 003 --full-kb     # полная KB (75KB вместо 33KB)
python -m bench.compare 003 --table-only  # перегенерировать таблицу
```

**Изоляция:** baseline и abra — два независимых stateless HTTP-запроса к API. Разные system prompts, никакого общего состояния. Baseline получает `"Senior SE"`, abra получает knowledge base как system prompt.

**Ослепление:** verdict-модель получает отчёты как «Report A» / «Report B» с рандомным маппингом. Деанонимизация после подсчёта метрик.

## Метрики verdict (GT-free)

Основные метрики не зависят от заранее известных багов:

- **Верификация** — для каждой находки: открыть файл/строку, проверить по коду. `verified` / `plausible` / `false`
- **Precision** — verified / total
- **Unique findings** — находки только одного отчёта
- **Actionability** — указана строка кода, root cause, путь к исправлению? `actionable` / `vague` / `no-fix`
- **Severity distribution** — weighted score: critical=3, high=2, medium=1, low=0.5
- **ROI** — overhead abra (tokens, cost) vs дельта качества

**GT (опционально):** если в `meta.yml` заполнен `ground_truth_bugs` — считается recall и severity calibration. GT привязан к коммиту и устаревает.

## Реестр

| # | Проект | Модели | Verdict | Данные |
|---|--------|--------|---------|--------|
| **001** | `isearch` | Claude Opus 4.6 (interactive) | [abra wins](001_isearch_audit/verdict.md) | — |
| **002** | `isearch` | Gemini 3.1 Pro (interactive) | *pending* | — |
| **003** | `isearch` | 7 моделей × 2 KB (API runner) | **abra 6 / baseline 7 / tie 1** | [Сводная таблица](003_isearch_audit_slim/results/COMPARISON.md) |

### Bench 003: ключевые выводы

14 прогонов: Gemini 2.5 Flash/Pro, 3.0 Flash/Pro, 3.1 Flash-Lite/Pro, DeepSeek Chat. Каждая модель — slim KB (33KB, 5 файлов) и full KB (75KB, 16 файлов).

1. **Full KB (75KB) вредит флагманам** — Lost in the Middle: модель тратит compute на соответствие фреймворку вместо поиска багов.
2. **Full KB помогает mid-tier** — работает как Chain of Thought рельсы для моделей со слабым внутренним "здравым смыслом".
3. **Slim KB оптимален** для флагманов — подтверждает архитектурное решение v3.0-slim.
4. **Abra ≠ волшебный промпт** — в zero-shot API почти паритет. Сила abra — в интерактивных агентных средах (Approval Gate, EXECUTION_STATE, пошаговая маршрутизация).

---
*«Разница, которая не создаёт разницы в физическом мире, не имеет значения» (Фильтр 5: Джеймс).*
