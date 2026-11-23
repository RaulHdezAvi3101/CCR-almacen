#!/usr/bin/env python3
"""Genera los datos ficticios de CCR para el laboratorio de la actividad integradora.

Solo biblioteca estandar. Escribe ccr.db y un respaldo.sql, igual que lo haria
el backup.sh del sitio.

Aviso para el docente: este archivo siembra a proposito varias de las fallas de
la lista. Las claves van con MD5 sin sal. La tabla usuarios trae cuentas debiles
y una cuenta admin/admin. Las notas de algunos clientes llevan etiquetas HTML.
Nada de esto es un descuido: es el material del ejercicio.

  python3 generar_datos.py
  python3 generar_datos.py --semilla 7 --salida /tmp/ccr
"""

import argparse
import hashlib
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from random import Random

HOY = date(2026, 11, 20)

SUCURSALES = (
    ("CEN", "Centro", "Avenida Morelos Sur 214, col. Centro, Cuernavaca", "777 312 4410", 24, 145),
    ("IND", "Industrial", "Calle Zinc 8, Civac, Jiutepec", "777 320 8830", 20, 98),
    ("NOR", "Norte", "Avenida Universidad 1502, Cuernavaca", "777 314 2277", 16, 112),
)

METROS = (1, 1.5, 2, 3, 4, 6, 8, 10, 12)

NOMBRES_H = (
    "José Luis", "Miguel Ángel", "Juan Carlos", "Luis Enrique", "Marco Antonio",
    "Alejandro", "Ricardo", "Fernando", "Roberto", "Javier",
    "Arturo", "Raúl", "Óscar", "Sergio", "Héctor",
    "Ignacio", "Emilio", "Rodrigo", "Andrés", "Pablo",
    "Diego", "Iván", "Gerardo", "Alberto", "Rubén",
)

NOMBRES_M = (
    "María Guadalupe", "Rocío", "Verónica", "Claudia", "Alejandra",
    "Adriana", "Mónica", "Patricia", "Gabriela", "Leticia",
    "Sofía", "Itzel", "Norma", "Beatriz", "Silvia",
    "Diana", "Alicia", "Laura", "Martha", "Cecilia",
    "Xóchitl", "Yolanda", "Elsa", "Rebeca", "Elena",
)

APELLIDOS = (
    "Beltrán", "Tapia", "Domínguez", "Salgado", "Fuentes",
    "Ramírez", "Cortés", "Nava", "Ruiz", "Solís",
    "Ríos", "Bravo", "Lozano", "Vega", "Zapata",
    "Herrera", "Mendoza", "Castañeda", "Rosales", "Ortiz",
    "Guzmán", "Bautista", "Aguilar", "Cervantes", "Palacios",
    "Quintero", "Rangel", "Villalobos", "Escobar", "Mejía",
    "Trujillo", "Barajas", "Cornejo", "Fajardo", "Ocampo",
)

EMPRESAS = (
    "Ferretería El Tornillo", "Papelería Central", "Dulces Morelos", "Taller Mecánico Rivera",
    "Boutique Aurora", "Distribuidora del Sur", "Panadería La Espiga", "Abarrotes Doña Chelo",
    "Refaccionaria Nueve", "Estética Lumiere", "Imprenta Gutenberg", "Mueblería Colima",
    "Farmacia San Gaspar", "Veterinaria Huellitas", "Café Tlahuica", "Constructora Zapata",
    "Textiles Cuernavaca", "Clínica Dental Sonrisa", "Escuela de Música Allegro", "Envíos Rápidos Morelos",
    "Despacho Contable Vega", "Arquitectura Verde", "Taller de Costura Progreso", "Lavandería Burbujas",
    "Herrería El Áncora", "Óptica Visión Sur", "Bicicletas Rodada", "Tienda Naturista Semilla",
    "Taller Eléctrico Volta", "Cocinas del Valle", "Ferretería La Llave", "Joyería Destello",
    "Fonda La Morelense", "Vidriería Transparente", "Publicidad Trazo", "Mudanzas Aliadas",
    "Refrigeración Polar", "Hojalatería El Rayo", "Agencia de Viajes Camino", "Editorial Ceiba",
)

DESPACHOS = (
    "Despacho Jurídico Nava y Asociados", "Contadores Ríos, S.C.", "Consultoría Fiscal Morelos",
    "Arquitectos Beltrán y Vega", "Notaría Pública 12",
)

CALLES = (
    "Privada Hidalgo", "Calle Galeana", "Avenida Plan de Ayala", "Calle Humboldt",
    "Prolongación Zapata", "Avenida Atlacomulco", "Calle Nueva China", "Avenida Teopanzolco",
    "Calle Lerdo de Tejada", "Privada Cuauhnáhuac",
)

CLAVES_DEBILES = (
    "123456", "password", "12345678", "bodega", "bodega2013", "ccr2014",
    "morelos", "cuernavaca", "almacen", "123456789", "qwerty", "abc123",
)

NOTAS_PLAIN = (
    "Paga en efectivo en recepción.",
    "Solicita factura mensual.",
    "Solo localizable por teléfono fijo.",
    "Ingresó por recomendación de otro cliente.",
    "Cambió de sucursal en el último año.",
    "Deja copia de la llave en recepción.",
    "Requiere aviso dos días antes del pago.",
    "Cliente con dos bodegas en la misma sucursal.",
)

# Notas que ya llevan etiquetas HTML. Sirven de pista de la falla 3: el panel
# las dibuja como formato en lugar de mostrarlas tal cual.
NOTAS_HTML = (
    "<b>Pago en efectivo.</b>",
    "<i>Factura mensual</i>",
    "<b>No</b> avisar por teléfono, solo por correo.",
    "<i>Adeudo pendiente de la bodega 12.</i>",
)

PERSONAL = (
    # usuario, nombre, correo, clave, rol
    ("soporte", "Itzel Ramírez Cortés", "soporte@ccr-almacenes.example", "ccr2014", "admin"),
    ("admin", "Administrador", "admin@ccr-almacenes.example", "admin", "admin"),
    ("r.beltran", "Rocío Beltrán Nava", "r.beltran@ccr-almacenes.example", "Morelos#2019", "encargado"),
    ("m.tapia", "Marco Antonio Tapia Ruiz", "m.tapia@ccr-almacenes.example", "Industrial.21", "encargado"),
    ("j.dominguez", "Juan Carlos Domínguez Solís", "j.dominguez@ccr-almacenes.example", "Norte2018$", "encargado"),
    ("v.salgado", "Verónica Salgado Ríos", "v.salgado@ccr-almacenes.example", "cobranza", "cobranza"),
    ("l.fuentes", "Luis Enrique Fuentes Bravo", "l.fuentes@ccr-almacenes.example", "recepcion1", "recepcion"),
    ("s.marquez", "Sofía Márquez Lozano", "s.marquez@ccr-almacenes.example", "Arco2020.", "admin"),
)


def md5(texto):
    """Sin sal y sin estiramiento. Es la falla 5, a proposito."""
    return hashlib.md5(texto.encode("utf-8")).hexdigest()


def sin_acentos(texto):
    tabla = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")
    return texto.translate(tabla)


def correo_persona(nombre):
    partes = sin_acentos(nombre).lower().split()
    return f"{partes[0]}.{partes[-1]}"


def rfc_persona(nombre, nacimiento):
    partes = sin_acentos(nombre).upper().split()
    letras = (partes[0][0] + partes[1][0] + partes[-1][0] + partes[-1][1]).replace("Ñ", "X")
    return f"{letras}{nacimiento:%y%m%d}H3A"


def rfc_empresa(nombre, alta):
    limpio = "".join(letra for letra in sin_acentos(nombre).upper() if letra.isalpha())
    return f"{limpio[:3]}{alta:%y%m%d}ABC"


def fecha_al_azar(rng, desde, hasta):
    dias = (hasta - desde).days
    return desde + timedelta(days=rng.randint(0, max(dias, 1)))


def construir(rng):
    sucursales, bodegas = [], []
    for indice, (clave, nombre, direccion, telefono, total, precio_metro) in enumerate(SUCURSALES, start=1):
        sucursales.append({
            "id": indice, "clave": clave, "nombre": nombre,
            "direccion": direccion, "telefono": telefono,
        })
        for numero in range(1, total + 1):
            metros = rng.choice(METROS)
            bodegas.append({
                "id": len(bodegas) + 1,
                "sucursal_id": indice,
                "numero": f"{clave}-{numero:02d}",
                "metros": metros,
                "precio": int(metros * precio_metro),
                "estado": "libre",
            })

    empresas_usadas = rng.sample(EMPRESAS, 30)
    clientes = []
    for indice in range(1, 151):
        if indice <= 30:
            tipo = "empresa"
            nombre = empresas_usadas[indice - 1]
            correo = f"contacto{indice}@" + sin_acentos(nombre).lower().replace(" ", "").replace(",", "").replace(".", "")[:18] + ".example"
            nacimiento = None
        elif indice <= 35:
            tipo = "despacho"
            nombre = DESPACHOS[indice - 31]
            correo = f"contacto{indice}@despachos.example"
            nacimiento = None
        else:
            tipo = "persona"
            completo = f"{rng.choice(NOMBRES_H + NOMBRES_M)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"
            nombre = completo
            nacimiento = fecha_al_azar(rng, date(1962, 1, 1), date(2001, 12, 31))
            correo = f"{correo_persona(completo)}{indice}@correo.example"

        rfc = rfc_empresa(nombre, date(2014, 1, 1)) if nacimiento is None else rfc_persona(nombre, nacimiento)

        if indice % 9 == 0:
            nota = rng.choice(NOTAS_HTML)
        elif indice % 5 == 0:
            nota = rng.choice(NOTAS_PLAIN)
        else:
            nota = ""

        clientes.append({
            "id": indice,
            "tipo": tipo,
            "nombre": nombre,
            "rfc": rfc,
            "correo": correo,
            "telefono": f"777 {rng.randint(100, 999)} {rng.randint(1000, 9999)}",
            "nota": nota,
            "creado": fecha_al_azar(rng, date(2014, 2, 1), HOY - timedelta(days=30)),
        })

    # Cada bodega con contrato vigente queda ocupada. Los demas contratos son
    # historicos, de clientes que ya se fueron.
    rng.shuffle(bodegas)
    activas = [b for b in bodegas[:48]]
    contratos, comprobantes, ocupadas = [], [], []
    for numero, bodega in enumerate(activas, start=1):
        cliente = rng.choice(clientes)
        bodega["estado"] = "ocupada"
        inicio = fecha_al_azar(rng, HOY - timedelta(days=700), HOY - timedelta(days=40))
        contratos.append({
            "id": numero, "cliente_id": cliente["id"], "bodega_id": bodega["id"],
            "inicio": inicio, "mensualidad": bodega["precio"],
            "deposito": bodega["precio"], "estado": "vigente",
        })
        ocupadas.append({"bodega": bodega, "cliente": cliente})

    for bodega in bodegas:
        if bodega["estado"] == "libre" and rng.random() < 0.12:
            bodega["estado"] = "mantenimiento"

    for _ in range(252):
        bodega = rng.choice(bodegas)
        cliente = rng.choice(clientes)
        inicio = fecha_al_azar(rng, date(2014, 3, 1), HOY - timedelta(days=200))
        meses = rng.randint(3, 24)
        contratos.append({
            "id": len(contratos) + 1, "cliente_id": cliente["id"], "bodega_id": bodega["id"],
            "inicio": inicio, "mensualidad": bodega["precio"],
            "deposito": bodega["precio"],
            "estado": "cancelado" if rng.random() < 0.08 else "terminado",
        })

    for contrato in contratos:
        meses = 4 if contrato["estado"] == "vigente" else rng.randint(1, 2)
        for atras in range(meses):
            periodo = (HOY.replace(day=1) - timedelta(days=31 * atras)).replace(day=1)
            comprobantes.append({
                "id": len(comprobantes) + 1,
                "contrato_id": contrato["id"],
                "periodo": f"{periodo:%Y-%m}",
                "monto": contrato["mensualidad"],
                "archivo": f"comprobante-{contrato['id']}-{periodo:%Y%m}.pdf",
                "subido": periodo + timedelta(days=rng.randint(1, 8)),
            })

    usuarios = []
    for indice, (usuario, nombre, correo, clave, rol) in enumerate(PERSONAL, start=1):
        usuarios.append({
            "id": indice, "usuario": usuario, "nombre": nombre, "correo": correo,
            "hash": md5(clave), "rol": rol,
            "sucursal_id": indice - 1 if rol == "encargado" else None,
            "activo": 1,
        })

    # Una cuenta de cliente por cada cliente con contrato vigente, con clave de
    # la lista corta. Se repite el cliente en varios contratos, pero la cuenta
    # es una sola.
    vistos = set()
    for contrato in contratos:
        if contrato["estado"] != "vigente":
            continue
        cliente = clientes[contrato["cliente_id"] - 1]
        if cliente["correo"] in vistos:
            continue
        vistos.add(cliente["correo"])
        usuarios.append({
            "id": len(usuarios) + 1,
            "usuario": cliente["correo"].split("@")[0],
            "nombre": cliente["nombre"],
            "correo": cliente["correo"],
            "hash": md5(rng.choice(CLAVES_DEBILES)),
            "rol": "cliente",
            "sucursal_id": None,
            "activo": 1,
        })

    return sucursales, bodegas, clientes, contratos, comprobantes, usuarios, ocupadas


ESQUEMA = """
CREATE TABLE sucursales (
    id INTEGER PRIMARY KEY,
    clave TEXT NOT NULL,
    nombre TEXT NOT NULL,
    direccion TEXT NOT NULL,
    telefono TEXT NOT NULL
);

CREATE TABLE bodegas (
    id INTEGER PRIMARY KEY,
    sucursal_id INTEGER NOT NULL REFERENCES sucursales(id),
    numero TEXT NOT NULL,
    metros REAL NOT NULL,
    precio INTEGER NOT NULL,
    estado TEXT NOT NULL
);

CREATE TABLE clientes (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    rfc TEXT,
    correo TEXT NOT NULL,
    telefono TEXT,
    nota TEXT,
    creado TEXT NOT NULL
);

CREATE TABLE contratos (
    id INTEGER PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    bodega_id INTEGER NOT NULL REFERENCES bodegas(id),
    inicio TEXT NOT NULL,
    mensualidad INTEGER NOT NULL,
    deposito INTEGER NOT NULL,
    estado TEXT NOT NULL
);

CREATE TABLE comprobantes (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    periodo TEXT NOT NULL,
    monto INTEGER NOT NULL,
    archivo TEXT NOT NULL,
    subido TEXT NOT NULL
);

CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY,
    usuario TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    correo TEXT NOT NULL,
    hash TEXT NOT NULL,
    rol TEXT NOT NULL,
    sucursal_id INTEGER,
    activo INTEGER NOT NULL
);

CREATE TABLE secretos (
    id INTEGER PRIMARY KEY,
    valor TEXT NOT NULL
);
"""


def escribir(ruta_base, datos):
    sucursales, bodegas, clientes, contratos, comprobantes, usuarios, _ = datos
    ruta_db = ruta_base / "ccr.db"
    if ruta_db.exists():
        ruta_db.unlink()

    con = sqlite3.connect(ruta_db)
    con.executescript(ESQUEMA)
    con.executemany(
        "INSERT INTO sucursales VALUES (?, ?, ?, ?, ?)",
        [(s["id"], s["clave"], s["nombre"], s["direccion"], s["telefono"]) for s in sucursales],
    )
    con.executemany(
        "INSERT INTO bodegas VALUES (?, ?, ?, ?, ?, ?)",
        [(b["id"], b["sucursal_id"], b["numero"], b["metros"], b["precio"], b["estado"]) for b in bodegas],
    )
    con.executemany(
        "INSERT INTO clientes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(c["id"], c["tipo"], c["nombre"], c["rfc"], c["correo"], c["telefono"], c["nota"], f"{c['creado']}")
         for c in clientes],
    )
    con.executemany(
        "INSERT INTO contratos VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(c["id"], c["cliente_id"], c["bodega_id"], f"{c['inicio']}", c["mensualidad"], c["deposito"], c["estado"])
         for c in contratos],
    )
    con.executemany(
        "INSERT INTO comprobantes VALUES (?, ?, ?, ?, ?, ?)",
        [(c["id"], c["contrato_id"], c["periodo"], c["monto"], c["archivo"], f"{c['subido']}")
         for c in comprobantes],
    )
    con.executemany(
        "INSERT INTO usuarios VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(u["id"], u["usuario"], u["nombre"], u["correo"], u["hash"], u["rol"], u["sucursal_id"], u["activo"])
         for u in usuarios],
    )
    # Tabla de secretos: solo alcanzable por UNION SELECT, no por consulta directa.
    con.execute("INSERT INTO secretos (valor) VALUES (?)", ("CCR{union_select_ok}",))
    con.commit()

    # El respaldo que el backup.sh del sitio dejaria en su propia raiz.
    # secretos no se vuelca: su unico vector es la inyeccion SQL (falla 12).
    with open(ruta_base / "respaldo.sql", "w", encoding="utf-8") as archivo:
        for linea in con.iterdump():
            if "secretos" not in linea.lower():
                archivo.write(linea + "\n")
    con.close()
    return ruta_db


def main():
    parser = argparse.ArgumentParser(description="Genera los datos ficticios de CCR.")
    parser.add_argument("--semilla", type=int, default=2014, help="semilla del generador (por defecto 2014)")
    parser.add_argument("--salida", type=Path, default=Path(__file__).resolve().parent,
                        help="carpeta donde escribir ccr.db y respaldo.sql")
    args = parser.parse_args()

    args.salida.mkdir(parents=True, exist_ok=True)
    rng = Random(args.semilla)
    datos = construir(rng)
    ruta_db = escribir(args.salida, datos)

    sucursales, bodegas, clientes, contratos, comprobantes, usuarios, ocupadas = datos
    print(f"Base: {ruta_db}")
    print(f"Sucursales: {len(sucursales)}")
    print(f"Bodegas: {len(bodegas)} "
          f"({sum(1 for b in bodegas if b['estado'] == 'ocupada')} ocupadas, "
          f"{sum(1 for b in bodegas if b['estado'] == 'libre')} libres, "
          f"{sum(1 for b in bodegas if b['estado'] == 'mantenimiento')} en mantenimiento)")
    print(f"Clientes: {len(clientes)}")
    print(f"Contratos: {len(contratos)} "
          f"({sum(1 for c in contratos if c['estado'] == 'vigente')} vigentes)")
    print(f"Comprobantes: {len(comprobantes)}")
    print(f"Usuarios: {len(usuarios)} "
          f"({sum(1 for u in usuarios if u['rol'] == 'cliente')} clientes, "
          f"{sum(1 for u in usuarios if u['rol'] != 'cliente')} de CCR)")
    print(f"Respaldo: {args.salida / 'respaldo.sql'}")
    print(f"Notas con HTML: {sum(1 for c in clientes if '<' in c['nota'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
