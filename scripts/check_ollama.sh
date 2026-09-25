#!/usr/bin/env bash
# Проверка Ollama и нужных моделей перед запуском RAG.
set -euo pipefail

echo "== Ollama health =="
curl -sf http://127.0.0.1:11434/api/tags >/dev/null
echo "OK: Ollama отвечает"

need_pull=0
for model in "nomic-embed-text" "qwen3.5:27b"; do
  if ollama list | awk '{print $1}' | grep -qx "$model"; then
    echo "OK: модель есть — $model"
  else
    echo "MISS: $model — будет скачана"
    need_pull=1
    ollama pull "$model"
  fi
done

echo "== GPU note =="
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
  echo "WARN: NVIDIA driver не активен — Ollama, скорее всего, на CPU (медленно)."
  echo "FIX (вручную в терминале): sudo apt install nvidia-dkms-580-open && sudo reboot"
fi

exit 0
