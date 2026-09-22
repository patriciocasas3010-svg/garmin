"""Guarda la conexión OAuth2 de Oura de cada paciente (access_token +
refresh_token) en la tabla "tokens_oura" de Postgres -- misma idea que
token_store.py (Garmin), pero con OAuth2 en vez de correo/contraseña:
Oura dejó de permitir Personal Access Tokens en diciembre de 2025, ahora
solo se puede conectar mandando al paciente a autorizar la app en
cloud.ouraring.com (ver conectar_oura_web.py), lo mismo que ya se hacía
con el link de un solo uso de Garmin.

El access_token de Oura expira (usualmente unas horas) pero el
refresh_token dura mucho más -- token_valido() se encarga de refrescarlo
solo, sin que el paciente tenga que volver a autorizar nada, mientras el
refresh_token siga vigente.

Trata estos tokens con el mismo cuidado que el de Garmin: nunca los
escribas en el chat de Claude ni los subas a ningún lado fuera de la base
de datos. CLIENT_ID y CLIENT_SECRET viven en los Secrets de Streamlit
Cloud (OURA_CLIENT_ID / OURA_CLIENT_SECRET), nunca en este archivo."""

from datetime import datetime, timedelta, timezone

import secrets
import sqlalchemy
import requests

TOKEN_URL = "https://api.ouraring.com/oauth/token"


def guardar_tokens(engine: sqlalchemy.engine.Engine, nombre: str, access_token: str, refresh_token: str, expires_in: int) -> None:
    expira_en = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO tokens_oura (nombre, access_token, refresh_token, expira_en, fecha_guardado)
                VALUES (:nombre, :access_token, :refresh_token, :expira_en, :fecha)
                ON CONFLICT (nombre) DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    expira_en = EXCLUDED.expira_en,
                    fecha_guardado = EXCLUDED.fecha_guardado
            """),
            {
                "nombre": nombre,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expira_en": expira_en,
                "fecha": datetime.now().strftime("%d.%m.%Y"),
            },
        )


def leer_conexion(engine: sqlalchemy.engine.Engine, nombre: str) -> dict | None:
    """{"access_token", "refresh_token", "expira_en", "fecha"} de este
    paciente, o None si nunca conectó (o se le quitó con eliminar_token)."""
    with engine.connect() as conn:
        fila = conn.execute(
            sqlalchemy.text(
                "SELECT access_token, refresh_token, expira_en, fecha_guardado FROM tokens_oura WHERE nombre = :nombre"
            ),
            {"nombre": nombre},
        ).first()
    if fila is None or not fila[0]:
        return None
    return {"access_token": fila[0], "refresh_token": fila[1], "expira_en": fila[2], "fecha": fila[3]}


def eliminar_token(engine: sqlalchemy.engine.Engine, nombre: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text(
                "UPDATE tokens_oura SET access_token = NULL, refresh_token = NULL, expira_en = NULL WHERE nombre = :nombre"
            ),
            {"nombre": nombre},
        )


def token_valido(engine: sqlalchemy.engine.Engine, nombre: str, client_id: str, client_secret: str) -> str | None:
    """Devuelve un access_token listo para usar contra la API de Oura --
    si el guardado ya expiró (o está por expirar), lo refresca solo con
    el refresh_token y guarda el par nuevo (Oura rota el refresh_token en
    cada uso, hay que quedarse siempre con el más reciente). None si el
    paciente nunca conectó Oura o el refresh_token ya no sirve."""
    conexion = leer_conexion(engine, nombre)
    if conexion is None:
        return None

    margen = timedelta(minutes=2)
    expira_en = conexion["expira_en"]
    if expira_en is not None and expira_en.tzinfo is None:
        expira_en = expira_en.replace(tzinfo=timezone.utc)
    if expira_en is not None and datetime.now(timezone.utc) < (expira_en - margen):
        return conexion["access_token"]

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": conexion["refresh_token"],
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        return None
    body = resp.json()
    guardar_tokens(engine, nombre, body["access_token"], body["refresh_token"], body["expires_in"])
    return body["access_token"]


def intercambiar_codigo(client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict:
    """Cambia el "code" de la redirección de Oura por el par
    access_token/refresh_token -- lanza una excepción si Oura lo rechaza
    (código vencido, ya usado, redirect_uri que no coincide con el
    registrado en cloud.ouraring.com/oauth/applications)."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Clave de conexión de un solo uso -- mismo mecanismo que
# token_store.generar_clave_conexion/validar_clave_conexion/invalidar_clave_conexion
# (Garmin), pero aquí también sirve como el "state" que le mandamos a Oura
# y que Oura nos regresa intacto al terminar la autorización -- así
# sabemos a qué paciente corresponde el "code" sin tener que confiar en
# nada más que venga en la URL de regreso.
# ---------------------------------------------------------------------------

def generar_clave_conexion(engine: sqlalchemy.engine.Engine, nombre: str) -> str:
    clave = secrets.token_urlsafe(16)
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO tokens_oura (nombre, clave_conexion) VALUES (:nombre, :clave)
                ON CONFLICT (nombre) DO UPDATE SET clave_conexion = EXCLUDED.clave_conexion
            """),
            {"nombre": nombre, "clave": clave},
        )
    return clave


def validar_clave_conexion(engine: sqlalchemy.engine.Engine, nombre: str, clave: str) -> bool:
    if not clave:
        return False
    with engine.connect() as conn:
        fila = conn.execute(
            sqlalchemy.text("SELECT clave_conexion FROM tokens_oura WHERE nombre = :nombre"), {"nombre": nombre},
        ).first()
    return fila is not None and fila[0] == clave


def paciente_por_clave(engine: sqlalchemy.engine.Engine, clave: str) -> str | None:
    """Al volver de Oura solo tenemos el "state" (esta misma clave) -- lo
    usamos para encontrar de qué paciente se trata, sin depender de que
    ningún otro parámetro haya sobrevivido la redirección."""
    if not clave:
        return None
    with engine.connect() as conn:
        fila = conn.execute(
            sqlalchemy.text("SELECT nombre FROM tokens_oura WHERE clave_conexion = :clave"), {"clave": clave},
        ).first()
    return fila[0] if fila else None


def invalidar_clave_conexion(engine: sqlalchemy.engine.Engine, nombre: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("UPDATE tokens_oura SET clave_conexion = NULL WHERE nombre = :nombre"), {"nombre": nombre},
        )
