# Эмпирические Бенчмарки (Eval Suite)

Контролируемые эксперименты: vanilla LLM vs abracadabra на одном и том же коде.

## Структура эксперимента

```
benchmarks/NNN_название/
├── BRIEF.md        ← задание (единый вход для обоих прогонов)
├── meta.yml        ← модель, версия, Ground Truth, ресурсы, метрики
├── baseline.md     ← результат vanilla-агента
├── abra.md         ← результат abra-агента
└── verdict.md      ← ослеплённый арбитраж
```

## Запуск

### Вариант 1: Одна команда (рекомендуемый)

```
abra bench NNN
```

Self-contained — не требует предварительного `abra init`.

**Что происходит:**

1. **Baseline + Init (параллельно)** — агент читает BRIEF.md, сразу запускает baseline-субагента (`run_in_background: true`) в чистом контексте (abra ещё не загружена). Параллельно выполняет `abra init` (загрузка Базы Знаний). Baseline не читает `.rules`, `.cursorrules`, `CLAUDE.md` — только BRIEF.md и код проекта.
2. **Abra audit** — после загрузки ядра выполняет задачу через полный конвейер (Пре-чеклист → Фазы 0–6 → Октагон), сохраняет `abra.md`.
3. **Verdict (ослепление)** — дожидается baseline-субагента, читает оба отчёта + `meta.yml`, рандомно присваивает «Report A» / «Report B», судит против Ground Truth. Деанонимизация только в финале.

Одна сессия, ноль ручной работы.

### Вариант 2: Раздельные сессии

Для случаев, когда нужен другой model/среда для baseline:

- **Сессия 1 (Baseline):** Чистая LLM без `.abracadabra` → `Прочитай BRIEF.md и выполни задачу`
- **Сессия 2 (Abra):** `abra init` → `abra audit NNN`
- **Сессия 3 (Verdict):** `abra verdict NNN`

### Сбор ресурсных метрик

После каждого прогона записать в `meta.yml` → `resources`:
- **tokens** (input/output/total) — из usage stats среды
- **init_tokens** — overhead загрузки базы знаний abra (чистый налог фреймворка)
- **wall_time_min** — от старта до сохранения файла
- **cost_usd** — по прайсу модели

### Изоляция Baseline

Baseline-субагент запускается с явным запретом на чтение `.abracadabra/`, `.rules`, `.cursorrules`, `CLAUDE.md`. Чистота контекста обеспечивается запретом в промпте, а не физической изоляцией (worktree не используется — субагент в worktree не может записать файлы в оригинальную директорию бенчмарка).

### Ослепление (Bias Mitigation)

Судья (фаза verdict) получает отчёты как «Report A» и «Report B» без маркеров авторства. Объективные метрики (recall, weighted score, severity calibration) не зависят от bias. Субъективные оценки (глубина, actionability) защищены ослеплением. Деанонимизация — только после вынесения вердикта.

### Метрики verdict

- **Recall** — нашёл / не нашёл GT-баг
- **Severity calibration** — совпала ли присвоенная severity с реальной. Правильная приоритизация одного critical > обнаружение пяти LOW
- **Weighted score** — critical=3, high=2, medium=1, low=0.5
- **Coverage map** — какие файлы прочитал каждый агент (breadth vs depth)
- **ROI** — overhead abra (tokens, cost) vs дельта качества

---

## Реестр

| # | Проект | Задача | Baseline | abra | Verdict |
|---|--------|--------|----------|------|---------|
| **001** | `isearch` | Аудит: поиск багов | Claude Opus 4.6 | v2.5.0 | [abra wins (50/50 recall, quality edge)](001_isearch_audit/verdict.md) |
| **002** | `isearch` | Аудит: поиск багов | Gemini 3.1 Pro | v2.5.0 | *pending* |
| **003** | `isearch` | Аудит: поиск багов | Claude Opus 4.6 | v3.0-slim | *pending* |

---
*«Разница, которая не создаёт разницы в физическом мире, не имеет значения» (Фильтр 5: Джеймс).*
