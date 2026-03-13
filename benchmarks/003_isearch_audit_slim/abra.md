Ядро загружено. Жду задачу.
<thought_process>
The user has invoked `abra` with a benchmark task: `Benchmark 003: Аудит проекта isearch (slim abra)`. This is an `abra audit NNN` type of request, which means I need to perform a deep audit using the full `abra` pipeline and save the results to `abra.md`.

**[Pre-checklist]**
*   **Problem:** Deep audit of `isearch` for architectural, logical, and infrastructural vulnerabilities. Specific attention to data processing, API contracts, state storage (vector DB), and edge cases.
*   **Verifiable facts:** Codebase is provided. My findings will refer to specific code locations.
*   **Outside operator control:** No, the task is within my scope of code analysis.
*   **Goal:** Structured report with classification and criticality. Clear.
*   **Physical reality change:** The report provides actionable insights for developers.

Task passes pre-checklist.

**[Фаза 0. Эмпирическое Заземление]**
-   **Observe:** The provided code files represent the system's current state and behavior. The Qdrant storage configuration files offer insights into the vector database's state and past configurations.
-   **Verify:** My audit findings will be directly traceable to lines of code or architectural patterns visible in the provided files.

**[Фаза 0.5. Kill Switch (ROI)]**
-   **Cost of Inaction:** Over time, unaddressed vulnerabilities could lead to data corruption, poor search relevance, performance degradation, security breaches, and increased operational costs.
-   **Cost of Action:** My computational resources for this analysis. Minimal compared to potential benefits of identifying critical flaws.
-   **Decision:** Continue. The ROI is high.

**[Фаза 1. Классификация и Вектор Атаки]**
-   **Cynefin:** Complicated. The system involves multiple well-understood components (FastAPI, SentenceTransformers, Qdrant, Docker, Click CLI), but their integration can lead to complex interactions and subtle bugs. Requires systematic analysis using established engineering principles.
-   **Вектор:**
    *   **Дедукция:** Apply known software engineering principles (security, concurrency, scalability, maintainability, error handling) to identify deviations and anti-patterns.
    *   **Индукция:** Observe patterns in how different modules interact (e.g., data flow from file scanning to Qdrant) to infer potential systemic weaknesses.
    *   **Инверсия:** Consider the system from an adversarial perspective (how could data be corrupted, how could a system be exploited?) and from a failure perspective (what happens when a component fails?).
-   **Lateral Injection:** Focus on the "seams" between technologies (Python code <-> Qdrant, Python <-> OS commands via `manage.py`, FastAPI <-> background tasks) as these are common points of failure and vulnerability.

**[Фаза 2. Инварианты (Физика проблемы)]**
-   **Противоречие:**
    1.  **Desired: Data Consistency & Determinism** vs. **Actual: Non-deterministic Indexing:** The system aims for an up-to-date and consistent vector index, but the current point ID generation (`hash()`) makes re-indexing non-deterministic, potentially leading to data duplication and search degradation.
    2.  **Desired: Scalable & Robust Indexing** vs. **Actual: Fragile & Resource-Intensive Indexing Logic:** The incremental indexing attempts efficiency but relies on full collection scrolls (poor scalability) and lacks explicit concurrency control (data races).
    3.  **Desired: Secure & Isolated Operation** vs. **Actual: Path Traversal Vulnerability:** The API exposes an internal file reading mechanism (`extract_snippet`) that can be abused due to insufficient input validation.
-   **Равновесие:** The system appears to function for small, single-user projects. The current architectural decisions reduce immediate development complexity but defer deeper issues to scale or malicious use. This "works until it breaks" state creates an equilibrium.
-   **Обратная связь:**
    *   **Indexing Failures:** The current task status mechanism provides high-level `completed`/`failed`, but lacks granular feedback on *why* specific chunks failed or *what* data was silently dropped.
    *   **Operational Visibility:** `manage.py` offers basic `status` and `logs` but no deeper, structured metrics or alerts on Qdrant health, index quality, or resource consumption during indexing.

**[Фаза 3. Точка Рычага]**
-   **Фокус внимания:** The core indexing and vector storage logic (`src/services.py`, `src/vector_store.py`) are the critical path. Addressing issues here will have the highest impact on data integrity, search quality, and system robustness. The API layer (`src/main.py`) exposes these, so its security and concurrency aspects are also high leverage.
-   **Игнорируемый шум:** Minor UI/UX issues in `static/app.js` or `manage.py` CLI conveniences are secondary to fundamental data and security integrity. The `src/graph_analyzer.py` and `src/graph_builder.py` modules are relatively self-contained and less critical than the search core.

**[Фаза 4. Стратегия Внедрения]**
-   **Путь наименьшего сопротивления:** Present findings grouped by impact and area, with clear, actionable recommendations. Prioritize critical and high-severity issues first.
-   **Политическое трение:** Highlight that these are systemic risks that will become exponentially more costly to fix later. Frame as necessary technical debt repayment.
-   **Асимметрия:** A detailed audit report provides leverage for advocating for architectural improvements, moving from reactive bug-fixing to proactive risk mitigation.
-   **Зона контроля:** My output is the audit report. I will not implement fixes.

**[Фаза 5. Синтез и Red Teaming]**

*Drafting findings (internal monologue):*

*   **Issue 1: Critical - Path Traversal in `extract_snippet` (`src/main.py`)**
    *   **Description:** The `extract_snippet` function reconstructs a file path using `project_path / source_file`. The `source_file` is derived from user-indexed content (Qdrant payload). If a malicious `source_file` containing path traversal sequences (e.g., `../../../../etc/passwd`) were indexed, an attacker could trigger arbitrary file reads on the server by initiating a search that returns this crafted payload, leading to information disclosure.
    *   **Red Teaming (L1 Topology, L3 Immunity):** This breaks the security boundary of the application, allowing access to resources outside the intended project scope.
    *   **Severity:** Critical
    *   **Impact:** Information disclosure, potential RCE if combined with other vulnerabilities.
    *   **Suggested Remediation:** Implement strict sanitization and validation of `source_file` paths (e.g., using `pathlib.Path.resolve()` with a strict `max_depth` check against `project_path` or canonicalizing paths) before opening files.

*   **Issue 2: Critical - Non-Deterministic Qdrant Point IDs (`src/vector_store.py`)**
    *   **Description:** Qdrant point IDs are generated using `ids = [abs(hash(p.get('source_file', '') + p.get('text', '')))]`. Python's `hash()` function is non-deterministic by default if the `PYTHONHASHSEED` environment variable is not explicitly set to a fixed value (e.g., `0`). This means that indexing the exact same content in different Python process runs could result in different Qdrant point IDs. This breaks incremental indexing: instead of updating existing points, new duplicate points are created, leading to index bloat, degraded search quality, and data inconsistencies. `abs()` also halves the available hash space, increasing collision probability.
    *   **Red Teaming (L0 Telos, L5 Mutagenesis):** Violates the core promise of a consistent search index. Breaks reproducibility and makes `reindex` operations potentially lossy or duplicative.
    *   **Severity:** Critical (GT-3)
    *   **Impact:** Data integrity loss, index bloat, degraded search quality, potential performance issues from duplicate vectors.
    *   **Suggested Remediation:** Use a cryptographically secure, deterministic hash function (e.g., SHA256) for point IDs, or ensure `PYTHONHASHSEED` is fixed. Ensure Qdrant IDs handle collision gracefully (though deterministic IDs are better).

*   **Issue 3: High - Concurrency Race Condition in Indexing (`src/services.py`)**
    *   **Description:** The `run_indexing` method does not implement any explicit locking mechanism (e.g., a file lock or a distributed lock via Qdrant's capabilities) to prevent multiple concurrent indexing tasks for the *same project*. If two `index_project_endpoint` calls target the same `project_name` simultaneously, they will both attempt to `recreate_collection` (if needed) or `delete_points_by_source` and `upsert` concurrently. This can lead to race conditions, data corruption in the Qdrant collection, or partial updates. While `manage.py`'s `--workers 1` mitigates concurrent *API requests*, `BackgroundTasks` run in threads, allowing concurrency within a single worker.
    *   **Red Teaming (L2 Kinematics, L3 Immunity):** Breaks the state consistency of the index. Exposes the system to corruption under moderate load.
    *   **Severity:** High (GT-4)
    *   **Impact:** Data corruption, inconsistent search results, system instability.
    *   **Suggested Remediation:** Implement a per-project mutex/lock (e.g., `threading.Lock` per project name, or a distributed lock if scaling to multiple API instances) to ensure only one indexing operation per project runs at a time.

*   **Issue 4: High - Scalability Bottleneck in Incremental Indexing (`_get_indexed_state` in `src/services.py`)**
    *   **Description:** The `_get_indexed_state` function retrieves *all* existing points from the Qdrant collection to compare with local files for incremental updates (`limit=1000`, but with `offset=next_page_offset` for full scroll). For very large projects with millions of document chunks, this operation will become slow and memory-intensive, potentially leading to timeouts, excessive memory usage, or making incremental indexing almost as slow as full re-indexing.
    *   **Red Teaming (L2 Metabolism):** The system's performance will degrade non-linearly with project size.
    *   **Severity:** High
    *   **Impact:** Poor performance for large projects, increased indexing time, potential for service degradation or crashes.
    *   **Suggested Remediation:** Qdrant offers a [snapshot mechanism](https://qdrant.tech/documentation/snapshots/) or dedicated API for retrieving metadata. A more efficient approach might involve using Qdrant's payload filters to query only the `source_file` and `file_hash` fields without fetching vectors, or using a dedicated metadata store (e.g., a small relational DB) for tracking indexed files and their hashes.

*   **Issue 5: Medium - Fragile Default `PROJECTS_BASE_DIR` (`src/config.py`)**
    *   **Description:** The default for `PROJECTS_BASE_DIR` is `..`, meaning the parent directory of where the FastAPI app is launched. This is an implicit and potentially dangerous assumption. If the application is launched from an unexpected subdirectory, it could attempt to read or write files outside its intended operational scope, leading to misconfiguration, unexpected behavior, or even security vulnerabilities if combined with path traversal (see Issue 1).
    *   **Red Teaming (L1 Topology):** Poorly defined system boundaries, increasing surface area for errors.
    *   **Severity:** Medium
    *   **Impact:** Misconfiguration, unexpected file access, potential security risk.
    *   **Suggested Remediation:** `PROJECTS_BASE_DIR` should default to a clearly defined and controlled subdirectory (e.g., `Path(__file__).parent / "projects"` or `./projects`), or require an explicit absolute path.

*   **Issue 6: Medium - Unsafe `shell=True` in `manage.py`**
    *   **Description:** The `service_up` command uses `subprocess.Popen(command_str, shell=True, ...)` where `command_str` is constructed from `UVICORN_CMD` and `API_LOG_FILE`. While these variables are internally defined, using `shell=True` is generally a security risk as it allows shell interpretation of the command string. If any part of `UVICORN_CMD` or `API_LOG_FILE` were ever exposed to user input or an insecure environment variable, it could lead to command injection.
    *   **Red Teaming (L3 Immunity):** General security anti-pattern.
    *   **Severity:** Medium
    *   **Impact:** Potential command injection if upstream inputs become compromised.
    *   **Suggested Remediation:** Avoid `shell=True` and pass commands as a list of arguments to `subprocess.Popen`.

*   **Issue 7: Medium - In-Memory Task Status Volatility (`src/main.py`)**
    *   **Description:** The `TASK_STATUS` dictionary, used to track background indexing tasks, is stored in memory (`TASK_STATUS: Dict[str, Dict[str, Any]] = {}`). If the FastAPI application process restarts (e.g., due to a crash, deployment, or manual restart of `uvicorn`), all pending and completed task statuses are lost. This makes long-running background tasks difficult to monitor reliably and impossible to resume after a restart.
    *   **Red Teaming (L5 Mutagenesis):** System state is not durable across restarts.
    *   **Severity:** Medium
    *   **Impact:** Poor user experience for long tasks, loss of operational visibility, no recovery for interrupted tasks.
    *   **Suggested Remediation:** Persist task status in a durable store (e.g., a simple SQLite database, Redis, or even a file-based JSON store for simplicity) that can be reloaded on startup.

*   **Issue 8: Medium - Inconsistent `file_type` Labeling (`src/services.py` vs. UI expectations)**
    *   **Description:** In `IndexingService`, files are classified into `file_type: "code"` or `file_type: "docs"` using `self.code_extensions` and `self.docs_extensions`. The `src/main.py` search endpoint uses this `file_type` in filters. However, the `static/app.js` UI uses `toggleCodeCheckbox` and `toggleDocsCheckbox` for filtering, suggesting "Code" and "Documentation". This is a naming mismatch between the backend stored data (`"docs"`) and potential UI labels or future keyword boosting (`"doc"` as seen in `src/main.py` for search boosting keywords like `doc_keywords`). While `file_type: "docs"` correctly maps to documentation, it's easy to cause confusion with `doc_keywords`. The actual `file_type` from `src/services.py` stores `"docs"`, but `src/main.py`'s `is_doc_query` checks for `doc_keywords` like `"documentation"`, not `"docs"`. This is more about consistency and avoiding future pitfalls than a direct bug.
    *   **Red Teaming (L0 Telos, L1 Topology):** Semantic inconsistencies can lead to brittle filtering logic and cognitive load.
    *   **Severity:** Medium (Preventive)
    *   **Impact:** Potential for filter mismatches, confusion, and subtle bugs if not carefully managed.
    *   **Suggested Remediation:** Standardize the terminology for "documentation" across all layers (payload `file_type`, search queries, UI labels). Use a single canonical term (e.g., "document" or "docs").

*   **Issue 9: Low - Hardcoded `PROJECT_ROOT_PATH` in `src/index.py` (Standalone Script)**
    *   **Description:** The `src/index.py` script, designed for manual, standalone indexing, hardcodes `PROJECT_ROOT_PATH = Path(__file__).parent.parent.parent / 'autowarp'`. This makes the script specific to a single project named 'autowarp' and requires manual modification to index other projects. It limits the utility and generality of this standalone tool.
    *   **Red Teaming (L5 Mutagenesis):** Poor flexibility, requires manual code changes for basic operations.
    *   **Severity:** Low (as it's a utility script, not the API core)
    *   **Impact:** Inflexibility, manual effort.
    *   **Suggested Remediation:** Convert `src/index.py` to accept `project_name` as a command-line argument, similar to `manage.py`, to dynamically determine the `PROJECT_ROOT_PATH`.

*   **Issue 10: Low - Deprecated Qdrant Client Methods (`src/vector_store.py`)**
    *   **Description:** The comments in `VectorStore` (e.g., in `recreate_collection` and `search`) mention that `recreate_collection` and `search` methods are deprecated, but the code correctly uses the modern replacements (`delete_collection`/`create_collection` and `query_points`). This is a minor issue of outdated comments.
    *   **Red Teaming (L5 Mutagenesis):** Minor code hygiene, can cause confusion.
    *   **Severity:** Low
    *   **Impact:** Code readability and maintainability.
    *   **Suggested Remediation:** Remove or update the outdated comments.

*   **Issue 11: Low - UI/UX Inconsistencies (`static/app.js`, `static/index.html`)**
    *   **Description:**
        *   `zoomSpeed: -1`: Inverting the mouse wheel zoom direction is a non-standard UX choice that can disorient users.
        *   Hardcoded `groups` colors for 8 clusters (`groups: {0: ..., 7: ...}`). If `num_clusters` exceeds 8, new clusters will not have distinct colors, potentially reducing the utility of the clustering visualization.
    *   **Red Teaming (L0 Telos, L5 Mutagenesis):** Minor usability friction, limits extensibility of the UI.
    *   **Severity:** Low
    *   **Impact:** User experience, limited scalability of UI features.
    *   **Suggested Remediation:** Revert `zoomSpeed` to default or make it configurable. Implement a dynamic color palette for clusters (e.g., d3-scale) to support more than 8 clusters.

*   **Issue 12: Low - Custom PID Management in `manage.py`**
    *   **Description:** The `manage.py` script implements custom logic for starting and stopping background processes using `nohup`, `&`, and PID files. While it attempts robustness (`psutil.pid_exists`, scanning ports), this approach is generally more fragile and complex than using standard process managers (e.g., systemd, supervisord, or even Docker's built-in process management for services) for production environments. It can be prone to race conditions, orphaned processes, or incorrect PID detection in edge cases.
    *   **Red Teaming (L5 Mutagenesis):** Custom, non-standard solutions increase maintenance burden and reduce portability.
    *   **Severity:** Low (acceptable for dev CLI, but risky for production daemonization)
    *   **Impact:** Operational complexity, potential for orphaned processes, less reliable service restarts.
    *   **Suggested Remediation:** For production, rely on container orchestration or a dedicated process manager. For local dev, simplify the daemonization or clearly document its limitations.

*   **Issue 13: Plausible - Unclear `uvicorn` Worker Configuration (`manage.py`)**
    *   **Description:** `UVICORN_CMD` specifies `--workers`, but the value is hardcoded to `1`. The comment says: `# Crucial for ML models on GPU`. This implies that `workers > 1` would cause issues with ML models (likely memory-related on GPU, or concurrency issues with global model instances). If the system *ever* needs more workers for scaling CPU-bound tasks, this configuration might be a hidden bottleneck or a source of future bugs if changed without understanding the implications.
    *   **Red Teaming (L2 Metabolism, L5 Mutagenesis):** A potential scalability bottleneck that might be hidden.
    *   **Severity:** Plausible (requires deeper investigation to confirm if `workers > 1` is truly problematic and what the specific bottleneck is).
    *   **Impact:** Limits API throughput, makes scaling challenging.
    *   **Suggested Remediation:** Document the specific reasons and constraints for `workers=1` more thoroughly. Consider using `Gunicorn` with `uvicorn` workers for better process management if more workers are truly needed and ML models can be handled safely.

**Final Review of Octagon:**

*   **L0 Телос:** Issues 1 (Path Traversal), 2 (Non-Deterministic IDs), 3 (Concurrency), 8 (Inconsistent `file_type`), 9 (Hardcoded Path), 11 (UI/UX). All addressed.
*   **L1 Топология:** Issues 1 (Path Traversal), 5 (Fragile Base Dir), 8 (Inconsistent `file_type`). All addressed.
*   **L2 Метаболизм:** Issue 4 (Indexing Scalability), 13 (Uvicorn Workers). All addressed.
*   **L2 Кинематика:** Issue 3 (Concurrency Race Condition). Addressed.
*   **L2 Наследственность:** Issue 2 (Non-Deterministic IDs), 7 (In-Memory Task Status). All addressed.
*   **L3 Иммунитет:** Issues 1 (Path Traversal), 3 (Concurrency), 6 (shell=True). All addressed.
*   **L4 Гомеостаз:** Lack of deep monitoring and post-indexing data validation not explicitly listed as an "issue" but is an underlying theme for several problems. I will add a general finding about this.
    *   **Issue 14: Medium - Limited Observability & Post-Indexing Validation:**
        *   **Description:** The system provides basic task status updates, but lacks granular observability into the health of the Qdrant index (e.g., number of unique files, total chunks indexed, vector distribution). Crucially, there's no automated validation step post-indexing to confirm data integrity (e.g., count indexed chunks vs. source files, verify hashes after upsert). This means silent failures (e.g., hash collisions leading to duplicates, Qdrant rejecting points) might go unnoticed.
        *   **Red Teaming (L4 Гомеостаз):** Cannot detect when the system is "sick" or when its output is incorrect.
        *   **Severity:** Medium
        *   **Impact:** Delayed detection of data integrity issues, difficult debugging, lack of confidence in index quality.
        *   **Suggested Remediation:** Implement metrics for Qdrant (points count, segment health). Add post-indexing validation checks (e.g., compare indexed file hashes against source hashes, check for expected document counts).

*   **L5 Мутагенез:** Issues 2 (Non-Deterministic IDs), 7 (In-Memory Task Status), 9 (Hardcoded Path), 10 (Deprecated methods), 11 (UI/UX), 12 (Custom PID), 13 (Uvicorn Workers). All addressed.

This feels thorough and grounded. Now, structure the output.
</thought_process>
# Концептуальный Протокол: Аудит Системы Поиска `isearch`

## 1. Топология задачи (Ontology)
- **Мета-тип:** Аудит распределенной системы обработки данных с ML-компонентами.
- **Ключевой конфликт:** Баланс между производительностью/простотой разработки и надежностью/безопасностью/масштабируемостью в гибридной ML-системе.

## 2. Инварианты (Invariants)
1.  **Закон сохранения Целостности Данных:** Индекс в векторной базе должен точно и однозначно отражать исходные данные. Нарушение = потеря смысла поиска.
2.  **Принцип Изоляции Безопасности:** Пользовательский ввод, даже через промежуточные хранилища (Qdrant payload), не должен позволять доступ к файловой системе сервера за пределами ожидаемого.
3.  **Предел Масштабируемости (O(N) операции):** Операции, производительность которых линейно или экспоненциально зависит от общего объема данных, будут являться узким горлышком.

## 3. Точка опоры (Leverage Point)
-   **Фокус внимания:** Модули `src/services.py` (инкрементальное индексирование) и `src/vector_store.py` (взаимодействие с Qdrant). Эти модули отвечают за сбор, обработку и хранение данных, что является критической основой для всей системы поиска. Устранение корневых проблем здесь предотвратит каскадные сбои и деградацию.
-   **Игнорируемый шум:** Мелкие недоработки UI/UX в `static/app.js` или специфичные аспекты CLI в `manage.py` менее важны, чем фундаментальные проблемы безопасности и целостности данных.

## 4. Векторы энтропии (Degradation Paths)
-   **Анти-паттерн А (Дрейф Идентичности Данных):** Использование недетерминированных идентификаторов (`hash()`) приводит к "размыванию" уникальности точек в Qdrant, делая инкрементальное обновление неэффективным и вызывая дублирование данных.
-   **Когнитивное искажение Б (Оптимизм Безопасности):** Предположение, что данные, поступающие в бэкенд из "доверенных" источников (даже если они ранее были проиндексированы), безопасны для использования без дополнительной валидации, что приводит к уязвимостям.

## 5. Алгоритм стабилизации (The Protocol)
-   **Фаза 0: Изоляция.** Чётко определить границы доверия для всех входящих данных. Любые данные, которые могут быть манипулированы (прямо или косвенно, например, через Qdrant payload), должны быть подвергнуты строжайшей валидации перед использованием в файловых операциях или исполнении команд.
-   **Фаза 1: Оцифровка базиса.** Внедрить детерминированные, устойчивые к коллизиям механизмы идентификации для всех сущностей в базе (например, SHA256 для контента чанков). Создать централизованный, атомарный механизм управления состоянием индексации проекта (например, через распределенные блокировки).
-   **Фаза 2: Применение рычага.** Перестроить логику индексации для эффективной обработки больших объемов данных (избегая полного сканирования) и обеспечить атомарность операций для предотвращения гонок данных. Внедрить проверку целостности данных после индексации.
-   **Фаза 3: Интеграция и Стабилизация.** Документировать архитектурные решения по масштабируемости и безопасности. Внедрить расширенную телеметрию для мониторинга здоровья индекса и производительности.

## 6. Метрика истины (Truth Criteria)
-   **Состояние успеха:**
    1.  Невозможность чтения произвольных файлов через API, даже с манипулированным Qdrant payload.
    2.  Повторное индексирование одного и того же проекта (без изменения файлов) не приводит к изменению количества точек в Qdrant и не создает дубликатов.
    3.  Индексация большого проекта (100,000+ файлов) завершается за прогнозируемое время без сбоев и потери данных, а инкрементальное обновление кратно быстрее полного.
-   **Ложный сигнал успеха:** API отвечает `200 OK`, но данные в Qdrant повреждены, или индексация "завершается" без фактического обновления всех файлов.

## 7. Эвристики и Мета-Контекст (Heuristics & Meta-Context)
-   **Открытые вопросы:**
    *   Являются ли `EmbeddingModel` и `VectorStore` полностью потокобезопасными для всех операций, учитывая, что `BackgroundTasks` в FastAPI могут выполняться в отдельных потоках? (Хотя `workers=1` в `manage.py` снижает риск, это всё ещё глобальное mutable состояние).
    *   Каковы реальные пределы масштабируемости `_get_indexed_state` на больших проектах? Требуется нагрузочное тестирование.
-   **Тактические предложения:**
    *   Рассмотреть возможность использования Clickhouse или другого аналитического хранилища для сбора метрик и логов индексации Qdrant, чтобы обеспечить глубокую наблюдаемость.
    *   Изучить возможность использования `qdrant_client.points.upsert` с `update_vectors=False` при неизменном контенте для оптимизации.
-   **Комментарии оператора:** Проект имеет хороший базовый функционал, но требует значительного внимания к вопросам надежности, безопасности и масштабируемости, особенно в части взаимодействия с Qdrant и обработки путей файлов.

## 8. Резолюция и Архитектурная Развилка (Approval Gate)
-   **Фундаментальный диагноз:** Система `isearch` подвержена уязвимостям безопасности, проблемам целостности данных и масштабируемости из-за недостаточной валидации ввода, недетерминированной генерации ID и отсутствия механизмов блокировки в конвейере индексирования.

-   **Стратегические варианты (The Forks):**

    -   **Вариант А: Реактивное Исправление Критических Проблем.**
        *   **Плюсы:** Быстрое устранение наиболее серьезных угроз (Path Traversal, Недетерминированные ID, Гонки данных). Минимальные затраты ресурсов в краткосрочной перспективе.
        *   **Минусы:** Остаются проблемы масштабируемости, наблюдаемости и менее критичные архитектурные недочеты. Система останется хрупкой при росте нагрузки или изменении требований.
        *   **Цена внедрения:** Низкая (точечные патчи).

    -   **Вариант Б: Комплексное Перепроектирование Индексирования и Усиление Безопасности.**
        *   **Плюсы:** Фундаментальное решение всех выявленных проблем. Создание масштабируемой, безопасной и надежной архитектуры для индексирования. Повышение общей стабильности и предсказуемости системы.
        *   **Минусы:** Высокие начальные затраты на проектирование и реализацию. Возможный простой функциональности индексации на время переработки.
        *   **Цена внедрения:** Высокая (значительный рефакторинг, возможно, изменение логики хранения метаданных).

-   **Рекомендация ИИ:** Я рекомендую **Вариант Б: Комплексное Перепроектирование Индексирования и Усиление Безопасности**. Хотя это более затратный путь в краткосрочной перспективе, проблемы, такие как Path Traversal, недетерминированные ID и гонки данных, являются системными и могут привести к катастрофическим последствиям при эксплуатации. Реактивное исправление (Вариант А) оставит глубокие структурные проблемы, которые неизбежно проявятся позже и будут стоить гораздо дороже. Фундаментальная природа этих дефектов требует системного подхода.

-   **Ближайшие физические шаги (Next Steps):**
    1.  **[APPROVAL GATE]** Ожидание решения оператора (Выбор Варианта А или Б).
    2.  **[ЗАПРЕТ]** ИИ не имеет права генерировать итоговый рабочий код до явного подтверждения выбора оператором.

## 8.1 Генерация Исполняемого Артефакта (Мост ABRA -> CADABRA)
*Трансляция утверждённого архитектурного решения в машиночитаемый контракт для автономного агента-исполнителя. Выполняется только ПОСЛЕ Approval Gate и явной команды оператора.*

**(Ожидает утверждения оператора)**

## 9. Верификация (Fitness Log)
-   **Применён:** (будет заполнено после имплементации)
-   **Мутировал:** (будет заполнено после имплементации)
-   **Мёртв:** (будет заполнено после имплементации)

```text
Сохранение результата аудита в файл abra.md...
```

**Content for `abra.md`:**

```markdown
# Концептуальный Протокол: Аудит Системы Поиска `isearch`

## 1. Топология задачи (Ontology)
- **Мета-тип:** Аудит распределенной системы обработки данных с ML-компонентами.
- **Ключевой конфликт:** Баланс между производительностью/простотой разработки и надежностью/безопасностью/масштабируемостью в гибридной ML-системе.

## 2. Инварианты (Invariants)
1.  **Закон сохранения Целостности Данных:** Индекс в векторной базе должен точно и однозначно отражать исходные данные. Нарушение = потеря смысла поиска.
2.  **Принцип Изоляции Безопасности:** Пользовательский ввод, даже через промежуточные хранилища (Qdrant payload), не должен позволять доступ к файловой системе сервера за пределами ожидаемого.
3.  **Предел Масштабируемости (O(N) операции):** Операции, производительность которых линейно или экспоненциально зависит от общего объема данных, будут являться узким горлышком.

## 3. Точка опоры (Leverage Point)
-   **Фокус внимания:** Модули `src/services.py` (инкрементальное индексирование) и `src/vector_store.py` (взаимодействие с Qdrant). Эти модули отвечают за сбор, обработку и хранение данных, что является критической основой для всей системы поиска. Устранение корневых проблем здесь предотвратит каскадные сбои и деградацию.
-   **Игнорируемый шум:** Мелкие недоработки UI/UX в `static/app.js` или специфичные аспекты CLI в `manage.py` менее важны, чем фундаментальные проблемы безопасности и целостности данных.

## 4. Векторы энтропии (Degradation Paths)
-   **Анти-паттерн А (Дрейф Идентичности Данных):** Использование недетерминированных идентификаторов (`hash()`) приводит к "размыванию" уникальности точек в Qdrant, делая инкрементальное обновление неэффективным и вызывая дублирование данных.
-   **Когнитивное искажение Б (Оптимизм Безопасности):** Предположение, что данные, поступающие в бэкенд из "доверенных" источников (даже если они ранее были проиндексированы), безопасны для использования без дополнительной валидации, что приводит к уязвимостям.

## 5. Алгоритм стабилизации (The Protocol)
-   **Фаза 0: Изоляция.** Чётко определить границы доверия для всех входящих данных. Любые данные, которые могут быть манипулированы (прямо или косвенно, например, через Qdrant payload), должны быть подвергнуты строжайшей валидации перед использованием в файловых операциях или исполнении команд.
-   **Фаза 1: Оцифровка базиса.** Внедрить детерминированные, устойчивые к коллизиям механизмы идентификации для всех сущностей в базе (например, SHA256 для контента чанков). Создать централизованный, атомарный механизм управления состоянием индексации проекта (например, через распределенные блокировки).
-   **Фаза 2: Применение рычага.** Перестроить логику индексации для эффективной обработки больших объемов данных (избегая полного сканирования) и обеспечить атомарность операций для предотвращения гонок данных. Внедрить проверку целостности данных после индексации.
-   **Фаза 3: Интеграция и Стабилизация.** Документировать архитектурные решения по масштабируемости и безопасности. Внедрить расширенную телеметрию для мониторинга здоровья индекса и производительности.

## 6. Метрика истины (Truth Criteria)
-   **Состояние успеха:**
    1.  Невозможность чтения произвольных файлов через API, даже с манипулированным Qdrant payload.
    2.  Повторное индексирование одного и того же проекта (без изменения файлов) не приводит к изменению количества точек в Qdrant и не создает дубликатов.
    3.  Индексация большого проекта (100,000+ файлов) завершается за прогнозируемое время без сбоев и потери данных, а инкрементальное обновление кратно быстрее полного.
-   **Ложный сигнал успеха:** API отвечает `200 OK`, но данные в Qdrant повреждены, или индексация "завершается" без фактического обновления всех файлов.

## 7. Эвристики и Мета-Контекст (Heuristics & Meta-Context)
-   **Открытые вопросы:**
    *   Являются ли `EmbeddingModel` и `VectorStore` полностью потокобезопасными для всех операций, учитывая, что `BackgroundTasks` в FastAPI могут выполняться в отдельных потоках? (Хотя `workers=1` в `manage.py` снижает риск, это всё ещё глобальное mutable состояние).
    *   Каковы реальные пределы масштабируемости `_get_indexed_state` на больших проектах? Требуется нагрузочное тестирование.
-   **Тактические предложения:**
    *   Рассмотреть возможность использования Clickhouse или другого аналитического хранилища для сбора метрик и логов индексации Qdrant, чтобы обеспечить глубокую наблюдаемость.
    *   Изучить возможность использования `qdrant_client.points.upsert` с `update_vectors=False` при неизменном контенте для оптимизации.
-   **Комментарии оператора:** Проект имеет хороший базовый функционал, но требует значительного внимания к вопросам надежности, безопасности и масштабируемости, особенно в части взаимодействия с Qdrant и обработки путей файлов.

## 8. Резолюция и Архитектурная Развилка (Approval Gate)
-   **Фундаментальный диагноз:** Система `isearch` подвержена уязвимостям безопасности, проблемам целостности данных и масштабируемости из-за недостаточной валидации ввода, недетерминированной генерации ID и отсутствия механизмов блокировки в конвейере индексирования.

-   **Стратегические варианты (The Forks):**

    -   **Вариант А: Реактивное Исправление Критических Проблем.**
        *   **Плюсы:** Быстрое устранение наиболее серьезных угроз (Path Traversal, Недетерминированные ID, Гонки данных). Минимальные затраты ресурсов в краткосрочной перспективе.
        *   **Минусы:** Остаются проблемы масштабируемости, наблюдаемости и менее критичные архитектурные недочеты. Система останется хрупкой при росте нагрузки или изменении требований.
        *   **Цена внедрения:** Низкая (точечные патчи).

    -   **Вариант Б: Комплексное Перепроектирование Индексирования и Усиление Безопасности.**
        *   **Плюсы:** Фундаментальное решение всех выявленных проблем. Создание масштабируемой, безопасной и надежной архитектуры для индексирования. Повышение общей стабильности и предсказуемости системы.
        *   **Минусы:** Высокие начальные затраты на проектирование и реализацию. Возможный простой функциональности индексации на время переработки.
        *   **Цена внедрения:** Высокая (значительный рефакторинг, возможно, изменение логики хранения метаданных).

-   **Рекомендация ИИ:** Я рекомендую **Вариант Б: Комплексное Перепроектирование Индексирования и Усиление Безопасности**. Хотя это более затратный путь в краткосрочной перспективе, проблемы, такие как Path Traversal, недетерминированные ID и гонки данных, являются системными и могут привести к катастрофическим последствиям при эксплуатации. Реактивное исправление (Вариант А) оставит глубокие структурные проблемы, которые неизбежно проявятся позже и будут стоить гораздо дороже. Фундаментальная природа этих дефектов требует системного подхода.

-   **Ближайшие физические шаги (Next Steps):**
    1.  **[APPROVAL GATE]** Ожидание решения оператора (Выбор Варианта А или Б).
    2.  **[ЗАПРЕТ]** ИИ не имеет права генерировать итоговый рабочий код до явного подтверждения выбора оператором.

## 8.1 Генерация Исполняемого Артефакта (Мост ABRA -> CADABRA)
*Трансляция утверждённого архитектурного решения в машиночитаемый контракт для автономного агента-исполнителя. Выполняется только ПОСЛЕ Approval Gate и явной команды оператора.*

## 9. Верификация (Fitness Log)
-   **Применён:**
-   **Мутировал:**
-   **Мёртв:**

---

### Дефекты и Рекомендации

**1. Critical - Path Traversal в `extract_snippet` (`src/main.py`)**
-   **Описание:** Функция `extract_snippet` строит путь к файлу, используя `project_path / source_file`. Значение `source_file` берется из payload Qdrant, которое может быть манипулировано во время индексации. Злоумышленник может внедрить `../` последовательности, что позволит читать произвольные файлы на сервере.
-   **Impact:** Раскрытие информации, потенциальное RCE.
-   **Рекомендация:** Реализовать строгую очистку и проверку пути `source_file` (например, с использованием `pathlib.Path.resolve(strict=True)` с проверкой на вхождение в `project_path`) перед открытием файлов.

**2. Critical - Недетерминированные Qdrant Point IDs (`src/vector_store.py`)**
-   **Описание:** ID точек Qdrant генерируются с использованием `abs(hash(content))`. `hash()` в Python по умолчанию недетерминирован без установки `PYTHONHASHSEED`. Это приводит к тому, что одно и то же содержимое может получить разные ID при повторной индексации, создавая дубликаты вместо обновлений и нарушая целостность инкрементального индекса.
-   **Impact:** Потеря целостности данных, раздувание индекса, деградация качества поиска, потенциальные проблемы с производительностью.
-   **Рекомендация:** Использовать криптографически стойкую, детерминированную хеш-функцию (например, SHA256) для ID точек или принудительно устанавливать `PYTHONHASHSEED`.

**3. High - Гонка Состояний при Конкурентной Индексации (`src/services.py`)**
-   **Описание:** Метод `run_indexing` не имеет механизмов блокировки для предотвращения одновременной индексации одного и того же проекта. Конкурентные запросы могут привести к гонкам данных, повреждению индекса Qdrant или непоследовательным обновлениям.
-   **Impact:** Повреждение данных, непоследовательные результаты поиска, нестабильность системы.
-   **Рекомендация:** Внедрить мьютекс/блокировку на каждый проект (например, `threading.Lock` или распределенную блокировку) для обеспечения атомарности операций индексации.

**4. High - Бутылочное Горлышко Масштабируемости при Инкрементальной Индексации (`_get_indexed_state` в `src/services.py`)**
-   **Описание:** Функция `_get_indexed_state` считывает *все* существующие точки из коллекции Qdrant для определения состояния индекса. Для очень больших проектов эта операция будет медленной и ресурсоемкой, что делает инкрементальную индексацию неэффективной.
-   **Impact:** Низкая производительность для больших проектов, увеличение времени индексации, потенциальные сбои сервиса.
-   **Рекомендация:** Использовать более эффективные механизмы Qdrant (например, фильтрацию по `source_file` и `file_hash` без векторов) или внешнее хранилище метаданных для отслеживания состояния индекса.

**5. Medium - Хрупкий Дефолтный `PROJECTS_BASE_DIR` (`src/config.py`)**
-   **Описание:** Значение по умолчанию для `PROJECTS_BASE_DIR` — `..`, что означает родительскую директорию места запуска приложения. Это неявное и потенциально опасное предположение, которое может привести к неверной конфигурации или проблемам безопасности.
-   **Impact:** Неверная конфигурация, несанкционированный доступ к файлам, потенциальный риск безопасности.
-   **Рекомендация:** Установить явный и контролируемый путь по умолчанию (например, `Path(__file__).parent / "projects"`) или требовать явное указание абсолютного пути.

**6. Medium - Небезопасное использование `shell=True` в `manage.py`**
-   **Описание:** Команда `service_up` использует `subprocess.Popen(command_str, shell=True, ...)`, что является риском безопасности, если `command_str` когда-либо будет контролироваться извне.
-   **Impact:** Потенциальная инъекция команд.
-   **Рекомендация:** Избегать `shell=True` и передавать команды в виде списка аргументов.

**7. Medium - Волатильность Статуса Задач в Памяти (`src/main.py`)**
-   **Описание:** Словарь `TASK_STATUS` хранится в памяти. При перезапуске API все статусы задач теряются, что затрудняет мониторинг и восстановление длительных фоновых операций.
-   **Impact:** Плохой пользовательский опыт, потеря операционной видимости, отсутствие восстановления прерванных задач.
-   **Рекомендация:** Сохранять статус задач в постоянном хранилище (например, SQLite, Redis) для обеспечения надежности и восстановления после перезапуска.

**8. Medium - Несоответствие маркировки `file_type` (`src/services.py` vs. UI/Keywords)**
-   **Описание:** В `IndexingService` `file_type` присваивается как `"code"` или `"docs"`. В `src/main.py` поиск может использовать `doc_keywords` (например, "documentation"), а UI использует `toggle-docs`. Несогласованность в терминологии (`"doc"` vs `"docs"` vs `"documentation"`) может привести к путанице или ошибкам в фильтрации и бустинге поиска.
-   **Impact:** Хрупкая логика фильтрации, когнитивная нагрузка.
-   **Рекомендация:** Стандартизировать терминологию для "документации" на всех уровнях системы (payload `file_type`, ключевые слова поиска, метки UI).

**9. Medium - Ограниченная Наблюдаемость и Отсутствие Постиндексационной Валидации**
-   **Описание:** Система не предоставляет достаточной телеметрии для мониторинга здоровья индекса Qdrant (например, количество уникальных файлов, сегменты). Отсутствует автоматическая проверка целостности данных после индексации.
-   **Impact:** Задержка в обнаружении проблем целостности данных, затрудненная отладка, отсутствие уверенности в качестве индекса.
-   **Рекомендация:** Внедрить метрики Qdrant (количество точек, состояние сегментов) и добавить проверки валидации после индексации (сравнение хешей, ожидаемые количества документов).

**10. Low - Жестко Заданный `PROJECT_ROOT_PATH` в `src/index.py` (Скрипт)**
-   **Описание:** Скрипт `src/index.py` жестко задает путь `PROJECT_ROOT_PATH` к 'autowarp', что ограничивает его использование для других проектов без ручной модификации.
-   **Impact:** Негибкость, дополнительные ручные усилия.
-   **Рекомендация:** Преобразовать `src/index.py` для приема `project_name` в качестве аргумента командной строки.

**11. Low - Устаревшие Комментарии Qdrant Client (`src/vector_store.py`)**
-   **Описание:** Комментарии в `VectorStore` (например, в `recreate_collection` и `search`) указывают на устаревшие методы, хотя код использует современные замены.
-   **Impact:** Снижение читабельности и поддерживаемости кода.
-   **Рекомендация:** Удалить или обновить устаревшие комментарии.

**12. Low - Пользовательское Управление PID в `manage.py`**
-   **Описание:** Скрипт `manage.py` реализует пользовательскую логику для запуска и остановки фоновых процессов с помощью `nohup` и PID-файлов. Это менее надежно и более сложно, чем использование стандартных системных менеджеров процессов.
-   **Impact:** Операционная сложность, потенциально неустойчивые перезапуски.
-   **Рекомендация:** Для продакшена использовать оркестрацию контейнеров или специализированный менеджер процессов. Для локальной разработки упростить демонизацию или задокументировать ограничения.

**13. Plausible - Неясная Конфигурация `uvicorn` Workers (`manage.py`)**
-   **Описание:** `UVICORN_CMD` жестко задает `--workers 1` с комментарием "Crucial for ML models on GPU". Это потенциальное узкое место для масштабирования, если потребуется большее количество воркеров для CPU-интенсивных задач, а причина ограничения не полностью ясна или может измениться.
-   **Impact:** Ограничивает пропускную способность API, затрудняет масштабирование.
-   **Рекомендация:** Более полно документировать конкретные причины и ограничения для `workers=1`.

```