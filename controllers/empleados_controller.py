# Controlador del módulo de Empleados: plantilla del personal y asignación
# a proyectos.
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for

from exportar import moneda, respuesta_exportacion
from models import db_session
from models.empleado import DEPARTAMENTOS_EMPLEADO, Empleado
from models.proyecto import Proyecto

bp = Blueprint("empleados", __name__, url_prefix="/empleados")


def _consulta_filtrada():
    departamento = request.args.get("departamento") or ""
    consulta = db_session.query(Empleado)
    if departamento in DEPARTAMENTOS_EMPLEADO:
        consulta = consulta.filter(Empleado.departamento == departamento)
    return consulta.order_by(Empleado.nombre).all(), departamento


@bp.route("/")
def lista():
    empleados, departamento = _consulta_filtrada()
    return render_template("empleados/lista.html", empleados=empleados,
                           departamentos=DEPARTAMENTOS_EMPLEADO,
                           filtro_departamento=departamento)


@bp.route("/exportar/<formato>")
def exportar(formato):
    empleados, departamento = _consulta_filtrada()
    titulo = "Empleados"
    if departamento:
        titulo += f" · {departamento}"
    columnas = ("Nombre", "Puesto", "Departamento", "Correo", "Teléfono",
                "Proyecto asignado", "Salario diario", "Estatus")
    filas = [(e.nombre, e.puesto, e.departamento, e.correo or "—",
              e.telefono or "—",
              e.proyecto.clave if e.proyecto else "Disponible",
              moneda(e.salario_diario), "Activo" if e.activo else "Baja")
             for e in empleados]
    return respuesta_exportacion(formato, "empleados", titulo, columnas, filas)


def _cargar_form(empleado: Empleado, form) -> str | None:
    empleado.nombre = (form.get("nombre") or "").strip()
    empleado.puesto = (form.get("puesto") or "").strip()
    empleado.departamento = form.get("departamento") or ""
    empleado.correo = (form.get("correo") or "").strip()
    empleado.telefono = (form.get("telefono") or "").strip()
    empleado.activo = form.get("activo") == "on"
    proyecto_id = form.get("proyecto_id")
    empleado.proyecto_id = int(proyecto_id) if proyecto_id else None
    if not empleado.nombre or not empleado.puesto:
        return "Nombre y puesto son obligatorios."
    if empleado.departamento not in DEPARTAMENTOS_EMPLEADO:
        return "Seleccione un departamento válido."
    if empleado.proyecto_id and not db_session.get(Proyecto, empleado.proyecto_id):
        return "El proyecto seleccionado no existe."
    try:
        empleado.salario_diario = Decimal(form.get("salario_diario") or "0")
        if empleado.salario_diario < 0:
            return "El salario diario no puede ser negativo."
    except ArithmeticError:
        return "Salario diario no válido."
    return None


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    empleado = Empleado(activo=True)
    if request.method == "POST":
        error = _cargar_form(empleado, request.form)
        if error:
            flash(error, "error")
        else:
            db_session.add(empleado)
            db_session.commit()
            flash(f"Empleado {empleado.nombre} dado de alta.", "ok")
            return redirect(url_for("empleados.lista"))
    proyectos = db_session.query(Proyecto).order_by(Proyecto.clave).all()
    return render_template("empleados/form.html", empleado=empleado,
                           departamentos=DEPARTAMENTOS_EMPLEADO,
                           proyectos=proyectos, es_nuevo=True)


@bp.route("/<int:id>/editar", methods=["GET", "POST"])
def editar(id):
    empleado = db_session.get(Empleado, id)
    if not empleado:
        flash("El empleado no existe.", "error")
        return redirect(url_for("empleados.lista"))
    if request.method == "POST":
        error = _cargar_form(empleado, request.form)
        if error:
            db_session.rollback()
            flash(error, "error")
        else:
            db_session.commit()
            flash("Empleado actualizado.", "ok")
            return redirect(url_for("empleados.lista"))
    proyectos = db_session.query(Proyecto).order_by(Proyecto.clave).all()
    return render_template("empleados/form.html", empleado=empleado,
                           departamentos=DEPARTAMENTOS_EMPLEADO,
                           proyectos=proyectos, es_nuevo=False)


@bp.route("/<int:id>/eliminar", methods=["POST"])
def eliminar(id):
    empleado = db_session.get(Empleado, id)
    if empleado:
        db_session.delete(empleado)
        db_session.commit()
        flash("Empleado eliminado.", "ok")
    return redirect(url_for("empleados.lista"))
