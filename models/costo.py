from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base

CATEGORIAS = (
    "Materiales", "Mano de obra", "Maquinaria y equipo",
    "Subcontratos", "Indirectos",
)


class Costo(Base):
    __tablename__ = "costos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proyecto_id: Mapped[int] = mapped_column(
        ForeignKey("proyectos.id", ondelete="CASCADE"), nullable=False
    )
    categoria: Mapped[str] = mapped_column(
        Enum(*CATEGORIAS, name="categoria_costo"), nullable=False
    )
    concepto: Mapped[str] = mapped_column(String(200), nullable=False)
    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)

    proyecto = relationship("Proyecto", back_populates="costos")
    proveedor = relationship("Proveedor", back_populates="costos", lazy="selectin")
