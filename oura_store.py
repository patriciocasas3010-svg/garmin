"""Guarda el Personal Access Token de Oura de cada paciente (pegado
directo en el dashboard, ver dashboard_pacientes.py) en la tabla
"tokens_oura" de Postgres -- misma idea que token_store.py (Garmin), pero
más simple: Oura no tiene login con correo/contraseña ni MFA que
automatizar, el propio paciente genera su token en
cloud.ouraring.com/personal-access-tokens y lo pega una sola vez, así que
no hace falta ninguna "ClaveConexion" de un solo uso -- se guarda directo.

Trata este token con el mismo cuidado que el de Garmin: nunca lo escribas
en el chat de Claude ni lo subas a ningún lado fuera de la base de
datos."""

from datetime import date

import sqlalchemy


def guardar_token(engine: sqlalchemy.engine.Engine, nombre: str, token: str) -> None:
    token = token.strip()
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO tokens_oura (nombre, token, fecha_guardado)
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
            sqlalchemy.text("SELECT token, fecha_guardado FROM tokens_oura WHERE nombre = :nombre"),
            {"nombre": nombre},
        ).first()
    if fila is None or not fila[0]:
        return None
    return {"token": fila[0], "fecha": fila[1]}


def eliminar_token(engine: sqlalchemy.engine.Engine, nombre: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("DELETE FROM tokens_oura WHERE nombre = :nombre"),
            {"nombre": nombre},
        )
