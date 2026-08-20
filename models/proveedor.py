from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class Proveedor(Base):
    """Catálogo de proveedores; los costos se ligan a él por listbox."""

    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    rfc: Mapped[str] = mapped_column(String(13), default="")
    telefono: Mapped[str] = mapped_column(String(30), default="")
    correo: Mapped[str] = mapped_column(String(150), default="")

    costos = relationship("Costo", back_populates="proveedor")
