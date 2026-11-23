"""Pruebas del catalogo de bodegas.

Comprueban que la pagina funciona y que la FALLA 1 sigue sembrada: el JSON
entrega los datos del cliente de las bodegas ocupadas.

  uv run pytest pruebas/test_bodegas.py -v
"""

import json


def test_catalogo_responde(cliente):
    respuesta = cliente.get("/bodegas")
    assert respuesta.status_code == 200
    assert b"Cat" in respuesta.data


def test_catalogo_tiene_las_tres_sucursales(cliente):
    respuesta = cliente.get("/bodegas")
    for sucursal in (b"Centro", b"Industrial", b"Norte"):
        assert sucursal in respuesta.data


def test_api_devuelve_las_sesenta_bodegas(cliente):
    respuesta = cliente.get("/api/bodegas")
    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert len(datos["bodegas"]) == 60


def test_api_filtra_por_sucursal(cliente):
    todos = cliente.get("/api/bodegas").get_json()["bodegas"]
    centro = cliente.get("/api/bodegas?sucursal=1").get_json()["bodegas"]
    assert len(centro) == 24
    assert all(b["sucursal"] == "Centro" for b in centro)
    assert len(centro) < len(todos)


def test_api_trae_los_tres_estados(cliente):
    datos = cliente.get("/api/bodegas").get_json()["bodegas"]
    estados = {b["estado"] for b in datos}
    assert estados == {"libre", "ocupada", "mantenimiento"}


# --- FALLA 1 -------------------------------------------------------------


def test_falla1_el_json_trae_los_datos_del_cliente(cliente):
    """FALLA 1: el JSON entrega nombre, correo, telefono y RFC del cliente."""
    datos = cliente.get("/api/bodegas").get_json()["bodegas"]
    ocupadas = [b for b in datos if b["estado"] == "ocupada"]
    assert len(ocupadas) == 48

    con_cliente = [b for b in ocupadas if b.get("cliente")]
    assert len(con_cliente) == 48, "las 48 ocupadas deben traer el bloque cliente"

    muestra = con_cliente[0]["cliente"]
    assert muestra["nombre"]
    assert "@" in muestra["correo"]
    assert muestra["telefono"]
    assert len(muestra["rfc"]) >= 10


def test_falla1_el_json_trae_el_contrato(cliente):
    """FALLA 1: y tambien el numero de contrato y la mensualidad."""
    datos = cliente.get("/api/bodegas").get_json()["bodegas"]
    ocupadas = [b for b in datos if b["estado"] == "ocupada"]
    for bodega in ocupadas:
        assert bodega["contrato"]["id"]
        assert bodega["contrato"]["inicio"]
        assert bodega["contrato"]["mensualidad"] > 0


def test_falla1_no_hace_falta_sesion(cliente):
    """FALLA 1: el JSON se entrega sin sesion, a cualquiera que pida la ruta."""
    respuesta = cliente.get("/api/bodegas")
    assert respuesta.status_code == 200
    assert "@" in respuesta.get_data(as_text=True)


def test_falla1_la_pagina_no_muestra_los_datos_en_el_html(cliente):
    """El HTML de la pagina no trae los datos: vienen del JSON. Eso es lo que
    hace que haya que abrir la pestana de red o el visor de codigo."""
    html = cliente.get("/bodegas").get_data(as_text=True)
    assert "@correo.example" not in html
    assert "api/bodegas" in html


def test_las_libres_no_traen_cliente(cliente):
    datos = cliente.get("/api/bodegas").get_json()["bodegas"]
    libres = [b for b in datos if b["estado"] == "libre"]
    assert libres
    for bodega in libres:
        assert "cliente" not in bodega


def test_el_json_es_valido_y_completo(cliente):
    respuesta = cliente.get("/api/bodegas")
    texto = respuesta.get_data(as_text=True)
    datos = json.loads(texto)
    assert "bodegas" in datos
    for bodega in datos["bodegas"]:
        for campo in ("id", "numero", "metros", "precio", "estado", "sucursal"):
            assert campo in bodega


# --- Flag de FALLA 1 -------------------------------------------------------


def test_falla1_flag_en_el_json(cliente):
    """FALLA 1: el JSON contiene el flag en el campo _debug."""
    datos = cliente.get("/api/bodegas").get_json()
    assert datos.get("_debug") == "CCR{api_sin_autenticar}"
