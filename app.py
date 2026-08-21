# Punto de entrada de la aplicación (registra vistas y controladores).
#
# Patrón MVC:
#   - Modelos:       models/        (SQLAlchemy sobre MariaDB)
#   - Vistas:        views/         (plantillas Jinja2) + static/
#   - Controladores: controllers/   (blueprints de Flask)
#
# Autenticación: SSO por OpenID Connect (controllers/auth_controller.py).
import os
import sys
from datetime import timedelta

# Garantiza que el paquete de la app sea importable aunque el intérprete
# corra en modo aislado (p. ej. la distribución embebida de Python).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)
from flask_wtf import CSRFProtect

import config
import models
from controllers import (
    auth_controller,
    contabilidad_controller,
    costos_controller,
    dashboard_controller,
    empleados_controller,
    nomina_controller,
    proyectos_controller,
    usuarios_controller,
)
from models.usuario import Usuario

# Rutas accesibles sin sesión iniciada ("auth.mfa" y "auth.mfa_activar" son
# pasos intermedios del inicio de sesión: validan su propio estado pendiente).
ENDPOINTS_PUBLICOS = {
    "auth.login", "auth.login_sso", "auth.login_dev", "auth.callback",
    "auth.mfa", "auth.mfa_activar", "static",
}


def crear_app() -> Flask:
    app = Flask(__name__, template_folder="views", static_folder="static")
    app.secret_key = config.SECRET_KEY
    # Tamaño máximo de las cargas (facturas XML/PDF adjuntas).
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    # Cookies de sesión: HttpOnly (por defecto), SameSite y Secure (tras TLS);
    # la sesión caduca sola tras GP_SESION_HORAS.
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = config.COOKIES_SEGURAS
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=config.SESION_HORAS)

    # Token CSRF obligatorio en todos los POST (los formularios lo incluyen
    # como campo oculto csrf_token).
    CSRFProtect(app)

    models.init_db()
    from seed import sembrar_si_vacio
    sembrar_si_vacio()

    auth_controller.init_oauth(app)

    app.register_blueprint(auth_controller.bp)
    app.register_blueprint(dashboard_controller.bp)
    app.register_blueprint(proyectos_controller.bp)
    app.register_blueprint(costos_controller.bp)
    app.register_blueprint(contabilidad_controller.bp)
    app.register_blueprint(empleados_controller.bp)
    app.register_blueprint(nomina_controller.bp)
    app.register_blueprint(usuarios_controller.bp)

    @app.teardown_appcontext
    def cerrar_sesion(exc=None):
        models.db_session.remove()

    # ---- Autenticación ------------------------------------------------------
    @app.before_request
    def requerir_login():
        if request.endpoint in ENDPOINTS_PUBLICOS or request.endpoint is None:
            return None
        usuario = None
        if session.get("usuario_id"):
            usuario = models.db_session.get(Usuario, session["usuario_id"])
        if not usuario or not usuario.activo:
            # Solo se retira la sesión de usuario; se conserva el estado
            # intermedio del MFA (mfa_pendiente_id) para no romper el flujo
            # de verificación en dos pasos.
            session.pop("usuario_id", None)
            return redirect(url_for("auth.login"))
        g.usuario = usuario
        return None

    # ---- Vistas por departamento -------------------------------------------
    def puede_cambiar_departamento() -> bool:
        usuario = getattr(g, "usuario", None)
        return bool(usuario) and (usuario.rol == "Admin"
                                  or usuario.departamento == "Dirección")

    def departamento_actual() -> str:
        usuario = getattr(g, "usuario", None)
        if not usuario:
            return config.DEPARTAMENTO_DEFAULT
        # Solo Dirección/Admin pueden cambiar de vista; el resto ve la suya.
        if puede_cambiar_departamento():
            dep = session.get("departamento")
            return dep if dep in config.DEPARTAMENTOS else usuario.departamento
        return usuario.departamento

    @app.route("/departamento", methods=["POST"])
    def cambiar_departamento():
        dep = request.form.get("departamento")
        if puede_cambiar_departamento() and dep in config.DEPARTAMENTOS:
            session["departamento"] = dep
        return redirect(request.referrer or url_for("dashboard.index"))

    @app.before_request
    def restringir_modulos():
        # El dashboard, la búsqueda y los estáticos son visibles para todos;
        # cada módulo solo es accesible para los departamentos autorizados
        # y la administración de usuarios solo para el rol Admin.
        if request.endpoint in ENDPOINTS_PUBLICOS or request.endpoint is None:
            return None
        modulo = (request.blueprint or "").split(".")[0]
        if modulo == "usuarios":
            if g.usuario.rol != "Admin":
                flash("Solo los administradores gestionan usuarios.", "error")
                return redirect(url_for("dashboard.index"))
            return None
        if modulo in config.MODULOS:
            permitidos = config.DEPARTAMENTOS[departamento_actual()]
            if modulo not in permitidos:
                flash(
                    f"El departamento {departamento_actual()} no tiene acceso "
                    f"al módulo de {config.MODULOS[modulo]['titulo']}.",
                    "error",
                )
                return redirect(url_for("dashboard.index"))
        return None

    @app.context_processor
    def inyectar_globales():
        usuario = getattr(g, "usuario", None)
        dep = departamento_actual()
        return {
            "usuario_actual": usuario,
            "es_admin": bool(usuario) and usuario.rol == "Admin",
            "puede_cambiar_departamento": puede_cambiar_departamento(),
            "departamento_actual": dep,
            "departamentos": list(config.DEPARTAMENTOS.keys()),
            "modulos_visibles": {
                clave: datos for clave, datos in config.MODULOS.items()
                if clave in config.DEPARTAMENTOS.get(dep, [])
            },
            "motor_bd": models.MOTOR_ACTIVO,
            "sso_habilitado": config.OIDC_HABILITADO,
        }

    @app.template_filter("moneda")
    def moneda(valor):
        try:
            return f"${valor:,.2f}"
        except (TypeError, ValueError):
            return "$0.00"

    @app.errorhandler(404)
    def no_encontrado(_):
        return render_template("404.html"), 404

    # ---- Cabeceras de seguridad ---------------------------------------------
    # 'unsafe-inline' en script-src cubre el script y los manejadores en línea
    # de layout.html; retirarlo requiere mover ese código a un archivo estático.
    _CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "frame-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )

    @app.after_request
    def cabeceras_seguridad(respuesta):
        respuesta.headers.setdefault("Content-Security-Policy", _CSP)
        respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
        respuesta.headers.setdefault("X-Frame-Options", "DENY")
        respuesta.headers.setdefault("Referrer-Policy", "same-origin")
        if config.COOKIES_SEGURAS:
            respuesta.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return respuesta

    return app


app = crear_app()

if __name__ == "__main__":
    if config.MODO_DEV:
        app.run(host="127.0.0.1", port=5090, debug=False)
    else:
        # Servidor WSGI apto para producción (el de Flask es solo de desarrollo).
        from waitress import serve
        serve(app, host="127.0.0.1", port=5090)
