# Bitácora de auditoría: deja rastro de quién ejecutó las acciones sensibles
# (cambios de cuentas y roles, restablecimiento de MFA, eliminaciones y
# exportaciones con datos personales).
from datetime import datetime

from flask import g
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models import Base, db_session


class Auditoria(Base):
    __tablename__ = "auditorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now,
                                            nullable=False)
    usuario: Mapped[str] = mapped_column(String(150), nullable=False)
    accion: Mapped[str] = mapped_column(String(80), nullable=False)
    detalle: Mapped[str] = mapped_column(String(400), default="")


def registrar(accion: str, detalle: str = "") -> None:
    """Agrega un registro de auditoría y lo confirma de inmediato.

    Se llama después del commit de la acción auditada, para que un fallo en
    la bitácora nunca revierta la operación (ni al revés).
    """
    actor = getattr(g, "usuario", None)
    db_session.add(Auditoria(
        usuario=actor.correo if actor else "(sistema)",
        accion=accion,
        detalle=detalle[:400],
    ))
    db_session.commit()
