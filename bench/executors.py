"""Песочница для выполнения кода модели: apply patch, run tests, check build."""

import os
import re
import shutil
import subprocess
import tempfile


class PatchResult:
    def __init__(self, success: bool, message: str = ""):
        self.success = success
        self.message = message


class TestResult:
    def __init__(self, passed: bool, total: int = 0, failed: int = 0,
                 output: str = "", return_code: int = 0):
        self.passed = passed
        self.total = total
        self.failed = failed
        self.output = output
        self.return_code = return_code


class ExecutionSandbox:
    """Изолированная среда для запуска кода модели.

    Копирует проект в tmpdir, применяет патч, запускает тесты.
    """

    def __init__(self, project_path: str):
        self.project_path = os.path.abspath(project_path)
        self.work_dir: str | None = None

    def __enter__(self):
        self.work_dir = tempfile.mkdtemp(prefix="bench_sandbox_")
        # Копируем проект (без .git для скорости)
        dest = os.path.join(self.work_dir, "project")
        shutil.copytree(
            self.project_path, dest,
            ignore=shutil.ignore_patterns('.git', '__pycache__', '.venv', 'node_modules'),
        )
        self.work_dir = dest
        return self

    def __exit__(self, *args):
        if self.work_dir and os.path.exists(os.path.dirname(self.work_dir)):
            shutil.rmtree(os.path.dirname(self.work_dir), ignore_errors=True)

    def apply_patch(self, model_output: str) -> PatchResult:
        """Извлекает и применяет патч из ответа модели.

        Поддерживает:
        1. Unified diff (```diff ... ```)
        2. Полные файлы (```python ... ``` с указанием имени файла)
        """
        # Стратегия 1: unified diff (```diff или любой code block с --- a/ +++ b/)
        diff_blocks = re.findall(r'```diff\s*\n(.*?)```', model_output, re.DOTALL)
        if not diff_blocks:
            # Fallback: ищем unified diff паттерн в любом code block
            all_blocks = re.findall(r'```\w*\s*\n(.*?)```', model_output, re.DOTALL)
            diff_blocks = [b for b in all_blocks if re.search(r'^---\s+a/', b, re.MULTILINE)]
        if diff_blocks:
            return self._apply_unified_diff("\n".join(diff_blocks))

        # Стратегия 2: именованные code blocks
        # Ищем паттерн: файл path/to/file.py:\n```python\ncontent\n```
        file_blocks = re.findall(
            r'(?:файл|file|path)?[:\s]*[`"]?([a-zA-Z0-9_./\\-]+\.\w{1,4})[`"]?\s*:?\s*\n```\w*\s*\n(.*?)```',
            model_output, re.DOTALL | re.IGNORECASE,
        )
        if file_blocks:
            return self._apply_file_blocks(file_blocks)

        return PatchResult(False, "Не удалось извлечь патч из ответа модели")

    def run_tests(self, test_cmd: str, timeout: int = 120) -> TestResult:
        """Запускает тесты в песочнице."""
        try:
            result = subprocess.run(
                test_cmd, shell=True, cwd=self.work_dir,
                capture_output=True, text=True, timeout=timeout,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            passed = result.returncode == 0
            total, failed = _parse_test_output(result.stdout + result.stderr)
            return TestResult(
                passed=passed, total=total, failed=failed,
                output=result.stdout + result.stderr,
                return_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return TestResult(passed=False, output=f"Таймаут {timeout}s", return_code=-1)
        except Exception as e:
            return TestResult(passed=False, output=str(e), return_code=-1)

    def check_build(self, build_cmd: str, timeout: int = 60) -> bool:
        """Проверяет компиляцию/lint."""
        try:
            result = subprocess.run(
                build_cmd, shell=True, cwd=self.work_dir,
                capture_output=True, text=True, timeout=timeout,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception):
            return False

    def diff_size(self) -> int:
        """Считает размер diff (строки changed) относительно оригинала."""
        try:
            result = subprocess.run(
                ["diff", "-r", "--brief", self.project_path, self.work_dir],
                capture_output=True, text=True, timeout=30,
            )
            # Подсчёт через git diff если есть git
            result2 = subprocess.run(
                f"diff -r -u {self.project_path} {self.work_dir} | grep -c '^[+-]' || true",
                shell=True, capture_output=True, text=True, timeout=30,
            )
            return int(result2.stdout.strip() or 0)
        except Exception:
            return -1

    def _apply_unified_diff(self, diff_text: str) -> PatchResult:
        """Применяет unified diff через patch.

        Пробует несколько стратегий: strict → fuzz → fuzzy line matching.
        Модели часто генерируют неточный контекст/номера строк в diff.
        Файлы восстанавливаются между попытками чтобы избежать partial apply.
        """
        # Сохраняем бэкап затронутых файлов
        affected = _extract_diff_files(diff_text)
        backups = {}
        for rel in affected:
            fp = os.path.join(self.work_dir, rel)
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    backups[fp] = f.read()

        def restore():
            for fp, content in backups.items():
                with open(fp, "wb") as f:
                    f.write(content)
            # Удалить .rej файлы
            for rel in affected:
                rej = os.path.join(self.work_dir, rel + ".rej")
                if os.path.exists(rej):
                    os.unlink(rej)

        strategies = [
            ["patch", "-p1", "--forward", "--batch"],
            ["patch", "-p1", "--forward", "--batch", "--fuzz=3"],
            ["patch", "-p0", "--forward", "--batch", "--fuzz=3"],
        ]

        last_err = ""
        for cmd in strategies:
            result = subprocess.run(
                cmd,
                input=diff_text,
                cwd=self.work_dir,
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return PatchResult(True, result.stdout)
            last_err = result.stdout + result.stderr
            restore()

        # Fallback: применяем каждый hunk по содержимому строк (без контекста)
        restore()
        return self._apply_fuzzy_lines(diff_text)

    def _apply_fuzzy_lines(self, diff_text: str) -> PatchResult:
        """Fallback: применяет diff по содержимому строк, игнорируя контекст и номера.

        Для каждого файла в diff:
        1. Находит все '-' строки (удаления) в исходном файле
        2. Заменяет на '+' строки (добавления)
        """
        hunks = _parse_diff_hunks(diff_text)
        if not hunks:
            return PatchResult(False, "fuzzy: не удалось распарсить hunks из diff")

        applied = 0
        errors = []
        for file_path, file_hunks in hunks.items():
            clean_path = file_path
            full_path = os.path.join(self.work_dir, clean_path)

            if not os.path.exists(full_path):
                errors.append(f"{clean_path}: файл не найден")
                continue

            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for minus_lines, plus_lines, anchor in file_hunks:
                if minus_lines:
                    # Замена: найти minus_lines и заменить на plus_lines
                    idx = _find_lines_in_file(lines, minus_lines)
                    if idx is None:
                        desc = minus_lines[0].rstrip()[:60]
                        errors.append(f"{clean_path}: не найден блок '{desc}...'")
                        continue
                    lines[idx:idx + len(minus_lines)] = plus_lines
                    applied += 1
                elif plus_lines:
                    # Pure addition: вставить plus_lines после anchor (или в начало файла)
                    if anchor:
                        idx = _find_anchor_in_file(lines, anchor)
                        if idx is None:
                            errors.append(f"{clean_path}: не найден anchor '{anchor.rstrip()[:60]}'")
                            continue
                        insert_at = idx + 1
                    else:
                        insert_at = 0  # начало файла
                    for j, pl in enumerate(plus_lines):
                        lines.insert(insert_at + j, pl)
                    applied += 1

            with open(full_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

        if applied > 0:
            msg = f"fuzzy applied {applied} hunk(s)"
            if errors:
                msg += f" (warnings: {'; '.join(errors)})"
            return PatchResult(True, msg)

        return PatchResult(False, f"fuzzy failed: {'; '.join(errors)}")

    def _apply_file_blocks(self, blocks: list[tuple[str, str]]) -> PatchResult:
        """Записывает полные файлы из code blocks."""
        applied = []
        for fpath, content in blocks:
            full_path = os.path.join(self.work_dir, fpath)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
            applied.append(fpath)

        if applied:
            return PatchResult(True, f"Записаны файлы: {', '.join(applied)}")
        return PatchResult(False, "Нет файлов для записи")


def _extract_diff_files(diff_text: str) -> list[str]:
    """Извлекает список файлов из unified diff (strip a/ prefix)."""
    files = []
    for line in diff_text.splitlines():
        if line.startswith("--- a/"):
            files.append(line[6:].strip())
        elif line.startswith("--- ") and not line.startswith("--- /dev/null"):
            files.append(line[4:].strip())
    return files


def _parse_diff_hunks(diff_text: str) -> dict[str, list[tuple[list[str], list[str], str | None]]]:
    """Парсит unified diff в {file: [(minus_lines, plus_lines, anchor_line), ...]}.

    anchor_line — последняя context-строка перед изменением (для pure additions).
    """
    result = {}
    current_file = None
    minus_block: list[str] = []
    plus_block: list[str] = []
    last_context: str | None = None

    def flush():
        if current_file and (minus_block or plus_block):
            result.setdefault(current_file, []).append(
                (list(minus_block), list(plus_block), last_context)
            )
        minus_block.clear()
        plus_block.clear()

    for line in diff_text.splitlines(keepends=True):
        if line.startswith("--- "):
            flush()
            path = line[4:].strip()
            if path.startswith("a/"):
                path = path[2:]
            current_file = path
            last_context = None
        elif line.startswith("+++ "):
            pass
        elif line.startswith("@@ "):
            flush()
            last_context = None
        elif line.startswith("-") and not line.startswith("---"):
            if plus_block and not minus_block:
                flush()
            minus_block.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            plus_block.append(line[1:])
        elif line.startswith(" "):
            flush()
            last_context = line[1:]  # strip leading space

    flush()
    return result


def _find_lines_in_file(file_lines: list[str], target_lines: list[str]) -> int | None:
    """Ищет блок target_lines в file_lines по stripped содержимому."""
    if not target_lines:
        return None

    target_stripped = [l.rstrip() for l in target_lines]
    first = target_stripped[0]
    n = len(target_stripped)

    for i in range(len(file_lines) - n + 1):
        if file_lines[i].rstrip() == first:
            if all(file_lines[i + j].rstrip() == target_stripped[j] for j in range(n)):
                return i
    return None


def _find_anchor_in_file(file_lines: list[str], anchor: str) -> int | None:
    """Ищет строку anchor в файле, возвращает индекс."""
    stripped = anchor.rstrip()
    for i, line in enumerate(file_lines):
        if line.rstrip() == stripped:
            return i
    return None


def _parse_test_output(output: str) -> tuple[int, int]:
    """Парсит количество тестов из pytest/unittest output."""
    # pytest: "5 passed, 2 failed"
    passed = 0
    failed = 0

    m = re.search(r'(\d+)\s+passed', output)
    if m:
        passed = int(m.group(1))
    m = re.search(r'(\d+)\s+failed', output)
    if m:
        failed = int(m.group(1))

    total = passed + failed
    if total == 0:
        # unittest: "Ran 5 tests"
        m = re.search(r'Ran\s+(\d+)\s+test', output)
        if m:
            total = int(m.group(1))
            m2 = re.search(r'FAILED.*failures=(\d+)', output)
            failed = int(m2.group(1)) if m2 else 0
            passed = total - failed

    return total, failed
