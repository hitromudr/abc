# Verdict v2: Benchmark 003 — isearch audit (slim abra v3.0)

**Дата:** 2026-03-12
**Модель:** Claude Opus 4.6 (оба отчёта)
**Abra version:** 3.0-slim
**Арбитр:** Claude Opus 4.6 (ослеплённый)

---

## 1. Ослепление

| Метка | Источник |
|-------|----------|
| Report A | baseline_v2.md — Senior SE, без фреймворка (28 находок, ~69K токенов, ~4.2 мин) |
| Report B | abra_v2.md — Abra v3.0-slim конвейер (17 находок, ~97K токенов, ~5.9 мин) |

---

## 2. Recall по Ground Truth

### GT-1: E5 prefix mismatch (CRITICAL)

**GT:** Модель `intfloat/multilingual-e5-large` требует префиксы "query:"/"passage:". Код их не использует.

**Верификация:** Текущий `config.py:29` содержит `MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"`, а не E5. Однако `preload_large.log` подтверждает, что проект исторически использовал E5. GT описывает архитектурный баг, который может проявляться при переключении модели обратно на E5.

- **Report A (Baseline):** MISS — не упоминает E5, префиксы, или проблему с моделью.
- **Report B (Abra):** MISS — не упоминает E5 или необходимость префиксов. Нет ссылок на модель E5.

### GT-2: Scope file_type filter mismatch (CRITICAL)

**GT:** chunker.py возвращает "doc", а API фильтрует по "docs" — scope=docs сломан.

**Верификация:** В текущем коде `chunker.py` не существует. Чанкинг встроен в `services.py:193`, где `file_type = "docs"`. API фильтрует по `scope: Literal["code", "docs"]`. Значения совпадают. Однако `graph_builder.py:197,204` использует `"doc"` (без "s") для типов узлов графа. GT может описывать баг из предыдущей версии кода, либо относится к graph_builder (но тот не участвует в search pipeline).

- **Report A (Baseline):** MISS — не упоминает file_type mismatch.
- **Report B (Abra):** MISS — не упоминает file_type mismatch или несоответствие "doc"/"docs".

### GT-3: Silent batch failures — hash()-based ID (HIGH)

**GT:** `abs(hash())` недетерминистичен между перезапусками (PYTHONHASHSEED). Дубли при reindex. `abs()` удваивает коллизии.

**Верификация:** Подтверждено. `vector_store.py:90` — `abs(hash(p.get('source_file', '') + p.get('text', '')))`.

- **Report A (Baseline):** **HIT** (C-01). Точное описание: рандомизация `hash()` через PYTHONHASHSEED, дублирование при рестартах, рост индекса. Severity: CRITICAL (GT: HIGH — overcalibrated).
- **Report B (Abra):** **HIT** (C-1). Точное описание: рандомизация `hash()`, дубликаты при перезапуске, `abs()` даёт коллизии. Отдельно упоминает проблему `abs()` с коллизиями. Severity: CRITICAL (GT: HIGH — overcalibrated).

### GT-4: Concurrency race condition (HIGH)

**GT:** Гонка данных при параллельной индексации. Нет блокировок.

**Верификация:** Подтверждено. `main.py:250` — `background_tasks.add_task()` без per-project lock.

- **Report A (Baseline):** **HIT** (H-04). Описывает race condition при параллельной индексации. Severity: HIGH. Совпадает с GT.
- **Report B (Abra):** **HIT** (H-1). Описывает race condition, отсутствие per-project блокировки, риск повреждения индекса. Severity: HIGH. Совпадает с GT.

### Сводка recall

| GT Bug | Severity | Report A | Report B |
|--------|----------|----------|----------|
| GT-1: E5 prefix | critical | MISS | MISS |
| GT-2: file_type mismatch | critical | MISS | MISS |
| GT-3: hash() ID | high | HIT (C-01) | HIT (C-1) |
| GT-4: Race condition | high | HIT (H-04) | HIT (H-1) |

**Recall:**
- Report A (Baseline): 2/4 GT bugs (50%)
- Report B (Abra): 2/4 GT bugs (50%)

**Примечание:** GT-1 и GT-2, вероятно, описывают баги из предыдущей версии кода. В текущей кодовой базе модель изменена на MiniLM (не требует префиксов), а `chunker.py` не существует (чанкинг в `services.py` уже использует "docs"). Оба отчёта корректно не нашли эти баги в текущем коде. Это не промах агентов, а несовпадение GT с текущей версией кода.

---

## 3. Severity Calibration

| GT Bug | GT Severity | Report A | Report B |
|--------|-------------|----------|----------|
| GT-3 | high | critical (+1 overcalibrated) | critical (+1 overcalibrated) |
| GT-4 | high | high (exact match) | high (exact match) |

Оба отчёта overcalibrировали GT-3 (hash ID) — подняли до CRITICAL. Аргументы обоих обоснованы: uncontrolled index growth и data corruption действительно критичны для production. GT оценивает как HIGH.

Калибровка: **паритет**.

---

## 4. Extras и галлюцинации

### Report A (Baseline) — 28 находок

**Extras (валидные находки вне GT):**

| Severity | Кол-во | Примеры |
|----------|--------|---------|
| CRITICAL | 2 | C-02: TASK_STATUS memory leak; C-03: CORS wildcard+credentials |
| HIGH | 5 | H-01: scroll limit 10K; H-02: нет auth; H-03: path traversal; H-05: dead code; H-06: Qdrant без API key |
| MEDIUM | 9 | M-01..M-09: should-фильтр, chunking, валидация, зависимости, docker, float16, shared model |
| LOW | 10 | L-01..L-10: полное чтение файла, emoji, относительный путь и т.д. |
| **Итого** | **26** | |

**Галлюцинации:**

| # | Описание | Вердикт |
|---|----------|---------|
| 1 | M-08: "Double float16 quantization" (`src/embedder.py:75`) | Requires verification. Код в `embedder.py:75` выполняет `.to(dtype=torch.float16)`, а Qdrant настроен на FLOAT16. Это не "double quantization" — это единственное преобразование. Однако потенциальная проблема с precision loss при encode+store обоснована, хотя формулировка преувеличена. **Не галлюцинация**, но overclaimed. |

**Итого галлюцинаций Report A: 0** (все утверждения находят подтверждение в коде)

### Report B (Abra) — 17 находок

**Extras (валидные находки вне GT):**

| Severity | Кол-во | Примеры |
|----------|--------|---------|
| CRITICAL | 1 | C-2: Path traversal; C-3: qdrant-client не в зависимостях |
| HIGH | 4 | H-2: TASK_STATUS memory; H-3: CORS; H-4: reindex параметр не используется; H-5: scroll 10K |
| MEDIUM | 6 | M-1..M-6: .env конфликт, порты docker, payload index, should-фильтр, score mutation, dead code |
| LOW | 5 | L-1..L-5: зависимости, health check, auth, emoji, print vs log |
| **Итого** | **15** | (минус 2 GT-хита) |

**Галлюцинации:**

| # | Описание | Вердикт |
|---|----------|---------|
| 1 | C-3: "qdrant-client не в зависимостях" помечена как CRITICAL | Requires verification. Это реальный баг (qdrant-client действительно не в pyproject.toml/requirements.txt), но CRITICAL — overcalibration. ImportError при установке — это скорее HIGH или MEDIUM, не CRITICAL. **Не галлюцинация**, но severity overcalibrated. |
| 2 | H-4: "reindex параметр не используется" | Подтверждено: `main.py:233` принимает `reindex: bool = Query(False)`, но не передаёт в `run_indexing_task()`. Валидная находка. |

**Итого галлюцинаций Report B: 0**

---

## 5. Weighted Score

Веса: critical=3, high=2, medium=1, low=0.5
HIT = полный вес, PARTIAL = 0.5 * вес, MISS = 0
Штраф за галлюцинацию: -2 за critical, -1 за остальные

### GT Score (max = 10)

- **Report A:** 0 (GT-1 miss) + 0 (GT-2 miss) + 2 (GT-3 HIT, high) + 2 (GT-4 HIT, high) = **4.0**
- **Report B:** 0 (GT-1 miss) + 0 (GT-2 miss) + 2 (GT-3 HIT, high) + 2 (GT-4 HIT, high) = **4.0**

### Extras Score

**Report A:**
- 2 critical extras = 2 * 3 = 6
- 5 high extras = 5 * 2 = 10
- 9 medium extras = 9 * 1 = 9
- 10 low extras = 10 * 0.5 = 5
- Extras total = **30**

**Report B:**
- 1 critical extra = 1 * 3 = 3
- 4 high extras = 4 * 2 = 8
- 6 medium extras = 6 * 1 = 6
- 5 low extras = 5 * 0.5 = 2.5
- Extras total = **19.5**

### Штрафы

- Report A: 0 галлюцинаций = **0**
- Report B: 0 галлюцинаций = **0**

### Total Score

- **Report A:** 4.0 (GT) + 30.0 (extras) - 0 (штрафы) = **34.0**
- **Report B:** 4.0 (GT) + 19.5 (extras) - 0 (штрафы) = **23.5**

---

## 6. Coverage Map

| Файл | Report A | Report B |
|------|----------|----------|
| src/main.py | + | + |
| src/config.py | + | + (через инварианты) |
| src/vector_store.py | + | + |
| src/embedder.py | + | + |
| src/services.py | + | + (через chunking) |
| src/graph_builder.py | + | + |
| src/graph_analyzer.py | - | - |
| src/index.py | + (dead code) | + (dead code) |
| src/search.py | + (dead code) | + (dead code) |
| docker-compose.yml | + | + |
| pyproject.toml | + | + |
| requirements.txt | - | + |
| manage.py | + | + |
| .env | - | + |
| tests/ | + (L-07) | - |
| setup.py | + (M-05) | - |
| **Breadth** | **12/16** | **12/16** |

Покрытие примерно равное. Report A взял tests/ и setup.py, Report B взял .env и requirements.txt.

---

## 7. ROI

| Метрика | Report A (Baseline) | Report B (Abra) |
|---------|---------------------|-----------------|
| Total tokens | ~69K | ~97K |
| Wall time | ~4.2 мин | ~5.9 мин |
| GT weighted score | 4.0/10 | 4.0/10 |
| GT recall | 50% | 50% |
| Total findings | 28 | 17 |
| Total weighted score | 34.0 | 23.5 |
| Hallucinations | 0 | 0 |
| Tokens per GT point | 17.3K | 24.3K |

Report A обнаружил на 65% больше находок при на 29% меньшем расходе токенов.

---

## 8. Вердикт

**Победитель: Report A (Baseline)**

**Причина:** При идентичном GT recall (2/4, оба нашли hash ID и race condition, оба пропустили E5 prefix и file_type mismatch), Baseline значительно превосходит по объёму extras: 28 находок vs 17, total weighted score 34.0 vs 23.5. Baseline потратил на 29% меньше токенов и на 29% меньше времени.

**Ключевые наблюдения:**

1. **GT-1 и GT-2 не представлены в текущем коде.** Оба GT-бага, по-видимому, относятся к предыдущей версии: модель сменена с E5 на MiniLM, `chunker.py` удалён и заменён инлайн-логикой в `services.py` с корректным значением "docs". Оба агента правильно не "нашли" эти баги, т.к. их нет в актуальном коде. Это ставит под сомнение валидность GT для данной версии кодовой базы.

2. **Baseline = ширина.** Report A обнаружил больше реальных проблем: path traversal, CORS, memory leak, scroll limit, dead code, отсутствие auth, Qdrant без API key, конфликт версий, неиспользуемые зависимости. Каждая находка подтверждается конкретной строкой кода.

3. **Abra = глубина, но меньше покрытие.** Report B структурирован через концептуальный протокол (Топология, Инварианты, Точка опоры), что даёт лучшее понимание архитектурных проблем. Однако это не привело к обнаружению большего количества багов. Уникальная находка Abra — H-4 (reindex параметр не используется) — валидная, но не критичная.

4. **Overcalibration GT-3.** Оба отчёта подняли hash ID до CRITICAL. Аргументация обоснована (рост индекса, дубли), но GT оценивает как HIGH.

5. **Нет галлюцинаций у обоих.** Оба отчёта работали строго по коду, ложных утверждений не обнаружено.

**Итог:** Baseline выигрывает за счёт лучшего соотношения сигнал/токен и большего объёма валидных находок при равном GT recall. Abra не реализовала своё преимущество в структурированном анализе — фреймворк добавил overhead (+40% токенов, +40% времени) без прироста в recall.

**Оговорка:** Если бы GT-1 и GT-2 присутствовали в текущем коде, результат мог бы быть другим. Фреймворк Abra теоретически лучше находит контрактные mismatch-баги (как E5 prefix), но для этого баг должен существовать в анализируемой версии.
