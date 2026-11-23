"""Preparacion comun de las pruebas.

Cada prueba corre contra una copia de ccr.db, una bitacora propia y carpetas
de archivos temporales. Asi las pruebas no ensucian nada de lo que usan los
alumnos.
"""

import base64
import json
import shutil

import pytest

import app as modulo_app
import bitacora


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    copia = tmp_path / "ccr.db"
    shutil.copy(modulo_app.RUTA_BASE, copia)

    comprobantes = tmp_path / "comprobantes"
    if modulo_app.CARPETA_COMPROBANTES.exists():
        shutil.copytree(modulo_app.CARPETA_COMPROBANTES, comprobantes)
    else:
        comprobantes.mkdir()
    subidos = tmp_path / "subidos"
    subidos.mkdir()

    modulo_app.app.config.update(
        BASE_DATOS=str(copia),
        CARPETA_COMPROBANTES=str(comprobantes),
        CARPETA_SUBIDOS=str(subidos),
        CARPETA_PUBLICO=str(modulo_app.CARPETA_PUBLICO),
        RUTA_BITACORA=str(tmp_path / "bitacora.db"),
        TESTING=True,
    )
    monkeypatch.setattr(modulo_app, "CARPETA_COMPROBANTES", comprobantes)
    monkeypatch.setattr(modulo_app, "CARPETA_SUBIDOS", subidos)
    monkeypatch.setattr(bitacora, "RUTA_BITACORA", tmp_path / "bitacora.db")

    with modulo_app.app.test_client() as c:
        yield c


@pytest.fixture()
def ruta_bitacora(tmp_path, monkeypatch):
    ruta = tmp_path / "bitacora.db"
    monkeypatch.setattr(bitacora, "RUTA_BITACORA", ruta)
    return ruta


@pytest.fixture()
def carpeta_subidos(tmp_path):
    return tmp_path / "subidos"


def cookie_de(usuario="cliente", rol="cliente", sucursal=None):
    """Arma una cookie como la que acepta el sitio: base64 sin firma."""
    datos = {"usuario": usuario, "nombre": usuario, "rol": rol, "sucursal": sucursal}
    crudo = json.dumps(datos).encode("utf-8")
    return base64.urlsafe_b64encode(crudo).decode("ascii").rstrip("=")


COOKIE_ADMIN = cookie_de(usuario="soporte", rol="admin")


def poner_admin(cliente):
    """Deja al cliente de pruebas con una sesion de administrador."""
    cliente.set_cookie("ccr_sesion", cookie_de(usuario="soporte", rol="admin"))
    return cliente


def poner_cliente(cliente):
    """Sesion de un cliente real de la base, para ver sus comprobantes."""
    import sqlite3

    con = sqlite3.connect(cliente.application.config["BASE_DATOS"])
    con.row_factory = sqlite3.Row
    fila = con.execute(
        "SELECT u.usuario, u.correo FROM usuarios u"
        " JOIN clientes c ON c.correo = u.correo"
        " JOIN contratos ct ON ct.cliente_id = c.id AND ct.estado = 'vigente'"
        " LIMIT 1"
    ).fetchone()
    con.close()
    cliente.set_cookie("ccr_sesion", cookie_de(usuario=fila["usuario"], rol="cliente"))
    return fila
