from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base

TIPOS = ("Civil", "Eléctrico")
ESTADOS = ("Planeación", "En curso", "Suspendido", "Terminado")


class Proyecto(Base):
    __tablename__ = "proyectos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clave: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    tipo: Mapped[str] = mapped_column(Enum(*TIPOS, name="tipo_proyecto"), nullable=False)
    cliente: Mapped[str] = mapped_column(String(150), nullable=False)
    ubicacion: Mapped[str] = mapped_column(String(200), default="")
    descripcion: Mapped[str] = mapped_column(Text, default="")
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin_prevista: Mapped[date | None] = mapped_column(Date, nullable=True)
    presupuesto: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    avance: Mapped[int] = mapped_column(Integer, default=0)  # porcentaje 0-100
    estado: Mapped[str] = mapped_column(
        Enum(*ESTADOS, name="estado_proyecto"), default="Planeación", nullable=False
    )

    costos = relationship("Costo", back_populates="proyecto",
                          cascade="all, delete-orphan", lazy="selectin")
    movimientos = relationship("MovimientoContable", back_populates="proyecto",
                               lazy="selectin")
    empleados = relationship("Empleado", back_populates="proyecto", lazy="selectin")

    # --- Totales usados por el seguimiento integrado del proyecto ---
    @property
    def costo_total(self) -> Decimal:
        return sum((c.monto for c in self.costos), Decimal("0"))

    @property
    def ingresos(self) -> Decimal:
        return sum((m.monto for m in self.movimientos if m.tipo == "Ingreso"), Decimal("0"))

    @property
    def egresos(self) -> Decimal:
        return sum((m.monto for m in self.movimientos if m.tipo == "Egreso"), Decimal("0"))

    @property
    def presupuesto_disponible(self) -> Decimal:
        return (self.presupuesto or Decimal("0")) - self.costo_total

    @property
    def uso_presupuesto(self) -> int:
        if not self.presupuesto:
            return 0
        return min(100, int(self.costo_total * 100 / self.presupuesto))
