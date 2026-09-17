"""Guarda y lee el historial de resultados de InBody de cada paciente, en
la tabla "inbody" de Postgres -- así el nutriólogo lleva el historial de
composición corporal de cada paciente en el mismo lugar, sin mezclarlo
con el resumen de Garmin/Apple Health (tabla "resumen")."""

import pandas as pd
import sqlalchemy

ENCABEZADOS = [
    "Nombre", "Fecha", "Modelo", "Altura_cm", "Edad", "Sexo",
    "Peso_kg", "MasaGrasa_kg", "MME_kg", "GrasaVisceral",
    "AguaTotal_L", "AguaIntra_L", "AguaExtra_L", "IMC", "PGC_pct", "BMR_kcal",
]


def guardar_registro(engine: sqlalchemy.engine.Engine, nombre: str, campos: dict) -> None:
    """Agrega una fila nueva al historial -- cada resultado de InBody es
    una medición puntual (como un peso en una báscula), no algo que se
    "actualice"; por eso siempre se agrega, nunca se sobreescribe."""
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO inbody (
                    nombre, fecha, modelo, altura_cm, edad, sexo, peso_kg, masa_grasa_kg,
                    mme_kg, grasa_visceral, agua_total_l, agua_intra_l, agua_extra_l, imc, pgc_pct, bmr_kcal
                ) VALUES (
                    :nombre, :fecha, :modelo, :altura_cm, :edad, :sexo, :peso_kg, :masa_grasa_kg,
                    :mme_kg, :grasa_visceral, :agua_total_l, :agua_intra_l, :agua_extra_l, :imc, :pgc_pct, :bmr_kcal
                )
            """),
            {
                "nombre": nombre,
                "fecha": campos.get("fecha") or "",
                "modelo": campos.get("modelo") or "",
                "altura_cm": campos.get("altura_cm"),
                "edad": campos.get("edad"),
                "sexo": campos.get("sexo") or "",
                "peso_kg": campos.get("peso_kg"),
                "masa_grasa_kg": campos.get("masa_grasa_kg"),
                "mme_kg": campos.get("mme_kg"),
                "grasa_visceral": campos.get("grasa_visceral"),
                "agua_total_l": campos.get("agua_total_l"),
                "agua_intra_l": campos.get("agua_intra_l"),
                "agua_extra_l": campos.get("agua_extra_l"),
                "imc": campos.get("imc"),
                "pgc_pct": campos.get("pgc_pct"),
                "bmr_kcal": campos.get("bmr_kcal"),
            },
        )


def leer_historial(engine: sqlalchemy.engine.Engine, nombre: str) -> pd.DataFrame:
    return pd.read_sql(
        sqlalchemy.text("""
            SELECT
                fecha AS "Fecha", modelo AS "Modelo", altura_cm AS "Altura_cm", edad AS "Edad",
                sexo AS "Sexo", peso_kg AS "Peso_kg", masa_grasa_kg AS "MasaGrasa_kg",
                mme_kg AS "MME_kg", grasa_visceral AS "GrasaVisceral", agua_total_l AS "AguaTotal_L",
                agua_intra_l AS "AguaIntra_L", agua_extra_l AS "AguaExtra_L", imc AS "IMC",
                pgc_pct AS "PGC_pct", bmr_kcal AS "BMR_kcal"
            FROM inbody WHERE nombre = :nombre ORDER BY id
        """),
        engine, params={"nombre": nombre},
    )
