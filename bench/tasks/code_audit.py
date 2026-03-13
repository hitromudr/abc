"""Класс задачи: аудит кодовой базы (существующий, извлечён из runner.py)."""

from ..task_class import TaskClass

BASELINE_SYSTEM = (
    "Ты — Senior Software Engineer. Проведи глубокий аудит кодовой базы. "
    "Выдай структурированный отчёт с классификацией дефектов и оценкой критичности."
)


class CodeAuditTask(TaskClass):

    def build_baseline_prompt(self, brief: str, project_ctx: str, meta: dict) -> tuple[str, str]:
        user_prompt = f"## Задание\n\n{brief}\n\n## Исходный код проекта\n\n{project_ctx}"
        return BASELINE_SYSTEM, user_prompt

    def build_abra_prompt(self, brief: str, project_ctx: str, abra_kb: str, meta: dict) -> tuple[str, str]:
        system_prompt = abra_kb
        user_prompt = f"abra\n\n{brief}\n\n## Исходный код проекта\n\n{project_ctx}"
        return system_prompt, user_prompt
