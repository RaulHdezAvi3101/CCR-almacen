"""Pruebas del alta de clientes y del panel.

Cubren la FALLA 2 en su segunda via (el alta avisa si el correo existe) y la
FALLA 3 (la nota del cliente se dibuja como HTML en el panel).

  uv run pytest pruebas/test_alta.py -v
"""

import sqlite3

from conftest import COOKIE_ADMIN, poner_admin


def test_formulario_de_alta(cliente):
    respuesta = cliente.get("/alta")
    assert respuesta.status_code == 200
    assert b"Alta de clientes" in respuesta.data


def test_alta_crea_el_cliente_y_el_usuario(cliente):
    respuesta = cliente.post("/alta", data={
        "nombre": "Prueba Cliente",
        "correo": "prueba.alta@correo.example",
        "telefono": "777 111 2222",
        "rfc": "PRCL900101ABC",
        "nota": "Ingreso por internet",
        "bodega": "CEN-02",
    })
    assert respuesta.status_code == 200
    assert b"Alta registrada" in respuesta.data

    con = sqlite3.connect(cliente.application.config["BASE_DATOS"])
    con.row_factory = sqlite3.Row
    nuevo = con.execute(
        "SELECT nombre, correo, nota FROM clientes WHERE correo = ?",
        ("prueba.alta@correo.example",),
    ).fetchone()
    assert nuevo["nombre"] == "Prueba Cliente"
    assert nuevo["nota"] == "Ingreso por internet"

    cuenta = con.execute(
        "SELECT usuario, hash, rol FROM usuarios WHERE correo = ?",
        ("prueba.alta@correo.example",),
    ).fetchone()
    con.close()
    assert cuenta["usuario"] == "prueba.alta"
    assert cuenta["rol"] == "cliente"
    assert len(cuenta["hash"]) == 32


def test_alta_exige_nombre_y_correo(cliente):
    respuesta = cliente.post("/alta", data={"nombre": "", "correo": ""})
    assert b"obligatorios" in respuesta.data


def test_alta_rechaza_correo_sin_arroba(cliente):
    respuesta = cliente.post("/alta", data={"nombre": "X", "correo": "sin-arroba"})
    assert b"correo electronico valido" in respuesta.data


# --- FALLA 2, segunda via ------------------------------------------------


def test_falla2_el_alta_dice_si_el_correo_ya_existe(cliente):
    """FALLA 2: el alta confirma la existencia de un correo en el sistema."""
    con = sqlite3.connect(cliente.application.config["BASE_DATOS"])
    correo = con.execute("SELECT correo FROM clientes LIMIT 1").fetchone()[0]
    con.close()

    existente = cliente.post("/alta", data={"nombre": "X", "correo": correo})
    assert b"ya esta registrado" in existente.data

    nuevo = cliente.post("/alta", data={"nombre": "Y", "correo": "nuevo.nadie@correo.example"})
    assert b"ya esta registrado" not in nuevo.data


def test_falla2_permite_enumerar_correos_de_clientes(cliente):
    """FALLA 2: con una lista de correos se sabe quien es cliente de CCR."""
    con = sqlite3.connect(cliente.application.config["BASE_DATOS"])
    correos = [f[0] for f in con.execute(
        "SELECT correo FROM clientes ORDER BY id LIMIT 5"
    ).fetchall()]
    con.close()

    encontrados = 0
    for correo in correos:
        r = cliente.post("/alta", data={"nombre": "X", "correo": correo})
        if b"ya esta registrado" in r.data:
            encontrados += 1
    assert encontrados == len(correos)


# --- FALLA 3 ------------------------------------------------------------


def test_falla3_la_nota_se_dibuja_como_html(cliente):
    """FALLA 3: la nota con una etiqueta se dibuja como etiqueta, no como texto."""
    poner_admin(cliente)
    respuesta = cliente.post("/alta", data={
        "nombre": "Cliente XSS",
        "correo": "xss.prueba@correo.example",
        "nota": "<b>nota-en-negritas</b>",
    })
    assert b"Alta registrada" in respuesta.data

    panel = cliente.get("/panel/clientes")
    assert panel.status_code == 200
    html = panel.get_data(as_text=True)
    # El <b> sale crudo, sin escapar. Si estuviera escapado se veria &lt;b&gt;.
    assert "<b>nota-en-negritas</b>" in html
    assert "&lt;b&gt;" not in html


def test_falla3_admite_una_etiqueta_de_script(cliente):
    """FALLA 3: el mismo campo acepta <script>, que es lo que roba la cookie."""
    poner_admin(cliente)
    etiqueta = '<script>document.title="pwned"</script>'
    cliente.post("/alta", data={
        "nombre": "Cliente Script",
        "correo": "script.prueba@correo.example",
        "nota": etiqueta,
    })

    html = cliente.get("/panel/clientes").get_data(as_text=True)
    assert etiqueta in html
    # La prueba confirma que la defensa (escapar) no esta puesta a proposito.
    assert "&lt;script&gt;" not in html


def test_falla3_las_notas_sembradas_tambien_salen_crudas(cliente):
    """Los datos de ejemplo ya traen 16 notas con etiquetas."""
    poner_admin(cliente)
    html = cliente.get("/panel/clientes").get_data(as_text=True)
    assert "<b>Pago en efectivo.</b>" in html or "<i>Factura mensual</i>" in html


# --- Acceso al panel -----------------------------------------------------


def test_panel_clientes_pide_sesion(cliente):
    respuesta = cliente.get("/panel/clientes")
    assert respuesta.status_code == 302


def test_panel_clientes_rechaza_al_cliente(cliente):
    from conftest import cookie_de

    cliente.set_cookie("ccr_sesion", cookie_de(usuario="v.salgado", rol="cliente"))
    respuesta = cliente.get("/panel/clientes")
    assert respuesta.status_code == 403


def test_panel_clientes_entra_con_cookie_forjada(cliente):
    poner_admin(cliente)
    respuesta = cliente.get("/panel/clientes")
    assert respuesta.status_code == 200
    assert b"Clientes registrados" in respuesta.data
