# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это

**abracadabra** — моно-репо из двух AI-агентов, работающих в паре:
- **abra** — Архитектор. Когнитивный конвейер для анализа сложных задач и генерации Концептуальных Протоколов.
- **cadabra** — Исполнитель (Прораб). Получает машиночитаемый контракт (`EXECUTION_STATE.md`) от abra и автономно выполняет шаги.

Язык — русский. Технические термины на языке оригинала.

## Структура

```
abracadabra/
├── abra/                       ← Архитектор
│   ├── core_rules.md           ← системный промпт abra (роль, правила, workflow)
│   ├── docs/
│   │   ├── 01_БАЗА_ЗНАНИЙ/     ← Октагон (8 осей Red Teaming)
│   │   ├── 02_ИНСТРУМЕНТЫ/     ← алгоритм (Фазы 0–6), шаблон протокола, автономный пайплайн, EXECUTION_STATE
│   │   └── 03_РЕШЕНИЯ/         ← готовые протоколы
│   └── scripts/
│       └── sync_context.sh     ← синхронизация контекста (v6.0)
├── cadabra/                    ← Исполнитель
│   ├── core_rules.md           ← системный промпт cadabra
│   └── docs/
│       └── 02_ФОРМАТ_ERROR_LOG.md ← спецификация обратного канала
├── benchmarks/                 ← Eval Suite: A/B-тесты abra vs vanilla LLM
├── bench/                      ← Bench Runner: мульти-модельный раннер (Python + LiteLLM)
├── .rules                      ← симлинк → abra/core_rules.md (для Zed)
├── .cursorrules                ← симлинк → abra/core_rules.md (для Cursor)
├── CLAUDE.md                   ← этот файл
└── README.md
```

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

Контракт исполнителя: `abra/docs/02_ИНСТРУМЕНТЫ/06_ШАБЛОН_EXECUTION_STATE.md` — машиночитаемый артефакт с METADATA, CONTEXT, KILL BOX, DAG, ERROR_LOG, COMPLETION_PROOF + правила оркестрации.

## Bench Runner

`bench/` — Python-раннер для мульти-модельных A/B тестов через LiteLLM. Зависимости: `litellm`, `pyyaml`.

```bash
python -m bench.runner NNN --model MODEL [--abra] [--full-kb] [--verdict] [--tag TAG]
python -m bench.compare NNN [--full-kb] [--table-only]
```

Результаты в `benchmarks/NNN_*/results/<tag>/`. Сводка — `COMPARISON.md`.
