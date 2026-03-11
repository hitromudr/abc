# abracadabra

🇬🇧 **English** | [🇷🇺 Русский](README.md)

[![Version](https://img.shields.io/badge/version-2.4.0-green.svg)](CHANGELOG.md)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Cognitive exoskeleton for LLMs — strict architecture instead of prompt engineering.**

LLMs without constraints are an ocean of entropy: hallucinations, context rot, and blind sycophancy. abracadabra applies architectural seals — a system of cognitive filters, cybernetic rituals, and survival matrices — forcing the model to operate according to the laws of your physics.

## Two agents, one ritual

abracadabra is a Two-Phase Commit architecture implementing the law of the [Double Helix](abra/docs/00_ИНИЦИАЛИЗАЦИЯ/02_ДВОЙНАЯ_СПИРАЛЬ_РАЗРАБОТКИ.md) (Process & Product):

- **abra** (Architect) creates the **Process**. It blocks the instinct of immediate code generation and runs the task through [8 philosophical filters](abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md) and 8 engineering axes of the [Octagon](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md). If the task is an illusion, `abra` destroys it. If it's real, it forges an architectural contract.
- **cadabra** (Executor) creates the **Product**. A blind golem-foreman: takes the [contract](abra/docs/02_ИНСТРУМЕНТЫ/06_ШАБЛОН_EXECUTION_STATE.md) from `abra` and methodically executes it step-by-step. On failure: 3 local repair attempts within the allowed Scope, then a hard stop and [return of control](abra/docs/02_ИНСТРУМЕНТЫ/07_ОРКЕСТРАЦИЯ_ЦИКЛА.md) to the Architect.

```
Operator → abra init → [Core loaded] → abra [task] → Conceptual Protocol → Approval Gate
                                                                               ↓
                                           Operator approves → abra generates EXECUTION_STATE.md
                                                                               ↓
                                           cadabra [path to EXECUTION_STATE.md] → DAG → validation → done/blocked
```

## Quick Start

### Integration into an existing project (Main Scenario)

abracadabra is a meta-framework. To solve product tasks, you need to connect it to your working repository.

1. Add `abracadabra` as a submodule to the root of your project. This creates a hidden `.abracadabra/` folder — all paths below are relative to it:

```bash
git submodule add https://github.com/hitromudr/abc.git .abracadabra
```

After running, your project root will contain:

```
your-project/
├── .abracadabra/        ← submodule (this repository)
│   ├── abra/
│   ├── cadabra/
│   └── CLAUDE.md
└── your code...
```

2. Connect the system rules to your AI editor:

| IDE | Setup (run in the root of your project) |
|---|---|
| **Zed** | `ln -s .abracadabra/abra/core_rules.md .rules` |
| **Cursor** | `ln -s .abracadabra/abra/core_rules.md .cursorrules` |
| **Claude Code** | `cp .abracadabra/CLAUDE.md .` |

### Analysis only (No installation required)

Download [`03_АВТОНОМНЫЙ_ПАЙПЛАЙН.md`](abra/docs/02_ИНСТРУМЕНТЫ/03_АВТОНОМНЫЙ_ПАЙПЛАЙН.md) and attach it to any LLM chat:

| Platform | Model | How to run |
|---|---|---|
| [ChatGPT](https://chatgpt.com) | GPT-4o | Attach file → write your task |
| [Claude.ai](https://claude.ai) | Sonnet | Attach file → write your task |
| [Google AI Studio](https://aistudio.google.com) | Gemini 2.5 Pro (1M context) | System Instructions → paste file content → write your task |
| [Grok](https://grok.com) | Grok 3 | Attach file → write your task |
| [Kimi](https://kimi.moonshot.cn) | Kimi (128K context) | Attach file → write your task |
| [DeepSeek](https://chat.deepseek.com) | DeepSeek-R1 | Attach file → write your task |
| [Qwen](https://chat.qwen.ai) | Qwen 3 | Attach file → write your task |

Want to create a ready-made bot (Coze, Telegram, HuggingChat)? See [DEPLOY.md](DEPLOY.md).

*Note: This runs only **abra** (analysis & protocol). For the full cycle (analysis + execution), an AI-IDE with file system access is required.*

**Step 1 — Core Initialization.** In a new chat, type:

```
abra init
```

The Agent will load the Knowledge Base into the context and reply "Core loaded. Waiting for task."

**Step 2 — Task Assignment.** After initialization, type:

```
abra [your task]
```

> **Can I just type `abra [task]` right away?** Yes. The Agent will split it into two tacts: load the core, ask you to press Continue, and only on the second step begin the analysis. But `abra init` → `abra [task]` is safer as you explicitly control the transition.
>
> **Why two tacts (Two-Step Boot)?** An LLM cannot simultaneously load 10+ architecture files and perform a high-quality analysis of a complex task. Combining them causes attention collapse — the model starts hallucinating frameworks from memory instead of reading the files. Separating I/O and CPU generation steps eliminates this hardware limitation.

**Step 3 — Execution.** After the protocol is approved by the Operator, the Architect generates a contract (usually in `.work/EXECUTION_STATE.md`). Open a new chat and launch the Executor:

```
cadabra .work/EXECUTION_STATE.md
```

`cadabra` will read the contract and begin executing the DAG.

## Before / After

**Task:** *"Our microservices are slow, what should we do?"*

**Without abracadabra** (typical LLM response):
> "I recommend optimizing database queries, implementing Redis caching, considering a move to gRPC, using connection pooling..."

A boilerplate list without diagnostics. It is unknown what exactly is slow.

**With abracadabra** (after passing through the pipeline):
> **Task rejected ([Phase 0](abra/docs/02_ИНСТРУМЕНТЫ/01_АЛГОРИТМ_РАЗБОРА_ЗАДАЧИ.md)).** Missing metrics: p99 latency, RPS, flamegraph, traces. "Slow" is a linguistic illusion ([Wittgenstein's Filter](abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md)). Provide: 1) a trace of a specific slow query, 2) a latency graph for the last week, 3) current CPU/RAM on the nodes.

`abra` forced the model *to refuse solving a non-existent problem* and demanded empirical physical data.

## When NOT to use

abracadabra is an exoskeleton, not a spacesuit. It is designed for tasks requiring decomposition (Complicated/Complex domains according to [Cynefin](abra/docs/01_БАЗА_ЗНАНИЙ/02_КОГНИТИВНЫЙ_ЛАНДШАФТ.md#7-фреймворк-cynefin-сноуден)). Do not run it if:

- **The task is simple** — known solution, 6 phases are not needed.
- **The task is creative** — narrative, design, brainstorming (formalization kills non-linear thinking).
- **Speed is required** — you need an answer in 10 seconds, not an architectural document.
- **You need a conversation** — discussing or thinking out loud.

## Key Mechanisms

[**8 Absolute Filters**](abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md#8-абсолютных-фильтров-реальности) — a pre-checklist for task invalidity:

| # | Filter | Question |
|---|---|---|
| 1 | [Wittgenstein (Language)](abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md#1-фильтр-витгенштейна-лингвистическая-валидность) | A real physical conflict or a language illusion? |
| 2 | [Descartes (Knowledge)](abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md#2-фильтр-декарта-радикальное-сомнение-и-аксиоматика) | What am I mathematically certain of? |
| 3 | [Seneca (Action)](abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md#3-фильтр-сенеки-локус-контроля) | Is this within my zone of control? |
| 4 | [Aristotle (Purpose)](abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md#4-фильтр-аристотеля-телеология--телос) | What is the true ultimate goal (Telos) of the system? |
| 5 | [James (Pragmatism)](abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md#5-фильтр-джеймса-прагматика) | Will the solution measurably change physical reality tomorrow? |
| 6 | [Hammurabi (Causality)](abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md#6-фильтр-хаммурапи-протокол-и-юрисдикция) | What fundamental contract was broken? |
| 7 | [Sun Tzu (Timing)](abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md#7-фильтр-сунь-цзы-кайрос--стратегический-тайминг) | Is now the right moment to act? |
| 8 | [Plato (Scale)](abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md#8-фильтр-платона-масштаб--уровень-абстракции) | Am I looking at the correct level of abstraction? |

[**Engineering Octagon**](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md) — 8 axes for validating any solution:
[Topology](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md#1-топология-и-мембрана-архитектура--api) → [Metabolism](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md#2-метаболизм-и-ресурсы-алгоритмическая-сложность--toc) → [Kinematics](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md#3-кинематика-стейт-машина--жизненный-цикл) → [Heredity](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md#4-наследственность-и-состояние-память--базы-данных) → [Immunity](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md#5-иммунитет-и-деградация-обработка-исключений--security) → [Homeostasis](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md#6-гомеостаз-телеметрия-и-кибернетика) → [Mutagenesis](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md#7-мутагенез-cicd--деплой--эволюция) → [Telos](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md#8-телос-метрика-остановки--бизнес-ценность)

[**The Double Helix**](abra/docs/00_ИНИЦИАЛИЗАЦИЯ/02_ДВОЙНАЯ_СПИРАЛЬ_РАЗРАБОТКИ.md) — every task must advance both the Product (the solution) and the Process (system improvement) simultaneously. One-off fixes are prohibited.

**Cross-domain Invariants** — fundamental laws from 6 areas ([thermodynamics](abra/docs/03_РЕШЕНИЯ/02_КРОСС_ДОМЕННЫЕ_ИНВАРИАНТЫ/001_ТЕРМОДИНАМИКА_И_МАТЕРИЯ.md), [cybernetics](abra/docs/03_РЕШЕНИЯ/02_КРОСС_ДОМЕННЫЕ_ИНВАРИАНТЫ/002_КИБЕРНЕТИКА_И_ТОПОЛОГИЯ.md), [biology](abra/docs/03_РЕШЕНИЯ/02_КРОСС_ДОМЕННЫЕ_ИНВАРИАНТЫ/003_ЭВОЛЮЦИЯ_И_БИОЛОГИЯ.md), [game theory](abra/docs/03_РЕШЕНИЯ/02_КРОСС_ДОМЕННЫЕ_ИНВАРИАНТЫ/004_ТЕОРИЯ_ИГР_И_АГЕНТЫ.md), [cognitive science](abra/docs/03_РЕШЕНИЯ/02_КРОСС_ДОМЕННЫЕ_ИНВАРИАНТЫ/005_КОГНИТИВИСТИКА_И_АНТРОПОЛОГИЯ.md), [semiotics](abra/docs/03_РЕШЕНИЯ/02_КРОСС_ДОМЕННЫЕ_ИНВАРИАНТЫ/006_СЕМАНТИКА_И_МИФОЛОГИЯ.md)), grounded into engineering patterns.

## Structure

*Note: Core documentation is currently maintained in Russian.*

| Path | Description |
|------|----------|
| [`abra/core_rules.md`](abra/core_rules.md) | Architect's system prompt |
| [`abra/docs/00_ИНИЦИАЛИЗАЦИЯ/`](abra/docs/00_ИНИЦИАЛИЗАЦИЯ/) | [Manifesto](abra/docs/00_ИНИЦИАЛИЗАЦИЯ/01_МАНИФЕСТ_ПРОЕКТА.md), [Double Helix](abra/docs/00_ИНИЦИАЛИЗАЦИЯ/02_ДВОЙНАЯ_СПИРАЛЬ_РАЗРАБОТКИ.md) |
| [`abra/docs/01_БАЗА_ЗНАНИЙ/`](abra/docs/01_БАЗА_ЗНАНИЙ/) | [Filters](abra/docs/01_БАЗА_ЗНАНИЙ/01_АБСОЛЮТНЫЕ_ФИЛЬТРЫ_ВХОДА.md), [Landscape](abra/docs/01_БАЗА_ЗНАНИЙ/02_КОГНИТИВНЫЙ_ЛАНДШАФТ.md), [Octagon](abra/docs/01_БАЗА_ЗНАНИЙ/03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md), [Conflict Matrix](abra/docs/01_БАЗА_ЗНАНИЙ/04_МАТРИЦА_КОНФЛИКТОВ_И_АРБИТРАЖ.md), [Vectors](abra/docs/01_БАЗА_ЗНАНИЙ/05_ВЕКТОРЫ_МЫШЛЕНИЯ.md), [Organic Systems](abra/docs/01_БАЗА_ЗНАНИЙ/06_ОРГАНИЧЕСКИЕ_СИСТЕМЫ.md) |
| [`abra/docs/02_ИНСТРУМЕНТЫ/`](abra/docs/02_ИНСТРУМЕНТЫ/) | [Pipeline](abra/docs/02_ИНСТРУМЕНТЫ/01_АЛГОРИТМ_РАЗБОРА_ЗАДАЧИ.md), [Protocol Template](abra/docs/02_ИНСТРУМЕНТЫ/02_ШАБЛОН_ИТОГОВОГО_ПРОТОКОЛА.md), [Autonomous Pipeline](abra/docs/02_ИНСТРУМЕНТЫ/03_АВТОНОМНЫЙ_ПАЙПЛАЙН.md), [EXECUTION_STATE](abra/docs/02_ИНСТРУМЕНТЫ/06_ШАБЛОН_EXECUTION_STATE.md), [Orchestration](abra/docs/02_ИНСТРУМЕНТЫ/07_ОРКЕСТРАЦИЯ_ЦИКЛА.md) |
| [`abra/docs/03_РЕШЕНИЯ/`](abra/docs/03_РЕШЕНИЯ/) | Library of crystallized protocols |
| [`abra/docs/04_ХРОНИКИ/`](abra/docs/04_ХРОНИКИ/) | Empirical Journal (System reflection & dynamic tracking) |
| [`cadabra/`](cadabra/) | Executor: [system prompt](cadabra/core_rules.md), [philosophy](cadabra/docs/01_ФИЛОСОФИЯ_GSD.md), [error format](cadabra/docs/02_ФОРМАТ_ERROR_LOG.md), [examples](cadabra/docs/03_ПРИМЕРЫ_КОНТРАКТОВ.md) |
| `.rules` / `.cursorrules` | Symlinks → `abra/core_rules.md` (Zed / Cursor) |
| [`CLAUDE.md`](CLAUDE.md) | Instructions for Claude Code |

## License

[MIT](LICENSE)