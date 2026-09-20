#!/usr/bin/env bash
# Commit y push de los archivos que genera el monitor, resistente a que otra corrida haya empujado entre medio.
#
# El 20-sep-2026 una corrida lenta terminó junto con la siguiente: las dos habían hecho checkout del mismo commit,
# el "git pull --rebase" chocó (CONFLICT en data.json, historial.jsonl y descubiertas.json) y la corrida murió sin
# publicar. Aquí el conflicto se resuelve solo, con un criterio por archivo:
#   * data.json, alertas.json, descubiertas.json: son una foto completa; gana la recién generada.
#   * historial.jsonl: es un registro que solo crece; se conservan las líneas de ambas, sin repetir.
set -euo pipefail
cd "$(dirname "$0")/.."
ARCHIVOS=(data.json historial.jsonl alertas.json descubiertas.json)
RAMA="${1:-main}"

for intento in 1 2 3; do
  git add -- "${ARCHIVOS[@]}"
  if git diff --cached --quiet; then echo "sin cambios que publicar"; exit 0; fi
  git commit -q -m "monitor: $(date -u +'%Y-%m-%d %H:%M UTC')"
  if git push -q origin "HEAD:$RAMA" 2>/dev/null; then echo "publicado (intento $intento)"; exit 0; fi

  echo "el remoto avanzó; rehaciendo el commit sobre origin/$RAMA (intento $intento)"
  tmp=$(mktemp -d)
  for f in "${ARCHIVOS[@]}"; do [ -e "$f" ] && cp "$f" "$tmp/$(basename "$f")"; done
  git fetch -q origin "$RAMA"
  git reset -q --hard "origin/$RAMA"
  for f in "${ARCHIVOS[@]}"; do [ -e "$tmp/$(basename "$f")" ] && cp "$tmp/$(basename "$f")" "$f"; done
  # historial.jsonl: unir lo que traía el remoto con lo nuestro, en orden y sin repetir
  if [ -e "$tmp/historial.jsonl" ]; then
    git show "origin/$RAMA:historial.jsonl" > "$tmp/remoto.jsonl" 2>/dev/null || : > "$tmp/remoto.jsonl"
    awk 'NR==FNR{visto[$0]=1; print; next} !($0 in visto)' "$tmp/remoto.jsonl" "$tmp/historial.jsonl" > historial.jsonl
  fi
  rm -rf "$tmp"
done

echo "no se pudo publicar tras 3 intentos" >&2
exit 1
