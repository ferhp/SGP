from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base

DEPARTAMENTOS_EMPLEADO = (
    "Obra civil", "Obra eléctrica", "Costos", "Contabilidad",
    "Recursos Humanos", "Administración",
)


class Empleado(Base):
    __tablename__ = "empleados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    puesto: Mapped[str] = mapped_column(String(100), nullable=False)
    departamento: Mapped[str] = mapped_column(
        Enum(*DEPARTAMENTOS_EMPLEADO, name="departamento_empleado"), nullable=False
    )
    correo: Mapped[str] = mapped_column(String(150), default="")
    telefono: Mapped[str] = mapped_column(String(30), default="")
    salario_diario: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    proyecto_id: Mapped[int | None] = mapped_column(
        ForeignKey("proyectos.id", ondelete="SET NULL"), nullable=True
    )

    proyecto = relationship("Proyecto", back_populates="empleados")
    recibos = relationship("ReciboNomina", back_populates="empleado",
                           cascade="all, delete-orphan", lazy="selectin")
