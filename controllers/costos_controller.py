# Controlador del módulo de Costos: registro de costos por proyecto y categoría.
# Consultar está abierto a los departamentos con acceso al módulo; capturar
# (registrar/editar/eliminar) requiere el permiso "captura_costos" del usuario.
from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from exportar import moneda, respuesta_exportacion
from models import db_session
from models.auditoria import registrar
from models.costo import CATEGORIAS, Costo
from models.proveedor import Proveedor
from models.proyecto import Proyecto

bp = Blueprint("costos", __name__, url_prefix="/costos")


def _sin_permiso_captura():
    """Redirige a la lista si el usuario no puede capturar costos."""
    if g.usuario.puede_capturar_costos:
        return None
    flash("No tiene permiso para capturar costos; solicítelo a un administrador.",
          "error")
    return redirect(url_for("costos.lista"))


def _consulta_filtrada():
    proyecto_id = request.args.get("proyecto", type=int)
    categoria = request.args.get("categoria") or ""
    consulta = db_session.query(Costo)
    if proyecto_id:
        consulta = consulta.filter(Costo.proyecto_id == proyecto_id)
    if categoria in CATEGORIAS:
        consulta = consulta.filter(Costo.categoria == categoria)
    costos = consulta.order_by(Costo.fecha.desc(), Costo.id.desc()).all()
    return costos, proyecto_id, categoria


@bp.route("/")
def lista():
    costos, proyecto_id, categoria = _consulta_filtrada()
    proyectos = db_session.query(Proyecto).order_by(Proyecto.clave).all()
    total = sum((c.monto for c in costos), Decimal("0"))
    return render_template("costos/lista.html", costos=costos, proyectos=proyectos,
                           categorias=CATEGORIAS, filtro_proyecto=proyecto_id,
                           filtro_categoria=categoria, total=total,
                           hoy=date.today(), proveedores=_proveedores())


@bp.route("/exportar/<formato>")
def exportar(formato):
    costos, proyecto_id, categoria = _consulta_filtrada()
    titulo = "Costos"
    if proyecto_id:
        proyecto = db_session.get(Proyecto, proyecto_id)
        if proyecto:
            titulo += f" · {proyecto.clave}"
    if categoria:
        titulo += f" · {categoria}"
    columnas = ("Fecha", "Proyecto", "Categoría", "Concepto", "Proveedor", "Monto")
    filas = [(str(c.fecha), f"{c.proyecto.clave} — {c.proyecto.nombre}",
              c.categoria, c.concepto,
              c.proveedor.nombre if c.proveedor else "—", moneda(c.monto))
             for c in costos]
    total = sum((c.monto for c in costos), Decimal("0"))
    filas.append(("", "", "", "", "TOTAL", moneda(total)))
    return respuesta_exportacion(formato, "costos", titulo, columnas, filas)


# ---- Catálogo de proveedores -------------------------------------------------

def _cargar_proveedor(proveedor: Proveedor, form) -> str | None:
    proveedor.nombre = (form.get("nombre") or "").strip()
    proveedor.rfc = (form.get("rfc") or "").strip().upper()
    proveedor.telefono = (form.get("telefono") or "").strip()
    proveedor.correo = (form.get("correo") or "").strip()
    if not proveedor.nombre:
        return "El nombre del proveedor es obligatorio."
    if proveedor.rfc and len(proveedor.rfc) not in (12, 13):
        return "El RFC debe tener 12 o 13 caracteres."
    duplicado = (
        db_session.query(Proveedor)
        .filter(Proveedor.nombre == proveedor.nombre, Proveedor.id != (proveedor.id or 0))
        .first()
    )
    if duplicado:
        return f"Ya existe un proveedor con el nombre {proveedor.nombre}."
    return None


@bp.route("/proveedores")
def proveedores():
    return render_template("costos/proveedores.html", proveedores=_proveedores())


@bp.route("/proveedores/nuevo", methods=["GET", "POST"])
def proveedor_nuevo():
    bloqueo = _sin_permiso_captura()
    if bloqueo:
        return bloqueo
    proveedor = Proveedor()
    if request.method == "POST":
        error = _cargar_proveedor(proveedor, request.form)
        if error:
            flash(error, "error")
        else:
            db_session.add(proveedor)
            db_session.commit()
            flash(f"Proveedor {proveedor.nombre} dado de alta.", "ok")
            return redirect(url_for("costos.proveedores"))
    return render_template("costos/proveedor_form.html", proveedor=proveedor,
                           es_nuevo=True)


@bp.route("/proveedores/<int:id>/editar", methods=["GET", "POST"])
def proveedor_editar(id):
    bloqueo = _sin_permiso_captura()
    if bloqueo:
        return bloqueo
    proveedor = db_session.get(Proveedor, id)
    if not proveedor:
        flash("El proveedor no existe.", "error")
        return redirect(url_for("costos.proveedores"))
    if request.method == "POST":
        error = _cargar_proveedor(proveedor, request.form)
        if error:
            db_session.rollback()
            flash(error, "error")
        else:
            db_session.commit()
            flash("Proveedor actualizado.", "ok")
            return redirect(url_for("costos.proveedores"))
    return render_template("costos/proveedor_form.html", proveedor=proveedor,
                           es_nuevo=False)


@bp.route("/proveedores/<int:id>/eliminar", methods=["POST"])
def proveedor_eliminar(id):
    bloqueo = _sin_permiso_captura()
    if bloqueo:
        return bloqueo
    proveedor = db_session.get(Proveedor, id)
    if proveedor:
        if proveedor.costos:
            flash(f"No se puede eliminar {proveedor.nombre}: tiene "
                  f"{len(proveedor.costos)} costos ligados.", "error")
            return redirect(url_for("costos.proveedores"))
        nombre = proveedor.nombre
        db_session.delete(proveedor)
        db_session.commit()
        registrar("proveedores.eliminacion", nombre)
        flash("Proveedor eliminado.", "ok")
    return redirect(url_for("costos.proveedores"))


def _proveedores():
    return db_session.query(Proveedor).order_by(Proveedor.nombre).all()


def _cargar_form(costo: Costo, form) -> str | None:
    try:
        costo.proyecto_id = int(form.get("proyecto_id") or 0)
    except ValueError:
        costo.proyecto_id = 0
    costo.categoria = form.get("categoria") or ""
    costo.concepto = (form.get("concepto") or "").strip()
    proveedor_id = form.get("proveedor_id")
    costo.proveedor_id = int(proveedor_id) if proveedor_id else None
    if not db_session.get(Proyecto, costo.proyecto_id):
        return "Seleccione el proyecto al que pertenece el costo."
    if costo.categoria not in CATEGORIAS:
        return "Seleccione una categoría válida."
    if not costo.concepto:
        return "El concepto es obligatorio."
    if costo.proveedor_id and not db_session.get(Proveedor, costo.proveedor_id):
        return "El proveedor seleccionado no existe."
    try:
        costo.monto = Decimal(form.get("monto") or "")
        if costo.monto <= 0:
            return "El monto debe ser mayor que cero."
    except ArithmeticError:
        return "Monto no válido."
    try:
        costo.fecha = datetime.strptime(form.get("fecha") or "", "%Y-%m-%d").date()
    except ValueError:
        return "La fecha es obligatoria."
    return None


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    bloqueo = _sin_permiso_captura()
    if bloqueo:
        return bloqueo
    costo = Costo()
    if request.method == "POST":
        error = _cargar_form(costo, request.form)
        if error:
            flash(error, "error")
        else:
            db_session.add(costo)
            db_session.commit()
            flash("Costo registrado.", "ok")
            return redirect(url_for("costos.lista", proyecto=costo.proyecto_id))
    proyectos = db_session.query(Proyecto).order_by(Proyecto.clave).all()
    return render_template("costos/form.html", costo=costo, proyectos=proyectos,
                           categorias=CATEGORIAS, es_nuevo=True,
                           preseleccion=request.args.get("proyecto", type=int),
                           proveedores=_proveedores())


@bp.route("/<int:id>/editar", methods=["GET", "POST"])
def editar(id):
    bloqueo = _sin_permiso_captura()
    if bloqueo:
        return bloqueo
    costo = db_session.get(Costo, id)
    if not costo:
        flash("El costo no existe.", "error")
        return redirect(url_for("costos.lista"))
    if request.method == "POST":
        error = _cargar_form(costo, request.form)
        if error:
            db_session.rollback()
            flash(error, "error")
        else:
            db_session.commit()
            flash("Costo actualizado.", "ok")
            return redirect(url_for("costos.lista", proyecto=costo.proyecto_id))
    proyectos = db_session.query(Proyecto).order_by(Proyecto.clave).all()
    return render_template("costos/form.html", costo=costo, proyectos=proyectos,
                           categorias=CATEGORIAS, es_nuevo=False, preseleccion=None,
                           proveedores=_proveedores())


@bp.route("/<int:id>/eliminar", methods=["POST"])
def eliminar(id):
    bloqueo = _sin_permiso_captura()
    if bloqueo:
        return bloqueo
    costo = db_session.get(Costo, id)
    if costo:
        detalle = (f"costo {costo.id}: {costo.categoria} ${costo.monto} — "
                   f"{costo.concepto}")
        db_session.delete(costo)
        db_session.commit()
        registrar("costos.eliminacion", detalle)
        flash("Costo eliminado.", "ok")
    return redirect(url_for("costos.lista"))
