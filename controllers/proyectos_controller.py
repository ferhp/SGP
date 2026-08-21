# Controlador del módulo de Proyectos: alta, edición, baja y seguimiento
# integrado (costos, contabilidad, personal y nómina de cada proyecto).
import math
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for

from exportar import moneda, respuesta_exportacion
from models import db_session
from models.auditoria import registrar
from models.empleado import Empleado
from models.nomina import ReciboNomina
from models.proyecto import ESTADOS, TIPOS, Proyecto

bp = Blueprint("proyectos", __name__, url_prefix="/proyectos")

# Colores de las series de la gráfica del proyecto (trío categórico seguro
# para daltonismo, tonos Okabe-Ito): presupuesto en azul, costo acumulado
# en naranja e ingresos en verde azulado.
COLOR_PRESUPUESTO = "#2a78d6"
COLOR_COSTO = "#eb6834"
COLOR_INGRESOS = "#009e73"

_MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun",
                 "jul", "ago", "sep", "oct", "nov", "dic")


def _curva_s(proyecto):
    """Series de la curva S del proyecto, todas en % del presupuesto.

    El eje X son las semanas del proyecto con su fecha, del inicio al término
    previsto (u hoy si no hay término). Sobre esas fechas:
    - Presupuesto: el costo total autorizado del proyecto, como referencia
      constante al 100 % (la gráfica la dibuja punteada).
    - Costo acumulado (real): suma acumulada de los costos registrados a cada
      fecha, como % del presupuesto; solo hasta hoy (sin puntos futuros).
    - Ingresos (real): suma acumulada de los movimientos contables de tipo
      Ingreso ligados al proyecto, también como % del presupuesto y hasta hoy.
    """
    inicio = proyecto.fecha_inicio
    fin = proyecto.fecha_fin_prevista or date.today()
    if fin <= inicio:
        fin = inicio + timedelta(days=7)
    semanas = max(1, math.ceil((fin - inicio).days / 7))
    fechas = [min(inicio + timedelta(days=7 * i), fin) for i in range(semanas + 1)]

    presupuesto = float(proyecto.presupuesto or 0)
    costo = float(proyecto.costo_total)
    ingresos_total = float(proyecto.ingresos)
    reales = None
    serie_ingresos = None
    if presupuesto > 0:
        hoy = date.today()

        def acumulada(pares):
            """Serie acumulada de (fecha, monto) como % del presupuesto."""
            pares = sorted(pares, key=lambda par: par[0])
            serie = []
            for f in fechas:
                if f > hoy:
                    serie.append(None)  # las series reales terminan hoy
                else:
                    acumulado = sum(m for fecha_mov, m in pares if fecha_mov <= f)
                    serie.append(round(100 * acumulado / presupuesto, 1))
            return serie

        reales = acumulada((c.fecha, float(c.monto)) for c in proyecto.costos)
        serie_ingresos = acumulada((m.fecha, float(m.monto))
                                   for m in proyecto.movimientos
                                   if m.tipo == "Ingreso")

    return {
        "etiqueta": proyecto.clave,
        "nombre": proyecto.nombre,
        "color_plan": COLOR_PRESUPUESTO,
        "color_costo": COLOR_COSTO,
        "color_ingresos": COLOR_INGRESOS,
        "etiquetas": [f"{f.day:02d} {_MESES_CORTOS[f.month - 1]}" for f in fechas],
        "titulos": [f"Semana {i} · {f.day:02d} {_MESES_CORTOS[f.month - 1]} {f.year}"
                    for i, f in enumerate(fechas)],
        "reales": reales,
        "ingresos_serie": serie_ingresos,
        "presupuesto": presupuesto,
        "costo": costo,
        "ingresos": ingresos_total,
        "uso": proyecto.uso_presupuesto,
    }


def _fecha(valor, requerido=False):
    if not valor:
        if requerido:
            raise ValueError("fecha requerida")
        return None
    return datetime.strptime(valor, "%Y-%m-%d").date()


def _cargar_form(proyecto: Proyecto, form) -> str | None:
    """Copia los datos del formulario al modelo; regresa mensaje de error o None."""
    proyecto.clave = (form.get("clave") or "").strip().upper()
    proyecto.nombre = (form.get("nombre") or "").strip()
    proyecto.tipo = form.get("tipo") or ""
    proyecto.cliente = (form.get("cliente") or "").strip()
    proyecto.ubicacion = (form.get("ubicacion") or "").strip()
    proyecto.descripcion = (form.get("descripcion") or "").strip()
    proyecto.estado = form.get("estado") or "Planeación"
    if not proyecto.clave or not proyecto.nombre or not proyecto.cliente:
        return "Clave, nombre y cliente son obligatorios."
    if proyecto.tipo not in TIPOS:
        return "Seleccione el tipo de proyecto (civil o eléctrico)."
    if proyecto.estado not in ESTADOS:
        return "Estado no válido."
    try:
        proyecto.fecha_inicio = _fecha(form.get("fecha_inicio"), requerido=True)
        proyecto.fecha_fin_prevista = _fecha(form.get("fecha_fin_prevista"))
    except ValueError:
        return "La fecha de inicio es obligatoria (formato AAAA-MM-DD)."
    try:
        proyecto.presupuesto = Decimal(form.get("presupuesto") or "0")
        proyecto.avance = max(0, min(100, int(form.get("avance") or 0)))
    except (ValueError, ArithmeticError):
        return "Presupuesto o avance no válidos."
    return None


def _consulta_filtrada():
    filtro_tipo = request.args.get("tipo") or ""
    filtro_estado = request.args.get("estado") or ""
    consulta = db_session.query(Proyecto)
    if filtro_tipo in TIPOS:
        consulta = consulta.filter(Proyecto.tipo == filtro_tipo)
    if filtro_estado in ESTADOS:
        consulta = consulta.filter(Proyecto.estado == filtro_estado)
    return consulta.order_by(Proyecto.clave).all(), filtro_tipo, filtro_estado


@bp.route("/")
def lista():
    proyectos, filtro_tipo, filtro_estado = _consulta_filtrada()
    return render_template("proyectos/lista.html", proyectos=proyectos,
                           tipos=TIPOS, estados=ESTADOS,
                           filtro_tipo=filtro_tipo, filtro_estado=filtro_estado)


@bp.route("/exportar/<formato>")
def exportar(formato):
    proyectos, filtro_tipo, filtro_estado = _consulta_filtrada()
    titulo = "Proyectos"
    if filtro_tipo:
        titulo += f" · {filtro_tipo}"
    if filtro_estado:
        titulo += f" · {filtro_estado}"
    columnas = ("Clave", "Nombre", "Tipo", "Cliente", "Ubicación", "Inicio",
                "Término previsto", "Estado", "Avance", "Presupuesto",
                "Costo acumulado", "Ingresos", "Egresos")
    filas = [(p.clave, p.nombre, p.tipo, p.cliente, p.ubicacion,
              str(p.fecha_inicio), str(p.fecha_fin_prevista or "—"), p.estado,
              f"{p.avance} %", moneda(p.presupuesto), moneda(p.costo_total),
              moneda(p.ingresos), moneda(p.egresos))
             for p in proyectos]
    return respuesta_exportacion(formato, "proyectos", titulo, columnas, filas)


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    proyecto = Proyecto(fecha_inicio=date.today())
    if request.method == "POST":
        error = _cargar_form(proyecto, request.form)
        if not error and db_session.query(Proyecto).filter_by(clave=proyecto.clave).first():
            error = f"Ya existe un proyecto con la clave {proyecto.clave}."
        if error:
            flash(error, "error")
        else:
            db_session.add(proyecto)
            db_session.commit()
            flash(f"Proyecto {proyecto.clave} dado de alta.", "ok")
            return redirect(url_for("proyectos.detalle", id=proyecto.id))
    return render_template("proyectos/form.html", proyecto=proyecto,
                           tipos=TIPOS, estados=ESTADOS, es_nuevo=True)


@bp.route("/<int:id>")
def detalle(id):
    proyecto = db_session.get(Proyecto, id)
    if not proyecto:
        flash("El proyecto no existe.", "error")
        return redirect(url_for("proyectos.lista"))
    # Nómina relacionada: recibos de los empleados asignados al proyecto.
    ids_empleados = [e.id for e in proyecto.empleados]
    recibos = []
    if ids_empleados:
        recibos = (
            db_session.query(ReciboNomina)
            .filter(ReciboNomina.empleado_id.in_(ids_empleados))
            .order_by(ReciboNomina.fecha_pago.desc())
            .all()
        )
    costo_nomina = sum((r.neto for r in recibos), Decimal("0"))
    disponibles = (
        db_session.query(Empleado)
        .filter(Empleado.activo.is_(True), Empleado.proyecto_id.is_(None))
        .order_by(Empleado.nombre)
        .all()
    )
    return render_template("proyectos/detalle.html", proyecto=proyecto,
                           recibos=recibos, costo_nomina=costo_nomina,
                           empleados_disponibles=disponibles,
                           curva_s=_curva_s(proyecto))


@bp.route("/<int:id>/editar", methods=["GET", "POST"])
def editar(id):
    proyecto = db_session.get(Proyecto, id)
    if not proyecto:
        flash("El proyecto no existe.", "error")
        return redirect(url_for("proyectos.lista"))
    if request.method == "POST":
        error = _cargar_form(proyecto, request.form)
        if not error:
            duplicado = (
                db_session.query(Proyecto)
                .filter(Proyecto.clave == proyecto.clave, Proyecto.id != id)
                .first()
            )
            if duplicado:
                error = f"Ya existe otro proyecto con la clave {proyecto.clave}."
        if error:
            db_session.rollback()
            flash(error, "error")
        else:
            db_session.commit()
            flash("Proyecto actualizado.", "ok")
            return redirect(url_for("proyectos.detalle", id=id))
    return render_template("proyectos/form.html", proyecto=proyecto,
                           tipos=TIPOS, estados=ESTADOS, es_nuevo=False)


@bp.route("/<int:id>/eliminar", methods=["POST"])
def eliminar(id):
    proyecto = db_session.get(Proyecto, id)
    if proyecto:
        detalle = f"{proyecto.clave} — {proyecto.nombre}"
        for empleado in proyecto.empleados:
            empleado.proyecto_id = None
        db_session.delete(proyecto)
        db_session.commit()
        registrar("proyectos.eliminacion", detalle)
        flash(f"Proyecto {proyecto.clave} eliminado.", "ok")
    return redirect(url_for("proyectos.lista"))


@bp.route("/<int:id>/asignar-empleado", methods=["POST"])
def asignar_empleado(id):
    proyecto = db_session.get(Proyecto, id)
    empleado = db_session.get(Empleado, int(request.form.get("empleado_id", 0)))
    if proyecto and empleado:
        empleado.proyecto_id = proyecto.id
        db_session.commit()
        flash(f"{empleado.nombre} asignado a {proyecto.clave}.", "ok")
    return redirect(url_for("proyectos.detalle", id=id))


@bp.route("/<int:id>/liberar-empleado/<int:empleado_id>", methods=["POST"])
def liberar_empleado(id, empleado_id):
    empleado = db_session.get(Empleado, empleado_id)
    if empleado and empleado.proyecto_id == id:
        empleado.proyecto_id = None
        db_session.commit()
        flash(f"{empleado.nombre} liberado del proyecto.", "ok")
    return redirect(url_for("proyectos.detalle", id=id))
