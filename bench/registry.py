"""Реестр классов задач."""

from .task_class import TaskClass
from .tasks.code_audit import CodeAuditTask
from .tasks.bug_fix import BugFixTask
from .tasks.refactor import RefactorTask
from .tasks.greenfield import GreenfieldTask
from .tasks.code_review import CodeReviewTask
from .tasks.debug import DebugTask

TASK_CLASSES: dict[str, type[TaskClass]] = {
    "code_audit": CodeAuditTask,
    "bug_fix": BugFixTask,
    "refactor": RefactorTask,
    "greenfield": GreenfieldTask,
    "code_review": CodeReviewTask,
    "debug": DebugTask,
}


def get_task_class(meta: dict) -> TaskClass:
    """Возвращает экземпляр TaskClass по meta.yml. Default: code_audit."""
    name = meta.get("task_class", "code_audit")
    cls = TASK_CLASSES.get(name)
    if cls is None:
        raise ValueError(f"Неизвестный task_class: {name!r}. Доступные: {list(TASK_CLASSES)}")
    return cls()
