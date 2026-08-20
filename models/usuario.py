from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models import Base

ROLES = ("Admin", "Usuario")

GENEROS = ("Femenino", "Masculino", "Otro")

# Debe coincidir con las vistas por departamento definidas en config.DEPARTAMENTOS.
DEPARTAMENTOS_USUARIO = (
    "Dirección", "Proyectos", "Costos", "Contabilidad",
    "Recursos Humanos", "Nómina",
)


class Usuario(Base):
    """Usuario autenticado por SSO (OpenID Connect).

    `sub` es el identificador único que entrega el proveedor de identidad;
    el rol y el departamento controlan qué módulos puede ver en la app.
    Incluye los datos personales y laborales del expediente del usuario.
    """

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    correo: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    apellido_paterno: Mapped[str] = mapped_column(String(80), default="")
    apellido_materno: Mapped[str] = mapped_column(String(80), default="")
    nss: Mapped[str] = mapped_column(String(15), default="")
    curp: Mapped[str] = mapped_column(String(18), default="")
    rfc: Mapped[str] = mapped_column(String(13), default="")
    direccion: Mapped[str] = mapped_column(String(250), default="")
    telefono: Mapped[str] = mapped_column(String(30), default="")
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    genero: Mapped[str] = mapped_column(String(20), default="")
    fecha_ingreso: Mapped[date | None] = mapped_column(Date, nullable=True)
    puesto: Mapped[str] = mapped_column(String(100), default="")
    rol: Mapped[str] = mapped_column(
        Enum(*ROLES, name="rol_usuario"), default="Usuario", nullable=False
    )
    departamento: Mapped[str] = mapped_column(
        Enum(*DEPARTAMENTOS_USUARIO, name="departamento_usuario"),
        default="Proyectos", nullable=False,
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Permiso de captura en el módulo de Costos: quien lo tiene puede registrar,
    # editar y eliminar costos; el resto solo consulta. Los Admin siempre pueden.
    captura_costos: Mapped[bool] = mapped_column(Boolean, default=False)
    # MFA (verificación en dos pasos con TOTP): el secreto se genera al
    # activarla desde la app y se pide un código de 6 dígitos en cada acceso.
    # `mfa_requerido` lo marca el administrador: en el siguiente inicio de
    # sesión, el usuario deberá configurar el MFA en su dispositivo móvil
    # antes de entrar.
    mfa_requerido: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_habilitado: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secreto: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def puede_capturar_costos(self) -> bool:
        return self.rol == "Admin" or bool(self.captura_costos)

    @property
    def nombre_completo(self) -> str:
        partes = [self.nombre, self.apellido_paterno, self.apellido_materno]
        return " ".join(p for p in partes if p)
