# Capa de modelos (M de MVC): motor de base de datos y sesión de SQLAlchemy.
#
# El motor principal es MariaDB (mysql+pymysql). Si el servidor no responde al
# arrancar, se usa SQLite como respaldo de desarrollo para que la aplicación
# siga funcionando; la interfaz muestra qué motor está activo.
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker

import config


class Base(DeclarativeBase):
    pass


MOTOR_ACTIVO = "MariaDB"


def _crear_engine():
    global MOTOR_ACTIVO
    try:
        engine = create_engine(
            config.MARIADB_URI,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={"connect_timeout": 4},
        )
        with engine.connect():
            pass
        return engine
    except Exception as exc:  # servidor apagado, credenciales, red, etc.
        if not config.MODO_DEV:
            # En producción una BD caída debe detener el arranque: degradarse
            # en silencio a un archivo local enmascara la falla y deja los
            # datos fuera de los controles del servidor de base de datos.
            raise RuntimeError(
                f"MariaDB no disponible ({exc.__class__.__name__}) y la app no "
                "está en modo desarrollo; corrija la conexión (GP_DB_*)."
            ) from exc
        MOTOR_ACTIVO = "SQLite (respaldo de desarrollo)"
        print(f"[AVISO] MariaDB no disponible ({exc.__class__.__name__}); "
              f"usando respaldo SQLite en App_Data.")
        os.makedirs(config.APP_DATA, exist_ok=True)
        return create_engine(config.SQLITE_URI)


engine = _crear_engine()
db_session = scoped_session(sessionmaker(bind=engine, autoflush=False))

# Los modelos deben importarse antes de create_all para registrar sus tablas.
from models.proyecto import Proyecto            # noqa: E402,F401
from models.empleado import Empleado            # noqa: E402,F401
from models.costo import Costo                  # noqa: E402,F401
from models.contabilidad import MovimientoContable  # noqa: E402,F401
from models.nomina import ReciboNomina          # noqa: E402,F401
from models.proveedor import Proveedor          # noqa: E402,F401
from models.usuario import Usuario              # noqa: E402,F401
from models.auditoria import Auditoria          # noqa: E402,F401


def init_db():
    Base.metadata.create_all(engine)
    _migrar_columnas()
    _migrar_proveedores()


def _migrar_proveedores():
    # Antes, el proveedor de cada costo era texto libre (columna `proveedor`);
    # ahora es un catálogo (tabla proveedores) elegido por listbox. Convierte
    # los nombres ya capturados en registros del catálogo y liga los costos.
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    columnas = {c["name"] for c in inspector.get_columns("costos")}
    with engine.begin() as conn:
        if "proveedor_id" not in columnas:
            conn.execute(text("ALTER TABLE costos ADD COLUMN proveedor_id INT NULL"))
        if "proveedor" in columnas:
            nombres = conn.execute(text(
                "SELECT DISTINCT proveedor FROM costos "
                "WHERE proveedor IS NOT NULL AND proveedor <> ''"
            )).fetchall()
            for (nombre,) in nombres:
                existe = conn.execute(
                    text("SELECT id FROM proveedores WHERE nombre = :n"),
                    {"n": nombre},
                ).first()
                if not existe:
                    conn.execute(
                        text("INSERT INTO proveedores (nombre, rfc, telefono, correo) "
                             "VALUES (:n, '', '', '')"),
                        {"n": nombre},
                    )
            conn.execute(text(
                "UPDATE costos SET proveedor_id = "
                "(SELECT p.id FROM proveedores p WHERE p.nombre = costos.proveedor) "
                "WHERE proveedor IS NOT NULL AND proveedor <> ''"
            ))
            try:
                conn.execute(text("ALTER TABLE costos DROP COLUMN proveedor"))
            except Exception:
                pass  # motores antiguos sin DROP COLUMN: la columna queda sin uso


def _migrar_columnas():
    # create_all no altera tablas existentes; agrega aquí las columnas nuevas
    # que se hayan sumado después del primer despliegue.
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    pendientes = {
        "proyectos": {
            "numero_contrato": "ALTER TABLE proyectos ADD COLUMN numero_contrato VARCHAR(50) DEFAULT ''",
        },
        "usuarios": {
            "captura_costos": "ALTER TABLE usuarios ADD COLUMN captura_costos BOOLEAN DEFAULT 0",
            "mfa_habilitado": "ALTER TABLE usuarios ADD COLUMN mfa_habilitado BOOLEAN DEFAULT 0",
            "mfa_requerido": "ALTER TABLE usuarios ADD COLUMN mfa_requerido BOOLEAN DEFAULT 0",
            "mfa_secreto": "ALTER TABLE usuarios ADD COLUMN mfa_secreto VARCHAR(64) NULL",
            "apellido_paterno": "ALTER TABLE usuarios ADD COLUMN apellido_paterno VARCHAR(80) DEFAULT ''",
            "apellido_materno": "ALTER TABLE usuarios ADD COLUMN apellido_materno VARCHAR(80) DEFAULT ''",
            "nss": "ALTER TABLE usuarios ADD COLUMN nss VARCHAR(15) DEFAULT ''",
            "curp": "ALTER TABLE usuarios ADD COLUMN curp VARCHAR(18) DEFAULT ''",
            "rfc": "ALTER TABLE usuarios ADD COLUMN rfc VARCHAR(13) DEFAULT ''",
            "direccion": "ALTER TABLE usuarios ADD COLUMN direccion VARCHAR(250) DEFAULT ''",
            "telefono": "ALTER TABLE usuarios ADD COLUMN telefono VARCHAR(30) DEFAULT ''",
            "fecha_nacimiento": "ALTER TABLE usuarios ADD COLUMN fecha_nacimiento DATE NULL",
            "genero": "ALTER TABLE usuarios ADD COLUMN genero VARCHAR(20) DEFAULT ''",
            "fecha_ingreso": "ALTER TABLE usuarios ADD COLUMN fecha_ingreso DATE NULL",
            "puesto": "ALTER TABLE usuarios ADD COLUMN puesto VARCHAR(100) DEFAULT ''",
        },
        "movimientos_contables": {
            "archivo_xml": "ALTER TABLE movimientos_contables ADD COLUMN archivo_xml VARCHAR(255) NULL",
            "archivo_pdf": "ALTER TABLE movimientos_contables ADD COLUMN archivo_pdf VARCHAR(255) NULL",
        },
    }
    for tabla, columnas_nuevas in pendientes.items():
        existentes = {c["name"] for c in inspector.get_columns(tabla)}
        for columna, sentencia in columnas_nuevas.items():
            if columna not in existentes:
                with engine.begin() as conn:
                    conn.execute(text(sentencia))
