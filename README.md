# abracadabra

[![Version](https://img.shields.io/badge/version-3.2-green.svg)](CHANGELOG.md)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Когнитивный экзоскелет для LLM — жесткая архитектура вместо промпт-инженерии.**

LLM без ограничений — океан энтропии: галлюцинации, context rot, слепая угодливость. abracadabra накладывает архитектурные печати — когнитивные фильтры, инженерные оси и матрицы выживания, — заставляя модель работать по законам вашей физики.

## Два агента, один ритуал

- **abra** (Архитектор) — блокирует немедленную генерацию кода, прогоняет задачу через [конвейер](abra/docs/02_ИНСТРУМЕНТЫ/01_АЛГОРИТМ_РАЗБОРА_ЗАДАЧИ.md) (Фазы 0–6) и 8 инженерных осей [Октагона](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md). Если задача — иллюзия, `abra` её уничтожит. Если реальна — выкует архитектурный контракт.
- **cadabra** (Исполнитель) — берёт [контракт](abra/docs/02_ИНСТРУМЕНТЫ/06_ШАБЛОН_EXECUTION_STATE.md) от `abra` и методично исполняет шаг за шагом.

```
Оператор → abra init → [Ядро загружено] → abra [задача] → Концептуальный Протокол → Approval Gate
                                                                                         ↓
                                           Оператор утверждает → abra генерирует EXECUTION_STATE.md
                                                                                         ↓
                                           cadabra [путь к EXECUTION_STATE.md] → DAG → верификация → done/blocked
```

## Эмпирика: где abra работает, а где нет

16 контролируемых A/B тестов по 2 классам задач. Ослеплённый verdict, верификация по коду и тестам.

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

### Сводные выводы

**1. Раздутые промпты мертвы для новых моделей.**
Full KB (75KB) = DDoS на окно внимания флагманов. Slim KB (33KB) оптимален.

| KB | abra wins | baseline wins | tie |
|----|-----------|---------------|-----|
| Slim (33KB) | 3 | 3 | 1 |
| Full (75KB) | 4 | 3 | 0 |

**2. Alignment Tax: abra помогает слабым, мешает сильным.**
Слабые модели получают CoT-рельсы. Флагманы уже интернализировали структурное мышление — дополнительный контекст отвлекает.

**3. Abra вредит на code generation задачах.**
Bug fix — Clear-домен: задача конкретная, критерий успеха бинарный (тесты проходят или нет). Фреймворк добавляет overhead без прироста качества. Baseline-инструкция «исправь баг, выдай diff» — оптимальна.

**4. Ценность abra — не в промпте, а в маршрутизации.**
В zero-shot API (дёрнул модель → получил ответ) abra ≈ baseline. Сила раскрывается в **интерактивных агентных средах** (Claude Code, Cursor, Zed):
- Approval Gate останавливает перед необратимыми действиями
- EXECUTION_STATE.md изолирует зону поражения
- cadabra выполняет фикс атомарно и с тестами

**5. Класс задачи определяет эффект.**

| Класс | Результат | Эффект abra |
|-------|-----------|-------------|
| Code Audit | abra 6 / baseline 7 | ≈ паритет, помогает слабым моделям |
| Bug Fix | abra 0 / baseline 2 | вреден — overhead без прироста |

### Непроверенные классы задач

| Класс | Пример | Гипотеза |
|-------|--------|----------|
| Greenfield-архитектура | «Спроектируй систему уведомлений» | Approval Gate + Октагон дадут максимальный эффект |
| Рефакторинг legacy | «Разбей монолит на сервисы» | EXECUTION_STATE изолирует зону поражения |
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

## До / После

**Задача:** *"У нас микросервисы тормозят, что делать?"*

**Без abracadabra:**
> "Рекомендую оптимизировать запросы к базе данных, внедрить кеширование Redis, рассмотреть переход на gRPC..."

Шаблонный список без диагностики.

**С abracadabra:**
> **Задача отклонена (Фаза 0).** Отсутствуют метрики: p99 latency, RPS, flamegraph. "Тормозят" — языковая иллюзия. Предоставьте: 1) трейс медленного запроса, 2) график latency, 3) CPU/RAM на узлах.

## Когда НЕ использовать

- **Задача простая** — известное решение
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
