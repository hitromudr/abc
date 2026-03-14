#!/bin/bash
# Бенчмарк GSD vs Cadabra vs Baseline на задаче bench 005 (refactor dedup)
#
# Использование:
#   ./bench/run_gsd_bench.sh [gsd|cadabra|baseline] [tag]
#
# Примеры:
#   ./bench/run_gsd_bench.sh gsd gsd-opus-1
#   ./bench/run_gsd_bench.sh cadabra cadabra-opus-1
#   ./bench/run_gsd_bench.sh baseline baseline-opus-1

set -euo pipefail

MODE="${1:-gsd}"
TAG="${2:-${MODE}-$(date +%s)}"
PROJECT_DIR="$HOME/work/isearch"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/../benchmarks/005_isearch_refactor_dedup/results/$TAG"
WORK_DIR=$(mktemp -d "/tmp/bench005-${MODE}-XXXXXX")

echo "============================================"
echo "Bench 005: $MODE (tag: $TAG)"
echo "Work dir: $WORK_DIR"
echo "============================================"

# Копируем проект (без .git, __pycache__, .venv)
cp -r "$PROJECT_DIR" "$WORK_DIR/isearch"
rm -rf "$WORK_DIR/isearch/.git" "$WORK_DIR/isearch/__pycache__" "$WORK_DIR/isearch/.venv"

# Инициализируем git (GSD требует)
cd "$WORK_DIR/isearch"
git init -q
git add -A
git commit -q -m "initial"

TASK_DESC="Консолидировать 3 дублированных реализации загрузки .gitignore и классификации типов файлов в единый модуль src/file_utils.py. Требования: (1) не более 2 файлов из src/ содержат слова pathspec/gitignore, (2) не более 2 файлов из src/ содержат слова allowed_extensions/code_extensions/docs_extensions, (3) публичный API сохранён: IndexingService, build_graph(), load_documents(). Не изменять файлы тестов. 19 тестов должны проходить: pytest tests/unit/test_refactor_dedup.py tests/unit/test_graph_builder.py tests/unit/test_graph_analyzer.py -v"

START_TIME=$(date +%s)

# Убираем CLAUDECODE чтобы не блокировался вложенный запуск
unset CLAUDECODE 2>/dev/null || true

cd "$WORK_DIR/isearch"

if [ "$MODE" = "gsd" ]; then
    echo "Running GSD /gsd:quick --full ..."
    claude -p "/gsd:quick --full $TASK_DESC" \
      --permission-mode bypassPermissions \
      --max-budget-usd 5 \
      --output-format json \
      > "$WORK_DIR/claude_output.json" 2>&1

elif [ "$MODE" = "cadabra" ]; then
    echo "Running Cadabra (EXECUTION_STATE + Claude Code) ..."
    EXEC_STATE=$(cat "$SCRIPT_DIR/cadabra_exec_state.txt")
    claude -p "$EXEC_STATE" \
      --permission-mode bypassPermissions \
      --max-budget-usd 5 \
      --output-format json \
      > "$WORK_DIR/claude_output.json" 2>&1

elif [ "$MODE" = "baseline" ]; then
    echo "Running baseline (vanilla prompt) ..."
    claude -p "$TASK_DESC" \
      --permission-mode bypassPermissions \
      --max-budget-usd 5 \
      --output-format json \
      > "$WORK_DIR/claude_output.json" 2>&1

else
    echo "Unknown mode: $MODE (use gsd, cadabra, or baseline)"
    exit 1
fi

END_TIME=$(date +%s)
WALL_TIME=$((END_TIME - START_TIME))

echo ""
echo "Completed in ${WALL_TIME}s"
echo ""

# Объективные метрики
echo "=== Объективные метрики ==="

# Tests
cd "$WORK_DIR/isearch"
TEST_CMD="python -m pytest tests/unit/test_refactor_dedup.py tests/unit/test_graph_builder.py tests/unit/test_graph_analyzer.py -v"
if $TEST_CMD > "$WORK_DIR/test_output.txt" 2>&1; then
  TESTS_PASS=true
  echo "tests_pass: ✅"
else
  TESTS_PASS=false
  echo "tests_pass: ❌"
  tail -10 "$WORK_DIR/test_output.txt"
fi

# Compiles
if python -m py_compile src/services.py 2>/dev/null && \
   python -m py_compile src/graph_builder.py 2>/dev/null && \
   python -m py_compile src/index.py 2>/dev/null; then
  COMPILES=true
  echo "compiles: ✅"
else
  COMPILES=false
  echo "compiles: ❌"
fi

# API preserved
API_OK=true
for check in "src/services.py:IndexingService" "src/graph_builder.py:build_graph" "src/index.py:load_documents"; do
  FILE="${check%%:*}"
  SYMBOL="${check##*:}"
  if [ -f "$FILE" ] && grep -q "$SYMBOL" "$FILE"; then
    :
  else
    API_OK=false
  fi
done
echo "api_preserved: $([ "$API_OK" = true ] && echo '✅' || echo '❌')"

# Diff size (changed lines)
DIFF_SIZE=0
for f in src/file_utils.py src/services.py src/graph_builder.py src/index.py; do
  NEW_PATH="$WORK_DIR/isearch/$f"
  OLD_PATH="$PROJECT_DIR/$f"
  if [ -f "$NEW_PATH" ]; then
    if [ -f "$OLD_PATH" ]; then
      LINES=$(diff "$OLD_PATH" "$NEW_PATH" 2>/dev/null | grep -c '^[<>]' || true)
      DIFF_SIZE=$((DIFF_SIZE + LINES))
    else
      LINES=$(wc -l < "$NEW_PATH")
      DIFF_SIZE=$((DIFF_SIZE + LINES))
    fi
  fi
done
echo "diff_size: $DIFF_SIZE"

# Parse cost/tokens from claude output
COST="N/A"
TOKENS="N/A"
if [ -f "$WORK_DIR/claude_output.json" ]; then
  COST=$(python3 -c "
import json, sys
try:
    d = json.load(open('$WORK_DIR/claude_output.json'))
    print(d.get('cost_usd', d.get('costUSD', d.get('cost', 'N/A'))))
except: print('N/A')
" 2>/dev/null)
  TOKENS=$(python3 -c "
import json, sys
try:
    d = json.load(open('$WORK_DIR/claude_output.json'))
    u = d.get('usage', {})
    print(u.get('input_tokens', 0) + u.get('output_tokens', 0))
except: print('N/A')
" 2>/dev/null)
  echo "cost: \$$COST"
  echo "tokens: $TOKENS"
fi

echo "wall_time: ${WALL_TIME}s"

# Сохраняем результаты
mkdir -p "$RESULTS_DIR"
cat > "$RESULTS_DIR/metrics.yml" << YAML
mode: $MODE
tag: $TAG
tests_pass: $TESTS_PASS
compiles: $COMPILES
api_preserved: $API_OK
diff_size: $DIFF_SIZE
cost: $COST
tokens: $TOKENS
wall_time: $WALL_TIME
work_dir: $WORK_DIR
YAML

echo ""
echo "Результаты: $RESULTS_DIR/metrics.yml"
echo "Work dir: $WORK_DIR (не удалён для инспекции)"
