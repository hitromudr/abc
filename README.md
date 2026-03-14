# abracadabra

[![Version](https://img.shields.io/badge/version-3.2-green.svg)](CHANGELOG.md)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Cost router для агентных задач — дорогая модель думает один раз, дешёвая исполняет.**

GSD-агент (Get Shit Done — стандартный паттерн Claude Code / Cursor) — монолит: одна модель одновременно архитектор, кодер и дебаггер. GSD+Opus справляется с Complicated-задачами, но стоит дорого. GSD+дешёвая модель — проваливается: теряет контекст, ломает API, сжигает бюджет в зомби-циклах.

abracadabra разделяет роли: **abra** (архитектор) создаёт план с ограничениями (DAG + Kill Box + retry budget), **cadabra** (исполнитель) методично итерирует по плану. Результат: дешёвая модель с cadabra решает задачу с 100% success rate vs 0% у GSD. Сильная модель с cadabra — 3× быстрее GSD.

## Два агента, разделение ролей

- **abra** (Архитектор, `O(1)` вызов дорогой модели) — прогоняет задачу через [конвейер](abra/docs/02_ИНСТРУМЕНТЫ/01_АЛГОРИТМ_РАЗБОРА_ЗАДАЧИ.md) (Фазы 0–6) и 8 инженерных осей [Октагона](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md). Генерирует [EXECUTION_STATE.md](abra/docs/02_ИНСТРУМЕНТЫ/06_ШАБЛОН_EXECUTION_STATE.md) — архитектурный контракт с DAG, Kill Box и retry budget.
- **cadabra** (Исполнитель, `O(n)` итераций дешёвой модели) — методично исполняет контракт шаг за шагом. Не может выйти за Kill Box, не может перескочить шаги DAG, останавливается при исчерпании retry budget.

```
Оператор → abra init → [Ядро загружено] → abra [задача] → Концептуальный Протокол → Approval Gate
                                                                                         ↓
                                           Оператор утверждает → abra генерирует EXECUTION_STATE.md
                                                                                         ↓
                                           cadabra [путь к EXECUTION_STATE.md] → DAG → верификация → done/blocked
```

## Эмпирика: где abra работает, а где нет

22 контролируемых A/B тестов по 3 классам задач. Ослеплённый verdict, верификация по коду и тестам.

### Bench 003 — Code Audit (security/architecture)

[14 прогонов](benchmarks/003_isearch_audit_slim/results/COMPARISON.md): 7 моделей (Gemini 2.5–3.1, DeepSeek) × 2 режима KB (slim 33KB / full 75KB). Проект: isearch (~3K строк Python), 4 Ground Truth бага.

**Итого: abra 6 / baseline 7 / tie 1**

| Модель | Slim KB | Full KB |
|--------|---------|---------|
| DeepSeek Chat | baseline | **abra** |
| Gemini 2.5 Flash | **abra** | **abra** |
| Gemini 2.5 Pro | **abra** | baseline |
| Gemini 3 Flash | baseline | **abra** |
| Gemini 3 Pro | baseline | **abra** |
| Gemini 3.1 Flash Lite | **abra** | baseline |
| Gemini 3.1 Pro | tie | baseline |

Средние ресурсы: baseline $0.13 / 65s, abra $0.24 / 112s (+88% cost, +71% time).

### Bench 004 — Bug Fix (объективные метрики)

[2 прогона](benchmarks/004_isearch_bugfix_hash/results/COMPARISON.md): Opus (Claude Code) и Gemini 2.5 Flash. Задача: заменить недетерминистичный `hash()` на SHA-256 для генерации point ID. Оценка полностью автоматическая — apply patch → run tests → regression check.

**Итого: abra 0 / baseline 2 / tie 0**

| Модель | Baseline | Abra |
|--------|----------|------|
| Opus | ✅ tests pass, 11 строк, $0.06 | ✅ tests pass, 13 строк, $0.70 |
| Gemini 2.5 Flash | ✅ tests pass, 26 строк, $0.04 | ✗ не извлёк патч |

Opus: оба прошли, baseline компактнее и в 12× дешевле. Gemini: abra KB заблокировала генерацию патча (thinking model потратил все токены на рассуждения).

### Bench 005 — Refactor (Complicated-домен, cadabra)

[6 прогонов](benchmarks/005_isearch_refactor_dedup/results/COMPARISON.md): Opus и Gemini Flash × 3 фазы (baseline / abra / cadabra). Задача: консолидировать 3 дублированных реализации `.gitignore` и file type classification в единый модуль. Первый тест cadabra (abra→EXECUTION_STATE→cadabra→patch).

**Итого: ни одна модель не решила задачу в one-shot API**

| Модель | Baseline | Abra | Cadabra |
|--------|----------|------|---------|
| Opus | patch ✅, tests ✗, 100 строк, $0.71 | patch ✅, tests ✗, 90 строк, $0.75 | patch ✅, tests ✗, 90 строк, $0.74 |
| Gemini Flash | patch ✅, tests ✗, 186 строк, $0.06 | patch ✅, tests ✗, CC Δ-7.7, $0.08 | patch ✅, tests ✗, CC Δ-7.2, $0.10 |

Все модели создали `file_utils.py` и перенесли логику, но сломали Python import paths (`from src.file_utils import ...` не работает в sandbox). Рефакторинг в one-shot без интерактивной обратной связи (run tests → fix → retry) невозможен.

Cadabra в API-режиме = abra + один дополнительный вызов. Без доступа к файловой системе и тестам cadabra не может выполнить свой retry loop (правило RETRY BUDGET: 3 попытки починить после красного теста).

### Bench 005 — Cadabra vs GSD (интерактивный режим)

#### Сильная модель (Opus)

| Метрика | GSD + Opus | Cadabra + Opus |
|---------|:----------:|:--------------:|
| tests_pass | ✅ 19/19 | ✅ 19/19 |
| API preserved | ✅ | ✅ |
| diff (changed lines) | 277 | 266 |
| tool calls | 42 | 30 |
| duration | 987s | 307s |

**Оба справились.** GSD+Opus решает задачу. Cadabra компактнее (3× быстрее, -29% tool calls).

#### Дешёвая модель (Flash)

| Метрика | GSD + Flash | Cadabra + Flash |
|---------|:-----------:|:---------------:|
| tests_pass | ❌ (0%) | ✅ (100%) |
| API preserved | ❌ | ✅ |
| diff size | ~350–400 LOC | ~80 LOC |
| cost | ~$0.30 | ~$0.08 |

**GSD проваливается:** Context Bloat (стэктрейсы вымывают задачу), мутация API (нет Kill Box), зомби-циклы (нет retry budget).

**Cadabra работает:** EXECUTION_STATE.md — внешний файл, не вымывается. DAG + Kill Box + retry budget = физические законы. `O(1 × expensive + n × cheap)`.

**Ключевой вывод:** cadabra не побеждает сильную модель по качеству — он позволяет заменить её на дешёвую без потери результата.

### Сводные выводы

**1. Раздутые промпты мертвы для новых моделей.**
Full KB (75KB) = DDoS на окно внимания флагманов. Slim KB (33KB) оптимален.

| KB | abra wins | baseline wins | tie |
|----|-----------|---------------|-----|
| Slim (33KB) | 3 | 3 | 1 |
| Full (75KB) | 4 | 3 | 0 |

**2. Alignment Tax: abra помогает слабым, мешает сильным.**
Слабые модели получают CoT-рельсы. Флагманы уже интернализировали структурное мышление — дополнительный контекст отвлекает.

**3. GSD оптимален для Clear-задач.**
Bug fix — задача конкретная, критерий бинарный. Фреймворк = overhead. GSD решает за $0.04–0.06.

**4. GSD+Opus работает на Complicated, но дороже.**
Сильная модель удерживает контекст без рельс. GSD+Opus решил bench 005 (19/19 тестов), но: 987s и 42 tool calls vs cadabra 307s и 30 tool calls.

**5. Cadabra делает дешёвые модели надёжными на Complicated.**
Flash+cadabra: 100% success, $0.08. Flash+GSD: 0% success, $0.30. Cadabra не побеждает Opus по качеству — он позволяет заменить Opus на Flash без потери результата.

**6. Cynefin-маппинг (эмпирически подтверждён).**

| Класс | Cynefin | Сильная модель | Дешёвая модель |
|-------|---------|----------------|----------------|
| Code Audit | Complex | GSD ≈ abra | abra помогает |
| Bug Fix | Clear | GSD ✅ | GSD ✅ |
| Refactor | Complicated | GSD ✅ (медленнее) / Cadabra ✅ | GSD ❌ / **Cadabra ✅** |

### Непроверенные классы задач

| Класс | Пример | Гипотеза |
|-------|--------|----------|
| Greenfield-архитектура | «Спроектируй систему уведомлений» | Approval Gate + Октагон дадут максимальный эффект |
| Дебаг production | «500-ки на /api/orders после деплоя» | Grounding-фильтр отсечёт галлюцинации |
| Code review | «Ревью PR #142» | Октагон как чеклист осей проверки |

Каждый класс требует отдельного бенчмарка с релевантным проектом и Ground Truth.

**[Данные bench 003](benchmarks/003_isearch_audit_slim/results/COMPARISON.md)** | **[Данные bench 004](benchmarks/004_isearch_bugfix_hash/results/COMPARISON.md)** | **[Методология](benchmarks/README.md)**

## Quick Start

### Внедрение в проект (основной сценарий)

1. Добавьте `abracadabra` как сабмодуль:

```bash
git submodule add https://github.com/hitromudr/abc.git .abracadabra
```

2. Подключите системные правила:

```bash
# Zed
echo 'Прочитай файл .abracadabra/abra/core_rules.md и следуй его инструкциям.' >> .rules

# Cursor
echo 'Прочитай файл .abracadabra/abra/core_rules.md и следуй его инструкциям.' >> .cursorrules

# Claude Code
echo 'Прочитай файл .abracadabra/abra/core_rules.md и следуй его инструкциям.' >> CLAUDE.md
```

3. Инициализация:

```
abra init
```

4. Задача:

```
abra [описание задачи]
```

5. Исполнение (после утверждения протокола):

```
cadabra .work/EXECUTION_STATE.md
```

### Только анализ (любой web-чат)

Скачайте [`03_АВТОНОМНЫЙ_ПАЙПЛАЙН.md`](abra/docs/02_ИНСТРУМЕНТЫ/03_АВТОНОМНЫЙ_ПАЙПЛАЙН.md) и прикрепите в чат:

| Площадка | Модель | Как запустить |
|---|---|---|
| [ChatGPT](https://chatgpt.com) | GPT-4o | Прикрепите файл → задача |
| [Claude.ai](https://claude.ai) | Sonnet | Прикрепите файл → задача |
| [Google AI Studio](https://aistudio.google.com) | Gemini 3.1 Pro | System Instructions → вставьте текст → задача. [Готовый промпт](https://aistudio.google.com/prompts/15dRzT0yfD1XkMtRmeHnfptfBg_ez8mp0) |
| [DeepSeek](https://chat.deepseek.com) | DeepSeek-R1 | Прикрепите файл → задача |
| [Grok](https://grok.com) | Grok 3 | Прикрепите файл → задача |

### Bench Runner (мульти-модельное тестирование)

Мульти-модельный раннер бенчмарков с 6 классами задач, объективными метриками и multi-judge verdict:

```bash
pip install -r bench/requirements.txt

# Baseline + abra + verdict
python -m bench.runner 003 --model gemini/gemini-2.5-flash --tag my-test
python -m bench.runner 003 --model gemini/gemini-2.5-flash --abra --tag my-test
python -m bench.runner 003 --verdict --tag my-test

# Bug fix (объективные метрики — тесты вместо судьи)
python -m bench.runner 004 --model claude-code/opus --tag opus-test

# Multi-judge verdict (3 судьи, Cohen's kappa)
python -m bench.runner 003 --verdict --n-judges 3 --style-blind --tag my-test

# Opus/Sonnet через Claude Code подписку (без API-ключа)
python -m bench.runner 004 --model claude-code/opus --tag opus-test
python -m bench.runner 004 --model claude-code/sonnet --tag sonnet-test

# Массовый прогон + сводная таблица
python -m bench.compare 003 --table-only
```

**Классы задач:** `code_audit`, `bug_fix`, `refactor`, `greenfield`, `code_review`, `debug`. Задаётся в `meta.yml` бенчмарка (`task_class`). Bug fix и debug оцениваются полностью объективно (apply patch → run tests).

**Провайдеры:** Gemini, Claude (API и CLI), OpenAI, DeepSeek, Mistral, OpenRouter (100+ моделей). API-ключи через env vars. Claude Code — через подписку (`claude-code/opus`).

## GSD vs cadabra

**Задача:** *«Консолидируй 3 дублированных реализации .gitignore в единый модуль»*

**GSD + Opus:** ✅ справился. 19/19 тестов, 277 LOC diff, 42 tool calls, 987s.
**Cadabra + Opus:** ✅ справился. 19/19 тестов, 266 LOC diff, 30 tool calls, 307s. **3× быстрее.**

Сильная модель справляется в обоих режимах. Но что происходит с дешёвой?

**GSD + Flash (дешёвая модель):**
```
Turn 1: Создаёт file_utils.py, переносит логику          ← правильно
Turn 2: pytest → ImportError                               ← первый красный тест
Turn 3: Правит import → другой тест падает                 ← паника
Turn 4: Переписывает тест (!) чтобы проходил               ← нет Kill Box
Turn 5: «Заодно улучшу API build_graph()»                  ← scope creep
Turn 6–12: fix→break→fix→break...                          ← зомби-цикл
Итого: 350 LOC diff, API сломан, тесты переписаны, $0.30, ❌
```

**Cadabra + Flash (та же дешёвая модель + EXECUTION_STATE.md):**
```
Step 1/6: read sources                                     ← DAG
Step 2/6: create file_utils.py → py_compile OK             ← локальная верификация
Step 3/6: refactor index.py → py_compile OK                ← атомарный шаг
Step 4/6: refactor services.py → py_compile OK             ← Kill Box: API не тронут
Step 5/6: refactor graph_builder.py → py_compile OK        ← py_compile на каждом шаге
Step 6/6: pytest → 19/19 green                             ← COMPLETION_PROOF
Итого: 80 LOC diff, API сохранён, тесты зелёные, $0.08, ✅
```

**Cadabra не побеждает Opus — он позволяет заменить Opus на Flash.**

## До / После (abra — аналитические задачи)

**Задача:** *"У нас микросервисы тормозят, что делать?"*

**Без abracadabra:**
> "Рекомендую оптимизировать запросы к базе данных, внедрить кеширование Redis, рассмотреть переход на gRPC..."

Шаблонный список без диагностики.

**С abracadabra:**
> **Задача отклонена (Фаза 0).** Отсутствуют метрики: p99 latency, RPS, flamegraph. "Тормозят" — языковая иллюзия. Предоставьте: 1) трейс медленного запроса, 2) график latency, 3) CPU/RAM на узлах.

## Когда НЕ использовать (GSD оптимален)

- **Clear-задача** — баг-фикс, известное решение. GSD в 12× дешевле
- **Задача творческая** — нарратив, дизайн, брейншторм
- **Нужна скорость** — ответ за 10 секунд
- **Нужен разговор** — обсуждение, размышление вслух

## Структура

| Путь | Описание |
|------|----------|
| [`abra/core_rules.md`](abra/core_rules.md) | Системный промпт Архитектора |
| [`abra/docs/01_БАЗА_ЗНАНИЙ/`](abra/docs/01_БАЗА_ЗНАНИЙ/) | [Октагон](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md) (8 осей Red Teaming) |
| [`abra/docs/02_ИНСТРУМЕНТЫ/`](abra/docs/02_ИНСТРУМЕНТЫ/) | [Конвейер](abra/docs/02_ИНСТРУМЕНТЫ/01_АЛГОРИТМ_РАЗБОРА_ЗАДАЧИ.md), [Шаблон протокола](abra/docs/02_ИНСТРУМЕНТЫ/02_ШАБЛОН_ИТОГОВОГО_ПРОТОКОЛА.md), [Автономный пайплайн](abra/docs/02_ИНСТРУМЕНТЫ/03_АВТОНОМНЫЙ_ПАЙПЛАЙН.md), [EXECUTION_STATE](abra/docs/02_ИНСТРУМЕНТЫ/06_ШАБЛОН_EXECUTION_STATE.md) |
| [`abra/docs/03_РЕШЕНИЯ/`](abra/docs/03_РЕШЕНИЯ/) | Библиотека протоколов |
| [`cadabra/`](cadabra/) | Исполнитель: [системный промпт](cadabra/core_rules.md), [формат ошибок](cadabra/docs/02_ФОРМАТ_ERROR_LOG.md) |
| [`benchmarks/`](benchmarks/) | [Eval Suite](benchmarks/README.md): A/B-тесты abra vs vanilla LLM |
| [`bench/`](bench/) | [Bench Runner](bench/): мульти-модельный раннер бенчмарков |
| `.rules` / `.cursorrules` | Симлинки → `abra/core_rules.md` |

## Лицензия

[MIT](LICENSE)
