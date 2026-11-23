"""Bitacora de accesos del sitio CCR.

Guarda dos cosas: un renglon por cada intento de entrar, salga bien o mal, y
un renglon por cada peticion que recibe el sitio. Lo usa el login, la subida de
archivos y la pagina /registros.

Base aparte de ccr.db para que se pueda leer sin abrir la base de clientes.

  from bitacora import registrar, registrar_acceso, ultimos
"""

import sqlite3
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUTA_BITACORA = BASE / "bitacora.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS intentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    momento TEXT NOT NULL,
    usuario TEXT NOT NULL,
    resultado TEXT NOT NULL,
    ip TEXT,
    agente TEXT
);

CREATE TABLE IF NOT EXISTS accesos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    momento TEXT NOT NULL,
    ip TEXT,
    metodo TEXT,
    ruta TEXT,
    codigo INTEGER,
    agente TEXT,
    referente TEXT
);
"""


def conectar(ruta=None):
    con = sqlite3.connect(str(ruta or RUTA_BITACORA))
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def registrar(usuario, resultado, ip=None, agente=None, ruta=None):
    """Anota un intento. El resultado es 'ok', 'clave-mala' o 'no-existe'."""
    con = conectar(ruta)
    try:
        con.execute(
            "INSERT INTO intentos (momento, usuario, resultado, ip, agente) VALUES (?, ?, ?, ?, ?)",
            (ahora(), usuario, resultado, ip, agente),
        )
        con.commit()
    finally:
        con.close()


def registrar_acceso(ip, metodo, ruta, agente=None, referente=None, codigo=None, base=None):
    """Anota una peticion al sitio. Es el registro de trafico."""
    con = conectar(base)
    try:
        con.execute(
            "INSERT INTO accesos (momento, ip, metodo, ruta, codigo, agente, referente)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ahora(), ip, metodo, ruta, codigo, agente, referente),
        )
        con.commit()
    finally:
        con.close()


def ultimos(cuantos=200, ruta=None):
    con = conectar(ruta)
    try:
        return con.execute(
            "SELECT momento, usuario, resultado, ip, agente FROM intentos ORDER BY id DESC LIMIT ?",
            (cuantos,),
        ).fetchall()
    finally:
        con.close()


def ultimos_accesos(cuantos=300, base=None):
    con = conectar(base)
    try:
        return con.execute(
            "SELECT momento, ip, metodo, ruta, codigo, agente, referente"
            " FROM accesos ORDER BY id DESC LIMIT ?",
            (cuantos,),
        ).fetchall()
    finally:
        con.close()


def contar(usuario, ruta=None):
    """Cuantos intentos lleva un usuario. Existe para que se vea que nadie la usa."""
    con = conectar(ruta)
    try:
        fila = con.execute(
            "SELECT COUNT(*) FROM intentos WHERE usuario = ?", (usuario,)
        ).fetchone()
        return fila[0]
    finally:
        con.close()
