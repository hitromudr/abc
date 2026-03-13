"""Статистические утилиты: bootstrap CI, Mann-Whitney U, sample size."""

import random
import math


def bootstrap_ci(scores: list[float], n_bootstrap: int = 1000,
                 alpha: float = 0.05) -> tuple[float, float, float]:
    """Bootstrap confidence interval для среднего.

    Returns: (mean, lower_ci, upper_ci)
    """
    if not scores:
        return (0.0, 0.0, 0.0)
    if len(scores) == 1:
        return (scores[0], scores[0], scores[0])

    n = len(scores)
    means = []
    for _ in range(n_bootstrap):
        sample = [random.choice(scores) for _ in range(n)]
        means.append(sum(sample) / n)

    means.sort()
    lo = int(n_bootstrap * (alpha / 2))
    hi = int(n_bootstrap * (1 - alpha / 2))

    return (
        round(sum(scores) / n, 4),
        round(means[lo], 4),
        round(means[min(hi, len(means) - 1)], 4),
    )


def mann_whitney_u(a: list[float], b: list[float]) -> float | None:
    """Mann-Whitney U test (non-parametric). Returns p-value.

    Simplified implementation — для production рекомендуется scipy.stats.mannwhitneyu.
    Returns None при недостаточном количестве данных.
    """
    if len(a) < 2 or len(b) < 2:
        return None

    na, nb = len(a), len(b)

    # Rank all observations
    combined = [(v, 'a') for v in a] + [(v, 'b') for v in b]
    combined.sort(key=lambda x: x[0])

    # Assign ranks (handle ties)
    ranks = {}
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2
        for k in range(i, j):
            ranks[id(combined[k])] = avg_rank  # won't work, need index-based
        i = j

    # Recompute with indices
    rank_sum_a = 0.0
    idx = 0
    n = len(combined)
    i = 0
    while i < n:
        j = i
        while j < n and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2
        for k in range(i, j):
            if combined[k][1] == 'a':
                rank_sum_a += avg_rank
        i = j

    u_a = rank_sum_a - na * (na + 1) / 2
    u_b = na * nb - u_a
    u = min(u_a, u_b)

    # Normal approximation (valid for na, nb >= 8)
    mu = na * nb / 2
    sigma = math.sqrt(na * nb * (na + nb + 1) / 12)
    if sigma == 0:
        return 1.0

    z = abs((u - mu) / sigma)
    # Two-tailed p-value (approximation via error function)
    p = 2 * (1 - _norm_cdf(z))

    return round(p, 4)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF approximation."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def required_sample_size(effect_size: float, power: float = 0.8,
                         alpha: float = 0.05) -> int:
    """Минимальный размер выборки для заданного effect size (Cohen's d).

    Simplified formula: n ≈ (z_alpha + z_power)^2 * 2 / d^2
    """
    if effect_size <= 0:
        return 999

    z_alpha = _norm_ppf(1 - alpha / 2)
    z_power = _norm_ppf(power)

    n = math.ceil(2 * ((z_alpha + z_power) ** 2) / (effect_size ** 2))
    return max(n, 2)


def _norm_ppf(p: float) -> float:
    """Approximate inverse normal CDF (percent point function)."""
    # Rational approximation (Abramowitz & Stegun 26.2.23)
    if p <= 0:
        return -4.0
    if p >= 1:
        return 4.0
    if p == 0.5:
        return 0.0

    if p > 0.5:
        return -_norm_ppf(1 - p)

    t = math.sqrt(-2 * math.log(p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308

    return -(t - (c0 + c1 * t + c2 * t ** 2) / (1 + d1 * t + d2 * t ** 2 + d3 * t ** 3))


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------

TASK_WEIGHTS = {
    "bug_fix": 0.25,
    "code_audit": 0.20,
    "refactor": 0.15,
    "greenfield": 0.15,
    "code_review": 0.15,
    "debug": 0.10,
}


def composite_score(task_scores: dict[str, list[float]]) -> float:
    """Взвешенный composite score по всем классам задач.

    Args:
        task_scores: {task_class: [score1, score2, ...]}
    """
    total = 0.0
    weight_sum = 0.0

    for task, scores in task_scores.items():
        if not scores:
            continue
        weight = TASK_WEIGHTS.get(task, 0.1)
        total += weight * (sum(scores) / len(scores))
        weight_sum += weight

    if weight_sum == 0:
        return 0.0
    return round(total / weight_sum, 4)
