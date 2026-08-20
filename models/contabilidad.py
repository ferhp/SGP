from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base

TIPOS_MOVIMIENTO = ("Ingreso", "Egreso")

CUENTAS = (
    "Bancos", "Clientes", "Proveedores", "Anticipos de clientes",
    "Gastos de operación", "Impuestos", "Otros",
)


class MovimientoContable(Base):
    __tablename__ = "movimientos_contables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proyecto_id: Mapped[int | None] = mapped_column(
        ForeignKey("proyectos.id", ondelete="SET NULL"), nullable=True
    )
    tipo: Mapped[str] = mapped_column(
        Enum(*TIPOS_MOVIMIENTO, name="tipo_movimiento"), nullable=False
    )
    cuenta: Mapped[str] = mapped_column(
        Enum(*CUENTAS, name="cuenta_contable"), nullable=False
    )
    referencia: Mapped[str] = mapped_column(String(50), default="")  # factura / póliza
    concepto: Mapped[str] = mapped_column(String(200), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    # Factura adjunta: nombres de archivo dentro de config.FACTURAS_DIR.
    archivo_xml: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archivo_pdf: Mapped[str | None] = mapped_column(String(255), nullable=True)

    proyecto = relationship("Proyecto", back_populates="movimientos")
