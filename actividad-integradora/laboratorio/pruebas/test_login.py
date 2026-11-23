"""Pruebas del login de CCR.

La mitad de estas pruebas comprueba que el login funciona. La otra mitad
comprueba que las fallas sembradas siguen ahi. Si alguien "arregla" una falla
sin querer, la prueba falla y avisa.

  uv run pytest pruebas/test_login.py -v
"""

import base64
import json

import bitacora


def cookie_de(usuario="cliente", rol="cliente", sucursal=None):
    datos = {"usuario": usuario, "nombre": usuario, "rol": rol, "sucursal": sucursal}
    crudo = json.dumps(datos).encode("utf-8")
    return base64.urlsafe_b64encode(crudo).decode("ascii").rstrip("=")


# --- Lo que debe funcionar ------------------------------------------------


def test_portada_responde(cliente):
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert b"CCR" in respuesta.data


def test_formulario_de_login(cliente):
    respuesta = cliente.get("/login")
    assert respuesta.status_code == 200
    assert b"Acceso clientes" in respuesta.data


def test_login_correcto_da_acceso(cliente):
    respuesta = cliente.post(
        "/login", data={"usuario": "soporte", "clave": "ccr2014"}
    )
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/panel")


def test_login_de_cliente_va_a_su_cuenta(cliente):
    primera = cliente.get("/")
    assert primera.status_code == 200

    fila = cliente.application.config["BASE_DATOS"]
    import sqlite3

    con = sqlite3.connect(fila)
    con.row_factory = sqlite3.Row
    usuario = con.execute(
        "SELECT usuario FROM usuarios WHERE rol = 'cliente' LIMIT 1"
    ).fetchone()[0]
    con.close()

    # Las claves de cliente salen de una lista corta. Se prueban las comunes.
    for clave in ("123456", "password", "12345678", "bodega", "bodega2013",
                  "ccr2014", "morelos", "cuernavaca", "almacen", "123456789",
                  "qwerty", "abc123"):
        respuesta = cliente.post("/login", data={"usuario": usuario, "clave": clave})
        if respuesta.status_code == 302:
            assert respuesta.headers["Location"].endswith("/cuenta")
            return
    raise AssertionError("ninguna clave de la lista abrio la cuenta de cliente")


def test_cuenta_pide_sesion(cliente):
    respuesta = cliente.get("/cuenta")
    assert respuesta.status_code == 302
    assert "/login" in respuesta.headers["Location"]


def test_salir_borra_la_cookie(cliente):
    cliente.post("/login", data={"usuario": "soporte", "clave": "ccr2014"})
    respuesta = cliente.get("/salir")
    assert respuesta.status_code == 302
    assert "ccr_sesion=;" in respuesta.headers["Set-Cookie"]


def test_panel_correcto_para_encargado(cliente):
    respuesta = cliente.post(
        "/login", data={"usuario": "r.beltran", "clave": "Morelos#2019"}
    )
    assert respuesta.status_code == 302
    panel = cliente.get("/panel")
    assert panel.status_code == 200
    assert b"Panel del encargado" in panel.data


def test_panel_rechaza_al_cliente(cliente):
    cliente.set_cookie("ccr_sesion", cookie_de(usuario="cualquiera", rol="cliente"))
    respuesta = cliente.get("/panel")
    assert respuesta.status_code == 403
    assert b"Acceso restringido" in respuesta.data


# --- Lo que debe seguir roto, a proposito --------------------------------


def test_falla2_el_mensaje_distingue_si_el_usuario_existe(cliente):
    """FALLA 2: enumeracion de usuarios. Los dos mensajes son distintos."""
    inexistente = cliente.post(
        "/login", data={"usuario": "nadie.existe", "clave": "x"}
    )
    existente = cliente.post(
        "/login", data={"usuario": "soporte", "clave": "clave-equivocada"}
    )
    assert b"El usuario no existe" in inexistente.data
    assert b"La contrasena no es correcta" in existente.data
    assert inexistente.data != existente.data


def test_falla2_no_hay_bloqueo_por_intentos(cliente):
    """FALLA 2: veinte intentos fallidos y el sitio sigue respondiendo igual."""
    for _ in range(20):
        respuesta = cliente.post(
            "/login", data={"usuario": "soporte", "clave": "mala"}
        )
        assert respuesta.status_code == 200
        assert b"La contrasena no es correcta" in respuesta.data
    correcto = cliente.post("/login", data={"usuario": "soporte", "clave": "ccr2014"})
    assert correcto.status_code == 302


def test_falla4_la_cookie_es_fabricable(cliente):
    """FALLA 4: con un usuario que existe y rol admin, la cookie entra al panel."""
    cliente.set_cookie("ccr_sesion", cookie_de(usuario="v.salgado", rol="admin"))
    respuesta = cliente.get("/panel")
    assert respuesta.status_code == 200
    assert b"Panel del encargado" in respuesta.data


def test_falla4_necesita_un_usuario_que_exista(cliente):
    """FALLA 4 queda encadenada a la FALLA 2: sin enumerar no hay a quién suplantar."""
    cliente.set_cookie("ccr_sesion", cookie_de(usuario="cualquiera", rol="admin"))
    respuesta = cliente.get("/panel")
    assert respuesta.status_code == 403
    assert b"Acceso restringido" in respuesta.data


def test_falla4_no_revela_si_el_usuario_existe(cliente):
    """El panel responde igual con un usuario inventado que con uno real sin rol."""
    cliente.set_cookie("ccr_sesion", cookie_de(usuario="inventado", rol="admin"))
    inventado = cliente.get("/panel")
    cliente.set_cookie("ccr_sesion", cookie_de(usuario="v.salgado", rol="cliente"))
    sin_rol = cliente.get("/panel")
    assert inventado.status_code == sin_rol.status_code == 403
    assert inventado.data == sin_rol.data


def test_falla4_la_cookie_es_legible(cliente):
    """FALLA 4: el contenido de la cookie se lee sin ninguna llave."""
    respuesta = cliente.post("/login", data={"usuario": "soporte", "clave": "ccr2014"})
    valor = respuesta.headers["Set-Cookie"].split("ccr_sesion=")[1].split(";")[0]
    relleno = "=" * (-len(valor) % 4)
    datos = json.loads(base64.urlsafe_b64decode(valor + relleno).decode("utf-8"))
    assert datos["rol"] == "admin"
    assert datos["usuario"] == "soporte"


def test_falla5_las_claves_son_md5_sin_sal(cliente):
    """FALLA 5: admin/admin entra, y su hash es el MD5 conocido de 'admin'."""
    respuesta = cliente.post("/login", data={"usuario": "admin", "clave": "admin"})
    assert respuesta.status_code == 302

    import sqlite3

    con = sqlite3.connect(cliente.application.config["BASE_DATOS"])
    h = con.execute("SELECT hash FROM usuarios WHERE usuario = 'admin'").fetchone()[0]
    con.close()
    assert h == "21232f297a57a5a743894a0e4a801fc3"
    assert len(h) == 32


def test_falla15_la_cookie_no_es_httponly_ni_secure(cliente):
    """FALLA 15: la cookie viaja sin HttpOnly y sin Secure."""
    respuesta = cliente.post("/login", data={"usuario": "soporte", "clave": "ccr2014"})
    cabecera = respuesta.headers["Set-Cookie"]
    assert "HttpOnly" not in cabecera
    assert "Secure" not in cabecera


# --- La bitacora ---------------------------------------------------------


def test_bitacora_guarda_los_intentos(cliente, ruta_bitacora):
    cliente.post("/login", data={"usuario": "soporte", "clave": "ccr2014"})
    cliente.post("/login", data={"usuario": "soporte", "clave": "mala"})
    cliente.post("/login", data={"usuario": "fantasma", "clave": "x"})

    filas = bitacora.ultimos(10, ruta=ruta_bitacora)
    resultados = sorted(fila["resultado"] for fila in filas)
    assert resultados == ["clave-mala", "no-existe", "ok"]


def test_bitacora_no_bloquea_por_contar(cliente, ruta_bitacora):
    """Cuenta los intentos pero nadie los consulta. Es la FALLA 2 de nuevo."""
    for _ in range(30):
        cliente.post("/login", data={"usuario": "r.beltran", "clave": "mala"})
    assert bitacora.contar("r.beltran", ruta=ruta_bitacora) == 30
    correcto = cliente.post(
        "/login", data={"usuario": "r.beltran", "clave": "Morelos#2019"}
    )
    assert correcto.status_code == 302


# --- Flag de FALLA 4 -------------------------------------------------------


def test_falla4_flag_en_el_panel(cliente):
    """FALLA 4: el panel contiene el flag en su fuente HTML."""
    from conftest import poner_admin
    poner_admin(cliente)
    html = cliente.get("/panel").get_data(as_text=True)
    assert "CCR{cookie_forjada}" in html
