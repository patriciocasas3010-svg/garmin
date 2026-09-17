"""Borrado en cascada de un paciente -- usado solo desde la sección de
Settings del dashboard central (rol admin). Borra sus filas de TODAS las
tablas de Postgres que puedan tener datos de este paciente (la tabla
principal "resumen" más cada *_store.py), para no dejar historial
huérfano de alguien que ya no es paciente."""

import sqlalchemy

_TABLAS = (
    ("Principal (Garmin/Apple/Oura)", "resumen"),
    ("Enfoque", "enfoque"),
    ("Notas", "notas"),
    ("InBody", "inbody"),
    ("Antropometria", "antropometria"),
    ("Calorias", "calorias"),
    ("Estudios", "estudios"),
    ("TokensGarmin", "tokens_garmin"),
)


def eliminar_paciente(engine: sqlalchemy.engine.Engine, nombre: str) -> dict:
    """Borra al paciente de la tabla principal y de cada tabla
    relacionada. Regresa {etiqueta: filas_borradas}, solo para mostrarlo
    como confirmación en Settings."""
    borradas = {}
    with engine.begin() as conn:
        for etiqueta, tabla in _TABLAS:
            resultado = conn.execute(sqlalchemy.text(f"DELETE FROM {tabla} WHERE nombre = :nombre"), {"nombre": nombre})
            borradas[etiqueta] = resultado.rowcount
    return borradas
