# GestionProyectos (SIGEP)

Aplicación web en **Python (Flask)** con patrón **MVC** e interfaz tipo Google
(**SIGEP**, Sistema de Gestión de Proyectos) para la administración de
proyectos **civiles y eléctricos** de una
constructora. Los módulos están integrados para dar seguimiento a cada
proyecto dado de alta: costos, contabilidad, empleados y nómina se consultan
desde la ficha del proyecto.

## Módulos

| Módulo | Funcionalidad |
|---|---|
| **Proyectos** | Alta/edición/baja de obras (civiles o eléctricas), avance físico, presupuesto, estado y ficha integrada con costos, movimientos contables, personal asignado y nómina del proyecto. |
| **Costos** | Registro de costos por proyecto y categoría (materiales, mano de obra, maquinaria, subcontratos, indirectos) con filtros y totales. El proveedor se elige por listbox desde el **catálogo de proveedores** (con su propia administración: alta, edición y baja). La captura (apartado de registro rápido, alta, edición y borrado) requiere el permiso **captura de costos**; sin él, la vista es de consulta. |
| **Contabilidad** | Ingresos y egresos por cuenta, con referencia de factura/póliza, ligados a un proyecto o generales. |
| **Empleados** | Plantilla del personal por departamento y asignación a proyectos. |
| **Nómina** | Generación de recibos por periodo para la plantilla activa (percepciones = salario diario × días; deducciones simplificadas ISR 9 % + IMSS 3 %). |
| **Usuarios** | (solo rol Admin) administración de las cuentas SSO: rol, departamento, activación y permisos (p. ej. captura de costos; los Admin tienen todos los permisos). |

Además: **búsqueda global** tipo Google (proyectos, empleados, costos) y
**panel general** con indicadores.

## Vistas por departamento

Cada usuario pertenece a un departamento que define los módulos que ve:

| Departamento | Módulos visibles |
|---|---|
| Dirección | todos (y puede cambiar de vista con el selector superior) |
| Proyectos | Proyectos, Costos |
| Costos | Costos, Proyectos |
| Contabilidad | Contabilidad, Costos, Nómina |
| Recursos Humanos | Empleados, Nómina |
| Nómina | Nómina, Empleados |

El acceso se aplica en el servidor (no solo en el menú).

## Autenticación SSO (OpenID Connect)

El inicio de sesión se delega a un proveedor de identidad corporativo
mediante OIDC (flujo *authorization code* con [Authlib](https://authlib.org)).
Compatible con Microsoft Entra ID, Google Workspace, Keycloak, Okta, etc.

Variables de entorno:

| Variable | Descripción |
|---|---|
| `GP_OIDC_ISSUER` | Emisor OIDC. Entra ID: `https://login.microsoftonline.com/<tenant_id>/v2.0` · Google: `https://accounts.google.com` · Keycloak: `https://<host>/realms/<realm>` |
| `GP_OIDC_CLIENT_ID` / `GP_OIDC_CLIENT_SECRET` | Credenciales de la aplicación registrada en el IdP. |
| `GP_OIDC_SCOPES` | Alcances (por defecto `openid profile email`). |
| `GP_ADMIN_CORREOS` | Correos que reciben rol **Admin** en su primer acceso (separados por coma). |
| `GP_DEPARTAMENTO_NUEVOS` | Departamento asignado a usuarios nuevos (por defecto `Proyectos`). |

En el IdP registre la URL de redirección: `http://<host>:5090/callback`.

> **Modo desarrollo:** con `GP_MODO_DEV=1` y sin las variables `GP_OIDC_*`, la
> app muestra un acceso local que simula el SSO (basta un correo). La cuenta
> inicial `admin@constructora.mx` tiene rol Admin. Sin `GP_MODO_DEV`, la app
> exige la configuración completa (SSO, `GP_SECRET_KEY`, `GP_DB_PASSWORD`) y
> se niega a arrancar si falta algo.

### MFA (verificación en dos pasos)

Además del SSO, cada usuario puede activar un segundo factor **TOTP**
(Google Authenticator, Microsoft Authenticator, Authy…):

- Se activa desde el menú de usuario → **MFA**: la app muestra un código QR
  (o la clave manual) y se confirma con el primer código de 6 dígitos.
- Un **Admin** puede marcar **"Requerir MFA"** al agregar o editar un usuario:
  en su próximo inicio de sesión, el sistema le mostrará la vista de
  configuración (QR para su dispositivo móvil) y no podrá entrar hasta
  completarla. En el módulo Usuarios, esas cuentas aparecen como
  "Pendiente de configurar".
- A partir de entonces, cada inicio de sesión pide el código vigente después
  del SSO; sin él no se abre la sesión.
- Si el usuario pierde su dispositivo, un **Admin** puede restablecer su MFA
  desde Usuarios → Editar (el usuario vuelve a entrar solo con SSO y puede
  configurarla de nuevo). El propio usuario puede desactivarla con un código
  vigente.
- El estado del MFA de cada cuenta es visible en el módulo Usuarios.

## Base de datos: MariaDB

La app usa **MariaDB** vía SQLAlchemy + PyMySQL. Configuración por variables
de entorno: `GP_DB_HOST`, `GP_DB_PORT`, `GP_DB_USER`, `GP_DB_PASSWORD`,
`GP_DB_NAME` (por defecto `127.0.0.1:3306`, usuario `gestion`, BD
`gestion_proyectos`).

- `db/schema_mariadb.sql` crea la base, el usuario y las tablas (la app
  también crea las tablas automáticamente al arrancar con `create_all`).
- Si el servidor MariaDB no responde al arrancar, la app usa **SQLite** en
  `App_Data/` como respaldo de desarrollo y lo indica en la barra lateral.
- Al primer arranque con la base vacía se insertan datos de ejemplo.

## Ejecución

```bash
cd GestionProyectos
pip install -r requirements.txt
GP_MODO_DEV=1 python app.py   # http://127.0.0.1:5090 (desarrollo local)
```

En Windows (PowerShell): `$env:GP_MODO_DEV = "1"; python app.py`.

En producción **no** defina `GP_MODO_DEV`. La app entonces exige
`GP_SECRET_KEY` (clave aleatoria de al menos 32 bytes), `GP_DB_PASSWORD`,
las variables `GP_OIDC_*`, sirve con **waitress** (WSGI) en lugar del
servidor de desarrollo de Flask, marca las cookies como `Secure` (requiere
HTTPS, p. ej. detrás de un proxy TLS) y no permite el respaldo SQLite ni el
acceso local de desarrollo. Variables adicionales: `GP_SESION_HORAS`
(caducidad de la sesión, por defecto 8), `GP_COOKIES_SEGURAS` (fuerza cookies
seguras también en desarrollo) y `GP_OIDC_CONFIAR_CORREO` (permite vincular
cuentas por correo cuando el IdP verifica los correos pero no envía el claim
`email_verified`).

Las acciones sensibles (altas/cambios de usuarios, restablecimiento de MFA,
eliminaciones y exportaciones con datos personales) quedan en la tabla
`auditorias`.

> En esta máquina hay un Python embebido en `_tools/python` y el wrapper
> `_tools/rungp.cmd` que arranca la app restaurando las variables de entorno
> que el sandbox elimina.

## Estructura MVC

```
GestionProyectos/
├── app.py                  # punto de entrada: registra blueprints, auth y filtros
├── config.py               # MariaDB, OIDC y vistas por departamento
├── seed.py                 # datos de ejemplo (solo con BD vacía)
├── models/                 # M: SQLAlchemy (Proyecto, Empleado, Costo,
│                           #    MovimientoContable, ReciboNomina, Usuario)
├── controllers/            # C: blueprints (dashboard, proyectos, costos,
│                           #    contabilidad, empleados, nomina, auth, usuarios)
├── views/                  # V: plantillas Jinja2 (layout tipo Google + módulos)
├── static/css/estilo.css   # estilos Material/Google
└── db/schema_mariadb.sql   # esquema para MariaDB
```
