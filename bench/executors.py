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
        # Стратегия 1: unified diff
        diff_blocks = re.findall(r'```diff\s*\n(.*?)```', model_output, re.DOTALL)
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

        Пробует несколько стратегий: strict → fuzz=3 → p0.
        Модели часто генерируют неточный контекст в diff.
        """
        patch_file = os.path.join(self.work_dir, ".patch")
        with open(patch_file, "w") as f:
            f.write(diff_text)

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
                os.unlink(patch_file)
                return PatchResult(True, result.stdout)
            last_err = result.stdout + result.stderr

        os.unlink(patch_file)
        return PatchResult(False, f"patch failed: {last_err}")

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
