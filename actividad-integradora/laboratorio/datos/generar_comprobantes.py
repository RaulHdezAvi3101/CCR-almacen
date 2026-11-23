#!/usr/bin/env python3
"""Crea los archivos de comprobante en disco, uno por fila de la base.

El sitio de CCR guarda los comprobantes con el nombre que viene en la tabla.
Este programa los dibuja como PDF de una pagina para que la descarga entregue
algo que se pueda abrir.

  python3 generar_comprobantes.py
"""

import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUTA_DB = BASE / "ccr.db"
CARPETA = BASE / "comprobantes"

PLANTILLA = """%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]
  /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >>
  /Contents 4 0 R >> endobj
4 0 obj << /Length LARGO >>
stream
BT
/F2 16 Tf 60 780 Td (Almacenes CCR, S.A. de C.V.) Tj
/F1 10 Tf 60 760 Td (Avenida Morelos Sur 214, col. Centro, Cuernavaca, Morelos) Tj
/F2 13 Tf 60 720 Td (Comprobante de pago de renta) Tj
/F1 11 Tf
60 690 Td (Folio:) Tj 130 690 Td (FOLIO) Tj
60 672 Td (Periodo:) Tj 130 672 Td (PERIODO) Tj
60 654 Td (Sucursal:) Tj 130 654 Td (SUCURSAL) Tj
60 636 Td (Bodega:) Tj 130 636 Td (BODEGA) Tj
60 618 Td (Cliente:) Tj 130 618 Td (CLIENTE) Tj
60 600 Td (Contrato:) Tj 130 600 Td (CONTRATO) Tj
60 570 Td (Monto pagado:) Tj 130 570 Td ($MONTO.00 M.N.) Tj
60 552 Td (Fecha de pago:) Tj 130 552 Td (SUBIDO) Tj
60 510 Td (Este comprobante ampara el pago de la renta del periodo indicado.) Tj
60 496 Td (Conservelo como comprobante fiscal. No es un CFDI.) Tj
ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
6 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> endobj
trailer << /Root 1 0 R >>
%%%%EOF
"""


def limpiar(texto):
    """Quita acentos y parentesis, que rompen el texto de un PDF sencillo."""
    reemplazos = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
                  "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "ñ": "n", "Ñ": "N"}
    for viejo, nuevo in reemplazos.items():
        texto = str(texto).replace(viejo, nuevo)
    return texto.replace("(", "[").replace(")", "]")


def main():
    CARPETA.mkdir(exist_ok=True)
    con = sqlite3.connect(RUTA_DB)
    con.row_factory = sqlite3.Row

    filas = con.execute(
        "SELECT cp.id, cp.periodo, cp.monto, cp.archivo, cp.subido,"
        "       ct.id AS contrato, s.nombre AS sucursal, b.numero AS bodega,"
        "       cl.nombre AS cliente"
        "  FROM comprobantes cp"
        "  JOIN contratos ct ON ct.id = cp.contrato_id"
        "  JOIN bodegas b ON b.id = ct.bodega_id"
        "  JOIN sucursales s ON s.id = b.sucursal_id"
        "  JOIN clientes cl ON cl.id = ct.cliente_id"
        "  ORDER BY cp.id"
    ).fetchall()

    creados = 0
    for fila in filas:
        cuerpo = PLANTILLA
        valores = {
            "FOLIO": f"CCR-{fila['id']:05d}",
            "PERIODO": limpiar(fila["periodo"]),
            "SUCURSAL": limpiar(fila["sucursal"]),
            "BODEGA": limpiar(fila["bodega"]),
            "CLIENTE": limpiar(fila["cliente"])[:52],
            "CONTRATO": str(fila["contrato"]),
            "MONTO": f"{fila['monto']:,}",
            "SUBIDO": limpiar(fila["subido"]),
        }
        for marca, valor in valores.items():
            cuerpo = cuerpo.replace(marca, valor)

        # El largo declarado debe coincidir con el flujo real.
        inicio = cuerpo.index("stream\n") + len("stream\n")
        fin = cuerpo.index("\nendstream")
        largo = len(cuerpo[inicio:fin].encode("latin-1"))
        cuerpo = cuerpo.replace("/Length LARGO", f"/Length {largo}")

        destino = CARPETA / fila["archivo"]
        destino.write_bytes(cuerpo.encode("latin-1", errors="replace"))
        creados += 1

    con.close()
    print(f"Comprobantes creados: {creados}")
    print(f"Carpeta: {CARPETA}")


if __name__ == "__main__":
    main()
