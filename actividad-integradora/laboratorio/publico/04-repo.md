# ccr-bodegas

Respaldo del código del sitio de Almacenes CCR. Se subió para no perderlo cuando cambiaron la máquina de desarrollo.

## Archivos

```text
ccr-bodegas/
├── README.md
├── config.py
├── sesion.py
├── backup.sh
└── requirements.txt
```

## README.md

```text
# CCR-Bodegas v2.1

Sitio de catálogo, alta de clientes y comprobantes de pago.

## Instalación

pip install -r requirements.txt
python app.py

## Notas

- La base vive en ccr.db, junto al código.
- El panel del encargado (versión 2013) se sirve en /admin-viejo.
- El panel nuevo está en /panel y requiere sesión.
- No subir credenciales al repo.
```

## config.py

```python
# CCR-Bodegas v2.1 - configuracion de produccion (respaldo)
# Autor: Sistemas Alarcon, S.C.

DEBUG = False

DB_HOST = "localhost"
DB_USER = "soporte"
DB_PASS = "ccr2014"
DB_NAME = "ccr.db"

ADMIN_PANEL = "/admin-viejo"
SECRET = "ccr"

MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB max por archivo subido
```

## sesion.py

```python
# sesion.py - Modulo de sesiones de CCR-Bodegas v2.1
# Autor: Sistemas Alarcon, S.C. - 2013
# Se importa desde app.py para leer y escribir la cookie de sesion.

import base64
import json


def armar_sesion(usuario, nombre, rol, sucursal):
    datos = {
        "usuario": usuario,
        "nombre": nombre,
        "rol": rol,
        "sucursal": sucursal,
    }
    crudo = json.dumps(datos).encode("utf-8")
    return base64.b64encode(crudo).decode("ascii")


def leer_sesion(valor):
    crudo = base64.b64decode(valor.encode("ascii")).decode("utf-8")
    return json.loads(crudo)
```

## backup.sh

```sh
#!/bin/sh
# Respaldo diario de la base. Lo corre el cron a las 23:00.
# El archivo queda en la raiz del sitio para descargarlo desde el panel.
cd /var/www/ccr
sqlite3 ccr.db .dump > respaldo.sql
cp respaldo.sql /var/www/ccr/respaldo.sql
```

## requirements.txt

```text
Flask==3.0.3
waitress==3.0.0
```

---

Última modificación del respaldo: 14 de septiembre de 2021.
