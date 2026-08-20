# Controlador del módulo de Contabilidad: ingresos y egresos por cuenta,
# con referencia de factura/póliza y proyecto opcional. Cada movimiento puede
# llevar adjunta su factura (XML y PDF), guardada en config.FACTURAS_DIR.
import os
from datetime import datetime
from decimal import Decimal

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   send_file, url_for)
from werkzeug.utils import secure_filename

import config
from exportar import moneda, respuesta_exportacion
from models import db_session
from models.contabilidad import CUENTAS, TIPOS_MOVIMIENTO, MovimientoContable
from models.proyecto import Proyecto

bp = Blueprint("contabilidad", __name__, url_prefix="/contabilidad")

_EXTENSIONES = {"xml": ".xml", "pdf": ".pdf"}


def _ruta_factura(nombre_archivo):
    return os.path.join(config.FACTURAS_DIR, nombre_archivo)


def _eliminar_factura(mov, tipo):
    nombre = getattr(mov, f"archivo_{tipo}")
    if nombre:
        ruta = _ruta_factura(nombre)
        if os.path.exists(ruta):
            os.remove(ruta)


def _guardar_facturas(mov, archivos):
    """Guarda los adjuntos XML/PDF del formulario. Regresa error o None.

    Requiere que `mov` ya tenga id (para nombrar los archivos). Si ya había
    un archivo del mismo tipo, se reemplaza.
    """
    os.makedirs(config.FACTURAS_DIR, exist_ok=True)
    for tipo, extension in _EXTENSIONES.items():
        archivo = archivos.get(f"factura_{tipo}")
        if not archivo or not archivo.filename:
            continue
        nombre = secure_filename(archivo.filename)
        if not nombre.lower().endswith(extension):
            return (f"El archivo de la factura {tipo.upper()} debe tener "
                    f"extensión {extension}.")
        _eliminar_factura(mov, tipo)
        guardado = f"mov{mov.id}_{nombre}"
        archivo.save(_ruta_factura(guardado))
        setattr(mov, f"archivo_{tipo}", guardado)
    return None


def _consulta_filtrada():
    proyecto_id = request.args.get("proyecto", type=int)
    tipo = request.args.get("tipo") or ""
    consulta = db_session.query(MovimientoContable)
    if proyecto_id:
        consulta = consulta.filter(MovimientoContable.proyecto_id == proyecto_id)
    if tipo in TIPOS_MOVIMIENTO:
        consulta = consulta.filter(MovimientoContable.tipo == tipo)
    movimientos = consulta.order_by(
        MovimientoContable.fecha.desc(), MovimientoContable.id.desc()
    ).all()
    return movimientos, proyecto_id, tipo


@bp.route("/")
def lista():
    movimientos, proyecto_id, tipo = _consulta_filtrada()
    ingresos = sum((m.monto for m in movimientos if m.tipo == "Ingreso"), Decimal("0"))
    egresos = sum((m.monto for m in movimientos if m.tipo == "Egreso"), Decimal("0"))
    proyectos = db_session.query(Proyecto).order_by(Proyecto.clave).all()
    return render_template("contabilidad/lista.html", movimientos=movimientos,
                           proyectos=proyectos, tipos=TIPOS_MOVIMIENTO,
                           filtro_proyecto=proyecto_id, filtro_tipo=tipo,
                           ingresos=ingresos, egresos=egresos,
                           saldo=ingresos - egresos)


@bp.route("/exportar/<formato>")
def exportar(formato):
    movimientos, proyecto_id, tipo = _consulta_filtrada()
    titulo = "Contabilidad"
    if proyecto_id:
        proyecto = db_session.get(Proyecto, proyecto_id)
        if proyecto:
            titulo += f" · {proyecto.clave}"
    if tipo:
        titulo += f" · {tipo}s"
    columnas = ("Fecha", "Tipo", "Cuenta", "Referencia", "Concepto",
                "Proyecto", "Monto")
    filas = [(str(m.fecha), m.tipo, m.cuenta, m.referencia or "—", m.concepto,
              m.proyecto.clave if m.proyecto else "General", moneda(m.monto))
             for m in movimientos]
    ingresos = sum((m.monto for m in movimientos if m.tipo == "Ingreso"), Decimal("0"))
    egresos = sum((m.monto for m in movimientos if m.tipo == "Egreso"), Decimal("0"))
    filas.append(("", "", "", "", "", "TOTAL INGRESOS", moneda(ingresos)))
    filas.append(("", "", "", "", "", "TOTAL EGRESOS", moneda(egresos)))
    filas.append(("", "", "", "", "", "SALDO", moneda(ingresos - egresos)))
    return respuesta_exportacion(formato, "contabilidad", titulo, columnas, filas)


def _cargar_form(mov: MovimientoContable, form) -> str | None:
    mov.tipo = form.get("tipo") or ""
    mov.cuenta = form.get("cuenta") or ""
    mov.referencia = (form.get("referencia") or "").strip()
    mov.concepto = (form.get("concepto") or "").strip()
    proyecto_id = form.get("proyecto_id")
    mov.proyecto_id = int(proyecto_id) if proyecto_id else None
    if mov.tipo not in TIPOS_MOVIMIENTO:
        return "Seleccione si es ingreso o egreso."
    if mov.cuenta not in CUENTAS:
        return "Seleccione una cuenta válida."
    if not mov.concepto:
        return "El concepto es obligatorio."
    if mov.proyecto_id and not db_session.get(Proyecto, mov.proyecto_id):
        return "El proyecto seleccionado no existe."
    try:
        mov.monto = Decimal(form.get("monto") or "")
        if mov.monto <= 0:
            return "El monto debe ser mayor que cero."
    except ArithmeticError:
        return "Monto no válido."
    try:
        mov.fecha = datetime.strptime(form.get("fecha") or "", "%Y-%m-%d").date()
    except ValueError:
        return "La fecha es obligatoria."
    return None


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    mov = MovimientoContable()
    if request.method == "POST":
        error = _cargar_form(mov, request.form)
        if not error:
            db_session.add(mov)
            db_session.flush()  # asigna id para nombrar los adjuntos
            error = _guardar_facturas(mov, request.files)
        if error:
            db_session.rollback()
            flash(error, "error")
        else:
            db_session.commit()
            flash("Movimiento registrado.", "ok")
            return redirect(url_for("contabilidad.lista"))
    proyectos = db_session.query(Proyecto).order_by(Proyecto.clave).all()
    return render_template("contabilidad/form.html", mov=mov, proyectos=proyectos,
                           tipos=TIPOS_MOVIMIENTO, cuentas=CUENTAS, es_nuevo=True)


@bp.route("/<int:id>/editar", methods=["GET", "POST"])
def editar(id):
    mov = db_session.get(MovimientoContable, id)
    if not mov:
        flash("El movimiento no existe.", "error")
        return redirect(url_for("contabilidad.lista"))
    if request.method == "POST":
        error = _cargar_form(mov, request.form) or _guardar_facturas(mov, request.files)
        if error:
            db_session.rollback()
            flash(error, "error")
        else:
            db_session.commit()
            flash("Movimiento actualizado.", "ok")
            return redirect(url_for("contabilidad.lista"))
    proyectos = db_session.query(Proyecto).order_by(Proyecto.clave).all()
    return render_template("contabilidad/form.html", mov=mov, proyectos=proyectos,
                           tipos=TIPOS_MOVIMIENTO, cuentas=CUENTAS, es_nuevo=False)


@bp.route("/<int:id>/factura/<tipo>")
def factura(id, tipo):
    """Entrega la factura adjunta: el PDF en línea (para el visor emergente)
    y el XML como descarga."""
    mov = db_session.get(MovimientoContable, id)
    if tipo not in _EXTENSIONES or not mov:
        abort(404)
    nombre = getattr(mov, f"archivo_{tipo}")
    if not nombre:
        abort(404)
    ruta = _ruta_factura(nombre)
    if not os.path.exists(ruta):
        abort(404)
    if tipo == "pdf":
        return send_file(ruta, mimetype="application/pdf")
    return send_file(ruta, as_attachment=True, download_name=nombre,
                     mimetype="application/xml")


@bp.route("/<int:id>/eliminar", methods=["POST"])
def eliminar(id):
    mov = db_session.get(MovimientoContable, id)
    if mov:
        _eliminar_factura(mov, "xml")
        _eliminar_factura(mov, "pdf")
        db_session.delete(mov)
        db_session.commit()
        flash("Movimiento eliminado.", "ok")
    return redirect(url_for("contabilidad.lista"))
