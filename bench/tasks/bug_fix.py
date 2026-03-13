"""Класс задачи: исправление бага (полностью объективная оценка)."""

from ..task_class import TaskClass
from ..executors import ExecutionSandbox

BASELINE_SYSTEM = (
    "Ты — Senior Software Engineer. Тебе дан проект с известным багом и падающим тестом. "
    "Исправь баг минимальным патчем. Выдай результат как unified diff (```diff ... ```) "
    "или полные изменённые файлы (```python ... ``` с указанием пути)."
)


class BugFixTask(TaskClass):

    def build_baseline_prompt(self, brief: str, project_ctx: str, meta: dict) -> tuple[str, str]:
        task_config = meta.get("task_config", {})
        failing_test = task_config.get("failing_test", "")
        test_info = f"\n\n## Падающий тест\n\n`{failing_test}`" if failing_test else ""

        user_prompt = (
            f"## Задание\n\n{brief}{test_info}"
            f"\n\n## Исходный код проекта\n\n{project_ctx}"
        )
        return BASELINE_SYSTEM, user_prompt

    def build_abra_prompt(self, brief: str, project_ctx: str, abra_kb: str, meta: dict) -> tuple[str, str]:
        task_config = meta.get("task_config", {})
        failing_test = task_config.get("failing_test", "")
        test_info = f"\n\n## Падающий тест\n\n`{failing_test}`" if failing_test else ""

        system_prompt = abra_kb
        user_prompt = (
            f"abra\n\n{brief}{test_info}"
            f"\n\n## Исходный код проекта\n\n{project_ctx}"
        )
        return system_prompt, user_prompt

    def evaluate_objective(self, model_output: str, meta: dict, project_path: str) -> dict:
        """Объективная оценка: apply patch → run tests."""
        task_config = meta.get("task_config", {})
        test_cmd = task_config.get("test_cmd", "")
        build_cmd = task_config.get("build_cmd", "")

        result = {
            "patch_applied": False,
            "tests_pass": False,
            "regression_free": False,
            "compiles": False,
            "diff_size": -1,
        }

        if not test_cmd:
            return result

        with ExecutionSandbox(project_path) as sandbox:
            # Apply patch
            patch_result = sandbox.apply_patch(model_output)
            result["patch_applied"] = patch_result.success
            if not patch_result.success:
                result["patch_error"] = patch_result.message
                return result

            # Build check
            if build_cmd:
                result["compiles"] = sandbox.check_build(build_cmd)

            # Run failing test
            test_result = sandbox.run_tests(test_cmd)
            result["tests_pass"] = test_result.passed
            result["test_total"] = test_result.total
            result["test_failed"] = test_result.failed

            # Regression: run full test suite if specified
            full_test_cmd = task_config.get("full_test_cmd", "")
            if full_test_cmd:
                regression = sandbox.run_tests(full_test_cmd)
                result["regression_free"] = regression.passed
            else:
                result["regression_free"] = test_result.passed

            # Diff size
            result["diff_size"] = sandbox.diff_size()

        return result
