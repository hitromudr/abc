

```diff
--- /dev/null
+++ b/src/file_utils.py
@@ -0,0 +1,69 @@
+"""
+Consolidated file utility module.
+
+Single source of truth for:
+- .gitignore loading
+- File type classification
+- File scanning with gitignore + extension filtering
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
+# File Type Classification — single definition
+# ==============================================================================
+
+CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".sh", "dockerfile"}
+DOCS_EXTENSIONS = {".md", ".toml", ".txt", ".yml", ".yaml", ".json", ".html", ".css", ".ini"}
+ALLOWED_EXTENSIONS = CODE_EXTENSIONS | DOCS_EXTENSIONS
+
+
+def get_file_type(path: Path) -> Literal["code", "docs", "other"]:
+    """Classifies a file path as 'code', 'docs', or 'other'."""
+    if path.suffix in CODE_EXTENSIONS or path.name in CODE_EXTENSIONS:
+        return "code"
+    if path.suffix in DOCS_EXTENSIONS or path.name in DOCS_EXTENSIONS:
+        return "docs"
+    return "other"
+
+
+# ==============================================================================
+# Gitignore Loading — single implementation
+# ==============================================================================
+
+DEFAULT_GITIGNORE_PATTERNS = [
+    ".git/", ".idea/", ".vscode/", "__pycache__/", ".venv/",
+    "*.pyc", "*.egg-info/", "node_modules/", "dist/", "build/",
+    "*.log", ".DS_Store",
+]
+
+
+def load_gitignore_spec(root_path: Path) -> pathspec.PathSpec:
+    """
+    Loads .gitignore patterns from the project root, merged with sensible defaults.
+
+    This is the single canonical implementation used by all modules.
+    """
+    all_patterns = list(DEFAULT_GITIGNORE_PATTERNS)
+
+    gitignore_path = root_path / ".gitignore"
+    if gitignore_path.is_file():
+        try:
+            with open(gitignore_path, "r", encoding="utf-8") as f:
+                all_patterns.extend(f.read().splitlines())
+        except (IOError, OSError) as e:
+            log.warning(f"Could not read .gitignore file at {gitignore_path}: {e}")
+
+    return pathspec.PathSpec.from_lines("gitwildmatch", all_patterns)
+
+
+def is_allowed_extension(path: Path) -> bool:
+    """Check if a file has an allowed extension."""
+    return path.suffix in ALLOWED_EXTENSIONS or path.name in ALLOWED_EXTENSIONS
--- a/src/services.py
+++ b/src/services.py
@@ -3,12 +3,13 @@
 from pathlib import Path
-import pathspec
 from typing import List, Dict, Any, Set, Callable
 import logging
 import numpy as np
 
 from src.embedder import EmbeddingModel
 from src.vector_store import VectorStore
+from src.file_utils import (
+    load_gitignore_spec, get_file_type, is_allowed_extension,
+    CODE_EXTENSIONS, DOCS_EXTENSIONS, ALLOWED_EXTENSIONS,
+)
 
 log = logging.getLogger(__name__)
 
@@ -55,9 +56,9 @@
         self.embedder = embedder
         self.vector_store = vector_store
         self.projects_base_dir = projects_base_dir
-        # Define extensions for code and docs to determine file_type
-        self.code_extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".sh", "dockerfile"}
-        self.docs_extensions = {".md", ".toml", ".txt", ".yml", ".yaml", ".json", ".html", ".css", ".ini"}
-        self.allowed_extensions = self.code_extensions.union(self.docs_extensions)
+        # Use consolidated definitions from file_utils
+        self.code_extensions = CODE_EXTENSIONS
+        self.docs_extensions = DOCS_EXTENSIONS
+        self.allowed_extensions = ALLOWED_EXTENSIONS
 
     def _get_indexed_state(self, collection_name: str) -> Dict[str, str]:
         """
@@ -99,7 +100,7 @@
         Scans all files in the project directory, respecting .gitignore, and
         returns a dictionary mapping relative file paths to their content hash.
         """
         local_state = {}
-        spec = self._load_gitignore_spec(project_path)
+        spec = load_gitignore_spec(project_path)
 
         for dirpath, dirnames, filenames in os.walk(project_path, topdown=True):
             current_path = Path(dirpath)
@@ -118,7 +119,7 @@
                 if spec.match_file(rel_path_str):
                     continue
 
-                if file_path.suffix not in self.allowed_extensions and file_path.name not in self.allowed_extensions:
+                if not is_allowed_extension(file_path):
                     continue
 
                 file_hash = _calculate_file_hash(file_path)
@@ -127,22 +128,6 @@
 
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
@@ -178,12 +163,7 @@
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
@@ -10,7 +10,8 @@
 import re
 from pathlib import Path
 from typing import Dict, List, Set, Tuple
-import pathspec
+
+from src.file_utils import load_gitignore_spec
 
 # Pre-compiled regexes for different link types
 # Doc -> Doc: Looks for relative markdown links, ignoring http/https links.
@@ -156,16 +157,7 @@
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
@@ -174,10 +166,9 @@
 
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
             relative_depth = len(current_path.relative_to(scan_dir).parts)
@@ -187,8 +178,7 @@
         for filename in filenames:
             file_path = current_path / filename
             # Filter files using pathspec
-            if spec and spec.match_file(str(file_path.relative_to(project_root))):
+            if spec.match_file(str(file_path.relative_to(project_root))):
                 continue
 
             if filename.endswith((".py", ".md")):
--- a/src/index.py
+++ b/src/index.py
@@ -1,8 +1,9 @@
 import os
 import time
 from pathlib import Path
-import pathspec
 from embedder import EmbeddingModel
 from vector_store import VectorStore
+from file_utils import load_gitignore_spec, ALLOWED_EXTENSIONS
 
 # --- 1. Configuration for Indexing ---
 
@@ -11,30 +12,6 @@
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
     """
```