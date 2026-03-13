"""Класс задачи: реализация с нуля по спецификации."""

import os
import re
import tempfile

from ..task_class import TaskClass
from ..executors import ExecutionSandbox, _parse_test_output

BASELINE_SYSTEM = (
    "Ты — Senior Software Engineer. Тебе дана спецификация и тест-сьют. "
    "Реализуй решение, проходящее все тесты. "
    "Выдай полные файлы с указанием пути (```python path/to/file.py ... ```)."
)


class GreenfieldTask(TaskClass):

    def build_baseline_prompt(self, brief: str, project_ctx: str, meta: dict) -> tuple[str, str]:
        task_config = meta.get("task_config", {})
        test_file = task_config.get("test_file", "")
        test_section = ""
        if test_file:
            test_section = f"\n\n## Тест-сьют\n\nФайл: `{test_file}`\n(включён в исходный код ниже)"

        user_prompt = (
            f"## Спецификация\n\n{brief}{test_section}"
            f"\n\n## Исходный код проекта (scaffold)\n\n{project_ctx}"
        )
        return BASELINE_SYSTEM, user_prompt

    def build_abra_prompt(self, brief: str, project_ctx: str, abra_kb: str, meta: dict) -> tuple[str, str]:
        task_config = meta.get("task_config", {})
        test_file = task_config.get("test_file", "")
        test_section = ""
        if test_file:
            test_section = f"\n\n## Тест-сьют\n\nФайл: `{test_file}`\n(включён в исходный код ниже)"

        user_prompt = (
            f"abra\n\n{brief}{test_section}"
            f"\n\n## Исходный код проекта (scaffold)\n\n{project_ctx}"
        )
        return abra_kb, user_prompt

    def evaluate_objective(self, model_output: str, meta: dict, project_path: str) -> dict:
        """Объективная оценка: запись файлов → тесты → lint."""
        task_config = meta.get("task_config", {})
        test_cmd = task_config.get("test_cmd", "")
        build_cmd = task_config.get("build_cmd", "")
        lint_cmd = task_config.get("lint_cmd", "")

        result = {
            "files_created": False,
            "tests_pass": False,
            "test_pass_ratio": 0.0,
            "compiles": False,
            "lint_clean": False,
            "loc": 0,
        }

        if not test_cmd:
            return result

        with ExecutionSandbox(project_path) as sandbox:
            # Для greenfield: записываем файлы из ответа
            patch_result = sandbox.apply_patch(model_output)
            result["files_created"] = patch_result.success
            if not patch_result.success:
                result["patch_error"] = patch_result.message
                return result

            if build_cmd:
                result["compiles"] = sandbox.check_build(build_cmd)

            test_result = sandbox.run_tests(test_cmd)
            result["tests_pass"] = test_result.passed
            result["test_total"] = test_result.total
            result["test_failed"] = test_result.failed
            if test_result.total > 0:
                passed = test_result.total - test_result.failed
                result["test_pass_ratio"] = round(passed / test_result.total, 2)

            if lint_cmd:
                result["lint_clean"] = sandbox.check_build(lint_cmd)

            # LOC: считаем строки в новых/изменённых Python файлах
            result["loc"] = _count_new_loc(sandbox.work_dir, project_path)

        return result


def _count_new_loc(work_dir: str, original_dir: str) -> int:
    """Считает строки кода в файлах, которые были созданы или изменены."""
    import subprocess

    try:
        result = subprocess.run(
            f"diff -rq {original_dir} {work_dir} | grep -E 'differ|Only in {work_dir}' | wc -l",
            shell=True, capture_output=True, text=True, timeout=10,
        )
        # Грубая оценка: считаем все .py файлы в work_dir
        result2 = subprocess.run(
            f"find {work_dir} -name '*.py' -exec cat {{}} + | wc -l",
            shell=True, capture_output=True, text=True, timeout=10,
        )
        return int(result2.stdout.strip() or 0)
    except Exception:
        return 0
