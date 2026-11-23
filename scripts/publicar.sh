#!/usr/bin/env bash
# Commit y push de los archivos que genera el monitor, resistente a que otra corrida haya empujado entre medio.
#
# El 20-sep-2026 una corrida lenta terminó junto con la siguiente: las dos habían hecho checkout del mismo commit,
# el "git pull --rebase" chocó (CONFLICT en data.json, historial.jsonl y descubiertas.json) y la corrida murió sin
# publicar. Aquí el conflicto se resuelve solo, con un criterio por archivo:
#   * data.json, alertas.json, descubiertas.json: son una foto completa; gana la recién generada.
#   * historial.jsonl: es un registro que solo crece; se conservan las líneas de ambas, sin repetir, y después se
#     vuelve a archivar lo antiguo (monitor.py --rotar-historial), sin repetir lo que el remoto ya archivó.
#   * historial/AAAA-MM.jsonl.gz: solo crecen; se parte de los del remoto.
#
# Del 21 al 23-nov-2026 el push falló en cada corrida porque historial.jsonl pasó los 100 MiB que acepta GitHub,
# pero el error de git se tiraba a /dev/null y el script decía "el remoto avanzó" tres veces. Ahora:
#   * antes del commit se revisa que ningún archivo pase de LIMITE_BYTES (mensaje claro, sin intentar el push);
#   * el mensaje de git se muestra siempre que el push falla;
#   * solo se rehace el commit sobre origin cuando git dice que el remoto avanzó; si GitHub rechazó el contenido,
#     reintentar no sirve y se sale con error; cualquier otra falla (red) se reintenta con el mismo commit.
set -euo pipefail
cd "$(dirname "$0")/.."
ARCHIVOS=(data.json historial.jsonl historial alertas.json descubiertas.json)
RAMA="${1:-main}"
LIMITE_BYTES=$((95 * 1024 * 1024))   # GitHub rechaza archivos de más de 100 MiB (y advierte desde 50 MB)
# El remoto avanzó (otra corrida o un PR): "! [rejected] HEAD -> main (fetch first|non-fast-forward)", o dos pushes
# casi simultáneos: "cannot lock ref ... but expected ...".
CARRERA='\[rejected\].*\((fetch first|non-fast-forward)\)|cannot lock ref|incorrect old value'
# GitHub rechazó el contenido: archivo de más de 100 MiB (GH001), hook, protección de rama.
RECHAZO='remote rejected|pre-receive hook declined|GH001|GH006|GH013|file size limit|Large files detected|protected branch'

for intento in 1 2 3; do
  presentes=(); for f in "${ARCHIVOS[@]}"; do [ -e "$f" ] && presentes+=("$f"); done
  git add -A -- "${presentes[@]}"
  if git diff --cached --quiet; then echo "sin cambios que publicar"; exit 0; fi
  while IFS= read -r -d '' f; do
    [ -f "$f" ] || continue
    bytes=$(wc -c < "$f")
    if [ "$bytes" -gt "$LIMITE_BYTES" ]; then
      echo "ERROR: $f pesa $bytes bytes y GitHub rechaza archivos de más de 100 MiB; no se publica." >&2
      echo "       Revisar la rotación del historial (monitor.py: rotar_historial, HISTORIAL_DIAS, HISTORIAL_MAX_BYTES)." >&2
      exit 1
    fi
  done < <(git diff --cached --name-only -z)
  git commit -q -m "monitor: $(date -u +'%Y-%m-%d %H:%M UTC')"
  if salida=$(git push origin "HEAD:$RAMA" 2>&1); then echo "publicado (intento $intento)"; exit 0; fi

  echo "git push falló (intento $intento). Respuesta de git:" >&2
  printf '%s\n' "$salida" | sed 's/^/    /' >&2
  if [[ $salida =~ $CARRERA ]]; then
    echo "el remoto avanzó; rehaciendo el commit sobre origin/$RAMA (intento $intento)"
    tmp=$(mktemp -d)
    for f in data.json historial.jsonl alertas.json descubiertas.json; do [ -e "$f" ] && cp "$f" "$tmp/$f"; done
    git fetch -q origin "$RAMA"
    git reset -q --hard "origin/$RAMA"
    for f in data.json alertas.json descubiertas.json; do [ -e "$tmp/$f" ] && cp "$tmp/$f" "$f"; done
    # historial.jsonl: unir lo que traía el remoto con lo nuestro, en orden y sin repetir, y volver a archivar
    if [ -e "$tmp/historial.jsonl" ]; then
      git show "origin/$RAMA:historial.jsonl" > "$tmp/remoto.jsonl" 2>/dev/null || : > "$tmp/remoto.jsonl"
      awk 'NR==FNR{visto[$0]=1; print; next} !($0 in visto)' "$tmp/remoto.jsonl" "$tmp/historial.jsonl" > historial.jsonl
      python3 monitor.py --rotar-historial
    fi
    rm -rf "$tmp"
  elif [[ $salida =~ $RECHAZO ]]; then
    echo "GitHub rechazó el contenido del commit (ver arriba): reintentar no sirve." >&2
    exit 1
  else
    git reset -q --soft HEAD~1   # el próximo intento vuelve a hacer el mismo commit
    if [ "$intento" -lt 3 ]; then
      echo "no es una carrera con otra corrida; se reintenta en 20 s (posible falla de red)" >&2
      sleep 20
    fi
  fi
done

echo "no se pudo publicar tras 3 intentos" >&2
exit 1
