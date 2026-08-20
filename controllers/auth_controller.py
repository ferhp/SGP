# Controlador de autenticación SSO (OpenID Connect) con MFA (TOTP).
#
# Con GP_OIDC_* configurado, el inicio de sesión se delega al proveedor de
# identidad (Microsoft Entra ID, Google, Keycloak, Okta…) mediante el flujo
# "authorization code". Sin configuración, se habilita un acceso local de
# desarrollo que simula el SSO para poder trabajar sin IdP.
#
# MFA: verificación en dos pasos con códigos TOTP (Google/Microsoft
# Authenticator). Cada usuario la activa escaneando un código QR; a partir de
# entonces, tras el SSO se le pide el código de 6 dígitos.
import base64
import io
from datetime import datetime

import pyotp
import qrcode
from authlib.integrations.flask_client import OAuth
from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)

import config
from models import db_session
from models.usuario import DEPARTAMENTOS_USUARIO, Usuario

bp = Blueprint("auth", __name__)

oauth = OAuth()

EMISOR_MFA = "SIGEP"


def init_oauth(app):
    if not config.OIDC_HABILITADO:
        return
    oauth.init_app(app)
    oauth.register(
        "sso",
        client_id=config.OIDC_CLIENT_ID,
        client_secret=config.OIDC_CLIENT_SECRET,
        server_metadata_url=(
            config.OIDC_ISSUER.rstrip("/") + "/.well-known/openid-configuration"
        ),
        client_kwargs={"scope": config.OIDC_SCOPES},
    )


def _autenticar(sub: str, correo: str, nombre: str):
    """Da de alta o actualiza al usuario. Regresa (usuario, error)."""
    correo = (correo or "").strip().lower()
    if not correo:
        return None, "El proveedor de identidad no entregó un correo electrónico."
    usuario = (
        db_session.query(Usuario)
        .filter((Usuario.sub == sub) | (Usuario.correo == correo))
        .first()
    )
    if not usuario:
        depto = (config.DEPARTAMENTO_NUEVOS
                 if config.DEPARTAMENTO_NUEVOS in DEPARTAMENTOS_USUARIO
                 else "Proyectos")
        usuario = Usuario(sub=sub, correo=correo, nombre=nombre or correo,
                          departamento=depto, activo=True)
        if correo in config.ADMIN_CORREOS:
            usuario.rol = "Admin"
            usuario.departamento = "Dirección"
        db_session.add(usuario)
    else:
        usuario.sub = sub
        if nombre:
            usuario.nombre = nombre
    if not usuario.activo:
        db_session.rollback()
        return None, "Su cuenta está desactivada; contacte al administrador."
    db_session.commit()
    return usuario, None


def _abrir_sesion(usuario: Usuario):
    usuario.ultimo_acceso = datetime.now()
    db_session.commit()
    session.clear()
    session["usuario_id"] = usuario.id


def _continuar_login(usuario: Usuario):
    """Según el estado del MFA: pide el código, obliga a configurarlo
    (cuando el administrador lo marcó como requerido) o abre la sesión."""
    if usuario.mfa_habilitado and usuario.mfa_secreto:
        session.clear()
        session["mfa_pendiente_id"] = usuario.id
        return redirect(url_for("auth.mfa"))
    if usuario.mfa_requerido:
        session.clear()
        session["mfa_config_pendiente_id"] = usuario.id
        return redirect(url_for("auth.mfa_activar"))
    _abrir_sesion(usuario)
    return redirect(url_for("dashboard.index"))


def _verificar_totp(secreto: str, codigo: str) -> bool:
    codigo = (codigo or "").strip().replace(" ", "")
    if not secreto or not codigo.isdigit():
        return False
    return pyotp.TOTP(secreto).verify(codigo, valid_window=1)


def _qr_data_uri(texto: str) -> str:
    imagen = qrcode.make(texto, box_size=6, border=2)
    contenido = io.BytesIO()
    imagen.save(contenido, format="PNG")
    return "data:image/png;base64," + base64.b64encode(contenido.getvalue()).decode()


@bp.route("/login")
def login():
    if session.get("usuario_id"):
        return redirect(url_for("dashboard.index"))
    return render_template("auth/login.html", sso_habilitado=config.OIDC_HABILITADO,
                           issuer=config.OIDC_ISSUER)


@bp.route("/login/sso")
def login_sso():
    if not config.OIDC_HABILITADO:
        flash("El SSO no está configurado; use el acceso de desarrollo.", "error")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.callback", _external=True)
    return oauth.sso.authorize_redirect(redirect_uri)


@bp.route("/callback")
def callback():
    if not config.OIDC_HABILITADO:
        return redirect(url_for("auth.login"))
    try:
        token = oauth.sso.authorize_access_token()
    except Exception:
        flash("No se pudo completar el inicio de sesión con el proveedor.", "error")
        return redirect(url_for("auth.login"))
    error = None
    userinfo = token.get("userinfo") or {}
    if not userinfo:
        try:
            userinfo = oauth.sso.userinfo(token=token)
        except Exception:
            userinfo = {}
    usuario, error = _autenticar(
        sub=str(userinfo.get("sub", "")),
        correo=userinfo.get("email") or userinfo.get("preferred_username") or "",
        nombre=userinfo.get("name") or "",
    )
    if error:
        flash(error, "error")
        return redirect(url_for("auth.login"))
    return _continuar_login(usuario)


@bp.route("/login/dev", methods=["POST"])
def login_dev():
    # Acceso local que simula el SSO; solo existe cuando no hay IdP configurado.
    if config.OIDC_HABILITADO:
        return redirect(url_for("auth.login"))
    correo = (request.form.get("correo") or "").strip().lower()
    nombre = (request.form.get("nombre") or "").strip()
    if not correo or "@" not in correo:
        flash("Escriba un correo electrónico válido.", "error")
        return redirect(url_for("auth.login"))
    usuario, error = _autenticar(sub=f"dev|{correo}", correo=correo, nombre=nombre)
    if error:
        flash(error, "error")
        return redirect(url_for("auth.login"))
    return _continuar_login(usuario)


@bp.route("/mfa", methods=["GET", "POST"])
def mfa():
    # Segundo paso del inicio de sesión: solo con una autenticación previa
    # pendiente de MFA.
    usuario = db_session.get(Usuario, session.get("mfa_pendiente_id", 0))
    if not usuario or not usuario.mfa_habilitado or not usuario.mfa_secreto:
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        if _verificar_totp(usuario.mfa_secreto, request.form.get("codigo")):
            session.pop("mfa_pendiente_id", None)
            _abrir_sesion(usuario)
            return redirect(url_for("dashboard.index"))
        flash("Código incorrecto o vencido; intente de nuevo.", "error")
    return render_template("auth/mfa.html", correo=usuario.correo)


@bp.route("/mfa/activar", methods=["GET", "POST"])
def mfa_activar():
    # Configuración obligatoria del MFA durante el inicio de sesión, cuando
    # el administrador marcó la cuenta con "MFA requerido".
    usuario = db_session.get(Usuario, session.get("mfa_config_pendiente_id", 0))
    if not usuario or not usuario.activo or usuario.mfa_habilitado:
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        secreto = session.get("mfa_secreto_tmp")
        if secreto and _verificar_totp(secreto, request.form.get("codigo")):
            usuario.mfa_secreto = secreto
            usuario.mfa_habilitado = True
            db_session.commit()
            session.pop("mfa_secreto_tmp", None)
            session.pop("mfa_config_pendiente_id", None)
            _abrir_sesion(usuario)
            flash("Verificación en dos pasos configurada; bienvenido.", "ok")
            return redirect(url_for("dashboard.index"))
        flash("Código incorrecto; escanee el QR y vuelva a intentar.", "error")
    secreto = session.get("mfa_secreto_tmp")
    if not secreto:
        secreto = pyotp.random_base32()
        session["mfa_secreto_tmp"] = secreto
    uri = pyotp.totp.TOTP(secreto).provisioning_uri(
        name=usuario.correo, issuer_name=EMISOR_MFA
    )
    return render_template("auth/mfa_activar.html", correo=usuario.correo,
                           qr=_qr_data_uri(uri), secreto=secreto)


@bp.route("/mfa/configurar", methods=["GET", "POST"])
def mfa_configurar():
    # Requiere sesión iniciada (protegida por requerir_login en app.py).
    usuario = g.usuario
    if request.method == "POST":
        accion = request.form.get("accion")
        codigo = request.form.get("codigo")
        if accion == "activar" and not usuario.mfa_habilitado:
            secreto = session.get("mfa_secreto_tmp")
            if secreto and _verificar_totp(secreto, codigo):
                usuario.mfa_secreto = secreto
                usuario.mfa_habilitado = True
                db_session.commit()
                session.pop("mfa_secreto_tmp", None)
                flash("Verificación en dos pasos activada.", "ok")
                return redirect(url_for("dashboard.index"))
            flash("Código incorrecto; escanee el QR y vuelva a intentar.", "error")
        elif accion == "desactivar" and usuario.mfa_habilitado:
            if _verificar_totp(usuario.mfa_secreto, codigo):
                usuario.mfa_habilitado = False
                usuario.mfa_secreto = None
                db_session.commit()
                flash("Verificación en dos pasos desactivada.", "ok")
                return redirect(url_for("auth.mfa_configurar"))
            flash("Código incorrecto; no se desactivó el MFA.", "error")
    qr = None
    secreto = None
    if not usuario.mfa_habilitado:
        secreto = session.get("mfa_secreto_tmp")
        if not secreto:
            secreto = pyotp.random_base32()
            session["mfa_secreto_tmp"] = secreto
        uri = pyotp.totp.TOTP(secreto).provisioning_uri(
            name=usuario.correo, issuer_name=EMISOR_MFA
        )
        qr = _qr_data_uri(uri)
    return render_template("auth/mfa_configurar.html", usuario=usuario,
                           qr=qr, secreto=secreto)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Sesión cerrada.", "ok")
    return redirect(url_for("auth.login"))
