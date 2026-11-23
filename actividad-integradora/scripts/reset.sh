#!/usr/bin/env bash
# Restaura los tres grupos al estado limpio y reinicia los contenedores.
# Correr antes de cada sesión de laboratorio.
# Uso: bash scripts/reset.sh
set -euo pipefail

GRUPOS=3
ORIG="./laboratorio/datos"

if [ ! -f "$ORIG/ccr.db" ]; then
  echo "ERROR: laboratorio/datos/ccr.db no existe."
  echo "Primero corre: python3 laboratorio/datos/generar_datos.py"
  exit 1
fi
if [ ! -d "$ORIG/comprobantes" ] || [ -z "$(ls -A "$ORIG/comprobantes" 2>/dev/null)" ]; then
  echo "ERROR: laboratorio/datos/comprobantes/ no existe o está vacío."
  echo "Primero corre: python3 laboratorio/datos/generar_comprobantes.py"
  exit 1
fi

echo "Reseteando $GRUPOS grupos..."
for i in $(seq 1 "$GRUPOS"); do
  DIR="./datos/grupo$i"
  cp "$ORIG/ccr.db"        "$DIR/ccr.db"
  cp "$ORIG/respaldo.sql"  "$DIR/respaldo.sql"
  rm -rf "$DIR/comprobantes/"* "$DIR/subidos/"* 2>/dev/null || true
  cp -r "$ORIG/comprobantes/." "$DIR/comprobantes/"
  echo "  grupo$i reseteado"
done

docker compose restart
echo "Listo. Todos los grupos en estado inicial."
