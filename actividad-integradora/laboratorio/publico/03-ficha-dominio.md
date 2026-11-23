# Ficha de dominio y servicios

Documento interno del área de sistemas de Almacenes CCR. Se conserva para el control de los servicios contratados y la configuración del servidor de aplicaciones.

## Dominio principal

| Campo | Valor |
| --- | --- |
| Dominio | ccr-almacenes.example |
| Fecha de registro | 12 de marzo de 2013 |
| Registrador | Registro Local de Dominios |
| Estado | Activo |
| Última actualización de DNS | 8 de julio de 2019 |

## Contactos del registro

| Tipo | Nombre | Correo |
| --- | --- | --- |
| Contacto administrativo | Itzel Ramírez Cortés | soporte@ccr-almacenes.example |
| Contacto técnico | Proveedor externo | alarcon@sistemasalarcon.example |
| Contacto de respaldo (desde 2020) | Sofía Márquez Lozano | s.marquez@ccr-almacenes.example |

## Servidores de nombres

- ns1.hosting-local.example
- ns2.hosting-local.example

## Dominio alterno

| Campo | Valor |
| --- | --- |
| Dominio | ccr-bodegas.example |
| Fecha de registro | 12 de marzo de 2013 |
| Estado | Registrado, sin sitio activo |

Se registró el dominio alterno en la misma fecha que el principal, por recomendación del proveedor. Nunca se le publicó contenido. Consérvese el registro para evitar que un tercero lo utilice.

## Configuración del servidor de aplicaciones

| Campo | Valor |
| --- | --- |
| Sistema operativo | Ubuntu 20.04 LTS |
| Servidor web | Waitress (Python) |
| Puerto de la aplicación | 8000 |
| Base de datos | SQLite (archivo ccr.db en el directorio de la aplicación) |
| Ruta del respaldo diario | /var/www/ccr/respaldo.sql |

El servidor corre el sistema desde 2013. La migración a la nueva plataforma está pendiente de presupuesto.

## Servicios contratados

| Servicio | Proveedor | Vigencia |
| --- | --- | --- |
| Hosting | Hosting Local | Anual, renovado en marzo |
| Correo electrónico | Hosting Local | Anual, renovado en marzo |
| Certificado de seguridad (HTTPS) | No contratado | — |

**Nota sobre el certificado:** el proveedor notificó en julio de 2018 que el sitio opera sin cifrado y que la cookie de sesión viaja en texto claro. La Dirección de Administración recibió el aviso. Pendiente de resolución.

---

Sistemas Alarcón, S.C. — Mesa de servicio: 01 777 123 4567
