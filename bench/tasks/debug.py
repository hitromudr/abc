"""Класс задачи: debugging (диагноз + фикс по traceback)."""

from ..task_class import TaskClass
from ..executors import ExecutionSandbox

BASELINE_SYSTEM = (
    "Ты — Senior Software Engineer. Тебе дан проект с ошибкой, traceback и описание сбоя. "
    "Определи root cause и предложи минимальный фикс. "
    "Выдай: 1) Диагноз (root cause, файл, строка). "
    "2) Фикс как unified diff (```diff ... ```) или полный файл с путём."
)


class DebugTask(TaskClass):

    def build_baseline_prompt(self, brief: str, project_ctx: str, meta: dict) -> tuple[str, str]:
        task_config = meta.get("task_config", {})
        traceback = task_config.get("traceback", "")
        tb_section = ""
        if traceback:
            tb_section = f"\n\n## Traceback\n\n```\n{traceback}\n```"

        user_prompt = (
            f"## Описание сбоя\n\n{brief}{tb_section}"
            f"\n\n## Исходный код проекта\n\n{project_ctx}"
        )
        return BASELINE_SYSTEM, user_prompt

    def build_abra_prompt(self, brief: str, project_ctx: str, abra_kb: str, meta: dict) -> tuple[str, str]:
        task_config = meta.get("task_config", {})
        traceback = task_config.get("traceback", "")
        tb_section = ""
        if traceback:
            tb_section = f"\n\n## Traceback\n\n```\n{traceback}\n```"

        user_prompt = (
            f"abra\n\n{brief}{tb_section}"
            f"\n\n## Исходный код проекта\n\n{project_ctx}"
        )
        return abra_kb, user_prompt

    def evaluate_objective(self, model_output: str, meta: dict, project_path: str) -> dict:
        """Объективная оценка: root cause match + fix tests pass."""
        task_config = meta.get("task_config", {})
        test_cmd = task_config.get("test_cmd", "")
        build_cmd = task_config.get("build_cmd", "")
        root_cause_markers = task_config.get("root_cause_markers", [])

        result = {
            "correct_root_cause": None,
            "patch_applied": False,
            "fix_tests_pass": False,
            "compiles": False,
            "diff_size": -1,
        }

        # Проверяем root cause
        if root_cause_markers:
            text_lower = model_output.lower()
            hits = sum(1 for m in root_cause_markers if m.lower() in text_lower)
            # Считаем root cause верным если >= 50% маркеров найдены
            result["correct_root_cause"] = hits >= max(1, len(root_cause_markers) // 2)
            result["root_cause_hits"] = hits
            result["root_cause_total_markers"] = len(root_cause_markers)

        if not test_cmd:
            return result

        with ExecutionSandbox(project_path) as sandbox:
            patch_result = sandbox.apply_patch(model_output)
            result["patch_applied"] = patch_result.success
            if not patch_result.success:
                result["patch_error"] = patch_result.message
                return result

            if build_cmd:
                result["compiles"] = sandbox.check_build(build_cmd)

            test_result = sandbox.run_tests(test_cmd)
            result["fix_tests_pass"] = test_result.passed
            result["diff_size"] = sandbox.diff_size()

        return result
