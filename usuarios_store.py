"""Usuarios que pueden entrar al dashboard central (tú y las demás
nutriólogas que agregues desde Settings) -- guardados en la tabla
"usuarios" de Postgres.

Reemplaza la contraseña única compartida (APP_PASSWORD) por un login de
usuario/contraseña por persona, con un rol ("admin" o "nutriologo") que
decide si puede entrar a Settings (borrar pacientes/tokens, crear más
usuarios) y si ve a TODOS los pacientes o solo a los que tiene
asignados (ver enfoque_store.leer_todas_las_asignaciones / el campo
"nutriologo" del perfil).

La contraseña nunca se guarda en texto plano -- se guarda un hash
(PBKDF2 con una sal distinta por usuario), no reversible.

"admin" + el Secret APP_PASSWORD sigue funcionando siempre como acceso
de emergencia (ver dashboard_pacientes.py) -- así nunca te puedes
quedar fuera aunque esta tabla esté vacía o algo salga mal aquí."""

import hashlib
import secrets
from datetime import date

import sqlalchemy

ROLES = ["nutriologo", "admin"]

_ITERACIONES_HASH = 200_000


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERACIONES_HASH).hex()


def crear_usuario(
    engine: sqlalchemy.engine.Engine, usuario: str, nombre: str, password: str, rol: str = "nutriologo",
) -> None:
    """Crea o actualiza (si `usuario` ya existía, por ejemplo para
    cambiarle la contraseña o el rol) la cuenta de un nutriólogo."""
    salt = secrets.token_hex(16)
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO usuarios (usuario, nombre, password_hash, salt, rol, fecha)
                VALUES (:usuario, :nombre, :password_hash, :salt, :rol, :fecha)
                ON CONFLICT (usuario) DO UPDATE SET
                    nombre = EXCLUDED.nombre, password_hash = EXCLUDED.password_hash,
                    salt = EXCLUDED.salt, rol = EXCLUDED.rol, fecha = EXCLUDED.fecha
            """),
            {
                "usuario": usuario, "nombre": nombre, "password_hash": _hash_password(password, salt),
                "salt": salt, "rol": rol, "fecha": date.today().strftime("%d.%m.%Y"),
            },
        )


def verificar_login(engine: sqlalchemy.engine.Engine, usuario: str, password: str) -> dict | None:
    """{"usuario", "nombre", "rol"} si el usuario existe y la contraseña
    es correcta -- None si no."""
    if not usuario or not password:
        return None
    with engine.connect() as conn:
        fila = conn.execute(
            sqlalchemy.text("SELECT nombre, password_hash, salt, rol FROM usuarios WHERE usuario = :usuario"),
            {"usuario": usuario},
        ).mappings().first()
    if fila is None or not fila["salt"] or not fila["password_hash"]:
        return None
    if _hash_password(password, fila["salt"]) != fila["password_hash"]:
        return None
    return {"usuario": usuario, "nombre": fila["nombre"] or usuario, "rol": fila["rol"] or "nutriologo"}


def listar_usuarios(engine: sqlalchemy.engine.Engine) -> list[dict]:
    """Todos los usuarios ({"usuario", "nombre", "rol"}) -- para el
    listado en Settings y para el desplegable de "a quién se le asigna
    este paciente" al crear/editar uno."""
    with engine.connect() as conn:
        filas = conn.execute(sqlalchemy.text("SELECT usuario, nombre, rol FROM usuarios ORDER BY usuario")).all()
    return [{"usuario": u, "nombre": n or u, "rol": r or "nutriologo"} for u, n, r in filas]
