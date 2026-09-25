#!/usr/bin/env bash
# Athena — один скрипт запуска: Ollama + UI.
# Дальше только откройте браузер (скрипт попробует открыть сам).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOST="${ATHENA_HOST:-127.0.0.1}"
PORT="${ATHENA_PORT:-7860}"
URL="http://${HOST}:${PORT}"
LLM="${ATHENA_LLM:-qwen3.5:27b}"
EMBED="${ATHENA_EMBED:-nomic-embed-text}"

# Подхватить локальный .env, если есть (не коммитится)
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

echo "== Athena =="
echo "KB: ${ATHENA_KB:-$ROOT/knowledge_base (default)}"
echo "LLM: $LLM"
echo "UI: $URL"
echo

# --- venv ---
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "[1/5] Создаю venv и ставлю зависимости…"
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -U pip
  "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
else
  echo "[1/5] venv OK"
fi

# --- Ollama ---
echo "[2/5] Ollama…"
if ! curl -sf "${OLLAMA_HOST:-http://127.0.0.1:11434}/api/tags" >/dev/null 2>&1; then
  if command -v systemctl >/dev/null 2>&1 && systemctl is-enabled ollama >/dev/null 2>&1; then
    echo "      стартую ollama.service…"
    sudo systemctl start ollama || true
    sleep 2
  fi
  if ! curl -sf "${OLLAMA_HOST:-http://127.0.0.1:11434}/api/tags" >/dev/null 2>&1; then
    echo "      запускаю: ollama serve (фон)"
    nohup ollama serve >/tmp/athena-ollama.log 2>&1 &
    for i in {1..30}; do
      curl -sf "${OLLAMA_HOST:-http://127.0.0.1:11434}/api/tags" >/dev/null 2>&1 && break
      sleep 0.5
    done
  fi
fi
if ! curl -sf "${OLLAMA_HOST:-http://127.0.0.1:11434}/api/tags" >/dev/null 2>&1; then
  echo "ERROR: Ollama не отвечает. Установите и запустите: https://ollama.com"
  exit 1
fi
echo "      Ollama OK"

# --- models ---
echo "[3/5] Модели…"
need_pull=0
if ! ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$LLM"; then
  echo "      pull $LLM …"
  ollama pull "$LLM"
  need_pull=1
fi
if ! ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$EMBED" \
   && ! ollama list 2>/dev/null | awk '{print $1}' | grep -qx "${EMBED}:latest"; then
  echo "      pull $EMBED …"
  ollama pull "$EMBED"
  need_pull=1
fi
[[ "$need_pull" -eq 0 ]] && echo "      модели на месте"

# --- index ---
echo "[4/5] Индекс…"
need_ingest=0
if [[ ! -d "$ROOT/data/chroma" ]] || [[ -z "$(ls -A "$ROOT/data/chroma" 2>/dev/null || true)" ]]; then
  need_ingest=1
else
  if ! PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" - <<'PY' >/dev/null 2>&1
from app.config import CHROMA_DIR, COLLECTION_NAME
import chromadb
c = chromadb.PersistentClient(path=str(CHROMA_DIR))
col = c.get_collection(COLLECTION_NAME)
assert col.count() > 0
PY
  then
    need_ingest=1
  fi
fi

if [[ "$need_ingest" -eq 1 ]]; then
  echo "      собираю индекс (ingest)…"
  PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -m app.ingest
else
  echo "      индекс OK"
  echo "      обновить после правок заметок: ./start.sh не переиндексирует сам — выполните:"
  echo "      PYTHONPATH=. .venv/bin/python -m app.ingest"
fi

# --- free port / start UI ---
echo "[5/5] UI…"
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" >/dev/null 2>&1 || true
fi
sleep 0.5

export PYTHONPATH="$ROOT"
export ATHENA_LLM="$LLM"
export ATHENA_EMBED="$EMBED"

# прогрев LLM в фоне (не блокирует UI)
(
  curl -sf "${OLLAMA_HOST:-http://127.0.0.1:11434}/api/chat" \
    -d "{\"model\":\"$LLM\",\"messages\":[{\"role\":\"user\",\"content\":\"ok\"}],\"stream\":false,\"think\":false,\"options\":{\"num_predict\":4,\"num_ctx\":1024},\"keep_alive\":\"30m\"}" \
    >/tmp/athena-warmup.json 2>/dev/null || true
) &

nohup "$ROOT/.venv/bin/python" -m app.server >/tmp/athena-ui.log 2>&1 &
UI_PID=$!
echo "      PID=$UI_PID  log=/tmp/athena-ui.log"

for i in {1..40}; do
  if curl -sf "$URL/api/health" >/dev/null 2>&1; then
    echo
    echo "Готово. Откройте UI:"
    echo "  $URL"
    echo
    # открыть браузер, если возможно
    if command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$URL" >/dev/null 2>&1 || true
    elif command -v open >/dev/null 2>&1; then
      open "$URL" >/dev/null 2>&1 || true
    fi
    echo "Остановка позже: kill $UI_PID   или   fuser -k ${PORT}/tcp"
    exit 0
  fi
  sleep 0.25
done

echo "ERROR: UI не поднялся. Смотрите /tmp/athena-ui.log"
tail -n 40 /tmp/athena-ui.log || true
exit 1
