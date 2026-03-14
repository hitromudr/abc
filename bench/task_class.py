"""Абстрактная база для классов задач бенчмарка."""

from abc import ABC, abstractmethod


class TaskClass(ABC):
    """Базовый класс задачи. Каждый класс определяет промпты и метрики."""

    @abstractmethod
    def build_baseline_prompt(self, brief: str, project_ctx: str, meta: dict) -> tuple[str, str]:
        """Возвращает (system_prompt, user_prompt) для baseline фазы."""

    @abstractmethod
    def build_abra_prompt(self, brief: str, project_ctx: str, abra_kb: str, meta: dict) -> tuple[str, str]:
        """Возвращает (system_prompt, user_prompt) для abra фазы."""

    def build_cadabra_prompt(self, abra_output: str, project_ctx: str,
                             cadabra_rules: str, meta: dict) -> tuple[str, str]:
        """Возвращает (system_prompt, user_prompt) для cadabra фазы.

        abra_output: результат abra фазы (должен содержать EXECUTION_STATE).
        cadabra_rules: содержимое cadabra/core_rules.md.
        """
        system_prompt = (
            f"{cadabra_rules}\n\n"
            "ВАЖНО: Ты работаешь в режиме бенчмарка. У тебя нет доступа к файловой системе. "
            "Вместо этого выдай все изменения как unified diff (```diff ... ```). "
            "Выполни каждый шаг из EXECUTION_STATE и выдай финальный патч."
        )
        user_prompt = (
            f"cadabra\n\n"
            f"## EXECUTION_STATE от Архитектора\n\n{abra_output}\n\n"
            f"## Исходный код проекта\n\n{project_ctx}"
        )
        return system_prompt, user_prompt

    def evaluate_objective(self, model_output: str, meta: dict, project_path: str) -> dict:
        """Объективные метрики (без модели-арбитра). По умолчанию пусто."""
        return {}
