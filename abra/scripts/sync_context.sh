#!/usr/bin/env bash

# ==============================================================================
# sync_context.sh
# Точка входа для агента (Process Helix v5.1).
# v4.0: Самодиагностика лимитов среды.
# v5.0: Адаптация под моно-репо abracadabra (abra/ + cadabra/).
# v5.1: Автодетекция среды (Claude Code / Zed+Gemini). Адаптивный коэффициент токенов.
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ABRA_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$ABRA_ROOT/.." && pwd)"

# Имя репо для вывода путей агенту
REPO_NAME="$(basename "$REPO_ROOT")"

# --- АВТОДЕТЕКЦИЯ СРЕДЫ ---
# CLAUDECODE=1 — выставляется Claude Code CLI
# TERM_PROGRAM=Zed — выставляется встроенным терминалом Zed
if [[ "${CLAUDECODE:-}" == "1" ]]; then
    AGENT_ENV="claude"
    BYTES_PER_TOKEN=4    # Кириллица дороже в Claude BPE
elif [[ "${TERM_PROGRAM:-}" == "Zed" ]]; then
    AGENT_ENV="zed"
    BYTES_PER_TOKEN=6    # Gemini BPE эффективнее на UTF-8
else
    AGENT_ENV="unknown"
    BYTES_PER_TOKEN=4    # Консервативная оценка по умолчанию
fi

# Удаление устаревшего кэша (если остался от старых версий)
for cache in "$REPO_ROOT/.context_cache.md" "$ABRA_ROOT/.context_cache.md"; do
    [[ -f "$cache" ]] && rm -f "$cache"
done

echo "STATUS: ВАЛИДАЦИЯ КОНТЕКСТА (СИСТЕМА 2)"
echo "PROCESS HELIX: Автоматическое сканирование дерева (v5.1). Среда: $AGENT_ENV (${BYTES_PER_TOKEN} байт/токен)."
echo "--------------------------------------------------------------------------------"

# --- ЯДРО (обязательная загрузка) ---
CORE_PATHS=()

# .rules (симлинк в корне репо -> abra/core_rules.md)
if [[ -f "$ABRA_ROOT/core_rules.md" ]]; then
    CORE_PATHS+=("$REPO_NAME/abra/core_rules.md")
fi

# Корневые фасады
for root_file in "README.md"; do
    if [[ -f "$REPO_ROOT/$root_file" ]]; then
        CORE_PATHS+=("$REPO_NAME/$root_file")
    fi
done

# Автосканирование ядра abra
for dir in "docs/00_ИНИЦИАЛИЗАЦИЯ" "docs/01_БАЗА_ЗНАНИЙ" "docs/02_ИНСТРУМЕНТЫ"; do
    if [[ -d "$ABRA_ROOT/$dir" ]]; then
        while IFS= read -r -d '' file; do
            rel_path="${file#"$ABRA_ROOT/"}"
            CORE_PATHS+=("$REPO_NAME/abra/$rel_path")
        done < <(find "$ABRA_ROOT/$dir" -name "*.md" -type f -print0 | sort -z)
    fi
done

# --- ПЕРИФЕРИЯ (загружается при наличии контекста) ---
PERIPHERAL_PATHS=()

# abra/docs/03_РЕШЕНИЯ
if [[ -d "$ABRA_ROOT/docs/03_РЕШЕНИЯ" ]]; then
    while IFS= read -r -d '' file; do
        rel_path="${file#"$ABRA_ROOT/"}"
        PERIPHERAL_PATHS+=("$REPO_NAME/abra/$rel_path")
    done < <(find "$ABRA_ROOT/docs/03_РЕШЕНИЯ" -name "*.md" -type f -print0 | sort -z)
fi

# --- ПРОВЕРКА СИМЛИНКОВ ---
BROKEN_LINKS=0
for link in ".rules" ".cursorrules"; do
    link_path="$REPO_ROOT/$link"
    if [[ -L "$link_path" ]]; then
        if ! [[ -f "$link_path" ]]; then
            echo "[ОШИБКА] Битый симлинк: $link → $(readlink "$link_path")"
            BROKEN_LINKS=$((BROKEN_LINKS + 1))
        fi
    elif [[ ! -e "$link_path" ]]; then
        echo "[ПРЕДУПРЕЖДЕНИЕ] Отсутствует: $link (ожидается симлинк → abra/core_rules.md)"
    fi
done
if [[ $BROKEN_LINKS -gt 0 ]]; then
    echo "[КРИТИЧНО] $BROKEN_LINKS битых симлинков. Исправьте перед продолжением."
fi

# --- ВАЛИДАЦИЯ ---
TOTAL=$(( ${#CORE_PATHS[@]} + ${#PERIPHERAL_PATHS[@]} ))

echo "ЯДРО: ${#CORE_PATHS[@]} узлов | ПЕРИФЕРИЯ: ${#PERIPHERAL_PATHS[@]} узлов | ВСЕГО: $TOTAL"
echo ""

# --- ПРОВЕРКА ЛИМИТОВ (АПОПТОЗ) ---
TOTAL_BYTES=0
OVERSIZED_FILES=0

for path in "${CORE_PATHS[@]}" "${PERIPHERAL_PATHS[@]}"; do
    # Убираем имя репо из пути, чтобы получить путь от корня репо
    repo_rel="${path#"$REPO_NAME/"}"
    file_path="$REPO_ROOT/$repo_rel"
    if [[ -f "$file_path" ]]; then
        size=$(wc -c < "$file_path" | tr -d ' ')
        TOTAL_BYTES=$((TOTAL_BYTES + size))
        if [[ $size -gt 16384 ]]; then
            echo "[КРИТИЧЕСКАЯ УЯЗВИМОСТЬ] Файл $path превышает 16KB ($size байт). Риск тихой амнезии!"
            OVERSIZED_FILES=$((OVERSIZED_FILES + 1))
        fi
    fi
done

TOTAL_KB=$((TOTAL_BYTES / 1024))
TOTAL_TOKENS=$((TOTAL_BYTES / BYTES_PER_TOKEN))
TOTAL_KTOKENS=$((TOTAL_TOKENS / 1000))
if [[ $TOTAL_KB -gt 150 ]]; then
    echo "[УГРОЗА МЕТАБОЛИЗМУ] Общий вес контекста: ${TOTAL_KB}KB (~${TOTAL_KTOKENS}K токенов). Требуется дедупликация (Апоптоз)!"
else
    echo "[СТАТУС МЕТАБОЛИЗМА] Общий вес контекста: ${TOTAL_KB}KB (~${TOTAL_KTOKENS}K токенов). В пределах нормы."
fi

if [[ $OVERSIZED_FILES -gt 0 || $TOTAL_KB -gt 150 ]]; then
    echo "--------------------------------------------------------------------------------"
    echo ""
fi

echo "=== ДИРЕКТИВА АГЕНТУ (ОБЯЗАТЕЛЬНО К ИСПОЛНЕНИЮ) ==="
echo "Для восстановления контекста, выполни ОДИН МАССИВНЫЙ ПАРАЛЛЕЛЬНЫЙ ВЫЗОВ"
echo "\`read_file\` для всех перечисленных ниже путей одновременно (без пауз)."
echo ""

echo "--- ЯДРО (ОБЯЗАТЕЛЬНО) ---"
for path in "${CORE_PATHS[@]}"; do
    echo "- $path"
done

if [[ ${#PERIPHERAL_PATHS[@]} -gt 0 ]]; then
    echo ""
    echo "--- ПЕРИФЕРИЯ (ЗАГРУЗИТЬ ПРИ НАЛИЧИИ СВОБОДНОГО КОНТЕКСТА) ---"
    for path in "${PERIPHERAL_PATHS[@]}"; do
        echo "- $path"
    done
fi

echo ""
echo "[ВНИМАНИЕ: УГРОЗА МЕТАБОЛИЗМУ]"
echo "Помни о физических ограничениях инструментов чтения твоей среды исполнения!"
echo "Среда Zed аппаратно обрезает чтение на 16KB. Claude Code обрезает на 2000 строк."
echo "При чтении крупных артефактов обязательно проверяй полноту данных (отсутствие 'тихой амнезии')."
echo ""
echo "Запрещено читать файлы по одному (это ведет к потере фокуса)."
echo "Вызови инструмент \`read_file\` для каждого файла в ОДНОМ ответе."
echo "==================================================="
