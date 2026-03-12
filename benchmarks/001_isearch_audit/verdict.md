# Verdict: Benchmark 001 — isearch_audit

**Judge:** Claude Opus 4.6 | **Date:** 2026-03-12

---

## 1. Матрица покрытия Ground Truth

| GT-ID | Баг | Severity | Baseline | Abra |
|-------|-----|----------|----------|------|
| GT-1 | E5 prefix mismatch (`query:`/`passage:`) | critical | **MISS** | **HIT** — Дефект #4 (P0) |
| GT-2 | Scope `file_type` filter (`"doc"` != `"docs"`) | critical | **HIT** — Дефект #4 (HIGH) | **HIT** — Дефект #3 (P0) |
| GT-3 | Silent batch failures (uint64 vs int64) | high | **MISS** — #1 про hash collision, не batch rejection | **MISS** — #2 про PYTHONHASHSEED, не batch rejection |
| GT-4 | Concurrency race condition (collection-level) | high | **HIT** — Дефект #2 (CRITICAL): "Гонка при upsert/delete в одну коллекцию" | **MISS** — #5 про TASK_STATUS dict thread safety (другой race condition) |

### Recall

| Метрика | Baseline | Abra |
|---------|----------|------|
| GT-багов найдено | 2/4 | 2/4 |
| **Recall** | **50%** | **50%** |

**Примечание:** Recall одинаковый, но покрытие ортогональное — baseline нашёл GT-2 + GT-4, abra нашёл GT-1 + GT-2. Единственное пересечение — GT-2.

---

## 2. Extras (валидные баги сверх Ground Truth)

### Baseline extras (19)

| # | Дефект | Severity | Валидность |
|---|--------|----------|------------|
| 1 | Hash-based ID (PYTHONHASHSEED + collision) | CRITICAL | Valid |
| 3 | TASK_STATUS memory leak | CRITICAL | Valid |
| 5 | extract_snippet — missing start_line/end_line | HIGH | Valid |
| 6 | State file зависит от PROJECTS_BASE_DIR | HIGH | Valid |
| 7 | Scroll limit=10000 без пагинации | HIGH | Valid |
| 8 | Дублирование PROJECTS_BASE_DIR в .env | HIGH | Valid |
| 9 | should-фильтр при массовом удалении | HIGH | Valid |
| 10 | CORS wildcard + credentials | MEDIUM | Valid |
| 11 | Пустая строка в docs_extensions | MEDIUM | Valid |
| 12 | Нет аутентификации | MEDIUM | Valid |
| 13 | Нет rate limiting | MEDIUM | Valid |
| 14 | Version mismatch pyproject/setup.py | MEDIUM | Valid |
| 15 | Global mutable state для ML-моделей | MEDIUM | Valid |
| 16 | Brace-based chunker ломается на литералах | MEDIUM | Valid |
| 17 | print() вместо logging | MEDIUM | Valid |
| 18 | Дублированные комментарии | LOW | Valid |
| 19 | Дублированные импорты | LOW | Valid |
| 20 | Избыточное INFO-логирование | LOW | Valid |
| 21 | Health check не пингует Qdrant | LOW | Valid |

### Abra extras (13)

| # | Дефект | Severity | Валидность |
|---|--------|----------|------------|
| 1 | **Path Traversal** (project_name из URL) | P0 (CRITICAL) | **Valid — уникальная security-находка** |
| 2 | Нестабильные ID (PYTHONHASHSEED) | P0 | Valid |
| 5 | Race condition TASK_STATUS dict | P1 | Valid |
| 6 | Memory leak TASK_STATUS | P1 | Valid |
| 7 | Scroll limit=10000 | P1 | Valid |
| 8 | CORS wildcard + credentials | P1 | Valid |
| 9 | Keyword boosting `"docs"` vs `"doc"` | P1 | Valid (производная GT-2) |
| 10 | Не-атомарная запись state | P2 | Valid |
| 11 | Пустая строка в extensions | P2 | Valid |
| 12 | Health check не пингует Qdrant | P2 | Valid |
| 13 | State file в неожиданном месте | P2 | Valid |
| 14 | Brace-based chunker | P2 | Valid |
| 15 | Дублированные импорты | P2 | Valid |

### Галлюцинации

| Агент | Количество | Детали |
|-------|-----------|--------|
| Baseline | 0 | Все находки привязаны к file:line, верифицируемы |
| Abra | 0 | Все находки привязаны к file:line, верифицируемы |

---

## 3. Сравнительный анализ

### Количественный

| Метрика | Baseline | Abra | Преимущество |
|---------|----------|------|-------------|
| GT Recall | 2/4 (50%) | 2/4 (50%) | Паритет |
| Total findings | 21 | 15 | Baseline (+6) |
| CRITICAL/P0 | 3 | 4 | Abra (+1) |
| HIGH/P1 | 6 | 5 | Baseline (+1) |
| Extras | 19 | 13 | Baseline (+6) |
| Hallucinations | 0 | 0 | Паритет |
| Уникальные GT | GT-4 | GT-1 | — |

### Качественный

**Baseline сильнее в:**
- **Охват**: 21 vs 15 дефектов. Больше LOW/MEDIUM находок (print vs logging, verbose logging, duplicate comments).
- **GT-4 (collection-level race)**: Точно идентифицировал гонку при параллельной индексации в Qdrant. Abra нашёл только побочный race в dict.
- **extract_snippet**: Уникальная находка (#5) — baseline единственный, кто заметил, что `start_line`/`end_line` отсутствуют в payload.
- **Формат**: Каждый баг снабжён code snippet — удобно для разработчика.

**Abra сильнее в:**
- **GT-1 (E5 prefix)**: Критическая находка, baseline полностью пропустил. ~30% деградация retrieval quality — самый импактный product-баг в системе поиска.
- **Path Traversal**: Security-critical уязвимость вне GT. Baseline не заметил. `../../etc` обходит `is_dir()` и даёт доступ к файловой системе сервера.
- **Мета-паттерн**: Связал 3 дефекта (#3, #9, #11) общим корнем — рассогласование строковых констант без enum. Baseline перечислил их как изолированные баги.
- **Системное решение**: Предложил `FileType(str, Enum)` и стратегическую развилку (Quick Fixes vs Structural Hardening).
- **Структура**: Октагон-анализ привязал каждый баг к оси выживания (Телос, Иммунитет, Наследственность), что даёт архитектурный контекст.

---

## 4. Вердикт

**Победитель: abra (с небольшим отрывом)**

При одинаковом Recall (50%) и меньшем общем числе находок (15 vs 21), abra выигрывает по **ценности критических находок**:

1. **GT-1 (E5 prefix)** — baseline пропустил единственный баг, ради которого система поиска создавалась. Без `query:`/`passage:` вся e5-модель работает в деградированном режиме. Это не просто баг — это отказ ядра продукта.

2. **Path Traversal** — security-уязвимость, отсутствующая даже в Ground Truth. В реальном инциденте это эскалация до RCE.

3. **Мета-анализ** — abra не просто нашёл баги, а нашёл **генератор багов** (отсутствие enum для file_type). Baseline нашёл симптомы, abra нашёл причину.

Baseline компенсирует это широтой (extract_snippet, no auth, no rate limiting, version mismatch, global state) и точным попаданием в GT-4. Но в продуктовом контексте пропуск E5 prefix дороже, чем 6 дополнительных MEDIUM/LOW находок.

**Счёт: abra 7 : baseline 6** (условные баллы по весу находок)

---

## 5. Общие слепые зоны

Оба агента пропустили **GT-3 (Silent batch failures)**. Механизм: Qdrant может отклонить часть батча при несовпадении формата ID (unsigned vs int64), но система не проверяет ответ и не логирует потерю. Оба агента нашли проблему с hash-based ID (нестабильность, коллизии), но не идентифицировали тихий partial rejection на уровне Qdrant API.

**Гипотеза:** Этот баг требует знания внутренней семантики Qdrant batch API (что upsert может быть частичным), что выходит за рамки статического code review.
