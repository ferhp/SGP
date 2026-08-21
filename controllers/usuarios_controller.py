# Controlador de administración de usuarios SSO (solo rol Admin):
# alta y edición del expediente (datos personales y laborales), asignación de
# rol, departamento, permisos y activación de cuentas.
from datetime import datetime

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from exportar import respuesta_exportacion
from models import db_session
from models.auditoria import registrar
from models.usuario import DEPARTAMENTOS_USUARIO, GENEROS, ROLES, Usuario

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")


def _fecha(valor):
    if not valor:
        return None
    return datetime.strptime(valor, "%Y-%m-%d").date()


def _cargar_datos(usuario: Usuario, form, es_nuevo: bool):
    """Copia al modelo los datos del formulario. Regresa mensaje de error o None."""
    usuario.nombre = (form.get("nombre") or "").strip()
    usuario.apellido_paterno = (form.get("apellido_paterno") or "").strip()
    usuario.apellido_materno = (form.get("apellido_materno") or "").strip()
    if es_nuevo:
        usuario.correo = (form.get("correo") or "").strip().lower()
    usuario.nss = (form.get("nss") or "").strip()
    usuario.curp = (form.get("curp") or "").strip().upper()
    usuario.rfc = (form.get("rfc") or "").strip().upper()
    usuario.direccion = (form.get("direccion") or "").strip()
    usuario.telefono = (form.get("telefono") or "").strip()
    usuario.genero = form.get("genero") or ""
    usuario.puesto = (form.get("puesto") or "").strip()
    rol = form.get("rol") or ""
    departamento = form.get("departamento") or ""

    if not usuario.nombre:
        return "El nombre es obligatorio."
    if es_nuevo and (not usuario.correo or "@" not in usuario.correo):
        return "Escriba un correo electrónico válido."
    if rol not in ROLES or departamento not in DEPARTAMENTOS_USUARIO:
        return "Rol o departamento no válidos."
    if usuario.genero and usuario.genero not in GENEROS:
        return "Género no válido."
    if usuario.nss and (not usuario.nss.isdigit() or len(usuario.nss) != 11):
        return "El NSS debe tener 11 dígitos."
    if usuario.curp and len(usuario.curp) != 18:
        return "La CURP debe tener 18 caracteres."
    if usuario.rfc and len(usuario.rfc) not in (12, 13):
        return "El RFC debe tener 12 o 13 caracteres."
    try:
        usuario.fecha_nacimiento = _fecha(form.get("fecha_nacimiento"))
        usuario.fecha_ingreso = _fecha(form.get("fecha_ingreso"))
    except ValueError:
        return "Fecha de nacimiento o de ingreso no válidas (formato AAAA-MM-DD)."

    usuario.rol = rol
    usuario.departamento = departamento
    usuario.activo = form.get("activo") == "on"
    usuario.captura_costos = form.get("captura_costos") == "on"
    usuario.mfa_requerido = form.get("mfa_requerido") == "on"
    return None


@bp.route("/")
def lista():
    usuarios = db_session.query(Usuario).order_by(Usuario.nombre).all()
    return render_template("usuarios/lista.html", usuarios=usuarios)


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    """Alta manual de un usuario antes de su primer acceso por SSO.

    El registro se enlaza por correo: cuando la persona entre con el SSO,
    su `sub` del proveedor de identidad sustituye al provisional.
    """
    usuario = Usuario(rol="Usuario", departamento="Proyectos",
                      activo=True, captura_costos=False)
    if request.method == "POST":
        error = _cargar_datos(usuario, request.form, es_nuevo=True)
        if not error and db_session.query(Usuario).filter_by(correo=usuario.correo).first():
            error = f"Ya existe un usuario con el correo {usuario.correo}."
        if error:
            flash(error, "error")
        else:
            usuario.sub = f"pre|{usuario.correo}"
            db_session.add(usuario)
            db_session.commit()
            registrar("usuarios.alta",
                      f"{usuario.correo} rol={usuario.rol} "
                      f"departamento={usuario.departamento}")
            flash(f"Usuario {usuario.nombre_completo} agregado; quedará vinculado "
                  "a su cuenta SSO en su primer inicio de sesión.", "ok")
            return redirect(url_for("usuarios.lista"))
    return render_template("usuarios/nuevo.html", usuario=usuario,
                           roles=ROLES, departamentos=DEPARTAMENTOS_USUARIO,
                           generos=GENEROS)


@bp.route("/<int:id>/editar", methods=["GET", "POST"])
def editar(id):
    usuario = db_session.get(Usuario, id)
    if not usuario:
        flash("El usuario no existe.", "error")
        return redirect(url_for("usuarios.lista"))
    if request.method == "POST":
        rol = request.form.get("rol") or ""
        activo = request.form.get("activo") == "on"
        if usuario.id == g.usuario.id and (rol != "Admin" or not activo):
            flash("No puede quitarse a sí mismo el rol Admin ni desactivarse.", "error")
        else:
            error = _cargar_datos(usuario, request.form, es_nuevo=False)
            if error:
                db_session.rollback()
                flash(error, "error")
            else:
                mfa_restablecido = (request.form.get("restablecer_mfa") == "on"
                                    and usuario.mfa_habilitado)
                if mfa_restablecido:
                    # Para cuando el usuario pierde su dispositivo: podrá entrar
                    # de nuevo solo con el SSO y volver a configurar su MFA.
                    usuario.mfa_habilitado = False
                    usuario.mfa_secreto = None
                    flash(f"MFA de {usuario.nombre_completo} restablecido.", "ok")
                db_session.commit()
                registrar("usuarios.edicion",
                          f"{usuario.correo} rol={usuario.rol} "
                          f"departamento={usuario.departamento} "
                          f"activo={usuario.activo} "
                          f"captura_costos={usuario.captura_costos}"
                          + (" mfa_restablecido" if mfa_restablecido else ""))
                flash(f"Usuario {usuario.nombre_completo} actualizado.", "ok")
                return redirect(url_for("usuarios.lista"))
    return render_template("usuarios/form.html", usuario=usuario,
                           roles=ROLES, departamentos=DEPARTAMENTOS_USUARIO,
                           generos=GENEROS)


@bp.route("/exportar/<formato>")
def exportar(formato):
    usuarios = db_session.query(Usuario).order_by(Usuario.nombre).all()
    registrar("usuarios.exportacion",
              f"formato={formato} registros={len(usuarios)} (incluye datos "
              "personales: NSS, CURP, RFC, dirección)")
    columnas = ("ID", "Nombre", "Apellido paterno", "Apellido materno", "Correo",
                "NSS", "CURP", "RFC", "Dirección", "Teléfono",
                "Fecha de nacimiento", "Género", "Fecha de ingreso", "Puesto",
                "Rol", "Departamento", "Permisos", "MFA", "Último acceso", "Estatus")
    filas = [(u.id, u.nombre, u.apellido_paterno or "—", u.apellido_materno or "—",
              u.correo, u.nss or "—", u.curp or "—", u.rfc or "—",
              u.direccion or "—", u.telefono or "—",
              str(u.fecha_nacimiento) if u.fecha_nacimiento else "—",
              u.genero or "—",
              str(u.fecha_ingreso) if u.fecha_ingreso else "—",
              u.puesto or "—", u.rol, u.departamento,
              "Todos" if u.rol == "Admin"
              else ("Captura de costos" if u.captura_costos else "Consulta"),
              "Activado" if u.mfa_habilitado
              else ("Pendiente (requerido)" if u.mfa_requerido else "—"),
              u.ultimo_acceso.strftime("%Y-%m-%d %H:%M") if u.ultimo_acceso else "—",
              "Activo" if u.activo else "Desactivado")
             for u in usuarios]
    return respuesta_exportacion(formato, "usuarios", "Usuarios", columnas, filas)
