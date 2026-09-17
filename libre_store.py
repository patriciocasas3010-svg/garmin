"""Guarda a cuál paciente de la cuenta de LibreLinkUp del nutriólogo
(la que sigue a varios pacientes que comparten su glucosa) corresponde
cada paciente de este dashboard -- un vínculo por paciente, se
sobreescribe si cambia (no un historial), en la tabla "libre_vinculo"
de Postgres."""

import sqlalchemy


def guardar_vinculo(engine: sqlalchemy.engine.Engine, nombre: str, libre_id: str, libre_nombre: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO libre_vinculo (nombre, libre_patient_id, libre_patient_nombre)
                VALUES (:nombre, :libre_id, :libre_nombre)
                ON CONFLICT (nombre) DO UPDATE SET
                    libre_patient_id = EXCLUDED.libre_patient_id,
                    libre_patient_nombre = EXCLUDED.libre_patient_nombre
            """),
            {"nombre": nombre, "libre_id": str(libre_id), "libre_nombre": libre_nombre},
        )


def leer_vinculo(engine: sqlalchemy.engine.Engine, nombre: str) -> dict | None:
    with engine.connect() as conn:
        fila = conn.execute(
            sqlalchemy.text("SELECT libre_patient_id, libre_patient_nombre FROM libre_vinculo WHERE nombre = :nombre"),
            {"nombre": nombre},
        ).first()
    if fila is None or not fila[0]:
        return None
    return {"id": str(fila[0]), "nombre": fila[1]}
