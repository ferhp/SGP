# Controlador del panel principal y de la búsqueda global tipo Google.
from decimal import Decimal

from flask import Blueprint, render_template, request
from sqlalchemy import or_

from models import db_session
from models.contabilidad import MovimientoContable
from models.costo import Costo
from models.empleado import Empleado
from models.nomina import ReciboNomina
from models.proveedor import Proveedor
from models.proyecto import Proyecto

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    proyectos = db_session.query(Proyecto).order_by(Proyecto.clave).all()
    activos = [p for p in proyectos if p.estado == "En curso"]
    presupuesto_total = sum((p.presupuesto or Decimal("0") for p in proyectos), Decimal("0"))
    costo_total = sum((p.costo_total for p in proyectos), Decimal("0"))
    empleados_activos = db_session.query(Empleado).filter_by(activo=True).count()
    ingresos = sum((p.ingresos for p in proyectos), Decimal("0"))
    egresos = sum((p.egresos for p in proyectos), Decimal("0"))
    nomina_total = sum(
        (r.neto for r in db_session.query(ReciboNomina).all()), Decimal("0")
    )
    return render_template(
        "dashboard.html",
        proyectos=proyectos,
        total_proyectos=len(proyectos),
        proyectos_activos=len(activos),
        presupuesto_total=presupuesto_total,
        costo_total=costo_total,
        empleados_activos=empleados_activos,
        ingresos=ingresos,
        egresos=egresos,
        nomina_total=nomina_total,
    )


@bp.route("/buscar")
def buscar():
    q = (request.args.get("q") or "").strip()
    proyectos, empleados, costos = [], [], []
    if q:
        like = f"%{q}%"
        proyectos = (
            db_session.query(Proyecto)
            .filter(or_(Proyecto.nombre.ilike(like), Proyecto.clave.ilike(like),
                        Proyecto.cliente.ilike(like), Proyecto.ubicacion.ilike(like)))
            .all()
        )
        empleados = (
            db_session.query(Empleado)
            .filter(or_(Empleado.nombre.ilike(like), Empleado.puesto.ilike(like)))
            .all()
        )
        costos = (
            db_session.query(Costo)
            .outerjoin(Proveedor, Costo.proveedor_id == Proveedor.id)
            .filter(or_(Costo.concepto.ilike(like), Proveedor.nombre.ilike(like)))
            .all()
        )
    return render_template("buscar.html", q=q, proyectos=proyectos,
                           empleados=empleados, costos=costos)
