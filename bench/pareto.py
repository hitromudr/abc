"""Pareto frontier: выявление оптимальных моделей по quality × cost × speed."""


def is_dominated(a: dict, b: dict, dimensions: list[str],
                 maximize: set[str] | None = None) -> bool:
    """Проверяет что точка a доминируема точкой b.

    a доминируема если b не хуже по всем измерениям и строго лучше хотя бы по одному.
    maximize: множество dimensions где больше = лучше (остальные — меньше = лучше).
    """
    if maximize is None:
        maximize = {"quality_score"}

    dominated = True
    strictly_better = False

    for dim in dimensions:
        va = a.get(dim, 0)
        vb = b.get(dim, 0)

        if dim in maximize:
            if vb < va:
                dominated = False
                break
            if vb > va:
                strictly_better = True
        else:
            if vb > va:
                dominated = False
                break
            if vb < va:
                strictly_better = True

    return dominated and strictly_better


def pareto_frontier(results: list[dict],
                    dimensions: list[str] | None = None,
                    maximize: set[str] | None = None) -> list[dict]:
    """Возвращает Pareto-оптимальные модели.

    Args:
        results: список dict с ключами model, quality_score, cost_usd, wall_time_sec
        dimensions: измерения для сравнения
        maximize: какие dimensions максимизировать (остальные минимизируются)

    Returns:
        Подмножество results, не доминируемое ни одной другой точкой.
    """
    if dimensions is None:
        dimensions = ["quality_score", "cost_usd", "wall_time_sec"]
    if maximize is None:
        maximize = {"quality_score"}

    frontier = []
    for i, a in enumerate(results):
        dominated_by_any = False
        for j, b in enumerate(results):
            if i == j:
                continue
            if is_dominated(a, b, dimensions, maximize):
                dominated_by_any = True
                break
        if not dominated_by_any:
            frontier.append(a)

    return frontier


def efficiency_score(result: dict) -> float:
    """quality / cost — чем выше, тем эффективнее."""
    quality = result.get("quality_score", 0)
    cost = result.get("cost_usd", 0)
    if cost <= 0:
        return float('inf') if quality > 0 else 0.0
    return round(quality / cost, 2)
