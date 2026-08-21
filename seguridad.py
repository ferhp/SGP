# Utilidades de seguridad: cifrado de secretos MFA en reposo y control de
# intentos fallidos (fuerza bruta) para el login de desarrollo y el MFA.
import base64
import hashlib
import threading
from datetime import datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken

import config

# --- Cifrado en reposo de los secretos TOTP -----------------------------------
# La clave se deriva de SECRET_KEY: un volcado de la base de datos no basta
# para clonar los autenticadores; hace falta también la clave de la app.
# Los valores cifrados llevan el prefijo "enc$" para convivir con secretos
# antiguos guardados en claro (se cifran la siguiente vez que se escriben).
_PREFIJO = "enc$"


def _fernet() -> Fernet:
    clave = hashlib.sha256(config.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(clave))


def cifrar_secreto(secreto: str | None) -> str | None:
    if not secreto:
        return secreto
    return _PREFIJO + _fernet().encrypt(secreto.encode()).decode()


def descifrar_secreto(valor: str | None) -> str | None:
    if not valor or not valor.startswith(_PREFIJO):
        return valor  # secreto antiguo en claro
    try:
        return _fernet().decrypt(valor[len(_PREFIJO):].encode()).decode()
    except InvalidToken:
        # SECRET_KEY cambió: el secreto es irrecuperable; el código TOTP no
        # validará y un administrador deberá restablecer el MFA del usuario.
        return None


# --- Control de intentos fallidos ----------------------------------------------
# Contadores en memoria por clave ("mfa:<id>", "dev:<correo>", "dev-ip:<ip>").
# Tras MAX_INTENTOS fallos, la clave queda bloqueada BLOQUEO_MINUTOS.
MAX_INTENTOS = 5
BLOQUEO_MINUTOS = 15

_intentos: dict[str, tuple[int, datetime | None]] = {}
_candado = threading.Lock()


def segundos_bloqueado(clave: str) -> int:
    """Segundos restantes de bloqueo de la clave (0 si no está bloqueada)."""
    with _candado:
        fallos, hasta = _intentos.get(clave, (0, None))
        if hasta and hasta > datetime.now():
            return int((hasta - datetime.now()).total_seconds()) + 1
        if hasta:  # el bloqueo expiró: reinicia el contador
            _intentos.pop(clave, None)
        return 0


def registrar_fallo(clave: str) -> None:
    with _candado:
        fallos, hasta = _intentos.get(clave, (0, None))
        fallos += 1
        if fallos >= MAX_INTENTOS:
            hasta = datetime.now() + timedelta(minutes=BLOQUEO_MINUTOS)
        _intentos[clave] = (fallos, hasta)


def limpiar_intentos(clave: str) -> None:
    with _candado:
        _intentos.pop(clave, None)
