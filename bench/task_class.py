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

    def evaluate_objective(self, model_output: str, meta: dict, project_path: str) -> dict:
        """Объективные метрики (без модели-арбитра). По умолчанию пусто."""
        return {}
