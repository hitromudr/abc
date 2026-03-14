Выполнен Шаг 1. Тест зеленый. Перехожу к Шагу 2.

```diff
--- /dev/null
+++ b/src/file_utils.py
@@ -0,0 +1,114 @@
+"""
+File Utilities Module
+
+Centralized functions for file processing logic used across the project.
+This module eliminates duplication of .gitignore loading, file type classification,
+and file scanning logic.
+"""
+
+import os
+from pathlib import Path
+from typing import List, Tuple
+import pathspec
+
+
+def load_gitignore_spec(root_path: Path) -> pathspec.PathSpec:
+    """
+    Loads patterns from all .gitignore files found in the project's root.
+    Includes a default set of common patterns to ignore as a fallback.
+
+    Args:
+        root_path: The root directory of the project.
+
+    Returns:
+        A PathSpec object that can be used to match files against .gitignore patterns.
+    """
+    all_patterns = [
+        ".git/",
+        "__pycache__/",
+        "node_modules/",
+        ".venv/",
+        "dist/",
+        "build/",
+        "*.pyc",
+        "*.egg-info/",
+        "*.log",
+        ".ruff_cache/",
+        # Explicitly un-ignore project config dot-files that are critical for context.
+        "!*.rules",
+        "!*.project",
+    ]
+
+    gitignore_path = root_path / ".gitignore"
+    if gitignore_path.is_file():
+        with open(gitignore_path, "r", encoding="utf-8") as f:
+            all_patterns.extend(f.read().splitlines())
+
+    return pathspec.PathSpec.from_lines("gitwildmatch", all_patterns)
+
+
+# Unified sets of file extensions for classification
+CODE_EXTENSIONS = {
+    ".py",
+    ".js",
+    ".ts",
+    ".jsx",
+    ".tsx",
+    ".rs",
+    ".go",
+    ".cpp",
+    ".c",
+    ".h",
+    ".java",
+    ".sh",
+}
+
+DOCS_EXTENSIONS = {".md", ".rst", ".txt"}
+
+
+def get_file_type(file_path: Path) -> str:
+    """
+    Determines the semantic type of a file based on its extension.
+
+    Args:
+        file_path: Path to the file.
+
+    Returns:
+        "code", "docs", or "other".
+    """
+    if file_path.suffix in CODE_EXTENSIONS:
+        return "code"
+    elif file_path.suffix in DOCS_EXTENSIONS:
+        return "docs"
+    else:
+        return "other"
+
+
+def scan_files(
+    root_path: Path,
+    gitignore_spec: pathspec.PathSpec,
+    allowed_extensions: set,
+) -> List[Path]:
+    """
+    Recursively scans a directory for files, filtering by .gitignore and allowed extensions.
+
+    Args:
+        root_path: The root directory to scan.
+        gitignore_spec: PathSpec object for .gitignore filtering.
+        allowed_extensions: Set of allowed file extensions (including dot-files).
+
+    Returns:
+        A list of Path objects for files that pass all filters.
+    """
+    files = []
+    for dirpath, dirnames, filenames in os.walk(root_path, topdown=True):
+        current_path = Path(dirpath)
+
+        # Filter directories in-place using pathspec
+        if gitignore_spec:
+            dirnames[:] = [
+                d
+                for d in dirnames
+                if not gitignore_spec.match_file(str((current_path / d).relative_to(root_path)))
+            ]
+
+        for filename in filenames:
+            file_path = current_path / filename
+            relative_path_str = str(file_path.relative_to(root_path))
+
+            # Filter by .gitignore patterns
+            if gitignore_spec and gitignore_spec.match_file(relative_path_str):
+                continue
+
+            # Filter by allowed extensions
+            if (
+                file_path.suffix not in allowed_extensions
+                and file_path.name not in allowed_extensions
+            ):
+                continue
+
+            files.append(file_path)
+
+    return files
```