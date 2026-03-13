## Отчёт об Аудите Кодовой Базы Проекта `isearch`

**Дата аудита:** 2024-07-28
**Инженер-аудитор:** Senior Software/System Engineer
**Проект:** `isearch` (поисковая система)

### Введение

Проект `isearch` представляет собой систему для семантического поиска и анализа графов кода, построенную на FastAPI, Sentence Transformers и Qdrant. В ходе аудита были рассмотрены архитектурные решения, логика работы с данными, контракты API, взаимодействие с векторной базой данных и обработка пограничных случаев. Целью аудита является выявление потенциальных уязвимостей и областей для улучшения.

---

### Структурированный Отчёт о Дефектах

#### 1. Архитектурные Уязвимости

| Название Проблемы | Описание | Место | Критичность |
|---|---|---|---|
| **1.1. Недетерминированные Point ID в Qdrant (GT-3)** | Использование `abs(hash(content))` для генерации Point ID в Qdrant является критической уязвимостью. Функция `hash()` в Python не гарантирует стабильность и может возвращать разные значения для одного и того же строкового содержимого при разных запусках, на разных машинах или с разными версиями Python (без фиксации `PYTHONHASHSEED`). Это приводит к: 1) **Дублированию данных**: При инкрементальном индексировании те же чанки могут быть вставлены как новые точки, а не обновлены. 2) **Потере обновлений**: Старые точки остаются, новые создаются, что искажает состояние индекса. 3) **Удвоение коллизий**: `abs()` дополнительно уменьшает пространство хэшей, увеличивая вероятность коллизий. | `src/vector_store.py` (`upsert`), `src/services.py` | **Критическая** |
| **1.2. Гонка Условий при Обновлении Состояния Задач (GT-4)** | Состояние асинхронных задач (`TASK_STATUS`) хранится в глобальной in-memory переменной (`Dict[str, Dict[str, Any]]`) в `src/main.py`. При перезапуске приложения (например, при обновлении, сбое или завершении `uvicorn` в dev-режиме) вся информация о текущих задачах индексирования теряется. Это приводит к потере отслеживания прогресса для пользователя. Более того, при использовании нескольких `uvicorn` воркеров (или при потенциальной конкурентной записи из разных async-задач, хотя в `uvicorn --workers 1` это менее вероятно, но не исключено для сложных async-потоков), могут возникнуть гонки условий при обновлении `TASK_STATUS`. | `src/main.py` (`TASK_STATUS`, `update_task_status`), `static/app.js` (клиентская часть, полагающаяся на `TASK_STATUS`) | **Высокая** |
| **1.3. Скрытая Деструктивная Операция Reindex (Model Dimension Change)** | Логика инкрементального индексирования в `IndexingService.run_indexing` предусматривает пересоздание коллекции Qdrant (`self.vector_store.recreate_collection`) в случае, если текущая размерность векторов в коллекции (`collection_info.vectors_config.params.size`) не соответствует размерности текущей модели (`self.embedder.get_embedding_dim()`). Хотя это необходимо для корректности, такое поведение является деструктивным (полное удаление индекса проекта) и происходит без явного предупреждения или подтверждения пользователя, что может привести к неожиданной потере данных. | `src/services.py` (`IndexingService.run_indexing`) | **Высокая** |
| **1.4. Жесткое Кодирование Пути к Проекту в Скрипте `index.py`** | Скрипт `src/index.py` использует жестко закодированный путь `PROJECT_ROOT_PATH = Path(__file__).parent.parent.parent / 'autowarp'`. Этот скрипт, по-видимому, является автономной утилитой для индексирования конкретного проекта, а не частью основного API, который использует `IndexingService` с динамическим `projects_base_dir`. Это создает путаницу и является dead/misleading кодом, так как не отражает реальный механизм индексации, используемый FastAPI. | `src/index.py` | **Низкая** |
| **1.5. Отсутствие Блокировок на Уровне Проекта для Индексирования** | В текущей архитектуре отсутствует механизм предотвращения одновременного запуска нескольких задач индексирования для одного и того же проекта. Если пользователь запускает `index` для проекта `X` несколько раз подряд, это может привести к конкурентным операциям upsert и delete в Qdrant для одной коллекции, что потенциально может вызвать ошибки, дублирование данных или неконсистентное состояние. | `src/main.py` (`index_project_endpoint`), `src/services.py` (`IndexingService`) | **Средняя** |

#### 2. Логические Уязвимости

| Название Проблемы | Описание | Место | Критичность |
|---|---|---|---|
| **2.1. Неполный Скроллинг в Endpoint Кластеризации** | В эндпоинте `/projects/{project_name}/clusters` используется `vector_store.client.scroll(..., limit=10000)` для получения всех точек. Параметр `limit=10000` фиксирован, что означает, что для проектов с более чем 10 000 чанками будет получена лишь часть данных, что приведет к неполным и некорректным результатам кластеризации. Механизм пагинации с `offset` не используется для получения всех записей. | `src/main.py` (`perform_clustering`) | **Высокая** |
| **2.2. Неоптимальная Логика Keyword Boosting в Поиске** | Эвристика keyword boosting в `search_project_endpoint` (увеличение `score` на `0.1` для `top_hit` в группе) имеет несколько недостатков: 1) **Применяется только к первому хиту**: Только самый релевантный хит в каждой группе файлов получает буст, игнорируя другие потенциально релевантные хиты в том же файле. 2) **Пост-обработка**: Буст применяется после основного семантического поиска и группировки, что может не приводить к оптимальному переранжированию всех результатов. 3) **Наивные ключевые слова**: Список ключевых слов может быть неполным или чрезмерно общим, что может приводить к нежелательным бустам. Более надежным подходом было бы интегрировать ключевые слова непосредственно в запрос Qdrant (например, через `should` фильтры с `boost`) или реализовать более сложный алгоритм реранжирования. | `src/main.py` (`search_project_endpoint`) | **Средняя** |
| **2.3. Упрощенный Разрешитель Python Импортов в `graph_builder`** | Функция `_resolve_import_path` в `src/graph_builder.py` является упрощенной и может некорректно обрабатывать сложные сценарии импорта Python, такие как: - Динамические импорты (например, `importlib`). - Изменения `sys.path` во время выполнения. - Импорты из namespace-пакетов или установленных пакетов, не являющихся частью `project_root`. Это может привести к неполным или неверным связям в графе зависимостей для сложных Python-проектов. | `src/graph_builder.py` (`_resolve_import_path`, `parse_python_file`) | **Средняя** |
| **2.4. Неполное Определение Типов Файлов в `graph_builder` (Code Mention Regex)** | Регулярное выражение `CODE_MENTION_RE` в `src/graph_builder.py` для обнаружения упоминаний файлов кода в markdown ограничивает типы файлов до `py|js|ts|sh|yml|yaml`. Это означает, что упоминания других типов файлов, которые система может индексировать (например, `Dockerfile`, `.toml`, `.json`, `.css`, `.ini` из `IndexingService.allowed_extensions`), не будут учтены при построении графа зависимостей. Это приводит к неполному графу. | `src/graph_builder.py` (`CODE_MENTION_RE`, `parse_markdown_file`) | **Низкая** |
| **2.5. Слишком широкое исключение файлов в `Makefile`** | В `Makefile` для всех команд `make` устанавливаются пустые переменные окружения для прокси (`http_proxy="" ...`). Хотя это предотвращает попытки подключения к Qdrant через прокси, это также означает, что если любая часть приложения (например, `SentenceTransformer` при ленивой загрузке модели или её кешировании) попытается сделать внешний запрос, требующий прокси, она может потерпеть неудачу. `preload_model.py` предназначен для предварительной загрузки, но если модель не была предварительно загружена или кеш был очищен, это может привести к проблемам. | `Makefile` | **Средняя** |

#### 3. Инфраструктурные Уязвимости

| Название Проблемы | Описание | Место | Критичность |
|---|---|---|---|
| **3.1. Зависимость от `uv` без Явной Проверки Установки** | `Makefile` использует `uv run python manage.py` для всех команд. Это предполагает, что `uv` (или `uv.venv` если он не установлен) доступен и корректно настроен. Если `uv` не установлен в системе пользователя, `Makefile` будет выдавать ошибку "command not found" без предоставления четких инструкций по его установке. | `Makefile` | **Низкая** |
| **3.2. Хрупкое Управление `sys.path` в `preload_model.py`** | Использование `sys.path.append(os.getcwd())` в `preload_model.py` для обеспечения импорта из `src.config` является хрупким. Если скрипт запускается из директории, отличной от корня проекта, `os.getcwd()` вернет неверный путь, что приведет к `ImportError`. Более надежным подходом было бы использовать `sys.path.append(str(Path(__file__).parent.parent))` для явного добавления пути `src` в `sys.path`. | `preload_model.py` | **Низкая** |
| **3.3. Несоответствие Названия Qdrant Local Data в `debug_qdrant.py`** | В `debug_qdrant.py` клиент Qdrant инициализируется с `path="./test_qdrant"`, но в файловой системе существуют папки `qdrant_local_data` и `qdrant_storage`, которые, судя по всему, используются для локального хранения Qdrant. Это несоответствие может вызвать путаницу при отладке и некорректно показывать статус локальной базы данных. Это не уязвимость, а скорее проблема ясности. | `debug_qdrant.py`, `.qdrant_local_data`, `qdrant_storage` | **Низкая** |

#### 4. Уязвимости Обработки Данных

| Название Проблемы | Описание | Место | Критичность |
|---|---|---|---|
| **4.1. Потенциально Неэффективное Получение Файлов для Индексации** | В `src/index.py` (который, как было отмечено, является standalone скриптом, но демонстрирует базовую логику) `all_paths = list(root_path.rglob('*'))` сначала собирает ВСЕ пути в проекте, а затем фильтрует их по `.gitignore` и расширениям. Для очень больших проектов это может быть неэффективным по памяти и времени, так как создается большой список путей, многие из которых будут отфильтрованы. Более оптимальным является подход, используемый в `IndexingService._scan_local_files`, где `os.walk` модифицирует `dirnames` in-place, избегая обхода игнорируемых директорий. | `src/index.py` (`load_documents`) | **Средняя** |
| **4.2. Базовая Стратегия Чанкинга** | Стратегия чанкинга в `src/index.py` (`content.split('\n\n')`) и в `src/services.py` (`chunk_size_lines = 15, chunk_overlap_lines = 2`) является достаточно базовой. Для лучшего качества поиска, особенно для кода, более продвинутые методы чанкинга могут быть полезны, например: - Семантический чанкинг (основанный на структуре кода: функции, классы, комментарии). - Разделение по абзацам для документации. - Автоматическая адаптация размера чанка. Текущий подход может разрывать логические блоки кода или текста, что снижает релевантность эмбеддингов. | `src/index.py` (`load_documents`), `src/services.py` (`_process_files_in_batches`) | **Низкая** |

#### 5. Пограничные Случаи / Надёжность

| Название Проблемы | Описание | Место | Критичность |
|---|---|---|---|
| **5.1. Отсутствие Валидации `project_name` в API Endpoints** | Большинство API-эндпоинтов, таких как `index`, `search`, `graph`, `orphans`, принимают `project_name` как строковый параметр. Хотя он используется для создания пути (`projects_base_dir / project_name`), неявная валидация полагается на файловую систему (проверка `is_dir()`). Однако, если `project_name` содержит специальные символы, которые допустимы в URL, но недопустимы или имеют особое значение в именах файлов/директорий в ОС, это может привести к ошибкам. Более того, при использовании `Path.resolve()` это снижает риски, но явное ограничение символов для `project_name` через Pydantic-модель или регуляцию символов было бы безопаснее и надежнее. | `src/main.py` (все эндпоинты, принимающие `project_name`) | **Низкая** |
| **5.2. Потенциальная Несогласованность `API_PORT`** | Переменная `API_PORT` читается из `os.getenv("API_PORT", "8765")` в `manage.py`. Если API запускается через `manage.py service dev` или `manage.py service up`, этот порт используется. Однако, если `uvicorn` или `FastAPI` запущены вручную (не через `manage.py`), и переменная окружения `API_PORT` не установлена или установлена по-другому, `manage.py` будет пытаться взаимодействовать с неправильным портом, что приведет к ошибкам подключения. Это, скорее, вопрос эксплуатации и документирования. | `manage.py` | **Низкая** |

---

### Резюме и Рекомендации

Проект `isearch` демонстрирует хорошо продуманную структуру и использование современных технологий для семантического поиска. Однако, в ходе аудита были выявлены несколько критических и высокоприоритетных уязвимостей, которые могут серьезно повлиять на стабильность, целостность данных и надежность системы.

**Ключевые Рекомендации (для немедленного внедрения):**

1.  **Исправить Недетерминированные Point ID в Qdrant (GT-3):** Заменить `abs(hash(content))` на детерминированный алгоритм, например, SHA256 хэш строкового представления содержимого чанка, преобразованный в `UUID` или строку, которую Qdrant может использовать в качестве ID точки. Это критически важно для предотвращения дублирования данных и обеспечения корректного инкрементального индексирования.
2.  **Решить Проблему Гонки Условий и Потери Состояния Задач (GT-4):**
    *   Для `TASK_STATUS` следует рассмотреть персистентное хранилище (например, Redis, небольшая SQLite база или даже файл на диске) вместо in-memory словаря.
    *   Реализовать явный механизм блокировки (например, с использованием `asyncio.Lock` или распределенного мьютекса, если планируется масштабирование до нескольких инстансов API) для предотвращения одновременного индексирования одного и того же проекта.
3.  **Внедрить Уведомления о Деструктивных Операциях:** Добавить явные предупреждения или требования подтверждения для пользователя перед выполнением деструктивных действий, таких как полное пересоздание коллекции Qdrant из-за изменения размерности модели.
4.  **Улучшить Обработку Больших Проектов в Кластеризации:** В эндпоинте `/projects/{project_name}/clusters` реализовать корректную пагинацию (используя `next_page_offset` в цикле `while True`) для Qdrant `scroll`, чтобы гарантировать обработку всех векторов независимо от размера проекта.
5.  **Пересмотреть Стратегию Keyword Boosting:** Для улучшения качества поиска рассмотреть возможность интеграции keyword boosting непосредственно в запросы Qdrant (если это позволяет API Qdrant) или реализовать более продвинутый алгоритм реранжирования, который применяется ко всем релевантным хитам, а не только к `top_hit` в каждой группе.

Внедрение этих рекомендаций значительно повысит надежность, масштабируемость и пользовательский опыт проекта `isearch`.

---
*(Сохранение отчета в файл `baseline.md`)*
```
# iSearch Project Codebase Audit Report

## Date of Audit: 2024-07-28
## Auditor: Senior Software/System Engineer
## Project: `isearch` (Search Engine)

### Introduction

The `isearch` project is a system for semantic search and code graph analysis, built on FastAPI, Sentence Transformers, and Qdrant. This audit reviewed architectural decisions, data handling logic, API contracts, vector database interaction, and edge case processing. The goal of the audit is to identify potential vulnerabilities and areas for improvement.

---

### Structured Defect Report

#### 1. Architectural Vulnerabilities

| Problem Name | Description | Location | Criticality |
|---|---|---|---|
| **1.1. Non-deterministic Qdrant Point IDs (GT-3)** | Using `abs(hash(content))` to generate Point IDs in Qdrant is a critical vulnerability. Python's `hash()` function does not guarantee stability and can return different values for the same string content across different runs, on different machines, or with different Python versions (without fixing `PYTHONHASHSEED`). This leads to: 1) **Data Duplication**: During incremental indexing, the same chunks can be inserted as new points rather than updated. 2) **Lost Updates**: Old points remain while new ones are created, distorting the index state. 3) **Increased Collisions**: `abs()` further reduces the hash space, increasing collision probability. | `src/vector_store.py` (`upsert`), `src/services.py` | **Critical** |
| **1.2. Race Condition on Task Status Updates (GT-4)** | The state of asynchronous tasks (`TASK_STATUS`) is stored in a global in-memory variable (`Dict[str, Dict[str, Any]]`) in `src/main.py`. If the FastAPI application restarts (e.g., due to code changes in dev mode, deployment, crash, or `uvicorn` termination), all task status information is lost. This results in users losing track of their indexing progress. Furthermore, when using multiple `uvicorn` workers (or in the event of potential concurrent writes from different async tasks, though less likely with `--workers 1`, it's not impossible for complex async flows), race conditions can occur during `TASK_STATUS` updates. | `src/main.py` (`TASK_STATUS`, `update_task_status`), `static/app.js` (client-side relying on `TASK_STATUS`) | **High** |
| **1.3. Hidden Destructive Reindex Operation (Model Dimension Change)** | The incremental indexing logic in `IndexingService.run_indexing` involves recreating the Qdrant collection (`self.vector_store.recreate_collection`) if the current vector dimension in the collection (`collection_info.vectors_config.params.size`) does not match the dimension of the current model (`self.embedder.get_embedding_dim()`). While necessary for correctness, this behavior is destructive (a complete deletion of the project's index) and occurs without explicit user warning or confirmation, which can lead to unexpected data loss. | `src/services.py` (`IndexingService.run_indexing`) | **High** |
| **1.4. Hardcoded Project Path in `index.py` Script** | The `src/index.py` script uses a hardcoded path `PROJECT_ROOT_PATH = Path(__file__).parent.parent.parent / 'autowarp'`. This script appears to be a standalone indexing utility for a specific project, rather than part of the main API, which uses `IndexingService` with a dynamic `projects_base_dir`. This creates confusion and is essentially dead/misleading code, as it doesn't reflect the actual indexing mechanism used by FastAPI. | `src/index.py` | **Low** |
| **1.5. Lack of Per-Project Indexing Locks** | The current architecture lacks a mechanism to prevent multiple indexing tasks from running concurrently for the same project. If a user triggers `index` for project `X` multiple times in quick succession, it could lead to concurrent upsert and delete operations within Qdrant for the same collection, potentially causing errors, data duplication, or an inconsistent index state. | `src/main.py` (`index_project_endpoint`), `src/services.py` (`IndexingService`) | **Medium** |

#### 2. Logical Vulnerabilities

| Problem Name | Description | Location | Criticality |
|---|---|---|---|
| **2.1. Incomplete Scrolling in Clustering Endpoint** | The `/projects/{project_name}/clusters` endpoint uses `vector_store.client.scroll(..., limit=10000)` to retrieve points. The `limit=10000` parameter is fixed, meaning that for projects with more than 10,000 chunks, only a portion of the data will be retrieved, leading to incomplete and incorrect clustering results. Proper pagination using `offset` is not implemented to fetch all records. | `src/main.py` (`perform_clustering`) | **High** |
| **2.2. Suboptimal Keyword Boosting Logic in Search** | The keyword boosting heuristic in `search_project_endpoint` (increasing the `score` by `0.1` for the `top_hit` in a group) has several drawbacks: 1) **Only applies to the first hit**: Only the most relevant hit in each file group gets a boost, ignoring other potentially relevant hits within the same file. 2) **Post-processing**: The boost is applied after the primary semantic search and grouping, which may not lead to optimal re-ranking of all results. 3) **Naive Keywords**: The list of keywords can be incomplete or overly generic, potentially leading to unintended boosts. A more robust approach would involve integrating keyword matching directly into the Qdrant query (e.g., with `should` filters and boosts) or implementing a more sophisticated re-ranking algorithm. | `src/main.py` (`search_project_endpoint`) | **Medium** |
| **2.3. Simplified Python Import Resolver in `graph_builder`** | The `_resolve_import_path` function in `src/graph_builder.py` is simplified and may not correctly handle complex Python import scenarios, such as: - Dynamic imports (e.g., `importlib`). - `sys.path` modifications during runtime. - Imports from namespace packages or installed packages not part of the `project_root`. This could lead to incomplete or incorrect dependency graph connections for complex Python projects. | `src/graph_builder.py` (`_resolve_import_path`, `parse_python_file`) | **Medium** |
| **2.4. Incomplete File Type Definition in `graph_builder` (Code Mention Regex)** | The `CODE_MENTION_RE` regular expression in `src/graph_builder.py` for detecting code file mentions in markdown limits file types to `py|js|ts|sh|yml|yaml`. This means that mentions of other file types that the system can index (e.g., `Dockerfile`, `.toml`, `.json`, `.css`, `.ini` from `IndexingService.allowed_extensions`) will not be considered when building the dependency graph. This leads to an incomplete graph. | `src/graph_builder.py` (`CODE_MENTION_RE`, `parse_markdown_file`) | **Low** |
| **2.5. Overly Broad Proxy Disabling in `Makefile`** | In the `Makefile`, empty proxy environment variables (`http_proxy="" ...`) are set for all `make` commands. While this prevents Qdrant from being accessed via a proxy, it also means that if any part of the application (e.g., `SentenceTransformer` during lazy model loading or caching) attempts to make an external request that requires a proxy, it might fail. `preload_model.py` is intended for upfront loading, but if the model wasn't preloaded or the cache was cleared, this could lead to issues during runtime. | `Makefile` | **Medium** |

#### 3. Infrastructure Vulnerabilities

| Problem Name | Description | Location | Criticality |
|---|---|---|---|
| **3.1. Dependency on `uv` Without Explicit Installation Check** | The `Makefile` uses `uv run python manage.py` for all commands. This assumes that `uv` (or `uv.venv` if it's not installed) is available and correctly configured. If `uv` is not installed on the user's system, the `Makefile` will produce a "command not found" error without providing clear instructions for its installation. | `Makefile` | **Low** |
| **3.2. Fragile `sys.path` Management in `preload_model.py`** | The use of `sys.path.append(os.getcwd())` in `preload_model.py` to ensure `src.config` import is fragile. If the script is run from a directory other than the project root, `os.getcwd()` will return an incorrect path, leading to an `ImportError`. A more robust approach would be to use `sys.path.append(str(Path(__file__).parent.parent))` to explicitly add the `src` path to `sys.path`. | `preload_model.py` | **Low** |
| **3.3. Qdrant Local Data Naming Inconsistency in `debug_qdrant.py`** | In `debug_qdrant.py`, the Qdrant client is initialized with `path="./test_qdrant"`, but in the filesystem, `qdrant_local_data` and `qdrant_storage` folders appear to be used for local Qdrant storage. This inconsistency can cause confusion during debugging and might incorrectly report the status of the local database. This is not a vulnerability, but rather a clarity issue. | `debug_qdrant.py`, `.qdrant_local_data`, `qdrant_storage` | **Low** |

#### 4. Data Processing Vulnerabilities

| Problem Name | Description | Location | Criticality |
|---|---|---|---|
| **4.1. Potentially Inefficient File Discovery for Indexing** | In `src/index.py` (which, as noted, is a standalone script but demonstrates core logic), `all_paths = list(root_path.rglob('*'))` first collects ALL paths in the project and then filters them by `.gitignore` and extensions. For very large projects, this can be memory and time-inefficient, as a large list of paths is created, many of which will be filtered out. A more optimal approach, like the one used in `IndexingService._scan_local_files`, where `os.walk` modifies `dirnames` in-place, avoids traversing ignored directories altogether. | `src/index.py` (`load_documents`) | **Medium** |
| **4.2. Basic Chunking Strategy** | The chunking strategy in `src/index.py` (`content.split('\n\n')`) and in `src/services.py` (`chunk_size_lines = 15, chunk_overlap_lines = 2`) is quite basic. For better search quality, especially for code, more advanced chunking methods could be beneficial, such as: - Semantic chunking (based on code structure: functions, classes, comments). - Paragraph-based splitting for documentation. - Automatic adaptation of chunk size. The current approach might break logical blocks of code or text, reducing the relevance of embeddings. | `src/index.py` (`load_documents`), `src/services.py` (`_process_files_in_batches`) | **Low** |

#### 5. Edge Cases / Robustness

| Problem Name | Description | Location | Criticality |
|---|---|---|---|
| **5.1. Missing `project_name` Validation in API Endpoints** | Most API endpoints, such as `index`, `search`, `graph`, `orphans`, accept `project_name` as a string parameter. Although it's used to construct a path (`projects_base_dir / project_name`), the implicit validation relies on the file system (checking `is_dir()`). However, if `project_name` contains special characters that are valid in a URL but invalid or have special meaning in file/directory names on the OS, this could lead to errors. While `Path.resolve()` mitigates some risks, explicit character restrictions for `project_name` via a Pydantic model or input sanitization would be safer and more robust. | `src/main.py` (all endpoints accepting `project_name`) | **Low** |
| **5.2. Potential `API_PORT` Inconsistency** | The `API_PORT` variable is read from `os.getenv("API_PORT", "8765")` in `manage.py`. If the API is started via `manage.py service dev` or `manage.py service up`, this port is used. However, if `uvicorn` or `FastAPI` are started manually (not via `manage.py`), and the `API_PORT` environment variable is not set or set differently, `manage.py` will attempt to interact with the wrong port, leading to connection errors. This is primarily an operational/documentation issue. | `manage.py` | **Low** |

---

### Summary and Recommendations

The `isearch` project demonstrates a well-designed structure and the use of modern technologies for semantic search. However, the audit revealed several critical and high-priority vulnerabilities that could significantly impact the system's stability, data integrity, and reliability.

**Key Recommendations (for immediate implementation):**

1.  **Fix Non-deterministic Qdrant Point IDs (GT-3):** Replace `abs(hash(content))` with a deterministic algorithm, such as a SHA256 hash of the chunk's string content, converted to a `UUID` or a string that Qdrant can use as a point ID. This is critical for preventing data duplication and ensuring correct incremental indexing.
2.  **Address Task Status Race Conditions and Loss (GT-4):**
    *   For `TASK_STATUS`, consider a persistent store (e.g., Redis, a small SQLite database, or even a file on disk) instead of an in-memory dictionary.
    *   Implement an explicit locking mechanism (e.g., using `asyncio.Lock` or a distributed mutex if scaling to multiple API instances is planned) to prevent simultaneous indexing of the same project.
3.  **Implement Destructive Operation Notifications:** Add clear warnings or require user confirmation before performing destructive actions, such as the complete recreation of a Qdrant collection due to a model dimension change.
4.  **Improve Large Project Handling in Clustering:** In the `/projects/{project_name}/clusters` endpoint, implement proper pagination (using `next_page_offset` in a `while True` loop) for Qdrant `scroll` to ensure all vectors are processed regardless of project size.
5.  **Re-evaluate Keyword Boosting Strategy:** To improve search quality, consider integrating keyword boosting directly into Qdrant queries (if the Qdrant API allows for it) or implementing a more advanced re-ranking algorithm that applies to all relevant hits, not just the `top_hit` in each group.

Implementing these recommendations will significantly enhance the reliability, scalability, and user experience of the `isearch` project.
```## Отчёт об Аудите Кодовой Базы Проекта `isearch`

**Дата аудита:** 2024-07-28
**Инженер-аудитор:** Senior Software/System Engineer
**Проект:** `isearch` (поисковая система)

### Введение

Проект `isearch` представляет собой систему для семантического поиска и анализа графов кода, построенную на FastAPI, Sentence Transformers и Qdrant. В ходе аудита были рассмотрены архитектурные решения, логика работы с данными, контракты API, взаимодействие с векторной базой данных и обработка пограничных случаев. Целью аудита является выявление потенциальных уязвимостей и областей для улучшения.

---

### Структурированный Отчёт о Дефектах

#### 1. Архитектурные Уязвимости

| Название Проблемы | Описание | Место | Критичность |
|---|---|---|---|
| **1.1. Недетерминированные Point ID в Qdrant (GT-3)** | Использование `abs(hash(content))` для генерации Point ID в Qdrant является критической уязвимостью. Функция `hash()` в Python не гарантирует стабильность и может возвращать разные значения для одного и того же строкового содержимого при разных запусках, на разных машинах или с разными версиями Python (без фиксации `PYTHONHASHSEED`). Это приводит к: 1) **Дублированию данных**: При инкрементальном индексировании те же чанки могут быть вставлены как новые точки, а не обновлены. 2) **Потере обновлений**: Старые точки остаются, новые создаются, что искажает состояние индекса. 3) **Удвоение коллизий**: `abs()` дополнительно уменьшает пространство хэшей, увеличивая вероятность коллизий. | `src/vector_store.py` (`upsert`), `src/services.py` | **Критическая** |
| **1.2. Гонка Условий при Обновлении Состояния Задач (GT-4)** | Состояние асинхронных задач (`TASK_STATUS`) хранится в глобальной in-memory переменной (`Dict[str, Dict[str, Any]]`) в `src/main.py`. При перезапуске приложения (например, при обновлении, сбое или завершении `uvicorn` в dev-режиме) вся информация о текущих задачах индексирования теряется. Это приводит к потере отслеживания прогресса для пользователя. Более того, при использовании нескольких `uvicorn` воркеров (или при потенциальной конкурентной записи из разных async-задач, хотя в `uvicorn --workers 1` это менее вероятно, но не исключено для сложных async-потоков), могут возникнуть гонки условий при обновлении `TASK_STATUS`. | `src/main.py` (`TASK_STATUS`, `update_task_status`), `static/app.js` (клиентская часть, полагающаяся на `TASK_STATUS`) | **Высокая** |
| **1.3. Скрытая Деструктивная Операция Reindex (Model Dimension Change)** | Логика инкрементального индексирования в `IndexingService.run_indexing` предусматривает пересоздание коллекции Qdrant (`self.vector_store.recreate_collection`) в случае, если текущая размерность векторов в коллекции (`collection_info.vectors_config.params.size`) не соответствует размерности текущей модели (`self.embedder.get_embedding_dim()`). Хотя это необходимо для корректности, такое поведение является деструктивным (полное удаление индекса проекта) и происходит без явного предупреждения или подтверждения пользователя, что может привести к неожиданной потере данных. | `src/services.py` (`IndexingService.run_indexing`) | **Высокая** |
| **1.4. Жесткое Кодирование Пути к Проекту в Скрипте `index.py`** | Скрипт `src/index.py` использует жестко закодированный путь `PROJECT_ROOT_PATH = Path(__file__).parent.parent.parent / 'autowarp'`. Этот скрипт, по-видимому, является автономной утилитой для индексирования конкретного проекта, а не частью основного API, который использует `IndexingService` с динамическим `projects_base_dir`. Это создает путаницу и является dead/misleading кодом, так как не отражает реальный механизм индексации, используемый FastAPI. | `src/index.py` | **Низкая** |
| **1.5. Отсутствие Блокировок на Уровне Проекта для Индексирования** | В текущей архитектуре отсутствует механизм предотвращения одновременного запуска нескольких задач индексирования для одного и того же проекта. Если пользователь запускает `index` для проекта `X` несколько раз подряд, это может привести к конкурентным операциям upsert и delete в Qdrant для одной коллекции, что потенциально может вызвать ошибки, дублирование данных или неконсистентное состояние. | `src/main.py` (`index_project_endpoint`), `src/services.py` (`IndexingService`) | **Средняя** |

#### 2. Логические Уязвимости

| Название Проблемы | Описание | Место | Критичность |
|---|---|---|---|
| **2.1. Неполный Скроллинг в Endpoint Кластеризации** | В эндпоинте `/projects/{project_name}/clusters` используется `vector_store.client.scroll(..., limit=10000)` для получения всех точек. Параметр `limit=10000` фиксирован, что означает, что для проектов с более чем 10 000 чанками будет получена лишь часть данных, что приведет к неполным и некорректным результатам кластеризации. Механизм пагинации с `offset` не используется для получения всех записей. | `src/main.py` (`perform_clustering`) | **Высокая** |
| **2.2. Неоптимальная Логика Keyword Boosting в Поиске** | Эвристика keyword boosting в `search_project_endpoint` (увеличение `score` на `0.1` для `top_hit` в группе) имеет несколько недостатков: 1) **Применяется только к первому хиту**: Только самый релевантный хит в каждой группе файлов получает буст, игнорируя другие потенциально релевантные хиты в том же файле. 2) **Пост-обработка**: Буст применяется после основного семантического поиска и группировки, что может не приводить к оптимальному переранжированию всех результатов. 3) **Наивные ключевые слова**: Список ключевых слов может быть неполным или чрезмерно общим, что может приводить к нежелательным бустам. Более надежным подходом было бы интегрировать ключевые слова непосредственно в запрос Qdrant (например, через `should` фильтры с `boost`) или реализовать более сложный алгоритм реранжирования. | `src/main.py` (`search_project_endpoint`) | **Средняя** |
| **2.3. Упрощенный Разрешитель Python Импортов в `graph_builder`** | Функция `_resolve_import_path` в `src/graph_builder.py` является упрощенной и может некорректно обрабатывать сложные сценарии импорта Python, такие как: - Динамические импорты (например, `importlib`). - Изменения `sys.path` во время выполнения. - Импорты из namespace-пакетов или установленных пакетов, не являющихся частью `project_root`. Это может привести к неполным или неверным связям в графе зависимостей для сложных Python-проектов. | `src/graph_builder.py` (`_resolve_import_path`, `parse_python_file`) | **Средняя** |
| **2.4. Неполное Определение Типов Файлов в `graph_builder` (Code Mention Regex)** | Регулярное выражение `CODE_MENTION_RE` в `src/graph_builder.py` для обнаружения упоминаний файлов кода в markdown ограничивает типы файлов до `py|js|ts|sh|yml|yaml`. Это означает, что упоминания других типов файлов, которые система может индексировать (например, `Dockerfile`, `.toml`, `.json`, `.css`, `.ini` из `IndexingService.allowed_extensions`), не будут учтены при построении графа зависимостей. Это приводит к неполному графу. | `src/graph_builder.py` (`CODE_MENTION_RE`, `parse_markdown_file`) | **Низкая** |
| **2.5. Слишком широкое исключение файлов в `Makefile`** | В `Makefile` для всех команд `make` устанавливаются пустые переменные окружения для прокси (`http_proxy="" ...`). Хотя это предотвращает попытки подключения к Qdrant через прокси, это также означает, что если любая часть приложения (например, `SentenceTransformer` при ленивой загрузке модели или её кешировании) попытается сделать внешний запрос, требующий прокси, она может потерпеть неудачу. `preload_model.py` предназначен для предварительной загрузки, но если модель не была предварительно загружена или кеш был очищен, это может привести к проблемам во время выполнения. | `Makefile` | **Средняя** |

#### 3. Инфраструктурные Уязвимости

| Название Проблемы | Описание | Место | Критичность |
|---|---|---|---|
| **3.1. Зависимость от `uv` без Явной Проверки Установки** | `Makefile` использует `uv run python manage.py` для всех команд. Это предполагает, что `uv` (или `uv.venv` если он не установлен) доступен и корректно настроен. Если `uv` не установлен в системе пользователя, `Makefile` будет выдавать ошибку "command not found" без предоставления четких инструкций по его установке. | `Makefile` | **Низкая** |
| **3.2. Хрупкое Управление `sys.path` в `preload_model.py`** | Использование `sys.path.append(os.getcwd())` в `preload_model.py` для обеспечения импорта из `src.config` является хрупким. Если скрипт запускается из директории, отличной от корня проекта, `os.getcwd()` вернет неверный путь, что приведет к `ImportError`. Более надежным подходом было бы использовать `sys.path.append(str(Path(__file__).parent.parent))` для явного добавления пути `src` в `sys.path`. | `preload_model.py` | **Низкая** |
| **3.3. Несоответствие Названия Qdrant Local Data в `debug_qdrant.py`** | В `debug_qdrant.py` клиент Qdrant инициализируется с `path="./test_qdrant"`, но в файловой системе существуют папки `qdrant_local_data` и `qdrant_storage`, которые, судя по всему, используются для локального хранения Qdrant. Это несоответствие может вызвать путаницу при отладке и некорректно показывать статус локальной базы данных. Это не уязвимость, а скорее проблема ясности. | `debug_qdrant.py`, `.qdrant_local_data`, `qdrant_storage` | **Низкая** |

#### 4. Уязвимости Обработки Данных

| Название Проблемы | Описание | Место | Критичность |
|---|---|---|---|
| **4.1. Потенциально Неэффективное Получение Файлов для Индексации** | В `src/index.py` (который, как было отмечено, является standalone скриптом, но демонстрирует базовую логику) `all_paths = list(root_path.rglob('*'))` сначала собирает ВСЕ пути в проекте, а затем фильтрует их по `.gitignore` и расширениям. Для очень больших проектов это может быть неэффективным по памяти и времени, так как создается большой список путей, многие из которых будут отфильтрованы. Более оптимальным является подход, используемый в `IndexingService._scan_local_files`, где `os.walk` модифицирует `dirnames` in-place, избегая обхода игнорируемых директорий. | `src/index.py` (`load_documents`) | **Средняя** |
| **4.2. Базовая Стратегия Чанкинга** | Стратегия чанкинга в `src/index.py` (`content.split('\n\n')`) и в `src/services.py` (`chunk_size_lines = 15, chunk_overlap_lines = 2`) является достаточно базовой. Для лучшего качества поиска, особенно для кода, более продвинутые методы чанкинга могут быть полезны, например: - Семантический чанкинг (основанный на структуре кода: функции, классы, комментарии). - Разделение по абзацам для документации. - Автоматическая адаптация размера чанка. Текущий подход может разрывать логические блоки кода или текста, что снижает релевантность эмбеддингов. | `src/index.py` (`load_documents`), `src/services.py` (`_process_files_in_batches`) | **Низкая** |

#### 5. Пограничные Случаи / Надёжность

| Название Проблемы | Описание | Место | Критичность |
|---|---|---|---|
| **5.1. Отсутствие Валидации `project_name` в API Endpoints** | Большинство API-эндпоинтов, таких как `index`, `search`, `graph`, `orphans`, принимают `project_name` как строковый параметр. Хотя он используется для создания пути (`projects_base_dir / project_name`), неявная валидация полагается на файловую систему (проверка `is_dir()`). Однако, если `project_name` содержит специальные символы, которые допустимы в URL, но недопустимы или имеют особое значение в именах файлов/директорий в ОС, это может привести к ошибкам. Хотя `Path.resolve()` снижает риски Path Traversal, явное ограничение символов для `project_name` через Pydantic-модель или регуляцию символов было бы безопаснее и надежнее. | `src/main.py` (все эндпоинты, принимающие `project_name`) | **Низкая** |
| **5.2. Потенциальная Несогласованность `API_PORT`** | Переменная `API_PORT` читается из `os.getenv("API_PORT", "8765")` в `manage.py`. Если API запускается через `manage.py service dev` или `manage.py service up`, этот порт используется. Однако, если `uvicorn` или `FastAPI` запущены вручную (не через `manage.py`), и переменная окружения `API_PORT` не установлена или установлена по-другому, `manage.py` будет пытаться взаимодействовать с неправильным портом, что приведет к ошибкам подключения. Это, скорее, вопрос эксплуатации и документирования. | `manage.py` | **Низкая** |

---

### Резюме и Рекомендации

Проект `isearch` демонстрирует хорошо продуманную структуру и использование современных технологий для семантического поиска. Однако, в ходе аудита были выявлены несколько критических и высокоприоритетных уязвимостей, которые могут серьезно повлиять на стабильность, целостность данных и надежность системы.

**Ключевые Рекомендации (для немедленного внедрения):**

1.  **Исправить Недетерминированные Point ID в Qdrant (GT-3):** Заменить `abs(hash(content))` на детерминированный алгоритм, например, SHA256 хэш строкового представления содержимого чанка, преобразованный в `UUID` или строку, которую Qdrant может использовать в качестве ID точки. Это критически важно для предотвращения дублирования данных и обеспечения корректного инкрементального индексирования.
2.  **Решить Проблему Гонки Условий и Потери Состояния Задач (GT-4):**
    *   Для `TASK_STATUS` следует рассмотреть персистентное хранилище (например, Redis, небольшая SQLite база или даже файл на диске) вместо in-memory словаря.
    *   Реализовать явный механизм блокировки (например, с использованием `asyncio.Lock` или распределенного мьютекса, если планируется масштабирование до нескольких инстансов API) для предотвращения одновременного индексирования одного и того же проекта.
3.  **Внедрить Уведомления о Деструктивных Операциях:** Добавить явные предупреждения или требования подтверждения для пользователя перед выполнением деструктивных действий, таких как полное пересоздание коллекции Qdrant из-за изменения размерности модели.
4.  **Улучшить Обработку Больших Проектов в Кластеризации:** В эндпоинте `/projects/{project_name}/clusters` реализовать корректную пагинацию (используя `next_page_offset` в цикле `while True`) для Qdrant `scroll`, чтобы гарантировать обработку всех векторов независимо от размера проекта.
5.  **Пересмотреть Стратегию Keyword Boosting:** Для улучшения качества поиска рассмотреть возможность интеграции keyword boosting непосредственно в запросы Qdrant (если это позволяет API Qdrant) или реализовать более продвинутый алгоритм реранжирования, который применяется ко всем релевантным хитам, а не только к `top_hit` в каждой группе.

Внедрение этих рекомендаций значительно повысит надежность, масштабируемость и пользовательский опыт проекта `isearch`.

---
```python
# baseline.md
# iSearch Project Codebase Audit Report

## Date of Audit: 2024-07-28
## Auditor: Senior Software/System Engineer
## Project: `isearch` (Search Engine)

### Introduction

The `isearch` project is a system for semantic search and code graph analysis, built on FastAPI, Sentence Transformers, and Qdrant. This audit reviewed architectural decisions, data handling logic, API contracts, vector database interaction, and edge case processing. The goal of the audit is to identify potential vulnerabilities and areas for improvement.

---

### Structured Defect Report

#### 1. Architectural Vulnerabilities

| Problem Name | Description | Location | Criticality |
|---|---|---|---|
| **1.1. Non-deterministic Qdrant Point IDs (GT-3)** | Using `abs(hash(content))` to generate Point IDs in Qdrant is a critical vulnerability. Python's `hash()` function does not guarantee stability and can return different values for the same string content across different runs, on different machines, or with different Python versions (without fixing `PYTHONHASHSEED`). This leads to: 1) **Data Duplication**: During incremental indexing, the same chunks can be inserted as new points rather than updated. 2) **Lost Updates**: Old points remain while new ones are created, distorting the index state. 3) **Increased Collisions**: `abs()` further reduces the hash space, increasing collision probability. | `src/vector_store.py` (`upsert`), `src/services.py` | **Critical** |
| **1.2. Race Condition on Task Status Updates (GT-4)** | The state of asynchronous tasks (`TASK_STATUS`) is stored in a global in-memory variable (`Dict[str, Dict[str, Any]]`) in `src/main.py`. If the FastAPI application restarts (e.g., due to code changes in dev mode, deployment, crash, or `uvicorn` termination), all task status information is lost. This results in users losing track of their indexing progress. Furthermore, when using multiple `uvicorn` workers (or in the event of potential concurrent writes from different async tasks, though less likely with `--workers 1`, it's not impossible for complex async flows), race conditions can occur during `TASK_STATUS` updates. | `src/main.py` (`TASK_STATUS`, `update_task_status`), `static/app.js` (client-side relying on `TASK_STATUS`) | **High** |
| **1.3. Hidden Destructive Reindex Operation (Model Dimension Change)** | The incremental indexing logic in `IndexingService.run_indexing` involves recreating the Qdrant collection (`self.vector_store.recreate_collection`) if the current vector dimension in the collection (`collection_info.vectors_config.params.size`) does not match the dimension of the current model (`self.embedder.get_embedding_dim()`). While necessary for correctness, this behavior is destructive (a complete deletion of the project's index) and occurs without explicit user warning or confirmation, which can lead to unexpected data loss. | `src/services.py` (`IndexingService.run_indexing`) | **High** |
| **1.4. Hardcoded Project Path in `index.py` Script** | The `src/index.py` script uses a hardcoded path `PROJECT_ROOT_PATH = Path(__file__).parent.parent.parent / 'autowarp'`. This script appears to be a standalone indexing utility for a specific project, rather than part of the main API, which uses `IndexingService` with a dynamic `projects_base_dir`. This creates confusion and is essentially dead/misleading code, as it doesn't reflect the actual indexing mechanism used by FastAPI. | `src/index.py` | **Low** |
| **1.5. Lack of Per-Project Indexing Locks** | The current architecture lacks a mechanism to prevent multiple indexing tasks from running concurrently for the same project. If a user triggers `index` for project `X` multiple times in quick succession, it could lead to concurrent upsert and delete operations within Qdrant for the same collection, potentially causing errors, data duplication, or an inconsistent index state. | `src/main.py` (`index_project_endpoint`), `src/services.py` (`IndexingService`) | **Medium** |

#### 2. Logical Vulnerabilities

| Problem Name | Description | Location | Criticality |
|---|---|---|---|
| **2.1. Incomplete Scrolling in Clustering Endpoint** | The `/projects/{project_name}/clusters` endpoint uses `vector_store.client.scroll(..., limit=10000)` to retrieve points. The `limit=10000` parameter is fixed, meaning that for projects with more than 10,000 chunks, only a portion of the data will be retrieved, leading to incomplete and incorrect clustering results. Proper pagination using `offset` is not implemented to fetch all records. | `src/main.py` (`perform_clustering`) | **High** |
| **2.2. Suboptimal Keyword Boosting Logic in Search** | The keyword boosting heuristic in `search_project_endpoint` (increasing the `score` by `0.1` for the `top_hit` in a group) has several drawbacks: 1) **Only applies to the first hit**: Only the most relevant hit in each file group gets a boost, ignoring other potentially relevant hits within the same file. 2) **Post-processing**: The boost is applied after the primary semantic search and grouping, which may not lead to optimal re-ranking of all results. 3) **Naive Keywords**: The list of keywords can be incomplete or overly generic, potentially leading to unintended boosts. A more robust approach would involve integrating keyword matching directly into the Qdrant query (e.g., with `should` filters and boosts) or implementing a more sophisticated re-ranking algorithm. | `src/main.py` (`search_project_endpoint`) | **Medium** |
| **2.3. Simplified Python Import Resolver in `graph_builder`** | The `_resolve_import_path` function in `src/graph_builder.py` is simplified and may not correctly handle complex Python import scenarios, such as: - Dynamic imports (e.g., `importlib`). - `sys.path` modifications during runtime. - Imports from namespace packages or installed packages not part of the `project_root`. This could lead to incomplete or incorrect dependency graph connections for complex Python projects. | `src/graph_builder.py` (`_resolve_import_path`, `parse_python_file`) | **Medium** |
| **2.4. Incomplete File Type Definition in `graph_builder` (Code Mention Regex)** | The `CODE_MENTION_RE` regular expression in `src/graph_builder.py` for detecting code file mentions in markdown limits file types to `py|js|ts|sh|yml|yaml`. This means that mentions of other file types that the system can index (e.g., `Dockerfile`, `.toml`, `.json`, `.css`, `.ini` from `IndexingService.allowed_extensions`) will not be considered when building the dependency graph. This leads to an incomplete graph. | `src/graph_builder.py` (`CODE_MENTION_RE`, `parse_markdown_file`) | **Low** |
| **2.5. Overly Broad Proxy Disabling in `Makefile`** | In the `Makefile`, empty proxy environment variables (`http_proxy="" ...`) are set for all `make` commands. While this prevents Qdrant from being accessed via a proxy, it also means that if any part of the application (e.g., `SentenceTransformer` during lazy model loading or caching) attempts to make an external request that requires a proxy, it might fail. `preload_model.py` is intended for upfront loading, but if the model wasn't preloaded or the cache was cleared, this could lead to issues during runtime. | `Makefile` | **Medium** |

#### 3. Infrastructure Vulnerabilities

| Problem Name | Description | Location | Criticality |
|---|---|---|---|
| **3.1. Dependency on `uv` Without Explicit Installation Check** | The `Makefile` uses `uv run python manage.py` for all commands. This assumes that `uv` (or `uv.venv` if it's not installed) is available and correctly configured. If `uv` is not installed on the user's system, the `Makefile` will produce a "command not found" error without providing clear instructions for its installation. | `Makefile` | **Low** |
| **3.2. Fragile `sys.path` Management in `preload_model.py`** | The use of `sys.path.append(os.getcwd())` in `preload_model.py` to ensure `src.config` import is fragile. If the script is run from a directory other than the project root, `os.getcwd()` will return an incorrect path, leading to an `ImportError`. A more robust approach would be to use `sys.path.append(str(Path(__file__).parent.parent))` to explicitly add the `src` path to `sys.path`. | `preload_model.py` | **Low** |
| **3.3. Qdrant Local Data Naming Inconsistency in `debug_qdrant.py`** | In `debug_qdrant.py`, the Qdrant client is initialized with `path="./test_qdrant"`, but in the filesystem, `qdrant_local_data` and `qdrant_storage` folders appear to be used for local Qdrant storage. This inconsistency can cause confusion during debugging and might incorrectly report the status of the local database. This is not a vulnerability, but rather a clarity issue. | `debug_qdrant.py`, `.qdrant_local_data`, `qdrant_storage` | **Low** |

#### 4. Data Processing Vulnerabilities

| Problem Name | Description | Location | Criticality |
|---|---|---|---|
| **4.1. Potentially Inefficient File Discovery for Indexing** | In `src/index.py` (which, as noted, is a standalone script but demonstrates core logic), `all_paths = list(root_path.rglob('*'))` first collects ALL paths in the project and then filters them by `.gitignore` and extensions. For very large projects, this can be memory and time-inefficient, as a large list of paths is created, many of which will be filtered out. A more optimal approach, like the one used in `IndexingService._scan_local_files`, where `os.walk` modifies `dirnames` in-place, avoids traversing ignored directories altogether. | `src/index.py` (`load_documents`) | **Medium** |
| **4.2. Basic Chunking Strategy** | The chunking strategy in `src/index.py` (`content.split('\n\n')`) and in `src/services.py` (`chunk_size_lines = 15, chunk_overlap_lines = 2`) is quite basic. For better search quality, especially for code, more advanced chunking methods could be beneficial, such. as: - Semantic chunking (based on code structure: functions, classes, comments). - Paragraph-based splitting for documentation. - Automatic adaptation of chunk size. The current approach might break logical blocks of code or text, reducing the relevance of embeddings. | `src/index.py` (`load_documents`), `src/services.py` (`_process_files_in_batches`) | **Low** |

#### 5. Пограничные Случаи / Надёжность

| Название Проблемы | Описание | Место | Критичность |
|---|---|---|---|
| **5.1. Отсутствие Валидации `project_name` в API Endpoints** | Большинство API-эндпоинтов, таких как `index`, `search`, `graph`, `orphans`, принимают `project_name` как строковый параметр. Хотя он используется для создания пути (`projects_base_dir / project_name`), неявная валидация полагается на файловую систему (проверка `is_dir()`). Однако, если `project_name` содержит специальные символы, которые допустимы в URL, но недопустимы или имеют особое значение в именах файлов/директорий в ОС, это может привести к ошибкам. Хотя `Path.resolve()` снижает риски Path Traversal, явное ограничение символов для `project_name` через Pydantic-модель или регуляцию символов было бы безопаснее и надежнее. | `src/main.py` (все эндпоинты, принимающие `project_name`) | **Низкая** |
| **5.2. Потенциальная Несогласованность `API_PORT`** | Переменная `API_PORT` читается из `os.getenv("API_PORT", "8765")` в `manage.py`. Если API запускается через `manage.py service dev` или `manage.py service up`, этот порт используется. Однако, если `uvicorn` или `FastAPI` запущены вручную (не через `manage.py`), и переменная окружения `API_PORT` не установлена или установлена по-другому, `manage.py` будет пытаться взаимодействовать с неправильным портом, что приведет к ошибкам подключения. Это, скорее, вопрос эксплуатации и документирования. | `manage.py` | **Низкая** |

---

### Резюме и Рекомендации

Проект `isearch` демонстрирует хорошо продуманную структуру и использование современных технологий для семантического поиска. Однако, в ходе аудита были выявлены несколько критических и высокоприоритетных уязвимостей, которые могут серьезно повлиять на стабильность, целостность данных и надежность системы.

**Ключевые Рекомендации (для немедленного внедрения):**

1.  **Исправить Недетерминированные Point ID в Qdrant (GT-3):** Заменить `abs(hash(content))` на детерминированный алгоритм, например, SHA256 хэш строкового представления содержимого чанка, преобразованный в `UUID` или строку, которую Qdrant может использовать в качестве ID точки. Это критически важно для предотвращения дублирования данных и обеспечения корректного инкрементального индексирования.
2.  **Решить Проблему Гонки Условий и Потери Состояния Задач (GT-4):**
    *   Для `TASK_STATUS` следует рассмотреть персистентное хранилище (например, Redis, небольшая SQLite база или даже файл на диске) вместо in-memory словаря.
    *   Реализовать явный механизм блокировки (например, с использованием `asyncio.Lock` или распределенного мьютекса, если планируется масштабирование до нескольких инстансов API) для предотвращения одновременного индексирования одного и того же проекта.
3.  **Внедрить Уведомления о Деструктивных Операциях:** Добавить явные предупреждения или требования подтверждения для пользователя перед выполнением деструктивных действий, таких как полное пересоздание коллекции Qdrant из-за изменения размерности модели.
4.  **Улучшить Обработку Больших Проектов в Кластеризации:** В эндпоинте `/projects/{project_name}/clusters` реализовать корректную пагинацию (используя `next_page_offset` в цикле `while True`) для Qdrant `scroll`, чтобы гарантировать обработку всех векторов независимо от размера проекта.
5.  **Пересмотреть Стратегию Keyword Boosting:** Для улучшения качества поиска рассмотреть возможность интеграции keyword boosting непосредственно в запросы Qdrant (если это позволяет API Qdrant) или реализовать более продвинутый алгоритм реранжирования, который применяется ко всем релевантным хитам, а не только к `top_hit` в каждой группе.

Внедрение этих рекомендаций значительно повысит надежность, масштабируемость и пользовательский опыт проекта `isearch`.

---
```