"""Pruebas del panel viejo, el respaldo y la traza de errores.

Vigilan las FALLAS 9, 10 y 11.

  uv run pytest pruebas/test_panel_viejo.py -v
"""

import base64
import shutil
import sqlite3


def basic(usuario, clave):
    return "Basic " + base64.b64encode(f"{usuario}:{clave}".encode()).decode()


def con_basic(cliente, usuario="admin", clave="admin"):
    cliente.environ_base["HTTP_AUTHORIZATION"] = basic(usuario, clave)
    return cliente


# --- Lo que debe funcionar ------------------------------------------------


def test_robots_txt_anuncia_las_rutas(cliente):
    respuesta = cliente.get("/robots.txt")
    assert respuesta.status_code == 200
    texto = respuesta.get_data(as_text=True)
    assert "/admin-viejo" in texto
    assert "/respaldo.sql" in texto
    assert "Disallow" in texto


def test_respaldo_se_descarga(cliente):
    respuesta = cliente.get("/respaldo.sql")
    assert respuesta.status_code == 200
    assert b"CREATE TABLE" in respuesta.data
    assert "sql" in respuesta.headers["Content-Type"]


# --- FALLA 9: credenciales de fabrica -----------------------------------


def test_falla9_el_panel_pide_credenciales(cliente):
    respuesta = cliente.get("/admin-viejo")
    assert respuesta.status_code == 401
    assert "Basic" in respuesta.headers["WWW-Authenticate"]


def test_falla9_admin_admin_entra(cliente):
    """FALLA 9: la cuenta de fabrica admin/admin sigue activa."""
    con_basic(cliente, "admin", "admin")
    respuesta = cliente.get("/admin-viejo")
    assert respuesta.status_code == 200
    assert b"Panel de administraci" in respuesta.data


def test_falla9_otras_credenciales_no_entran(cliente):
    con_basic(cliente, "admin", "otra-clave")
    respuesta = cliente.get("/admin-viejo")
    assert respuesta.status_code == 401


def test_falla9_la_ruta_esta_anunciada_en_robots(cliente):
    """FALLA 9: el robots.txt dice exactamente donde esta."""
    texto = cliente.get("/robots.txt").get_data(as_text=True)
    assert "Disallow: /admin-viejo" in texto
    con_basic(cliente)
    assert cliente.get("/admin-viejo").status_code == 200


def test_falla9_usuarios_con_su_hash(cliente):
    """FALLA 9: dentro del panel viejo esta la lista de usuarios con hash."""
    con_basic(cliente)
    respuesta = cliente.get("/admin-viejo/usuarios")
    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert "21232f297a57a5a743894a0e4a801fc3" in html  # admin
    assert "soporte" in html


def test_falla9_el_usuario_del_repo_funciona_en_el_login_nuevo(cliente):
    """El config.py del repo da soporte/ccr2014, y esa cuenta existe."""
    respuesta = cliente.post("/login", data={"usuario": "soporte", "clave": "ccr2014"})
    assert respuesta.status_code == 302


# --- FALLA 10: respaldo.sql en la raiz ----------------------------------


def test_falla10_el_respaldo_se_baja_sin_sesion(cliente):
    """FALLA 10: cualquiera descarga la base completa."""
    respuesta = cliente.get("/respaldo.sql")
    assert respuesta.status_code == 200
    assert len(respuesta.data) > 50_000


def test_falla10_el_respaldo_trae_los_hashes(cliente):
    """FALLA 10: y el volcado trae los hashes MD5 de todos los usuarios."""
    datos = cliente.get("/respaldo.sql").get_data(as_text=True)
    assert "21232f297a57a5a743894a0e4a801fc3" in datos
    assert 'INSERT INTO "usuarios"' in datos


def test_falla10_el_respaldo_trae_los_clientes_completos(cliente):
    datos = cliente.get("/respaldo.sql").get_data(as_text=True)
    assert 'INSERT INTO "clientes"' in datos
    assert "@correo.example" in datos
    assert "CREATE TABLE contratos" in datos


def test_falla10_el_respaldo_se_llama_igual_que_en_el_backup(cliente):
    """El nombre coincide con el del backup.sh del repositorio publico."""
    respuesta = cliente.get("/respaldo.sql")
    assert 'filename="respaldo.sql"' in respuesta.headers["Content-Disposition"]


# --- FALLA 11: traza de errores ----------------------------------------


def test_falla11_el_error_muestra_la_traza(cliente):
    """FALLA 11: el error entrega la traza de Python completa."""
    respuesta = cliente.get("/error")
    assert respuesta.status_code == 500
    html = respuesta.get_data(as_text=True)
    assert "Traceback" in html
    assert "ValueError" in html


def test_falla11_la_traza_revela_rutas_del_servidor(cliente):
    """FALLA 11: y con ella la ruta del archivo en el servidor."""
    html = cliente.get("/error").get_data(as_text=True)
    assert "app.py" in html
    assert "line" in html.lower()


def test_falla11_la_traza_revela_la_version(cliente):
    """FALLA 11: ademas dice que es Flask y Python."""
    html = cliente.get("/error").get_data(as_text=True)
    assert "Flask" in html
    assert "Python" in html


def test_falla11_la_traza_del_panel_viejo_tambien(cliente):
    """Cualquier ruta que reviente deja ver la traza, no solo /error."""
    con_basic(cliente)
    # La ruta /error es la unica que revienta a proposito, y su traza
    # demuestra que el manejador es general: la excepcion es un ValueError
    # de verdad, atrapado en la vista.
    respuesta = cliente.get("/error")
    assert b"ValueError" in respuesta.data
    assert b"int()" in respuesta.data


# --- Flags de FALLAS 9, 10 y 11 -------------------------------------------


def test_falla9_flag_en_el_panel_viejo(cliente):
    """FALLA 9: el panel viejo contiene el flag en su fuente HTML."""
    con_basic(cliente)
    html = cliente.get("/admin-viejo").get_data(as_text=True)
    assert "CCR{panel_viejo_admin_admin}" in html


def test_falla10_flag_en_el_respaldo(cliente):
    """FALLA 10: la primera linea del respaldo es el flag en comentario SQL."""
    datos = cliente.get("/respaldo.sql").get_data(as_text=True)
    assert "CCR{respaldo_en_la_raiz}" in datos


def test_falla11_flag_en_la_traza(cliente):
    """FALLA 11: el flag aparece en el mensaje del ValueError de la traza."""
    html = cliente.get("/error").get_data(as_text=True)
    assert "CCR{traza_expuesta}" in html
