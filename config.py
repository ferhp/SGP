# Configuración de la aplicación.
# La base de datos principal es MariaDB; los parámetros se toman de variables
# de entorno (GP_DB_*) para no dejar credenciales en el código.
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DATA = os.path.join(BASE_DIR, "App_Data")

# Ruta de archivos del sistema donde se guardan las facturas adjuntas
# (XML y PDF) de los movimientos contables.
FACTURAS_DIR = os.environ.get("GP_FACTURAS_DIR", os.path.join(APP_DATA, "facturas"))

SECRET_KEY = os.environ.get("GP_SECRET_KEY", "cambiar-esta-clave-en-produccion")

# --- MariaDB -----------------------------------------------------------------
DB_HOST = os.environ.get("GP_DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("GP_DB_PORT", "3306")
DB_USER = os.environ.get("GP_DB_USER", "gestion")
DB_PASSWORD = os.environ.get("GP_DB_PASSWORD", "gestion123")
DB_NAME = os.environ.get("GP_DB_NAME", "gestion_proyectos")

MARIADB_URI = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)

# Respaldo para desarrollo cuando el servidor MariaDB no está disponible.
SQLITE_URI = "sqlite:///" + os.path.join(APP_DATA, "gestion_proyectos.db").replace("\\", "/")

# --- Autenticación SSO (OpenID Connect) ----------------------------------------
# Compatible con cualquier IdP OIDC: Microsoft Entra ID, Google Workspace,
# Keycloak, Okta, etc. Si el cliente no está configurado, la app entra en
# "modo desarrollo": un inicio de sesión local que simula el SSO.
#
#   Entra ID:  GP_OIDC_ISSUER=https://login.microsoftonline.com/<tenant_id>/v2.0
#   Google:    GP_OIDC_ISSUER=https://accounts.google.com
#   Keycloak:  GP_OIDC_ISSUER=https://<host>/realms/<realm>
OIDC_ISSUER = os.environ.get("GP_OIDC_ISSUER", "")
OIDC_CLIENT_ID = os.environ.get("GP_OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = os.environ.get("GP_OIDC_CLIENT_SECRET", "")
OIDC_SCOPES = os.environ.get("GP_OIDC_SCOPES", "openid profile email")
OIDC_HABILITADO = bool(OIDC_ISSUER and OIDC_CLIENT_ID and OIDC_CLIENT_SECRET)

# Correos que reciben rol Admin en su primer inicio de sesión (separados por coma).
ADMIN_CORREOS = {
    c.strip().lower()
    for c in os.environ.get("GP_ADMIN_CORREOS", "admin@constructora.mx").split(",")
    if c.strip()
}

# Departamento asignado a los usuarios nuevos que entran por SSO.
DEPARTAMENTO_NUEVOS = os.environ.get("GP_DEPARTAMENTO_NUEVOS", "Proyectos")

# --- Vistas por departamento ---------------------------------------------------
# Cada departamento ve únicamente los módulos que le corresponden.
# "dashboard" y "buscar" siempre están disponibles.
DEPARTAMENTOS = {
    "Dirección": ["proyectos", "costos", "contabilidad", "empleados", "nomina"],
    "Proyectos": ["proyectos", "costos"],
    "Costos": ["costos", "proyectos"],
    "Contabilidad": ["contabilidad", "costos", "nomina"],
    "Recursos Humanos": ["empleados", "nomina"],
    "Nómina": ["nomina", "empleados"],
}
DEPARTAMENTO_DEFAULT = "Dirección"

MODULOS = {
    "proyectos": {"titulo": "Proyectos", "icono": "engineering"},
    "costos": {"titulo": "Costos", "icono": "payments"},
    "contabilidad": {"titulo": "Contabilidad", "icono": "account_balance"},
    "empleados": {"titulo": "Empleados", "icono": "groups"},
    "nomina": {"titulo": "Nómina", "icono": "receipt_long"},
}
