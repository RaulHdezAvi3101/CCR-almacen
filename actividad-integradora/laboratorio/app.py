"""Sitio de Almacenes CCR.

Actividad integradora de seguridad informatica. Este sitio se construye con
fallas a proposito. No lo publiques fuera del entorno de la asignatura.

AVISO PARA EL DOCENTE: las fallas de autenticacion estan marcadas con la
palabra FALLA en los comentarios. Van en este orden en el codigo:

  FALLA 2  El login dice si el usuario existe y no bloquea los intentos.
  FALLA 4  La cookie lleva el rol en texto claro y sin firma.
  FALLA 5  Las claves se comparan contra un hash MD5 sin sal.
  FALLA 15 La cookie no lleva HttpOnly ni Secure, y el sitio es HTTP.

  uv run flask --app app run
  uv run waitress-serve --host 0.0.0.0 --port 8000 app:app
"""

import base64
import hashlib
import json
import sqlite3
from pathlib import Path

from flask import Flask, g, make_response, redirect, render_template, request, url_for

import bitacora

BASE = Path(__file__).resolve().parent
RUTA_BASE = BASE / "datos" / "ccr.db"
CARPETA_COMPROBANTES = BASE / "datos" / "comprobantes"
CARPETA_SUBIDOS = BASE / "datos" / "subidos"
CARPETA_PUBLICO = BASE / "publico"

app = Flask(__name__)
app.config["BASE_DATOS"] = str(RUTA_BASE)
app.config["NOMBRE_COOKIE"] = "ccr_sesion"
app.config["CARPETA_COMPROBANTES"] = str(CARPETA_COMPROBANTES)
app.config["CARPETA_SUBIDOS"] = str(CARPETA_SUBIDOS)
app.config["CARPETA_PUBLICO"] = str(CARPETA_PUBLICO)
app.config["RUTA_BITACORA"] = str(bitacora.RUTA_BITACORA)
# FALLA 8: el tope existe, pero es alto y no hay cuota acumulada.
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024


def abrir_base():
    con = sqlite3.connect(app.config["BASE_DATOS"])
    con.row_factory = sqlite3.Row
    return con


def base():
    """Conexion por peticion. Se cierra sola al terminar."""
    if "base" not in g:
        g.base = abrir_base()
    return g.base


@app.teardown_appcontext
def cerrar_base(excepcion=None):
    con = g.pop("base", None)
    if con is not None:
        con.close()


def md5(clave):
    """FALLA 5: MD5 sin sal. Es la misma funcion que uso el generador de datos."""
    return hashlib.md5(clave.encode("utf-8")).hexdigest()


def buscar_usuario(usuario):
    return base().execute(
        "SELECT id, usuario, nombre, correo, hash, rol, sucursal_id FROM usuarios"
        " WHERE usuario = ? AND activo = 1",
        (usuario,),
    ).fetchone()


def armar_sesion(datos):
    """FALLA 4: el contenido de la sesion va en base64 y sin firma.

    Cualquiera puede decodificarlo, cambiar el rol y volver a codificarlo.
    """
    crudo = json.dumps(datos).encode("utf-8")
    return base64.urlsafe_b64encode(crudo).decode("ascii").rstrip("=")


def leer_sesion(valor):
    """FALLA 4: se confia en lo que traiga la cookie, sin comprobar nada."""
    if not valor:
        return None
    relleno = "=" * (-len(valor) % 4)
    try:
        crudo = base64.urlsafe_b64decode(valor + relleno).decode("utf-8")
        datos = json.loads(crudo)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(datos, dict) or "usuario" not in datos:
        return None
    return datos


def sesion_actual():
    return leer_sesion(request.cookies.get(app.config["NOMBRE_COOKIE"]))


def poner_cookie(respuesta, datos):
    """FALLA 15: sin HttpOnly y sin Secure. Un script puede leer la cookie."""
    respuesta.set_cookie(
        app.config["NOMBRE_COOKIE"],
        armar_sesion(datos),
        max_age=8 * 60 * 60,
        path="/",
    )
    return respuesta


@app.context_processor
def inyectar_sesion():
    return {"sesion": sesion_actual()}


def registrar_evento(usuario, resultado):
    """Anota un intento en la bitacora configurada para esta instancia."""
    bitacora.registrar(usuario, resultado, request.remote_addr,
                       request.headers.get("User-Agent"),
                       ruta=app.config["RUTA_BITACORA"])


@app.after_request
def anotar_trafico(respuesta):
    """Deja rastro de cada peticion. Es lo que alimenta /registros."""
    ruta = request.path
    if ruta == "/registros":
        return respuesta
    if ruta.startswith("/static/"):
        return respuesta
    try:
        bitacora.registrar_acceso(
            request.remote_addr,
            request.method,
            ruta,
            request.headers.get("User-Agent"),
            request.headers.get("Referer"),
            respuesta.status_code,
            base=app.config["RUTA_BITACORA"],
        )
    except Exception:
        # Si la bitacora falla, el sitio sigue. Un sitio de 2013 no valida.
        pass
    return respuesta


@app.route("/")
def portada():
    con = base()
    sucursales = con.execute(
        "SELECT clave, nombre, direccion, telefono FROM sucursales ORDER BY id"
    ).fetchall()
    conteo = con.execute(
        "SELECT estado, COUNT(*) AS cuantas FROM bodegas GROUP BY estado"
    ).fetchall()
    estados = {fila["estado"]: fila["cuantas"] for fila in conteo}
    return render_template("portada.html", sucursales=sucursales, estados=estados)


@app.route("/bodegas")
def bodegas():
    """Catalogo de bodegas. La pagina arma la tabla con los datos del JSON."""
    con = base()
    sucursales = con.execute(
        "SELECT id, clave, nombre FROM sucursales ORDER BY id"
    ).fetchall()
    return render_template("bodegas.html", sucursales=sucursales)


@app.route("/api/bodegas")
def api_bodegas():
    """JSON que alimenta el catalogo.

    FALLA 1: manda los datos del cliente de TODAS las bodegas, ocupadas
    incluidas. La pagina solo las esconde con CSS. Quien abra la pestana de
    red, o vea el codigo fuente, encuentra nombre, correo y contrato de cada
    cliente sin necesidad de sesion.

    La consulta tambien trae el RFC y el telefono, que ni la pagina usa. Es
    el tipico "por si acaso" de un programador de 2013.
    """
    sucursal = request.args.get("sucursal", type=int)
    con = base()
    consulta = (
        "SELECT b.id, b.numero, b.metros, b.precio, b.estado,"
        "       s.clave AS sucursal_clave, s.nombre AS sucursal,"
        "       ct.id AS contrato, ct.inicio, ct.mensualidad,"
        "       c.nombre AS cliente, c.correo AS cliente_correo,"
        "       c.telefono AS cliente_telefono, c.rfc AS cliente_rfc"
        "  FROM bodegas b"
        "  JOIN sucursales s ON s.id = b.sucursal_id"
        "  LEFT JOIN contratos ct ON ct.bodega_id = b.id AND ct.estado = 'vigente'"
        "  LEFT JOIN clientes c ON c.id = ct.cliente_id"
    )
    if sucursal:
        consulta += " WHERE b.sucursal_id = ?"
        filas = con.execute(consulta + " ORDER BY b.numero", (sucursal,)).fetchall()
    else:
        filas = con.execute(consulta + " ORDER BY b.numero").fetchall()

    datos = []
    for fila in filas:
        bodega = {
            "id": fila["id"],
            "numero": fila["numero"],
            "metros": fila["metros"],
            "precio": fila["precio"],
            "estado": fila["estado"],
            "sucursal": fila["sucursal"],
            "sucursal_clave": fila["sucursal_clave"],
        }
        # FALLA 1: el bloque del cliente viaja aunque la bodega este ocupada.
        if fila["contrato"] is not None:
            bodega["contrato"] = {
                "id": fila["contrato"],
                "inicio": fila["inicio"],
                "mensualidad": fila["mensualidad"],
            }
            bodega["cliente"] = {
                "nombre": fila["cliente"],
                "correo": fila["cliente_correo"],
                "telefono": fila["cliente_telefono"],
                "rfc": fila["cliente_rfc"],
            }
        datos.append(bodega)
    # FALLA 1: campo de depuracion que el proveedor dejo sin quitar en 2013.
    return {"bodegas": datos, "_debug": "CCR{api_sin_autenticar}"}


@app.route("/comprobantes")
def comprobantes():
    """Lista de comprobantes del cliente con sesion."""
    datos = sesion_actual()
    if not datos:
        return redirect(url_for("login"))

    con = base()
    fila = con.execute(
        "SELECT id, nombre, correo FROM usuarios WHERE usuario = ?", (datos.get("usuario"),)
    ).fetchone()
    if fila is None:
        return redirect(url_for("login"))

    lista = con.execute(
        "SELECT cp.id, cp.periodo, cp.monto, cp.archivo, cp.subido,"
        "       ct.id AS contrato, b.numero AS bodega, s.nombre AS sucursal"
        "  FROM comprobantes cp"
        "  JOIN contratos ct ON ct.id = cp.contrato_id"
        "  JOIN bodegas b ON b.id = ct.bodega_id"
        "  JOIN sucursales s ON s.id = b.sucursal_id"
        "  JOIN clientes cl ON cl.id = ct.cliente_id"
        " WHERE cl.correo = ? ORDER BY cp.periodo DESC",
        (fila["correo"],),
    ).fetchall()

    return render_template("comprobantes.html", usuario=fila, lista=lista)


@app.route("/comprobante/<int:numero>")
def comprobante(numero):
    """Descarga de un comprobante por su numero.

    FALLA 6: no se comprueba de quien es el comprobante. El que sabe el
    numero lo descarga, tenga o no sesion, sea o no suyo. Los numeros son
    consecutivos y se pueden recorrer con un ciclo.
    """
    con = base()
    fila = con.execute(
        "SELECT cp.id, cp.periodo, cp.archivo, cp.monto,"
        "       cl.nombre AS cliente, cl.correo, b.numero AS bodega,"
        "       s.nombre AS sucursal, ct.id AS contrato"
        "  FROM comprobantes cp"
        "  JOIN contratos ct ON ct.id = cp.contrato_id"
        "  JOIN clientes cl ON cl.id = ct.cliente_id"
        "  JOIN bodegas b ON b.id = ct.bodega_id"
        "  JOIN sucursales s ON s.id = b.sucursal_id"
        " WHERE cp.id = ?",
        (numero,),
    ).fetchone()

    if fila is None:
        return render_template("no_encontrado.html", que="comprobante"), 404

    ruta = CARPETA_COMPROBANTES / fila["archivo"]
    if not ruta.exists():
        return render_template("no_encontrado.html", que="archivo del comprobante"), 404

    respuesta = make_response(ruta.read_bytes())
    respuesta.headers["Content-Type"] = "application/pdf"
    respuesta.headers["Content-Disposition"] = f'inline; filename="{fila["archivo"]}"'
    return respuesta


@app.route("/panel/comprobantes")
def panel_comprobantes():
    """Comprobantes subidos, vistos desde el panel."""
    datos = sesion_actual()
    if not datos:
        return redirect(url_for("login"))
    fila = buscar_usuario(datos.get("usuario", ""))
    if fila is None or datos.get("rol") not in ("admin", "encargado"):
        return render_template("sin_permiso.html", datos=datos), 403

    con = base()
    lista = con.execute(
        "SELECT cp.id, cp.periodo, cp.monto, cp.archivo, cp.subido,"
        "       cl.nombre AS cliente, b.numero AS bodega, s.nombre AS sucursal"
        "  FROM comprobantes cp"
        "  JOIN contratos ct ON ct.id = cp.contrato_id"
        "  JOIN clientes cl ON cl.id = ct.cliente_id"
        "  JOIN bodegas b ON b.id = ct.bodega_id"
        "  JOIN sucursales s ON s.id = b.sucursal_id"
        " ORDER BY cp.id DESC LIMIT 40"
    ).fetchall()
    return render_template("panel_comprobantes.html", datos=datos, lista=lista)


@app.route("/subir", methods=["GET", "POST"])
def subir():
    """Subida del comprobante de pago.

    FALLA 7: el nombre y la extension del archivo los pone el cliente, y el
    sitio los guarda tal cual. Se puede subir .html y abrirlo despues desde
    /archivo/<nombre>, donde el navegador lo ejecuta como pagina.

    FALLA 8: hay tope de 20 MB por archivo, pero no hay cuota por cliente ni
    por contrato. Cien archivos de 20 MB llenan el disco sin que nadie lo
    note.
    """
    datos = sesion_actual()
    if not datos:
        return redirect(url_for("login"))

    aviso = None
    error = None
    con = base()
    con.execute(
        "CREATE TABLE IF NOT EXISTS subidas ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  usuario TEXT, archivo TEXT, tamano INTEGER, momento TEXT)"
    )
    con.commit()

    if request.method == "POST":
        archivo = request.files.get("comprobante")
        if archivo is None or not archivo.filename:
            error = "Elija un archivo."
        else:
            # FALLA 7: se usa el nombre que manda el cliente, sin limpiarlo.
            # Con os.makedirs se crean las carpetas que el nombre incluya, asi
            # que un nombre con "../" escribe fuera de la carpeta de subidos.
            nombre = archivo.filename
            destino = CARPETA_SUBIDOS / nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            archivo.save(destino)
            tamano = destino.stat().st_size
            aviso = f"Archivo guardado: {nombre} ({tamano:,} bytes)."
            con.execute(
                "INSERT INTO subidas (usuario, archivo, tamano, momento)"
                " VALUES (?, ?, ?, datetime('now'))",
                (datos.get("usuario"), nombre, tamano),
            )
            con.commit()

    mias = con.execute(
        "SELECT archivo, tamano, momento FROM subidas WHERE usuario = ? ORDER BY id DESC",
        (datos.get("usuario"),),
    ).fetchall()

    return render_template("subir.html", usuario=datos, aviso=aviso, error=error, mias=mias)


@app.route("/archivo/<path:nombre>")
def archivo(nombre):
    """Sirve lo que el cliente subio.

    FALLA 7: se sirve con el tipo que adivine el navegador a partir del nombre.
    Un archivo llamado nota.html se ejecuta como pagina dentro del sitio.
    """
    ruta = CARPETA_SUBIDOS / nombre
    if not ruta.exists() or not ruta.is_file():
        return render_template("no_encontrado.html", que="archivo"), 404
    respuesta = make_response(ruta.read_bytes())
    respuesta.headers["Content-Disposition"] = f'inline; filename="{nombre}"'
    return respuesta


@app.route("/contratos")
@app.route("/contratos/<termino>")
def contratos(termino=None):
    """Buscador de contratos.

    FALLA 13: el termino se refleja en la pagina sin escapar.

    FALLA 12: la consulta se arma pegando el termino del usuario. El filtro
    quita SELECT, UNION y los comentarios, pero solo una vez y sin distinguir
    mayusculas de minusculas de forma completa. Hay que investigar como
    pasarlo.
    """
    termino = termino or request.args.get("q", "")
    filas = []
    error = None

    if termino:
        limpio = filtrar(termino)
        consulta = (
            "SELECT ct.id, ct.inicio, ct.estado, ct.mensualidad,"
            "       cl.nombre AS cliente, cl.correo, b.numero AS bodega,"
            "       s.nombre AS sucursal"
            "  FROM contratos ct"
            "  JOIN clientes cl ON cl.id = ct.cliente_id"
            "  JOIN bodegas b ON b.id = ct.bodega_id"
            "  JOIN sucursales s ON s.id = b.sucursal_id"
            f" WHERE ct.estado = 'vigente' AND (cl.nombre LIKE '%{limpio}%'"
            f"    OR b.numero LIKE '%{limpio}%')"
            "  ORDER BY ct.id LIMIT 50"
        )
        try:
            filas = base().execute(consulta).fetchall()
        except sqlite3.Error as exc:
            # FALLA 11: el error de SQL tambien se muestra tal cual.
            error = str(exc)

    return render_template("contratos.html", termino=termino, filas=filas, error=error)


def filtrar(texto):
    """Filtro casero del buscador.

    FALLA 12: quita las palabras peligrosas una sola vez y solo si aparecen
    escritas igual. Con una pasada no alcanza: si se forma de nuevo al quitar
    otra cosa, queda. Ademas no toca las comillas ni el punto y coma.
    """
    peligrosas = ("SELECT", "select", "Select", "UNION", "union", "Union",
                  "--", "/*", "*/", "OR 1=1", "or 1=1")
    for palabra in peligrosas:
        texto = texto.replace(palabra, "", 1)
    return texto


@app.route("/registros")
def registros():
    """FALLA 14: la bitacora de trafico del sitio, abierta a cualquiera.

    Sin sesion, sin permisos, sin nada. Muestra todas las peticiones de todos
    los equipos: rutas probadas, codigos de respuesta, direcciones y agentes.
    """
    accesos = bitacora.ultimos_accesos(300, base=app.config["RUTA_BITACORA"])
    intentos = bitacora.ultimos(150, ruta=app.config["RUTA_BITACORA"])
    return render_template("registros.html", accesos=accesos, intentos=intentos)


@app.route("/publico/")
@app.route("/publico/<nombre>")
def publico(nombre=None):
    """Documentos publicos de CCR: aviso de privacidad, vacante, directorio.

    Se sirven desde la carpeta publico/ y los pide el pie de pagina. El
    repositorio con el config.py se sirve como /publico/repositorio.
    """
    if nombre is None:
        documentos = [
            ("01-aviso-privacidad", "Aviso de privacidad"),
            ("02-vacante", "Bolsa de trabajo"),
            ("03-ficha-dominio", "Directorio y servicios"),
            ("04-repo", "Respaldo del codigo"),
        ]
        return render_template("publico_indice.html", documentos=documentos)

    permitidos = {
        "01-aviso-privacidad": "01-aviso-privacidad.md",
        "02-vacante": "02-vacante.md",
        "03-ficha-dominio": "03-ficha-dominio.md",
        "04-repo": "04-repo.md",
    }
    archivo = permitidos.get(nombre)
    if archivo is None:
        return render_template("no_encontrado.html", que="documento"), 404
    ruta = CARPETA_PUBLICO / archivo
    if not ruta.exists():
        return render_template("no_encontrado.html", que="documento"), 404
    return render_template("publico_documento.html", titulo=documento_titulo(nombre),
                           cuerpo=ruta.read_text(encoding="utf-8"))


def documento_titulo(nombre):
    return {
        "01-aviso-privacidad": "Aviso de privacidad",
        "02-vacante": "Bolsa de trabajo",
        "03-ficha-dominio": "Directorio y servicios",
        "04-repo": "Respaldo del codigo",
    }.get(nombre, "Documento")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    usuario = ""

    if request.method == "POST":
        usuario = (request.form.get("usuario") or "").strip()
        clave = request.form.get("clave") or ""
        fila = buscar_usuario(usuario)

        if fila is None:
            # FALLA 2: el mensaje distingue al usuario que no existe.
            error = "El usuario no existe en el sistema."
            registrar_evento(usuario, "no-existe")
        elif fila["hash"] != md5(clave):
            # FALLA 2: y este mensaje distingue al usuario que si existe.
            error = "La contrasena no es correcta."
            registrar_evento(usuario, "clave-mala")
        else:
            # FALLA 2: no hay contador de intentos ni bloqueo en ninguna rama.
            registrar_evento(usuario, "ok")
            datos = {
                "usuario": fila["usuario"],
                "nombre": fila["nombre"],
                "rol": fila["rol"],
                "sucursal": fila["sucursal_id"],
            }
            destino = "/panel" if fila["rol"] in ("admin", "encargado") else "/cuenta"
            return poner_cookie(make_response(redirect(destino)), datos)

    return render_template("login.html", error=error, usuario=usuario)


@app.route("/salir")
def salir():
    respuesta = make_response(redirect("/"))
    respuesta.delete_cookie(app.config["NOMBRE_COOKIE"], path="/")
    return respuesta


@app.route("/cuenta")
def cuenta():
    datos = sesion_actual()
    if not datos:
        return redirect(url_for("login"))
    fila = buscar_usuario(datos.get("usuario", ""))
    if fila is None:
        return redirect(url_for("login"))
    contratos = base().execute(
        "SELECT c.id, c.inicio, c.mensualidad, c.estado, b.numero, s.nombre AS sucursal"
        " FROM contratos c"
        " JOIN bodegas b ON b.id = c.bodega_id"
        " JOIN sucursales s ON s.id = b.sucursal_id"
        " JOIN clientes cl ON cl.id = c.cliente_id"
        " WHERE cl.correo = ? ORDER BY c.inicio DESC",
        (fila["correo"],),
    ).fetchall()
    return render_template("cuenta.html", usuario=fila, contratos=contratos)


@app.route("/alta", methods=["GET", "POST"])
def alta():
    """Alta de clientes. Crea la cuenta y el cliente en un solo paso."""
    error = None
    bien = None
    datos_form = {
        "nombre": "",
        "correo": "",
        "telefono": "",
        "rfc": "",
        "nota": "",
        "bodega": request.args.get("bodega", ""),
    }

    if request.method == "POST":
        for campo in datos_form:
            datos_form[campo] = (request.form.get(campo) or "").strip()

        if not datos_form["nombre"] or not datos_form["correo"]:
            error = "El nombre y el correo son obligatorios."
        elif "@" not in datos_form["correo"]:
            error = "Escriba un correo electronico valido."
        else:
            con = base()
            # FALLA 2 (segunda parte): el alta avisa si el correo ya esta
            # registrado. Con esto se enumeran clientes sin necesidad de
            # tocar el login. La comprobacion se hace aparte del login.
            ya_existe = con.execute(
                "SELECT id FROM clientes WHERE correo = ?", (datos_form["correo"],)
            ).fetchone()
            if ya_existe is not None:
                error = "Ese correo ya esta registrado en el sistema."
            else:
                usuario = datos_form["correo"].split("@")[0]
                # Si el nombre de usuario se repite, se le pega un numero.
                repetido = con.execute(
                    "SELECT id FROM usuarios WHERE usuario = ?", (usuario,)
                ).fetchone()
                if repetido is not None:
                    usuario = f"{usuario}{con.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0] + 1}"

                # FALLA 5: la clave inicial del cliente se guarda con MD5 sin
                # sal. Ademas se elige de una lista corta, igual que en los
                # datos de ejemplo, para que el agrietamiento sea posible.
                clave_inicial = "bodega2013"

                con.execute(
                    "INSERT INTO clientes (tipo, nombre, rfc, correo, telefono, nota, creado)"
                    " VALUES (?, ?, ?, ?, ?, ?, date('now'))",
                    (
                        "persona",
                        datos_form["nombre"],
                        datos_form["rfc"],
                        datos_form["correo"],
                        datos_form["telefono"],
                        datos_form["nota"],
                    ),
                )
                cliente_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
                con.execute(
                    "INSERT INTO usuarios (usuario, nombre, correo, hash, rol, sucursal_id, activo)"
                    " VALUES (?, ?, ?, ?, 'cliente', NULL, 1)",
                    (usuario, datos_form["nombre"], datos_form["correo"], md5(clave_inicial)),
                )
                con.commit()

                registrar_evento(f"alta:{datos_form['correo']}", "ok")
                bien = (
                    f"Alta registrada. Su usuario es {usuario} y su contrasena "
                    f"inicial es {clave_inicial}. Cambiela al entrar."
                )
                datos_form = {"nombre": "", "correo": "", "telefono": "",
                              "rfc": "", "nota": "", "bodega": ""}

    return render_template("alta.html", error=error, bien=bien, datos=datos_form
                           if isinstance(datos_form, dict) else {})


@app.route("/panel/clientes")
def panel_clientes():
    """Lista de clientes del panel. Aqui se dibuja la nota de cada cliente."""
    datos = sesion_actual()
    if not datos:
        return redirect(url_for("login"))
    fila = buscar_usuario(datos.get("usuario", ""))
    if fila is None or datos.get("rol") not in ("admin", "encargado"):
        return render_template("sin_permiso.html", datos=datos), 403

    con = base()
    clientes = con.execute(
        "SELECT id, tipo, nombre, correo, telefono, nota, creado"
        "  FROM clientes ORDER BY id DESC LIMIT 60"
    ).fetchall()
    return render_template("panel_clientes.html", datos=datos, clientes=clientes)


@app.route("/panel", methods=["GET"])
def panel():
    datos = sesion_actual()
    if not datos:
        return redirect(url_for("login"))

    # FALLA 4: el rol se toma de la cookie, que no va firmada. Basta con
    # escribir "rol": "admin" y volver a codificar.
    #
    # Lo unico que se comprueba es que el usuario exista en la base. Esa
    # comprobacion obliga a combinar esta falla con la FALLA 2: sin enumerar
    # usuarios no se sabe que nombre poner en la cookie.
    #
    # La respuesta es la misma exista o no el usuario, para no regalar otra
    # via de enumeracion desde aqui.
    fila = buscar_usuario(datos.get("usuario", ""))
    if fila is None:
        return render_template("sin_permiso.html", datos=datos), 403
    if datos.get("rol") not in ("admin", "encargado"):
        return render_template("sin_permiso.html", datos=datos), 403

    return render_template("panel.html", datos=datos)


@app.route("/admin-viejo", methods=["GET", "POST"])
def admin_viejo():
    """Panel de administracion de 2013, todavia en produccion.

    FALLA 9: usa autenticacion basica con la cuenta de fabrica admin/admin.
    La ruta esta anunciada en robots.txt y el usuario y la clave aparecen en
    el config.py del repositorio publico.

    FALLA 11: si algo falla, la pagina muestra la traza completa de Python con
    rutas del servidor y nombres de tablas.
    """
    usuario = ""
    error = None

    autorizado = False
    cabecera = request.headers.get("Authorization", "")
    if cabecera.startswith("Basic "):
        try:
            crudo = base64.b64decode(cabecera[6:]).decode("utf-8")
            usuario, _, clave = crudo.partition(":")
            if usuario == "admin" and clave == "admin":
                autorizado = True
        except (ValueError, UnicodeDecodeError):
            autorizado = False

    if not autorizado and request.method == "POST":
        usuario = (request.form.get("usuario") or "").strip()
        clave = request.form.get("clave") or ""
        if usuario == "admin" and clave == "admin":
            autorizado = True
        else:
            error = "Credenciales incorrectas."
            registrar_evento(f"admin-viejo:{usuario}", "clave-mala")

    if not autorizado:
        respuesta = make_response(render_template("admin_viejo_login.html",
                                                  error=error, usuario=usuario), 401)
        respuesta.headers["WWW-Authenticate"] = 'Basic realm="CCR Administracion"'
        return respuesta

    registrar_evento("admin-viejo:admin", "ok")

    con = base()
    totales = {
        "clientes": con.execute("SELECT COUNT(*) FROM clientes").fetchone()[0],
        "contratos": con.execute("SELECT COUNT(*) FROM contratos").fetchone()[0],
        "comprobantes": con.execute("SELECT COUNT(*) FROM comprobantes").fetchone()[0],
        "usuarios": con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0],
    }
    return render_template("admin_viejo.html", totales=totales)


@app.route("/admin-viejo/usuarios")
def admin_viejo_usuarios():
    """Listado de usuarios con su hash. Detras del mismo admin/admin."""
    cabecera = request.headers.get("Authorization", "")
    autorizado = False
    if cabecera.startswith("Basic "):
        try:
            crudo = base64.b64decode(cabecera[6:]).decode("utf-8")
            usuario, _, clave = crudo.partition(":")
            autorizado = usuario == "admin" and clave == "admin"
        except (ValueError, UnicodeDecodeError):
            autorizado = False

    if not autorizado:
        respuesta = make_response("Autorizacion requerida.", 401)
        respuesta.headers["WWW-Authenticate"] = 'Basic realm="CCR Administracion"'
        return respuesta

    filas = base().execute(
        "SELECT id, usuario, nombre, correo, hash, rol, activo FROM usuarios ORDER BY id"
    ).fetchall()
    return render_template("admin_viejo_usuarios.html", filas=filas)


@app.route("/respaldo.sql")
def respaldo():
    """FALLA 10: el volcado diario de la base quedo en la raiz del sitio.

    Lo deja ahi el backup.sh y nadie lo movio. Tiene la base entera: clientes,
    contratos, usuarios y sus hashes MD5.
    """
    ruta = RUTA_BASE.parent / "respaldo.sql"
    if not ruta.exists():
        return render_template("no_encontrado.html", que="respaldo"), 404
    # FALLA 10: el flag viaja como comentario SQL al inicio del volcado.
    cuerpo = b"-- CCR{respaldo_en_la_raiz}\n" + ruta.read_bytes()
    respuesta = make_response(cuerpo)
    respuesta.headers["Content-Type"] = "application/sql"
    respuesta.headers["Content-Disposition"] = 'attachment; filename="respaldo.sql"'
    return respuesta


@app.route("/robots.txt")
def robots():
    """FALLA 9 (parte): el robots.txt anuncia lo que se quiere esconder."""
    lineas = [
        "User-agent: *",
        "Disallow: /admin-viejo",
        "Disallow: /admin-viejo/usuarios",
        "Disallow: /panel",
        "Disallow: /respaldo.sql",
        "",
    ]
    return "\n".join(lineas), 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/error")
def error_forzado():
    """FALLA 11: ruta que revienta a proposito para ver la traza."""
    try:
        # FALLA 11: el flag queda en el mensaje del ValueError que aparece en
        # la traza. Solo se ve si se llega a /error y se lee el detalle tecnico.
        numero = int("CCR{traza_expuesta}")
    except ValueError as exc:
        # Se atrapa solo para poder dibujar la traza en la respuesta. Un sitio
        # de 2013 con debug encendido hace exactamente esto: devuelve el
        # traceback al navegador.
        import traceback

        traza = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        return pagina_de_error(traza), 500, {"Content-Type": "text/html; charset=utf-8"}
    return f"nunca llega: {numero}"


def pagina_de_error(traza):
    """FALLA 11: la pagina de error muestra la traza completa.

    Ruta del archivo, numero de linea, version de Python y de Flask, y el
    codigo de la funcion que fallo.
    """
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Error interno - CCR</title>
<link rel="stylesheet" href="/static/estilos.css"></head><body>
<div class="marco"><div class="cuerpo"><main class="contenido">
<h1>Error interno del servidor</h1>
<p>Ocurri&oacute; un problema al procesar su solicitud.</p>
<h2>Detalle tecnico</h2>
<pre class="traza">{traza}</pre>
<p class="nota-pie">CCR-Bodegas v2 &middot; Flask &middot; Python {__import__("sys").version.split()[0]}</p>
</main></div></div></body></html>"""


@app.errorhandler(500)
def error_interno(excepcion):
    """Cualquier otra excepcion no atrapada tambien deja ver la traza."""
    import traceback

    original = getattr(excepcion, "original_exception", None) or excepcion
    traza = "".join(traceback.format_exception(type(original), original,
                                              original.__traceback__))
    return pagina_de_error(traza), 500, {"Content-Type": "text/html; charset=utf-8"}


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
