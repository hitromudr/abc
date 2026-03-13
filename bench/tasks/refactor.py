"""Класс задачи: рефакторинг кода."""

from ..task_class import TaskClass
from ..executors import ExecutionSandbox

BASELINE_SYSTEM = (
    "Ты — Senior Software Engineer. Тебе дан проект и цель рефакторинга. "
    "Выполни рефакторинг минимальными изменениями, сохранив поведение. "
    "Выдай результат как unified diff (```diff ... ```) "
    "или полные изменённые файлы с указанием пути."
)


class RefactorTask(TaskClass):

    def build_baseline_prompt(self, brief: str, project_ctx: str, meta: dict) -> tuple[str, str]:
        user_prompt = f"## Задание\n\n{brief}\n\n## Исходный код проекта\n\n{project_ctx}"
        return BASELINE_SYSTEM, user_prompt

    def build_abra_prompt(self, brief: str, project_ctx: str, abra_kb: str, meta: dict) -> tuple[str, str]:
        user_prompt = f"abra\n\n{brief}\n\n## Исходный код проекта\n\n{project_ctx}"
        return abra_kb, user_prompt

    def evaluate_objective(self, model_output: str, meta: dict, project_path: str) -> dict:
        """Объективная оценка: patch → tests pass → AST preservation → complexity delta."""
        task_config = meta.get("task_config", {})
        test_cmd = task_config.get("test_cmd", "")
        build_cmd = task_config.get("build_cmd", "")

        result = {
            "patch_applied": False,
            "tests_pass": False,
            "compiles": False,
            "diff_size": -1,
            "api_preserved": None,
            "cyclomatic_delta": None,
        }

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
            result["tests_pass"] = test_result.passed
            result["diff_size"] = sandbox.diff_size()

            # AST comparison для target файлов
            target_files = task_config.get("target_files", [])
            if target_files:
                result["api_preserved"] = _check_api_preserved(
                    project_path, sandbox.work_dir, target_files
                )

            # Cyclomatic complexity delta
            if target_files:
                result["cyclomatic_delta"] = _cyclomatic_delta(
                    project_path, sandbox.work_dir, target_files
                )

        return result


def _check_api_preserved(original_path: str, patched_path: str,
                         target_files: list[str]) -> bool:
    """Проверяет что публичный API (функции, классы) не изменился."""
    import ast
    import os

    for fpath in target_files:
        if not fpath.endswith('.py'):
            continue

        orig = os.path.join(original_path, fpath)
        patched = os.path.join(patched_path, fpath)

        if not os.path.exists(patched):
            return False  # файл удалён

        try:
            orig_symbols = _public_symbols(orig) if os.path.exists(orig) else set()
            patched_symbols = _public_symbols(patched)

            # Все оригинальные публичные символы должны остаться
            if not orig_symbols.issubset(patched_symbols):
                return False
        except SyntaxError:
            return False

    return True


def _public_symbols(filepath: str) -> set[str]:
    """Извлекает публичные символы (функции и классы) из Python-файла."""
    import ast

    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    symbols = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith('_'):
                symbols.add(f"func:{node.name}")
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith('_'):
                symbols.add(f"class:{node.name}")
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not item.name.startswith('_'):
                            symbols.add(f"method:{node.name}.{item.name}")

    return symbols


def _cyclomatic_delta(original_path: str, patched_path: str,
                      target_files: list[str]) -> float | None:
    """Вычисляет изменение cyclomatic complexity (отрицательное = улучшение)."""
    import subprocess
    import os

    try:
        orig_cc = 0.0
        patched_cc = 0.0
        count = 0

        for fpath in target_files:
            if not fpath.endswith('.py'):
                continue

            orig = os.path.join(original_path, fpath)
            patched = os.path.join(patched_path, fpath)

            if os.path.exists(orig):
                orig_cc += _file_complexity(orig)
                count += 1
            if os.path.exists(patched):
                patched_cc += _file_complexity(patched)

        if count == 0:
            return None

        return round(patched_cc - orig_cc, 2)
    except Exception:
        return None


def _file_complexity(filepath: str) -> float:
    """Средняя cyclomatic complexity файла через radon (если доступен)."""
    try:
        import subprocess
        result = subprocess.run(
            ["radon", "cc", "-a", "-nc", filepath],
            capture_output=True, text=True, timeout=10,
        )
        # Парсим "Average complexity: A (1.5)"
        for line in result.stdout.splitlines():
            if "Average complexity" in line:
                import re
                m = re.search(r'\(([0-9.]+)\)', line)
                if m:
                    return float(m.group(1))
    except (FileNotFoundError, Exception):
        pass

    # Fallback: считаем ветвления через AST
    return _ast_complexity(filepath)


def _ast_complexity(filepath: str) -> float:
    """Грубая оценка complexity через подсчёт branch statements."""
    import ast

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except SyntaxError:
        return 0.0

    branches = 0
    functions = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                             ast.With, ast.Assert)):
            branches += 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions += 1

    if functions == 0:
        return float(branches)
    return round(branches / functions, 2)
