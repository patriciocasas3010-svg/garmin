"""Guarda el token de sesión de Garmin de cada paciente (el mismo que
genera export_token.py en su propia computadora) en la tabla
"tokens_garmin" de Postgres -- para que sync_diario.py pueda jalar el
dashboard de cada paciente todos los días sin que abra nada.

Ese token equivale a estar conectado a la cuenta de Garmin del paciente
(no es su contraseña, pero da acceso a los mismos datos) -- trátalo con
el mismo cuidado: nunca lo escribas en el chat de Claude ni lo subas a
ningún lado fuera de la base de datos.

A diferencia del resto de los *_store.py durante la época de Google
Sheets, este módulo necesitaba su propio caché manual porque también lo
usa sync_diario.py (un script normal, sin Streamlit corriendo) y porque
gspread no cachea nada por su cuenta -- con Postgres eso ya no aplica:
no hay cuota de lecturas por minuto, así que aquí ya no hace falta
ningún caché, solo el pool de conexiones normal de SQLAlchemy (ver
db.py). Sigue funcionando igual dentro y fuera de Streamlit porque
ambos le pasan un Engine ya armado (db.engine() o db.crear_engine()).

También lo usa conectar_garmin_web.py -- la página web donde el propio
paciente pega su correo/contraseña de Garmin una sola vez (sin Python ni
terminal en su computadora) para activar la sincronización automática.
Ese flujo usa una "ClaveConexion" de un solo uso (generar_clave_conexion/
validar_clave_conexion/invalidar_clave_conexion) para que el link que le
mandas por WhatsApp no sirva para nada una vez usado."""

import re
from datetime import date

import secrets
import sqlalchemy

_DELIMITADOR_RE = re.compile(r"-{10,}\s*\n(.*?)\n\s*-{10,}", re.S)


def _extraer_token(texto_pegado: str) -> str:
    """export_token.py imprime el token entre dos líneas de guiones, con
    instrucciones arriba y abajo -- si el paciente copia "todo el bloque"
    tal cual le dice el mensaje, esto se queda solo con lo de en medio.
    Si en vez de eso pegó solo el token (sin los guiones), se usa tal
    cual, sin tocarlo."""
    m = _DELIMITADOR_RE.search(texto_pegado)
    return (m.group(1) if m else texto_pegado).strip()


def guardar_token(engine: sqlalchemy.engine.Engine, nombre: str, texto_pegado: str) -> None:
    token = _extraer_token(texto_pegado)
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO tokens_garmin (nombre, token, fecha_guardado)
                VALUES (:nombre, :token, :fecha)
                ON CONFLICT (nombre) DO UPDATE SET token = EXCLUDED.token, fecha_guardado = EXCLUDED.fecha_guardado
            """),
            {"nombre": nombre, "token": token, "fecha": date.today().strftime("%d.%m.%Y")},
        )


def leer_token(engine: sqlalchemy.engine.Engine, nombre: str) -> dict | None:
    """{"token": str, "fecha": str} de este paciente, o None si nunca
    guardó uno (o lo quitó con eliminar_token)."""
    with engine.connect() as conn:
        fila = conn.execute(
            sqlalchemy.text("SELECT token, fecha_guardado FROM tokens_garmin WHERE nombre = :nombre"),
            {"nombre": nombre},
        ).first()
    if fila is None or not fila[0]:
        return None
    return {"token": fila[0], "fecha": fila[1]}


def listar_tokens(engine: sqlalchemy.engine.Engine) -> list[dict]:
    """Todos los pacientes con token guardado -- lo usa sync_diario.py
    para saber a quién sincronizar cada día."""
    with engine.connect() as conn:
        filas = conn.execute(
            sqlalchemy.text("SELECT nombre, token, fecha_guardado FROM tokens_garmin WHERE token IS NOT NULL AND token != ''"),
        ).all()
    return [{"nombre": n, "token": t, "fecha": f} for n, t, f in filas]


def eliminar_token(engine: sqlalchemy.engine.Engine, nombre: str) -> None:
    """Apaga la sincronización automática de este paciente (no borra su
    fila, solo el token -- así no se corre el riesgo de que sync_diario.py
    intente usar un token viejo/inválido para alguien que ya no quiere
    esto activado)."""
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("UPDATE tokens_garmin SET token = '', fecha_guardado = '' WHERE nombre = :nombre"),
            {"nombre": nombre},
        )


def generar_clave_conexion(engine: sqlalchemy.engine.Engine, nombre: str) -> str:
    """Genera una clave nueva de un solo uso para que este paciente se
    conecte solo desde conectar_garmin_web.py -- sobrescribe cualquier
    clave anterior sin usar (así un link viejo que mandaste por error
    deja de funcionar)."""
    clave = secrets.token_urlsafe(16)
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO tokens_garmin (nombre, clave_conexion) VALUES (:nombre, :clave)
                ON CONFLICT (nombre) DO UPDATE SET clave_conexion = EXCLUDED.clave_conexion
            """),
            {"nombre": nombre, "clave": clave},
        )
    return clave


def validar_clave_conexion(engine: sqlalchemy.engine.Engine, nombre: str, clave: str) -> bool:
    """True solo si `clave` es exactamente la que se generó para `nombre`
    y todavía no se usó (ver invalidar_clave_conexion)."""
    if not clave:
        return False
    with engine.connect() as conn:
        fila = conn.execute(
            sqlalchemy.text("SELECT clave_conexion FROM tokens_garmin WHERE nombre = :nombre"), {"nombre": nombre},
        ).first()
    return fila is not None and fila[0] == clave


def invalidar_clave_conexion(engine: sqlalchemy.engine.Engine, nombre: str) -> None:
    """Se llama justo después de guardar el token con éxito -- para que
    el link de conexión no se pueda volver a usar (por ejemplo si se
    quedó visible en un chat de WhatsApp)."""
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("UPDATE tokens_garmin SET clave_conexion = '' WHERE nombre = :nombre"), {"nombre": nombre},
        )
