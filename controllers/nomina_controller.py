# Controlador del módulo de Nómina: generación de recibos por periodo a partir
# de la plantilla activa, y consulta por periodo o empleado.
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for

from exportar import moneda, respuesta_exportacion
from models import db_session
from models.auditoria import registrar
from models.empleado import Empleado
from models.nomina import ReciboNomina

bp = Blueprint("nomina", __name__, url_prefix="/nomina")

# Deducciones simplificadas de ejemplo (ajustar a tablas fiscales reales):
TASA_ISR = Decimal("0.09")
TASA_IMSS = Decimal("0.03")


def _consulta_filtrada():
    periodo = request.args.get("periodo") or ""
    consulta = db_session.query(ReciboNomina)
    if periodo:
        consulta = consulta.filter(ReciboNomina.periodo == periodo)
    recibos = consulta.order_by(ReciboNomina.fecha_pago.desc(), ReciboNomina.id).all()
    return recibos, periodo


@bp.route("/")
def lista():
    recibos, periodo = _consulta_filtrada()
    periodos = [
        p[0] for p in db_session.query(ReciboNomina.periodo)
        .distinct().order_by(ReciboNomina.periodo.desc()).all()
    ]
    total_percepciones = sum((r.percepciones for r in recibos), Decimal("0"))
    total_deducciones = sum((r.deducciones for r in recibos), Decimal("0"))
    total_neto = sum((r.neto for r in recibos), Decimal("0"))
    return render_template("nomina/lista.html", recibos=recibos, periodos=periodos,
                           filtro_periodo=periodo,
                           total_percepciones=total_percepciones,
                           total_deducciones=total_deducciones,
                           total_neto=total_neto)


@bp.route("/exportar/<formato>")
def exportar(formato):
    recibos, periodo = _consulta_filtrada()
    titulo = "Nómina" + (f" · {periodo}" if periodo else "")
    columnas = ("Periodo", "Empleado", "Puesto", "Proyecto", "Fecha de pago",
                "Días", "Percepciones", "Deducciones", "Neto")
    filas = [(r.periodo, r.empleado.nombre, r.empleado.puesto,
              r.empleado.proyecto.clave if r.empleado.proyecto else "Oficina central",
              str(r.fecha_pago), r.dias_trabajados, moneda(r.percepciones),
              moneda(r.deducciones), moneda(r.neto))
             for r in recibos]
    filas.append(("", "", "", "", "", "TOTAL",
                  moneda(sum((r.percepciones for r in recibos), Decimal("0"))),
                  moneda(sum((r.deducciones for r in recibos), Decimal("0"))),
                  moneda(sum((r.neto for r in recibos), Decimal("0")))))
    return respuesta_exportacion(formato, "nomina", titulo, columnas, filas)


@bp.route("/generar", methods=["GET", "POST"])
def generar():
    hoy = date.today()
    quincena = "Q1" if hoy.day <= 15 else "Q2"
    periodo_sugerido = f"{hoy:%Y-%m} {quincena}"
    if request.method == "POST":
        periodo = (request.form.get("periodo") or "").strip()
        try:
            dias = int(request.form.get("dias") or 0)
            fecha_pago = datetime.strptime(
                request.form.get("fecha_pago") or "", "%Y-%m-%d"
            ).date()
        except ValueError:
            flash("Días trabajados y fecha de pago son obligatorios.", "error")
            return redirect(url_for("nomina.generar"))
        if not periodo or dias <= 0:
            flash("Indique el periodo y un número de días mayor que cero.", "error")
            return redirect(url_for("nomina.generar"))

        empleados = (
            db_session.query(Empleado)
            .filter(Empleado.activo.is_(True))
            .order_by(Empleado.nombre)
            .all()
        )
        ya_pagados = {
            r.empleado_id
            for r in db_session.query(ReciboNomina).filter_by(periodo=periodo).all()
        }
        generados = 0
        for empleado in empleados:
            if empleado.id in ya_pagados or not empleado.salario_diario:
                continue
            percepciones = (empleado.salario_diario * dias).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            deducciones = (percepciones * (TASA_ISR + TASA_IMSS)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            db_session.add(ReciboNomina(
                empleado_id=empleado.id,
                periodo=periodo,
                fecha_pago=fecha_pago,
                dias_trabajados=dias,
                percepciones=percepciones,
                deducciones=deducciones,
                neto=percepciones - deducciones,
            ))
            generados += 1
        db_session.commit()
        if generados:
            flash(f"Se generaron {generados} recibos del periodo {periodo}.", "ok")
        else:
            flash("No había recibos pendientes de generar para ese periodo.", "error")
        return redirect(url_for("nomina.lista", periodo=periodo))

    activos = db_session.query(Empleado).filter(
        Empleado.activo.is_(True), Empleado.salario_diario > 0
    ).count()
    return render_template("nomina/generar.html", periodo_sugerido=periodo_sugerido,
                           hoy=hoy, empleados_activos=activos)


@bp.route("/<int:id>/eliminar", methods=["POST"])
def eliminar(id):
    recibo = db_session.get(ReciboNomina, id)
    if recibo:
        detalle = f"recibo {recibo.id}, periodo {recibo.periodo}"
        db_session.delete(recibo)
        db_session.commit()
        registrar("nomina.eliminacion", detalle)
        flash("Recibo eliminado.", "ok")
    return redirect(url_for("nomina.lista"))
