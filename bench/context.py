"""Сборка контекста проекта: рекурсивный обход файлов → один текстовый блок."""

import os

INCLUDE_EXT = {
    ".py", ".yml", ".yaml", ".toml", ".env", ".js", ".ts", ".html",
    ".css", ".json", ".cfg", ".ini", ".sh", ".bash",
}
INCLUDE_NAMES = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", "Makefile"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", ".egg-info"}

# Приоритет расширений: .py первыми, конфиги потом
EXT_PRIORITY = {".py": 0, ".toml": 1, ".yml": 1, ".yaml": 1, ".sh": 2, ".js": 3, ".ts": 3, ".html": 4, ".css": 5, ".json": 5}

WARN_LIMIT = 100_000
DEFAULT_MAX_CHARS = 0  # 0 = без лимита


def build_project_context(project_path: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Рекурсивно читает исходники проекта, возвращает конкатенацию с разделителями.

    Args:
        project_path: путь к корню проекта
        max_chars: максимум символов контента (0 = без лимита). При превышении
                   файлы с низким приоритетом отсекаются.
    """
    file_entries: list[tuple[int, str, str]] = []  # (priority, relpath, content)

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        dirs.sort()

        for fname in sorted(files):
            ext = os.path.splitext(fname)[1]
            if ext not in INCLUDE_EXT and fname not in INCLUDE_NAMES:
                continue

            fpath = os.path.join(root, fname)
            relpath = os.path.relpath(fpath, project_path)

            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except (OSError, PermissionError):
                continue

            priority = EXT_PRIORITY.get(ext, 10)
            file_entries.append((priority, relpath, content))

    # Сортируем по приоритету, потом по пути
    file_entries.sort(key=lambda e: (e[0], e[1]))

    parts: list[str] = []
    total_chars = 0
    skipped = 0

    for _prio, relpath, content in file_entries:
        if max_chars > 0 and total_chars + len(content) > max_chars and parts:
            skipped += 1
            continue
        parts.append(f"=== {relpath} ===\n{content}")
        total_chars += len(content)

    if skipped:
        print(f"[INFO] Контекст обрезан: {skipped} файлов пропущено (лимит {max_chars:,} символов)")

    if total_chars > WARN_LIMIT and max_chars == 0:
        print(f"[WARN] Контекст проекта: {total_chars:,} символов (>{WARN_LIMIT:,}). Используйте --max-context для ограничения.")

    return "\n\n".join(parts)
