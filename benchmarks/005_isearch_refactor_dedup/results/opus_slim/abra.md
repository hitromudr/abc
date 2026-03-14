Задача Clear-домен. Конвейер не нужен — прямое решение.

```diff
--- /dev/null
+++ b/src/file_utils.py
@@ -0,0 +1,72 @@
+"""
+Consolidated file utilities for gitignore loading, file type classification,
+and directory scanning. Single source of truth — replaces duplicated logic
+in services.py, graph_builder.py, and index.py.
+"""
+
+import logging
+from pathlib import Path
+from typing import Literal
+
+import pathspec
+
+log = logging.getLogger(__name__)
+
+# ==============================================================================
+# File Type Classification
+# ==============================================================================
+
+CODE_EXTENSIONS = {
+    ".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".sh", "dockerfile",
+}
+
+DOCS_EXTENSIONS = {
+    ".md", ".toml", ".txt", ".yml", ".yaml", ".json", ".html", ".css", ".ini",
+}
+
+ALLOWED_EXTENSIONS = CODE_EXTENSIONS | DOCS_EXTENSIONS
+
+
+def get_file_type(path: Path) -> Literal["code", "docs", "other"]:
+    """Classify a file as code, docs, or other based on its extension/name."""
+    suffix = path.suffix
+    name = path.name
+    if suffix in CODE_EXTENSIONS or name in CODE_EXTENSIONS:
+        return "code"
+    if suffix in DOCS_EXTENSIONS or name in DOCS_EXTENSIONS:
+        return "docs"
+    return "other"
+
+
+# ==============================================================================
+# Gitignore Loading
+# ==============================================================================
+
+DEFAULT_IGNORE_PATTERNS = [
+    ".git/",
+    ".idea/",
+    ".vscode/",
+    "__pycache__/",
+    ".venv/",
+    "*.pyc",
+    "*.egg-info/",
+    "node_modules/",
+    "dist/",
+    "build/",
+    "*.log",
+    ".DS_Store",
+]
+
+
+def load_gitignore_spec(root_path: Path) -> pathspec.PathSpec:
+    """
+    Loads .gitignore patterns from the project root, combined with a robust
+    set of default patterns. Returns a PathSpec for matching.
+    """
+    all_patterns = list(DEFAULT_IGNORE_PATTERNS)
+
+    gitignore_path = root_path / ".gitignore"
+    if gitignore_path.is_file():
+        try:
+            with open(gitignore_path, "r", encoding="utf-8") as f:
+                all_patterns.extend(f.read().splitlines())
+        except (IOError, OSError) as e:
+            log.warning(f"Could not read .gitignore at {gitignore_path}: {e}")
+
+    return pathspec.PathSpec.from_lines("gitwildmatch", all_patterns)
--- a/src/services.py
+++ b/src/services.py
@@ -5,6 +5,7 @@
 from typing import List, Dict, Any, Set, Callable
 import logging
 import numpy as np
+from src.file_utils import load_gitignore_spec, get_file_type, ALLOWED_EXTENSIONS, CODE_EXTENSIONS, DOCS_EXTENSIONS
 
 from src.embedder import EmbeddingModel
 from src.vector_store import VectorStore
@@ -56,12 +57,9 @@
     def __init__(self, embedder: EmbeddingModel, vector_store: VectorStore, projects_base_dir: Path):
         self.embedder = embedder
         self.vector_store = vector_store
         self.projects_base_dir = projects_base_dir
-        # Define extensions for code and docs to determine file_type
-        self.code_extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".sh", "dockerfile"}
-        self.docs_extensions = {".md", ".toml", ".txt", ".yml", ".yaml", ".json", ".html", ".css", ".ini"}
-        self.allowed_extensions = self.code_extensions.union(self.docs_extensions)
+        self.allowed_extensions = ALLOWED_EXTENSIONS
 
     def _get_indexed_state(self, collection_name: str) -> Dict[str, str]:
         """
         Retrieves a map of {source_file: file_hash} for ALL documents in the
@@ -107,7 +105,7 @@
         local_state = {}
-        spec = self._load_gitignore_spec(project_path)
+        spec = load_gitignore_spec(project_path)
 
         for dirpath, dirnames, filenames in os.walk(project_path, topdown=True):
             current_path = Path(dirpath)
@@ -131,21 +129,6 @@
 
         return local_state
 
-    def _load_gitignore_spec(self, project_path: Path) -> pathspec.PathSpec:
-        """Loads gitignore patterns, including a set of default patterns."""
-        default_patterns = [
-            ".git/", ".idea/", ".vscode/", "__pycache__/", ".venv/",
-            "*.pyc", "*.egg-info/", "node_modules/", "dist/", "build/",
-            "*.log", ".DS_Store",
-        ]
-
-        gitignore_path = project_path / ".gitignore"
-        project_patterns = []
-        if gitignore_path.is_file():
-            try:
-                with open(gitignore_path, "r", encoding="utf-8") as f:
-                    project_patterns = f.read().splitlines()
-            except (IOError, OSError) as e:
-                log.warning(f"Could not read .gitignore file at {gitignore_path}: {e}")
-
-        return pathspec.PathSpec.from_lines("gitwildmatch", default_patterns + project_patterns)
-
     def _process_files_in_batches(
         self,
         project_path: Path,
@@ -181,12 +164,7 @@
                     continue
 
                 file_abs_path = project_path / file_rel_path
-                file_type = "other"
-                if file_abs_path.suffix in self.code_extensions or file_abs_path.name in self.code_extensions:
-                    file_type = "code"
-                elif file_abs_path.suffix in self.docs_extensions or file_abs_path.name in self.docs_extensions:
-                    file_type = "docs"
+                file_type = get_file_type(file_abs_path)
 
                 try:
                     with open(file_abs_path, "r", encoding="utf-8", errors="ignore") as f:
--- a/src/graph_builder.py
+++ b/src/graph_builder.py
@@ -9,7 +9,7 @@
 import re
 from pathlib import Path
 from typing import Dict, List, Set, Tuple
-import pathspec
+from src.file_utils import load_gitignore_spec
 
 # Pre-compiled regexes for different link types
 # Doc -> Doc: Looks for relative markdown links, ignoring http/https links.
@@ -156,15 +156,7 @@
     scan_dir = (project_root / start_path).resolve()
 
     # --- .gitignore parsing ---
-    spec = None
-    gitignore_path = project_root / ".gitignore"
-    if gitignore_path.exists():
-        with open(gitignore_path, "r", encoding="utf-8") as f:
-            # Add common ignore patterns; project's .gitignore can override these defaults.
-            base_patterns = ["*.pyc", "__pycache__/", ".git/", ".venv/"]
-            project_patterns = f.read().splitlines()
-            spec = pathspec.PathSpec.from_lines("gitwildmatch", base_patterns + project_patterns)
+    spec = load_gitignore_spec(project_root)
 
     # First pass: collect all valid nodes
     all_files = []
@@ -173,8 +165,7 @@
 
         # Filter directories in-place using pathspec to prevent traversal into ignored folders
-        if spec:
-            dirnames[:] = [
-                d for d in dirnames
-                if not spec.match_file(str((current_path / d).relative_to(project_root)))
-            ]
+        dirnames[:] = [
+            d for d in dirnames
+            if not spec.match_file(str((current_path / d).relative_to(project_root)))
+        ]
 
         if depth != -1:
@@ -185,8 +176,7 @@
         for filename in filenames:
             file_path = current_path / filename
             # Filter files using pathspec
-            if spec and spec.match_file(str(file_path.relative_to(project_root))):
+            if spec.match_file(str(file_path.relative_to(project_root))):
                 continue
 
             if filename.endswith((".py", ".md")):
--- a/src/index.py
+++ b/src/index.py
@@ -2,36 +2,13 @@
 import time
 from pathlib import Path
-import pathspec
 from embedder import EmbeddingModel
 from vector_store import VectorStore
+from file_utils import load_gitignore_spec, ALLOWED_EXTENSIONS
 
 # --- 1. Configuration for Indexing ---
 
 # The path to the project we want to index.
 # Assumes 'autowarp' is a sibling directory to 'isearch'.
 PROJECT_ROOT_PATH = Path(__file__).parent.parent.parent / 'autowarp'
 
-# A set of file extensions we are interested in. This acts as a primary filter.
-ALLOWED_EXTENSIONS = {
-    ".py", ".js", ".ts", ".jsx", ".tsx", ".md", ".toml", ".txt", ".rs", ".yml",
-    ".yaml", ".sh", ".json", ".html", ".css", "dockerfile", ".ini"
-}
-
-
-def load_gitignore_spec(root_path: Path) -> pathspec.PathSpec:
-    """
-    Loads patterns from all .gitignore files found in the project's root.
-    Includes a default set of common patterns to ignore as a fallback.
-    """
-    all_patterns = [
-        '.git/', '__pycache__/', 'node_modules/', '.venv/',
-        'dist/', 'build/', '*.pyc', '*.egg-info/', '*.log'
-    ]
-
-    gitignore_path = root_path / '.gitignore'
-    if gitignore_path.is_file():
-        print(f"Loading patterns from: {gitignore_path}")
-        with open(gitignore_path, 'r', encoding='utf-8') as f:
-            all_patterns.extend(f.read().splitlines())
-    else:
-        print("Warning: No .gitignore file found in the project root. Using default patterns.")
-
-    return pathspec.PathSpec.from_lines('gitwildmatch', all_patterns)
-
 
 def load_documents(root_path: Path) -> (list[str], list[dict]):
```

**Что сделано:**

| До | После |
|----|-------|
| 3 реализации `.gitignore` (services, graph_builder, index) | 1 в `file_utils.py`, импортируется тремя модулями |
| 2 набора расширений (services, index) | 1 в `file_utils.py` (`CODE_EXTENSIONS`, `DOCS_EXTENSIONS`, `ALLOWED_EXTENSIONS`) |
| Inline классификация `file_type` в services.py | `get_file_type(path)` в `file_utils.py` |

**Нюансы:**
- `graph_builder.py` раньше допускал `spec = None` (если нет `.gitignore`). Теперь `load_gitignore_spec` всегда возвращает PathSpec (как минимум с дефолтными паттернами) — это корректнее.
- `index.py` использует `from file_utils import ...` (без `src.`), т.к. он запускается как standalone скрипт с `sys.path` на `src/`.
- Публичные API (`IndexingService`, `build_graph`, `load_documents`) — сигнатуры не изменены.
- Дефолтные паттерны — супермножество из `services.py` (самый полный список). `.idea/`, `.vscode/`, `.DS_Store` добавлены и для `graph_builder` — это улучшение, а не регрессия.