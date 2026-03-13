<thought_process>
I am the **abra** (Architect) module.
My task is to perform a deep audit of the `isearch` project.
I will follow the `01_АЛГОРИТМ_РАЗБОРА_ЗАДАЧИ.md` and `03_ИНЖЕНЕРНЫЙ_ОКТАГОН_ВЫЖИВАНИЯ.md`.

### PHASE 0: Empirical Grounding & Pre-Check
- **Task:** Audit `isearch` (Search Engine).
- **Facts observed in code:**
    1. **`src/vector_store.py` (Line 92):** Point ID generation uses `abs(hash(source_file + text))`.
        - *Vulnerability:* Python's `hash()` is non-deterministic between processes (randomized since Python 3.3). This destroys idempotency. Re-indexing after a server restart will create duplicate entries instead of updating them.
    2. **`src/main.py` (Line 79) & `src/services.py` (Line 160):** Snippet extraction and file reading.
        - *Vulnerability:* Path Traversal. `extract_snippet` takes `file_path` from `payload.get("source_file")`. While `IndexingService` scans local files, the `SearchHit` payload can be manipulated or contain `../` if the index was poisoned.
    3. **`src/main.py` (Line 310):** Clustering with `limit=10000` points in one `scroll` call.
        - *Vulnerability:* Memory exhaustion (OOM). Loading 10k vectors (each 384 dimensions) + metadata in memory is risky for a web worker.
    4. **`src/services.py` (Line 59):** `_get_indexed_state` scrolls the entire collection to build a hash map.
        - *Vulnerability:* Scalability bottleneck. For 1M chunks, this will stall the indexing startup for minutes.
    5. **`src/main.py` (Line 132):** `TASK_STATUS` is a global dictionary.
        - *Vulnerability:* Memory leak and lack of persistence. Task states are lost on restart. No cleanup for old task IDs.
    6. **`manage.py` (Line 104):** Detached start using `nohup ... & echo $!`.
        - *Infrastructure:* Unreliable process management. PID files can become stale. No proper health-checking before marking as "Ready".
    7. **`src/embedder.py` (Line 14):** `cudnn.benchmark = True`.
        - *Performance:* Good for fixed-size inputs, but can cause overhead for variable text lengths in search.

### PHASE 1: Classification
- **Cynefin:** Complicated. The domain is search/ML, but the bugs are classic architectural and security failures.
- **Vektor:** Inversion (What breaks the "Semantic Search" promise?).

### PHASE 2: Invariants
1. **Idempotency of the Index:** Content -> ID must be stable across time/processes.
2. **Path Sanitization:** No relative paths outside `PROJECTS_BASE_DIR`.
3. **Resource Boundness:** All operations must have upper bounds on RAM/Time.

### PHASE 5: Octagon Red Teaming
- **Telos (L0):** Broken by `hash()` inconsistency. The system fails its core promise of incremental indexing.
- **Topology (L1):** Mismatch between scanned files and searchable files (Path Traversal).
- **Heredity (L2):** State (Task status) is transient.
- **Immunity (L3):** High risk of data leakage via snippets.

### PHASE 6: Synthesis
I will structure the report by critical vulnerabilities, logical flaws, and infrastructure debt.
</thought_process>

# Концептуальный Протокол: Архитектурный Аудит `isearch`

## 1. Топология задачи (Ontology)
- **Мета-тип:** Инженерный аудит поисковой системы на базе векторного хранилища.
- **Ключевой конфликт:** Производительность и "умное" индексирование vs Детерминизм и Безопасность.

## 2. Инварианты (Invariants)
1. **Закон Идемпотентности:** `ID(content) == Const`. Один и тот же фрагмент текста не должен порождать разные ID в БД при перезапуске процесса.
2. **Закон Мембраны:** Пользовательский ввод (пути файлов в метаданных) не должен приводить к доступу за пределы `PROJECTS_BASE_DIR`.
3. **Закон Метаболизма:** Потребление памяти не должно зависеть линейно от размера индекса (Отказ от `scroll` всего индекса в память).

## 3. Точка опоры (Leverage Point)
- **Фокус:** Механизм генерации Point ID и санитизация путей. Это закрывает 80% критических рисков (дубликаты и утечки).

## 4. Векторы энтропии (Degradation Paths)
- **Смерть Детерминизма:** Использование встроенного `hash()` в Python приводит к лавинообразному росту дубликатов в БД при каждом перезапусте сервера.
- **Инъекция Путей:** Метаданные `source_file` в Qdrant — это "отравленный ввод", который используется в `open()` без проверки.

## 5. Результаты Аудита (The Protocol)

### 5.1 Критические уязвимости (High Severity)

| ID | Название | Локация | Описание |
|---|---|---|---|
| **VULN-01** | **Недетерминированные ID** | `src/vector_store.py:92` | Использование `hash()` для генерации ID. В Python 3.3+ хеш рандомизируется при каждом запуске. **Эффект:** Инкрементальное индексирование сломано; при перезапуске всё индексируется как "новое", БД забивается дублями. |
| **VULN-02** | **Path Traversal (Чтение файлов)** | `src/main.py:79` | `extract_snippet` открывает файл по пути из `payload`. Атакующий может поместить в индекс путь вида `../../../../etc/passwd` и прочитать его через API поиска. |
| **VULN-03** | **OOM при кластеризации** | `src/main.py:310` | `vector_store.client.scroll` с лимитом 10,000 выкачивает все векторы в память. На больших проектах это приведет к моментальному падению воркера. |

### 5.2 Архитектурные дефекты (Medium Severity)

1. **Task Persistence:** `TASK_STATUS` — это глобальный словарь в памяти. При перезапуске сервера информация обо всех текущих индексациях исчезает, хотя фоновые процессы (если они выжили) могут продолжать писать в БД.
2. **Scalability (Index Sync):** `_get_indexed_state` (`services.py:59`) выкачивает хеши *всех* файлов при каждом запуске индексации. При росте количества файлов до 100k+ время подготовки к индексации станет неприемлемым.
3. **Race Condition:** Нет блокировки (Lock) на индексацию конкретного проекта. Если запустить `/index` дважды параллельно, состояние БД будет непредсказуемым.

### 5.3 Инфраструктурный долг (Low Severity)

- **Manage.py:** Использование `nohup ... & echo $!` — крайне хрупкий способ демонизации. PID-файл может остаться, если процесс убит через `SIGKILL`.
- **Environment:** По умолчанию `PROJECTS_BASE_DIR` указывает на `..`, что может привести к индексации системных директорий, если сервер запущен из корня.

## 6. Метрика истины (Truth Criteria)
- **Успех:** Переход на `hashlib.sha256` для ID, внедрение `Path.relative_to` в snippet extraction, замена `scroll` на постраничную обработку (generators).

## 7. Эвристики и Мета-Контекст
- **Патч конвейера:** Выявлена склонность LLM использовать `hash()` для простоты. Добавить в `MUST_NOT_DO` запрет на использование встроенного `hash()` для персистентных данных.

## 8. Резолюция (Executive Summary)
- **Фундаментальный диагноз:** Система страдает от отсутствия детерминизма в данных (ID) и "дырявых" границ безопасности при работе с ФС.
- **Рекомендация ИИ:** Срочно заменить `hash()` на стабильный `sha256` и внедрить проверку путей через `Path.resolve().is_relative_to()`.

---
**ACTION:** Записываю отчёт в `abra.md`.

```bash
# Команда для записи отчета (выполняется cadabra в реальном цикле)
# cat <<EOF > .abracadabra/benchmarks/003_isearch_audit_slim/abra.md
# ... [текст выше] ...
# EOF
```

**Ядро загружено. Жду задачу или подтверждение для генерации EXECUTION_STATE.**