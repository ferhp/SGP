from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class ReciboNomina(Base):
    __tablename__ = "recibos_nomina"
    __table_args__ = (
        UniqueConstraint("empleado_id", "periodo", name="uq_recibo_empleado_periodo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empleado_id: Mapped[int] = mapped_column(
        ForeignKey("empleados.id", ondelete="CASCADE"), nullable=False
    )
    periodo: Mapped[str] = mapped_column(String(30), nullable=False)  # p. ej. "2026-08 Q1"
    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False)
    dias_trabajados: Mapped[int] = mapped_column(Integer, nullable=False)
    percepciones: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deducciones: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    neto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    empleado = relationship("Empleado", back_populates="recibos")
