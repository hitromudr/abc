# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это

**abracadabra** — cost router для агентных задач. Дорогая модель думает один раз, дешёвая исполняет.

Два AI-агента работают в паре:
- **abra** — Архитектор. Когнитивный конвейер (Фазы 0–6 + Октагон) → Концептуальный Протокол → `EXECUTION_STATE.md`.
- **cadabra** — Исполнитель. Получает `EXECUTION_STATE.md` и автономно выполняет DAG-шаги с Kill Box, retry budget и локальной верификацией.

Язык — русский. Технические термины на языке оригинала.

## Структура

```
abracadabra/
├── abra/                       ← Архитектор
│   ├── core_rules.md           ← системный промпт abra (роль, правила, workflow)
│   ├── docs/
│   │   ├── 01_БАЗА_ЗНАНИЙ/     ← Октагон (8 осей Red Teaming)
│   │   ├── 02_ИНСТРУМЕНТЫ/     ← алгоритм (Фазы 0–6), шаблон протокола, EXECUTION_STATE
│   │   └── 03_РЕШЕНИЯ/         ← готовые протоколы
│   └── scripts/
│       └── sync_context.sh     ← синхронизация контекста
├── cadabra/                    ← Исполнитель
│   ├── core_rules.md           ← системный промпт cadabra
│   └── docs/
│       └── 02_ФОРМАТ_ERROR_LOG.md ← спецификация обратного канала
├── benchmarks/                 ← Eval Suite: A/B-тесты abra vs vanilla LLM
├── bench/                      ← Bench Runner: мульти-модельный раннер (Python + LiteLLM)
├── .rules                      ← симлинк → abra/core_rules.md (для Zed)
├── .cursorrules                ← симлинк → abra/core_rules.md (для Cursor)
└── README.md
```

## Архитектура pipeline

```
Оператор → abra init → [Ядро загружено] → abra [задача] → Концептуальный Протокол → Approval Gate
                                                                                        ↓
                                          Оператор утверждает → EXECUTION_STATE.md
                                                                                        ↓
                                          cadabra [путь] → DAG step-by-step → done/blocked
```

**abra** загружает 4 файла ядра (slim, ~33KB) или 15 файлов (full, ~75KB). Bench 003 показал: full KB помогает mid-tier моделям, но может снижать качество флагманов (Lost in the Middle). Slim — дефолт.

**cadabra** — «слепой голем»: не проектирует, не анализирует, только исполняет атомарные шаги DAG. Инварианты: SCOPE_ISOLATION (только файлы из approved scope), KILL_BOX (запрещённые действия), RETRY_BUDGET (макс. 3 попытки починить шаг, потом `blocked`). Статусы: `draft` → `approved` → `in_progress` → `done` | `blocked`.

**EXECUTION_STATE.md** — машиночитаемый контракт: METADATA, CONTEXT, KILL BOX, DAG, ERROR_LOG, COMPLETION_PROOF.

## Заметки по совместимости

- `.rules` и `.cursorrules` — симлинки на `abra/core_rules.md`. Подхватываются Zed и Cursor соответственно.
- `abra` — текстовый ключ в промпте: AI распознаёт его из `.rules` и запускает pipeline. **ВАЖНО:** Последующие уточнения пишутся **БЕЗ** префикса `abra`.
- Автономный пайплайн (`abra/docs/02_ИНСТРУМЕНТЫ/03_АВТОНОМНЫЙ_ПАЙПЛАЙН.md`) — сжатая версия для web-чатов.

## Правила из .rules (фактические)

1. **NO YAPPING** — запрещены преамбулы, извинения, клише. Только сигнал.
2. **THOUGHT PROCESS** — внутренний монолог в `<thought_process>` перед любым финальным ответом.
3. **GROUNDING** — без метрик/логов задача отклоняется. Абстракция обязана разворачиваться в физический факт.
4. **APPROVAL GATE** — запрещено выбирать архитектурный путь за оператора.
5. **ГРАНИЦЫ ПРИМЕНИМОСТИ** — конвейер НЕ запускается на: Clear-домен, творческие задачи, задачи на скорость/интуицию.

## Формат протоколов

Выходной документ по шаблону `abra/docs/02_ИНСТРУМЕНТЫ/02_ШАБЛОН_ИТОГОВОГО_ПРОТОКОЛА.md`: Топология, Инварианты, Точка опоры, Векторы энтропии, Алгоритм стабилизации, Метрика истины, Эвристики, Резолюция (+ секция 8.1: генерация EXECUTION_STATE для cadabra), Верификация.

## Bench Runner

`bench/` — мульти-модельный раннер бенчмарков. 6 классов задач, объективные метрики, multi-judge verdict.

### Зависимости и настройка

```bash
pip install -r bench/requirements.txt   # litellm, pyyaml
```

API-ключи — через стандартные env vars провайдеров LiteLLM: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY` и т.д. Claude Code CLI-модели (`claude-code/opus`, `claude-code/sonnet`) работают через подписку без API-ключа.

### Команды

```bash
# Baseline прогон
python -m bench.runner NNN --model MODEL --tag TAG

# Abra прогон (с контекстом KB)
python -m bench.runner NNN --model MODEL --abra [--full-kb] --tag TAG

# Ослеплённый verdict (A/B арбитраж)
python -m bench.runner NNN --verdict --n-judges 3 --style-blind --tag TAG

# Мульти-модельное сравнение → COMPARISON.md
python -m bench.compare NNN [--full-kb] [--table-only]
```

Дополнительные флаги runner: `--project PATH` (override проекта из meta.yml), `--max-context N` (лимит символов контекста, 0=без лимита), `--max-turns N` (макс. итераций CLI-агента, default 10), `--timeout N` (таймаут вызова модели в секундах, default 600).

### Модели

LiteLLM формат: `gemini/gemini-2.5-flash`, `deepseek/deepseek-chat`, `openrouter/...`.
CLI-агенты (интерактивный режим с доступом к FS и тестам): `claude-code/opus`, `claude-code/sonnet`, `qwen-code/coder`, `gemini-code/gemini-2.5-pro`. Определяются по префиксу в `models.py:is_cli_model()`.

### Классы задач

`code_audit`, `bug_fix`, `refactor`, `greenfield`, `code_review`, `debug`. Задаётся в `meta.yml` бенчмарка (`task_class`). Bug fix и debug оцениваются объективно (apply patch → run tests → regression check).

### Результаты

Хранятся в `benchmarks/NNN_*/results/<tag>/`. Сводка — `benchmarks/NNN_*/results/COMPARISON.md`.

### Архитектура bench/

- `runner.py` — CLI entry point: baseline / abra / cadabra / verdict фазы
- `models.py` — бэкенд: LiteLLM API + CLI subprocess (claude-code/, qwen-code/, gemini-code/)
- `task_class.py` → `registry.py` → `tasks/` — абстрактная база, реестр, реализации 6 классов
- `executors.py` — песочница: apply patch → run tests (tmpdir isolation)
- `judges.py` — multi-judge: cross-family exclusion, majority vote, Cohen's kappa
- `verdict.py` + `metrics.py` — ослеплённый A/B арбитраж + извлечение JSON
- `statistics.py` — bootstrap CI, Mann-Whitney U, composite score
- `pareto.py` — Pareto frontier: quality × cost × speed
- `cadabra_runtime.py` — парсер EXECUTION_STATE для API-уровня cadabra

**Два режима оценки:**
- **Objective** (bug_fix, refactor, debug): `ExecutionSandbox` применяет патч → запускает тесты → regression check. Автоматический вердикт без LLM-судьи.
- **Subjective** (code_audit, code_review): LLM-судья в ослеплённом A/B-режиме, multi-judge с Cohen's kappa.

Режим определяется наличием метода `evaluate_objective()` в TaskClass.

### Создание нового бенчмарка

```
benchmarks/NNN_описание/
├── meta.yml          ← task_class, project_path, ground_truth, verdict_model
├── BRIEF.md          ← задание для модели
└── results/          ← результаты прогонов (автогенерация)
    ├── <tag>/        ← baseline.md, abra.md, verdict.md, metrics.yml
    └── COMPARISON.md ← сводная таблица (bench.compare)
```

`meta.yml` обязателен. Поле `task_class` определяет pipeline оценки (default: `code_audit`).

### Добавление нового task class

1. Создать `bench/tasks/my_task.py` с классом, наследующим `TaskClass` (ABC из `task_class.py`)
2. Реализовать `build_baseline_prompt()` и `build_abra_prompt()`
3. Для объективной оценки — переопределить `evaluate_objective()`
4. Зарегистрировать в `bench/registry.py` → `TASK_CLASSES`

## Cynefin-маппинг (эмпирически подтверждён)

| Класс | Cynefin | Сильная модель | Дешёвая модель |
|-------|---------|----------------|----------------|
| Code Audit | Complex | GSD ≈ abra | abra помогает |
| Bug Fix | Clear | GSD ✅ | GSD ✅ |
| Refactor | Complicated | GSD ✅ (медленнее) / Cadabra ✅ | GSD ❌ / **Cadabra ✅** |
