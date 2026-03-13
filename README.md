# abracadabra

[![Version](https://img.shields.io/badge/version-3.1-green.svg)](CHANGELOG.md)
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

14 контролируемых A/B тестов ([bench 003](benchmarks/003_isearch_audit_slim/results/COMPARISON.md)): 7 моделей (Gemini 2.5–3.1, DeepSeek, Mistral) × 2 режима KB (slim 33KB / full 75KB). Ослеплённый verdict, верификация каждой находки по коду.

**Итого: abra 6 / baseline 7 / tie 1** — в zero-shot API режиме abra не даёт статистического преимущества.

### Ключевые выводы

**1. Раздутые промпты мертвы для новых моделей.**
Full KB (75KB) работает как DDoS на окно внимания флагманов — модель тратит compute на соответствие фреймворку вместо поиска багов. Slim KB (33KB) даёт лучшие результаты на сильных моделях.

| KB | abra wins | baseline wins | tie |
|----|-----------|---------------|-----|
| Slim (33KB) | 3 | 3 | 1 |
| Full (75KB) | 4 | 3 | 0 |

**2. Abra помогает слабым, мешает сильным (Alignment Tax).**
Слабые модели получают "рельсы" от фреймворка (Chain of Thought инъекция). Флагманы уже интернализировали структурное мышление — дополнительный контекст отвлекает.

**3. Ценность abra — не в промпте, а в маршрутизации.**
В zero-shot API (дёрнул модель → получил ответ) abra ≈ baseline. Сила abra раскрывается в **интерактивных агентных средах** (Claude Code, Cursor, Zed), где:
- Approval Gate останавливает модель перед необратимыми действиями
- EXECUTION_STATE.md изолирует зону поражения
- cadabra выполняет фикс атомарно и с тестами

Baseline-агент найдёт баг и молча перепишет полфайла. `abra` найдёт тот же баг, но остановится, сгенерирует контракт и заставит исполнителя работать в заданных границах.

### Ограничения текущей эмпирики

Bench 003 проверяет **один класс задач** — security/architecture audit кодовой базы (~3K строк Python). Результаты не экстраполируются на другие домены.

**Непроверенные классы задач:**

| Класс | Пример | Гипотеза |
|-------|--------|----------|
| Greenfield-архитектура | «Спроектируй систему уведомлений» | Approval Gate + Октагон дадут максимальный эффект |
| Рефакторинг legacy | «Разбей монолит на сервисы» | EXECUTION_STATE изолирует зону поражения |
| Дебаг production | «500-ки на /api/orders после деплоя» | Grounding-фильтр отсечёт галлюцинации |
| Миграция стека | «Перевези с REST на gRPC» | cadabra-конвейер для пошагового исполнения |
| Code review | «Ревью PR #142» | Октагон как чеклист осей проверки |
| Оптимизация перформанса | «p99 latency > 2s» | Требование метрик на входе (Фаза 0) |
| Data pipeline дизайн | «ETL из 5 источников в DWH» | Матрица конфликтов для trade-off решений |
| Incident response | «База лежит, пользователи без данных» | Скорость vs глубина — возможно, overhead |

Каждый класс требует отдельного бенчмарка с релевантным проектом и Ground Truth.

**[Полные данные bench 003](benchmarks/003_isearch_audit_slim/results/COMPARISON.md)** | **[Методология](benchmarks/README.md)**

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

Code-based раннер для A/B тестов abra vs baseline на произвольных моделях через LiteLLM:

```bash
pip install -r bench/requirements.txt

# Baseline
python -m bench.runner 003 --model gemini/gemini-3.1-pro-preview --tag my-test

# Abra (slim KB)
python -m bench.runner 003 --model gemini/gemini-3.1-pro-preview --abra --tag my-test

# Abra (full KB)
python -m bench.runner 003 --model gemini/gemini-3.1-pro-preview --abra --full-kb --tag my-test

# Verdict
python -m bench.runner 003 --verdict --verdict-model gemini/gemini-2.5-flash --tag my-test

# Массовый прогон всех моделей + сводная таблица
python -m bench.compare 003
python -m bench.compare 003 --full-kb
python -m bench.compare 003 --table-only  # перегенерировать таблицу
```

Поддерживаемые провайдеры: Gemini, Claude, OpenAI, DeepSeek, Mistral, OpenRouter (100+ моделей). API-ключи через env vars (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`).

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
