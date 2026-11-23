#!/usr/bin/env bash
# Inicializa los datos de cada grupo copiando la DB original.
# Correr una sola vez antes del primer `docker compose up -d`.
# Uso: bash scripts/init.sh
set -euo pipefail

GRUPOS=3
ORIG="./laboratorio/datos"

# La DB y los comprobantes no van en git — se generan en el servidor.
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

echo "Inicializando $GRUPOS grupos..."
for i in $(seq 1 "$GRUPOS"); do
  DIR="./datos/grupo$i"
  mkdir -p "$DIR/comprobantes" "$DIR/subidos"
  cp "$ORIG/ccr.db"        "$DIR/ccr.db"
  cp "$ORIG/respaldo.sql"  "$DIR/respaldo.sql"
  cp -r "$ORIG/comprobantes/." "$DIR/comprobantes/"
  echo "  grupo$i listo"
done
echo "Hecho. Ahora corre: docker compose up -d"
