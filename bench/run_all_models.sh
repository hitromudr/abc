#!/bin/bash
# Массовый запуск bench 005: GSD vs Cadabra vs Baseline
#
# Claude модели: через claude -p (baseline + cadabra + gsd)
# Non-Claude модели: через cadabra_runtime.py (только cadabra runtime)
#
# Использование:
#   ./bench/run_all_models.sh [sonnet|gemini|deepseek|all]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN="$SCRIPT_DIR/run_gsd_bench.sh"
TARGET="${1:-all}"

echo "================================"
echo "Bench 005: Multi-model benchmark"
echo "Target: $TARGET"
echo "================================"

# ─── Claude модели (через claude -p) ───

if [ "$TARGET" = "sonnet" ] || [ "$TARGET" = "all" ]; then
    echo ""
    echo "═══ SONNET ═══"
    "$RUN" baseline "baseline-sonnet-1" "sonnet"
    "$RUN" cadabra "cadabra-sonnet-1" "sonnet"
    "$RUN" gsd "gsd-sonnet-1" "sonnet"
fi

# ─── Non-Claude модели (через cadabra_runtime.py) ───

if [ "$TARGET" = "deepseek" ] || [ "$TARGET" = "all" ]; then
    echo ""
    echo "═══ DEEPSEEK (cadabra runtime only) ═══"
    DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY "$HOME/work/autowarp/.env" | cut -d= -f2)
    export DEEPSEEK_API_KEY
    PYTHONUNBUFFERED=1 python -m bench.cadabra_runtime \
        --project "$HOME/work/isearch" \
        --model deepseek/deepseek-chat \
        --tag ds-rt-bench-1
fi

# Gemini через LiteLLM (нужен GEMINI_API_KEY)
# if [ "$TARGET" = "gemini" ] || [ "$TARGET" = "all" ]; then
#     echo ""
#     echo "═══ GEMINI (cadabra runtime only) ═══"
#     # Uncomment when ready:
#     # PYTHONUNBUFFERED=1 python -m bench.cadabra_runtime \
#     #     --project "$HOME/work/isearch" \
#     #     --model gemini/gemini-2.5-flash \
#     #     --tag gemini25flash-rt-1
# fi

echo ""
echo "═══ DONE ═══"
echo "Results: benchmarks/005_isearch_refactor_dedup/results/"
