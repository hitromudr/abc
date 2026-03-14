# Эмпирические Бенчмарки (Eval Suite)

Контролируемые эксперименты: vanilla LLM vs abracadabra на одном и том же коде.

## Структура эксперимента

```
benchmarks/NNN_название/
├── BRIEF.md        ← задание (единый вход для обоих прогонов)
├── meta.yml        ← модель, версия, GT, task_class, task_config
├── baseline.md     ← результат vanilla-агента
├── abra.md         ← результат abra-агента
├── verdict.md      ← ослеплённый арбитраж
└── results/        ← мульти-модельные прогоны (bench runner)
    ├── COMPARISON.md           ← сводная таблица + выводы
    └── <model>_<kb>/           ← результаты по модели
        ├── baseline.md
        ├── abra.md
        ├── verdict.md
        └── metrics.yml         ← токены, cost, objective metrics
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

### 2. Bench Runner (мульти-модельный, API + CLI)

```bash
pip install -r bench/requirements.txt

# Code audit (verdict через модель-судью)
python -m bench.runner 003 --model gemini/gemini-2.5-flash --tag test
python -m bench.runner 003 --model gemini/gemini-2.5-flash --abra --tag test
python -m bench.runner 003 --verdict --tag test

# Bug fix (объективные метрики — без судьи)
python -m bench.runner 004 --model claude-code/opus --tag opus-test

# Multi-judge (3 судьи из разных семейств, Cohen's kappa)
python -m bench.runner 003 --verdict --n-judges 3 --style-blind --tag test

# Opus через Claude Code подписку (без API-ключа)
python -m bench.runner 004 --model claude-code/opus --tag opus-test

# Сводная таблица
python -m bench.compare 004 --table-only
```

**Изоляция:** baseline и abra — два независимых stateless запроса. Разные system prompts, никакого общего состояния.

**Ослепление:** verdict-модель получает отчёты как «Report A» / «Report B» с рандомным маппингом. Деанонимизация после подсчёта метрик.

**Cross-judge:** `--n-judges 3` запускает 3 судей из разных семейств (Gemini, DeepSeek, Claude, OpenAI). Модель-производитель исключается из пула. Majority vote + Cohen's kappa для inter-rater reliability.

## Метрики

### Объективные (без судьи)

| Метрика | Классы задач |
|---------|-------------|
| `tests_pass` | bug_fix, refactor, greenfield, debug |
| `regression_free` | bug_fix, refactor |
| `compiles` | все code-producing |
| `diff_size` | bug_fix, refactor, debug |
| `gt_recall` | code_audit, code_review |
| `file_ref_valid` | code_audit, code_review |

### Субъективные (verdict, GT-free)

- **Верификация** — для каждой находки: `verified` / `plausible` / `false`
- **Precision** — verified / total
- **Weighted score** — critical=3, high=2, medium=1, low=0.5
- **Unique findings** — находки только одного отчёта

**GT (опционально):** если в `meta.yml` заполнен `ground_truth_bugs` — считается recall. GT привязан к коммиту и устаревает.

## Классы задач

| Класс | Метрики | Судья нужен? |
|-------|---------|:------------:|
| `code_audit` | findings, precision, severity, GT recall | да |
| `bug_fix` | tests_pass, regression_free, compiles, diff_size | **нет** |
| `refactor` | tests_pass, api_preserved, cyclomatic_delta | **нет** |
| `greenfield` | test_pass_ratio, lint_clean, LOC | **нет** |
| `code_review` | GT recall, precision, file_ref_valid | частично |
| `debug` | correct_root_cause, fix_tests_pass | частично |

Bug fix и refactor — **якорные классы**: оценка полностью объективная, тесты = Ground Truth.

## Реестр

| # | Проект | Класс | Модели | Результат | Данные |
|---|--------|-------|--------|-----------|--------|
| **001** | `isearch` | code_audit | Claude Opus 4.6 (interactive) | [abra wins](001_isearch_audit/verdict.md) | — |
| **002** | `isearch` | code_audit | Gemini 3.1 Pro (interactive) | *pending* | — |
| **003** | `isearch` | code_audit | 7 моделей × 2 KB (API) | **abra 6 / baseline 7 / tie 1** | [Таблица](003_isearch_audit_slim/results/COMPARISON.md) |
| **004** | `isearch` | bug_fix | Opus + Gemini Flash | **abra 0 / baseline 2** | [Таблица](004_isearch_bugfix_hash/results/COMPARISON.md) |
| **005** | `isearch` | refactor | Opus + Gemini Flash (×3 фазы) | **все 0 (one-shot)** | [Таблица](005_isearch_refactor_dedup/results/COMPARISON.md) |

### Bench 003: Code Audit (14 прогонов)

7 моделей × 2 KB (slim 33KB / full 75KB). Ослеплённый verdict.

| Вывод | Детали |
|-------|--------|
| Full KB вредит флагманам | Lost in the Middle — compute на фреймворк вместо поиска багов |
| Full KB помогает mid-tier | CoT-рельсы для моделей со слабой внутренней структурой |
| Slim KB оптимален | Для флагманов 33KB > 75KB |
| Abra ≈ baseline в API | Сила abra — в интерактивной маршрутизации, не в промпте |

### Bench 004: Bug Fix (2 модели)

Объективная оценка: apply patch → run tests → regression check. Судья не нужен.

| Вывод | Детали |
|-------|--------|
| Оба Opus варианта прошли | Baseline 11 строк / $0.06, abra 13 строк / $0.70 — baseline в 12× дешевле |
| Gemini abra провалился | Thinking model потратил токены на рассуждения, не сгенерировал патч |
| Abra вреден для bug fix | Clear-домен — конкретная задача, бинарный критерий. Фреймворк = overhead |

### Bench 005: Refactor (6 прогонов, cadabra)

Opus + Gemini Flash × 3 фазы (baseline / abra / cadabra). Консолидация 3× дублированной gitignore логики.

| Вывод | Детали |
|-------|--------|
| **One-shot refactor невозможен** | Все 6 прогонов: patch applied ✅, tests ✗. Модели создают правильную архитектуру, но ломают import paths |
| Cadabra в API = abra + 1 вызов | Без файловой системы и тестов retry loop не работает |
| Gemini abra снижает CC | CC Δ-7.7 (лучшая архитектура), но compiles=False |
| Рефакторинг = интерактивный агент | Нужен цикл: patch → test → fix → retry |

### Bench 005: Cadabra vs GSD (интерактивный режим)

API-режим = 0% success. Интерактивный режим — cadabra vs GSD-агент (монолитный агент: «ты сеньор, пиши код, гоняй тесты, чини ошибки»).

| Метрика | GSD + Tools | Cadabra + Tools |
|---------|:-----------:|:---------------:|
| tests_pass | ❌ (0%) | ✅ (100%) |
| API preserved | ❌ | ✅ |
| diff size | ~350–400 LOC | ~80 LOC |
| cost | ~$0.30 | ~$0.08 |

**Почему GSD проваливается:** Context Bloat (стэктрейсы вымывают задачу), мутация API (оптимизирует «зелёный свет», не обратную совместимость), зомби-циклы ($1.50 до max_turns), `O(n × expensive)`.

**Почему cadabra работает:** EXECUTION_STATE.md — внешний файл, не вымывается. DAG + Kill Box + retry budget = физические законы итерации. `O(1 × expensive + n × cheap)`.

### Кросс-задачные выводы

| Класс задачи | Cynefin | Оптимальный подход | Почему |
|-------------|---------|-------------------|--------|
| Code Audit | Complex | abra ≈ GSD | Abra помогает слабым моделям |
| Bug Fix | Clear | GSD (vanilla) | Задача конкретная, фреймворк = overhead |
| Refactor | Complicated | **abra → cadabra** | GSD: Context Bloat, мутация API, зомби-циклы |
| *Greenfield* | *Complex* | *гипотеза: abra* | *Approval Gate + Октагон для trade-off* |

**Главный вывод:** abracadabra = cost router для агентных задач. GSD: `O(n × expensive)`. Cadabra: `O(1 × expensive + n × cheap)`. Ценность — не улучшение top-модели, а safe delegation на дешёвые модели.

---
*«Разница, которая не создаёт разницы в физическом мире, не имеет значения» (Фильтр 5: Джеймс).*
