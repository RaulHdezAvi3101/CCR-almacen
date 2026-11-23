"""Pruebas de comprobantes: descarga por numero, subida y archivos.

Vigilan las FALLAS 6, 7 y 8.

  uv run pytest pruebas/test_comprobantes.py -v
"""

import io
import sqlite3

from conftest import cookie_de, poner_admin, poner_cliente


# --- Lo que debe funcionar ------------------------------------------------


def test_lista_pide_sesion(cliente):
    respuesta = cliente.get("/comprobantes")
    assert respuesta.status_code == 302


def test_lista_muestra_los_comprobantes_del_cliente(cliente):
    poner_cliente(cliente)
    respuesta = cliente.get("/comprobantes")
    assert respuesta.status_code == 200
    assert b"Comprobantes de pago" in respuesta.data


def test_descarga_un_pdf_valido(cliente):
    respuesta = cliente.get("/comprobante/1")
    assert respuesta.status_code == 200
    assert respuesta.data.startswith(b"%PDF")
    assert "application/pdf" in respuesta.headers["Content-Type"]


def test_comprobante_inexistente_da_404(cliente):
    respuesta = cliente.get("/comprobante/99999")
    assert respuesta.status_code == 404


def test_panel_comprobantes_pide_sesion(cliente):
    respuesta = cliente.get("/panel/comprobantes")
    assert respuesta.status_code == 302


def test_panel_comprobantes_entra_con_admin(cliente):
    poner_admin(cliente)
    respuesta = cliente.get("/panel/comprobantes")
    assert respuesta.status_code == 200
    assert b"Comprobantes recibidos" in respuesta.data


# --- FALLA 6: descarga por numero consecutivo ----------------------------


def test_falla6_se_descarga_sin_sesion(cliente):
    """FALLA 6: el comprobante se entrega a cualquiera, sin sesion."""
    respuesta = cliente.get("/comprobante/1")
    assert respuesta.status_code == 200
    assert respuesta.data.startswith(b"%PDF")


def test_falla6_cualquier_comprobante_es_accesible(cliente):
    """FALLA 6: no se comprueba de quien es el comprobante."""
    for numero in (1, 100, 300, 574):
        respuesta = cliente.get(f"/comprobante/{numero}")
        assert respuesta.status_code == 200
        assert respuesta.data.startswith(b"%PDF")


def test_falla6_los_numeros_son_consecutivos(cliente):
    """FALLA 6: con un ciclo se recorren todos."""
    encontrados = 0
    for numero in range(1, 21):
        if cliente.get(f"/comprobante/{numero}").status_code == 200:
            encontrados += 1
    assert encontrados == 20


def test_falla6_el_pdf_trae_los_datos_del_cliente(cliente):
    """FALLA 6: y el archivo trae el nombre del cliente que lo pago."""
    respuesta = cliente.get("/comprobante/1")
    assert b"Comprobante de pago" in respuesta.data


# --- FALLA 7: nombre y tipo del archivo --------------------------------


def test_falla7_el_nombre_lo_pone_el_cliente(cliente, carpeta_subidos):
    """FALLA 7: el archivo se guarda con el nombre que manda el cliente."""
    poner_cliente(cliente)
    respuesta = cliente.post(
        "/subir",
        data={"comprobante": (io.BytesIO(b"%PDF-1.4 falso"), "mi-nombre-raro.pdf")},
        content_type="multipart/form-data",
    )
    assert b"Archivo guardado" in respuesta.data
    assert (carpeta_subidos / "mi-nombre-raro.pdf").exists()


def test_falla7_acepta_html_y_lo_sirve_como_pagina(cliente, carpeta_subidos):
    """FALLA 7: se puede subir un .html y el sitio lo sirve como pagina."""
    poner_cliente(cliente)
    html = b"<html><body><h1>pagina del atacante</h1><script>alert(1)</script></body></html>"
    respuesta = cliente.post(
        "/subir",
        data={"comprobante": (io.BytesIO(html), "nota.html")},
        content_type="multipart/form-data",
    )
    assert b"Archivo guardado" in respuesta.data

    servido = cliente.get("/archivo/nota.html")
    assert servido.status_code == 200
    assert b"pagina del atacante" in servido.data
    # Se entrega como HTML: el navegador lo ejecuta dentro del sitio.
    assert "text/html" in servido.headers.get("Content-Type", "") or "text/html" in servido.mimetype


def test_falla7_se_puede_pisar_un_archivo_existente(cliente, carpeta_subidos):
    """FALLA 7: dos clientes con el mismo nombre se pisan el archivo."""
    poner_cliente(cliente)
    for contenido in (b"primero", b"segundo"):
        cliente.post(
            "/subir",
            data={"comprobante": (io.BytesIO(contenido), "mismo-nombre.pdf")},
            content_type="multipart/form-data",
        )
    assert (carpeta_subidos / "mismo-nombre.pdf").read_bytes() == b"segundo"


def test_falla7_se_puede_subir_con_ruta_relativa(cliente, carpeta_subidos):
    """FALLA 7: el nombre se usa tal cual, sin limpiar la ruta."""
    poner_cliente(cliente)
    respuesta = cliente.post(
        "/subir",
        data={"comprobante": (io.BytesIO(b"contenido"), "subcarpeta/archivo.pdf")},
        content_type="multipart/form-data",
    )
    assert b"Archivo guardado" in respuesta.data
    # La carpeta la crea el propio sitio a partir del nombre que mando el cliente.
    assert (carpeta_subidos / "subcarpeta" / "archivo.pdf").exists()


def test_falla7_el_nombre_permite_salir_de_la_carpeta(cliente, carpeta_subidos):
    """FALLA 7: un nombre con ../ escribe fuera de la carpeta de subidos.

    Es la version mas grave de la misma falla: no se limpia el nombre.
    """
    poner_cliente(cliente)
    respuesta = cliente.post(
        "/subir",
        data={"comprobante": (io.BytesIO(b"fuera"), "../escapado.txt")},
        content_type="multipart/form-data",
    )
    assert b"Archivo guardado" in respuesta.data
    fuera = carpeta_subidos.parent / "escapado.txt"
    assert fuera.exists(), "el archivo deberia haber quedado fuera de la carpeta"


# --- FALLA 8: tope sin cuota -------------------------------------------


def test_falla8_acepta_archivos_de_varios_megas(cliente, carpeta_subidos):
    """FALLA 8: 5 MB entran sin problema."""
    poner_cliente(cliente)
    grande = io.BytesIO(b"x" * (5 * 1024 * 1024))
    respuesta = cliente.post(
        "/subir",
        data={"comprobante": (grande, "grande.pdf")},
        content_type="multipart/form-data",
    )
    assert b"Archivo guardado" in respuesta.data
    assert (carpeta_subidos / "grande.pdf").stat().st_size == 5 * 1024 * 1024


def test_falla8_no_hay_cuota_ni_limite_de_cantidad(cliente, carpeta_subidos):
    """FALLA 8: el mismo cliente puede subir veinte archivos sin que nada lo frene."""
    poner_cliente(cliente)
    for numero in range(20):
        respuesta = cliente.post(
            "/subir",
            data={"comprobante": (io.BytesIO(b"x" * 1000), f"archivo-{numero}.pdf")},
            content_type="multipart/form-data",
        )
        assert b"Archivo guardado" in respuesta.data
    assert len(list(carpeta_subidos.iterdir())) == 20


def test_falla8_el_tope_es_de_veinte_megas(cliente):
    """FALLA 8: el tope existe, pero es de 20 MB."""
    import app as modulo_app

    assert modulo_app.app.config["MAX_CONTENT_LENGTH"] == 20 * 1024 * 1024


def test_la_tabla_de_subidas_registra_al_usuario(cliente):
    poner_admin(cliente)
    cliente.post(
        "/subir",
        data={"comprobante": (io.BytesIO(b"datos"), "con-registro.pdf")},
        content_type="multipart/form-data",
    )
    con = sqlite3.connect(cliente.application.config["BASE_DATOS"])
    fila = con.execute(
        "SELECT usuario, archivo, tamano FROM subidas WHERE archivo = 'con-registro.pdf'"
    ).fetchone()
    con.close()
    assert fila is not None
    assert fila[0] == "soporte"
    assert fila[1] == "con-registro.pdf"
