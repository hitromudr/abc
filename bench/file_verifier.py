"""Верификация file:line ссылок в находках без модели-арбитра.

Ловит очевидные галлюцинации: файл не существует, строка вне диапазона,
указанная функция/класс не найдены в файле.
"""

import os
import re


def verify_finding_reference(finding: dict, project_path: str) -> str:
    """Проверяет ссылку на файл/строку в находке.

    Returns: 'valid' | 'file_not_found' | 'line_out_of_range' | 'no_reference'
    """
    title = finding.get("title", "")
    desc = finding.get("description", "")
    text = f"{title} {desc}"

    # Извлекаем file references: path/to/file.py:123 или path/to/file.py (line 123)
    file_refs = _extract_file_refs(text)
    if not file_refs:
        return "no_reference"

    for fpath, line_no in file_refs:
        full_path = os.path.join(project_path, fpath)

        if not os.path.isfile(full_path):
            # Попробуем найти с разными вариантами пути
            alt = _find_alternative(fpath, project_path)
            if alt:
                full_path = alt
            else:
                return "file_not_found"

        if line_no is not None:
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                if line_no > len(lines) or line_no < 1:
                    return "line_out_of_range"
            except OSError:
                return "file_not_found"

    return "valid"


def verify_all_findings(findings: list[dict], project_path: str) -> dict:
    """Верифицирует все находки. Возвращает сводку.

    Returns:
        {
            "total": int,
            "valid": int,
            "file_not_found": int,
            "line_out_of_range": int,
            "no_reference": int,
            "details": [{"finding_id": "A1", "status": "valid"}, ...],
        }
    """
    counts = {"valid": 0, "file_not_found": 0, "line_out_of_range": 0, "no_reference": 0}
    details = []

    for f in findings:
        status = verify_finding_reference(f, project_path)
        counts[status] += 1
        details.append({"finding_id": f.get("id", "?"), "status": status})

    return {
        "total": len(findings),
        **counts,
        "details": details,
    }


def _extract_file_refs(text: str) -> list[tuple[str, int | None]]:
    """Извлекает file:line ссылки из текста.

    Поддерживает форматы:
    - path/to/file.py:123
    - path/to/file.py (line 123)
    - `path/to/file.py`
    """
    refs = []
    # pattern: file.ext:line
    for m in re.finditer(r'[`"]?([a-zA-Z0-9_./\\-]+\.\w{1,4}):(\d+)', text):
        refs.append((m.group(1), int(m.group(2))))

    # pattern: file.ext (line N)
    for m in re.finditer(r'[`"]?([a-zA-Z0-9_./\\-]+\.\w{1,4})\s*\((?:line|строка)\s*(\d+)\)', text, re.IGNORECASE):
        refs.append((m.group(1), int(m.group(2))))

    # pattern: just file.ext (no line)
    if not refs:
        for m in re.finditer(r'[`"]?([a-zA-Z0-9_./\\-]+\.(?:py|js|ts|go|rs|yaml|yml|toml|json|md|sh))', text):
            refs.append((m.group(1), None))

    return refs


def _find_alternative(fpath: str, project_path: str) -> str | None:
    """Пытается найти файл с альтернативным путём (без ведущего src/ и т.п.)."""
    basename = os.path.basename(fpath)

    for root, _dirs, files in os.walk(project_path):
        if basename in files:
            return os.path.join(root, basename)
        # Ограничиваем глубину обхода
        depth = root.replace(project_path, "").count(os.sep)
        if depth > 4:
            _dirs.clear()

    return None
