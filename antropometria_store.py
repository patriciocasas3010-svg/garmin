"""Guarda y lee el historial de mediciones antropométricas (pliegues,
circunferencias, % grasa por Faulkner) de cada paciente, en la tabla
"antropometria" de Postgres -- igual que inbody_store.py, sin mezclarse
con los demás datos."""

import pandas as pd
import sqlalchemy

ENCABEZADOS = [
    "Nombre", "Fecha",
    "GrasaFaulkner_pct", "GrasaCalculado_kg",
    "Pliegue_Supraespinal_mm", "Pliegue_MusloFrontal_mm",
    "Pliegue_PantorrillaMedial_mm", "Pliegue_Abdominal_mm",
    "Pliegue_Tricipital_mm", "Pliegue_Subescapular_mm",
    "Pliegue_Suprailiaco_mm", "Pliegue_Bicipital_mm",
    "Circ_Cadera_cm", "Circ_Pantorrilla_cm", "Circ_MusloMedio_cm",
    "Circ_BrazoContraido_cm", "Circ_Cintura_cm", "Circ_BrazoRelajado_cm",
    "Circ_Muslo_cm",
]


def guardar_registro(engine: sqlalchemy.engine.Engine, nombre: str, campos: dict) -> None:
    """Agrega una fila nueva -- cada medición es un punto en el tiempo, se
    agrega siempre, nunca se sobreescribe."""
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO antropometria (
                    nombre, fecha, grasa_faulkner_pct, grasa_calculado_kg,
                    pliegue_supraespinal_mm, pliegue_muslo_frontal_mm, pliegue_pantorrilla_medial_mm,
                    pliegue_abdominal_mm, pliegue_tricipital_mm, pliegue_subescapular_mm,
                    pliegue_suprailiaco_mm, pliegue_bicipital_mm,
                    circ_cadera_cm, circ_pantorrilla_cm, circ_muslo_medio_cm,
                    circ_brazo_contraido_cm, circ_cintura_cm, circ_brazo_relajado_cm, circ_muslo_cm
                ) VALUES (
                    :nombre, :fecha, :grasa_faulkner_pct, :grasa_calculado_kg,
                    :pliegue_supraespinal_mm, :pliegue_muslo_frontal_mm, :pliegue_pantorrilla_medial_mm,
                    :pliegue_abdominal_mm, :pliegue_tricipital_mm, :pliegue_subescapular_mm,
                    :pliegue_suprailiaco_mm, :pliegue_bicipital_mm,
                    :circ_cadera_cm, :circ_pantorrilla_cm, :circ_muslo_medio_cm,
                    :circ_brazo_contraido_cm, :circ_cintura_cm, :circ_brazo_relajado_cm, :circ_muslo_cm
                )
            """),
            {
                "nombre": nombre,
                "fecha": campos.get("fecha") or "",
                "grasa_faulkner_pct": campos.get("grasa_faulkner_pct"),
                "grasa_calculado_kg": campos.get("grasa_calculado_kg"),
                "pliegue_supraespinal_mm": campos.get("pliegue_supraespinal_mm"),
                "pliegue_muslo_frontal_mm": campos.get("pliegue_muslo_frontal_mm"),
                "pliegue_pantorrilla_medial_mm": campos.get("pliegue_pantorrilla_medial_mm"),
                "pliegue_abdominal_mm": campos.get("pliegue_abdominal_mm"),
                "pliegue_tricipital_mm": campos.get("pliegue_tricipital_mm"),
                "pliegue_subescapular_mm": campos.get("pliegue_subescapular_mm"),
                "pliegue_suprailiaco_mm": campos.get("pliegue_suprailiaco_mm"),
                "pliegue_bicipital_mm": campos.get("pliegue_bicipital_mm"),
                "circ_cadera_cm": campos.get("circ_cadera_cm"),
                "circ_pantorrilla_cm": campos.get("circ_pantorrilla_cm"),
                "circ_muslo_medio_cm": campos.get("circ_muslo_medio_cm"),
                "circ_brazo_contraido_cm": campos.get("circ_brazo_contraido_cm"),
                "circ_cintura_cm": campos.get("circ_cintura_cm"),
                "circ_brazo_relajado_cm": campos.get("circ_brazo_relajado_cm"),
                "circ_muslo_cm": campos.get("circ_muslo_cm"),
            },
        )


def leer_historial(engine: sqlalchemy.engine.Engine, nombre: str) -> pd.DataFrame:
    return pd.read_sql(
        sqlalchemy.text("""
            SELECT
                fecha AS "Fecha",
                grasa_faulkner_pct AS "GrasaFaulkner_pct", grasa_calculado_kg AS "GrasaCalculado_kg",
                pliegue_supraespinal_mm AS "Pliegue_Supraespinal_mm",
                pliegue_muslo_frontal_mm AS "Pliegue_MusloFrontal_mm",
                pliegue_pantorrilla_medial_mm AS "Pliegue_PantorrillaMedial_mm",
                pliegue_abdominal_mm AS "Pliegue_Abdominal_mm",
                pliegue_tricipital_mm AS "Pliegue_Tricipital_mm",
                pliegue_subescapular_mm AS "Pliegue_Subescapular_mm",
                pliegue_suprailiaco_mm AS "Pliegue_Suprailiaco_mm",
                pliegue_bicipital_mm AS "Pliegue_Bicipital_mm",
                circ_cadera_cm AS "Circ_Cadera_cm", circ_pantorrilla_cm AS "Circ_Pantorrilla_cm",
                circ_muslo_medio_cm AS "Circ_MusloMedio_cm", circ_brazo_contraido_cm AS "Circ_BrazoContraido_cm",
                circ_cintura_cm AS "Circ_Cintura_cm", circ_brazo_relajado_cm AS "Circ_BrazoRelajado_cm",
                circ_muslo_cm AS "Circ_Muslo_cm"
            FROM antropometria WHERE nombre = :nombre ORDER BY id
        """),
        engine, params={"nombre": nombre},
    )
