#!/usr/bin/env python3
"""Copia todos los datos reales de la hoja de Google (las 11 pestañas) a
las 11 tablas de Postgres ya creadas con schema.sql -- corre UNA sola
vez, para pasar del piloto en Sheets al piloto en Supabase.

Lee credenciales de variables de entorno (nunca de un archivo en disco,
para no dejarlas regadas):

    GOOGLE_CREDENTIALS_JSON  -- el JSON completo de la service account
    SHEET_ID                 -- el id de la hoja de Google
    DATABASE_URL             -- postgresql://... de Supabase

TRUNCATE al inicio de cada tabla antes de copiar -- pensado para correr
contra una base recién creada (vacía); si se vuelve a correr, empieza
limpio en vez de duplicar filas."""

import json
import os
from datetime import datetime

import gspread
import sqlalchemy
from google.oauth2.service_account import Credentials


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _txt(v):
    return v if v not in (None, "") else None


def _json_o_none(v):
    if not v:
        return None
    try:
        json.loads(v)
        return v
    except (TypeError, ValueError):
        print(f"    aviso: JSON inválido, se guarda como None: {v!r}")
        return None


def _fecha_calorias(v):
    if not v:
        return None
    try:
        return datetime.strptime(v, "%d.%m.%Y").date()
    except ValueError:
        try:
            return datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError:
            return None


def main():
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    sheet_id = os.environ["SHEET_ID"]
    database_url = os.environ["DATABASE_URL"]

    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    engine = sqlalchemy.create_engine(database_url)

    resumen = 0

    def migrar_tabla(hoja_nombre, tabla, mapeo, columnas_jsonb=(), requerido="nombre"):
        """`mapeo`: {columna_postgres: (columna_sheets, función_de_conversión)}.
        `columnas_jsonb`: nombres de columnas (ya en postgres) que son JSONB
        -- se les agrega CAST(:col AS JSONB) en vez de solo :col, porque
        Postgres no convierte texto a jsonb solo de verlo."""
        nonlocal resumen
        try:
            ws = sh.worksheet(hoja_nombre)
        except gspread.exceptions.WorksheetNotFound:
            print(f"[{hoja_nombre}] no existe en la hoja -- se omite.")
            return
        registros = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
        print(f"[{hoja_nombre}] {len(registros)} filas leídas de Sheets.")

        with engine.begin() as conn:
            conn.execute(sqlalchemy.text(f"TRUNCATE TABLE {tabla}"))
            insertadas, omitidas = 0, 0
            for row in registros:
                fila = {col_pg: fn(row.get(col_sheets)) for col_pg, (col_sheets, fn) in mapeo.items()}
                if not fila.get(requerido):
                    omitidas += 1
                    continue
                columnas = ", ".join(fila.keys())
                placeholders = ", ".join(
                    f"CAST(:{k} AS JSONB)" if k in columnas_jsonb else f":{k}" for k in fila.keys()
                )
                conn.execute(sqlalchemy.text(f"INSERT INTO {tabla} ({columnas}) VALUES ({placeholders})"), fila)
                insertadas += 1
        print(f"[{hoja_nombre}] -> {tabla}: {insertadas} insertadas, {omitidas} omitidas (sin '{requerido}').")
        resumen += insertadas

    # ---- Hoja1 (la principal, sh.sheet1 -- no tiene nombre de pestaña fijo) ----
    ws_principal = sh.sheet1
    registros = ws_principal.get_all_records(value_render_option="UNFORMATTED_VALUE")
    print(f"[Hoja1/{ws_principal.title}] {len(registros)} filas leídas de Sheets.")
    with engine.begin() as conn:
        conn.execute(sqlalchemy.text("TRUNCATE TABLE resumen"))
        insertadas, omitidas = 0, 0
        for row in registros:
            nombre = _txt(row.get("Nombre"))
            if not nombre:
                omitidas += 1
                continue
            conn.execute(
                sqlalchemy.text("""
                    INSERT INTO resumen (nombre, fecha, calificacion, recuperacion, sueno, actividad,
                        dias_con_actividad, dias_sin_actividad, rhr_7d, datos, fuente)
                    VALUES (:nombre, :fecha, :calificacion, :recuperacion, :sueno, :actividad,
                        :dias_con_actividad, :dias_sin_actividad, :rhr_7d, CAST(:datos AS JSONB), :fuente)
                """),
                {
                    "nombre": nombre, "fecha": _txt(row.get("Fecha")),
                    "calificacion": _num(row.get("Calificacion")), "recuperacion": _num(row.get("Recuperacion")),
                    "sueno": _num(row.get("Sueno")), "actividad": _num(row.get("Actividad")),
                    "dias_con_actividad": _num(row.get("DiasConActividad")),
                    "dias_sin_actividad": _num(row.get("DiasSinActividad")),
                    "rhr_7d": _num(row.get("RHR7d")), "datos": _json_o_none(row.get("Datos")),
                    "fuente": _txt(row.get("Fuente")),
                },
            )
            insertadas += 1
    print(f"[Hoja1] -> resumen: {insertadas} insertadas, {omitidas} omitidas.")
    resumen += insertadas

    migrar_tabla("Enfoque", "enfoque", {
        "nombre": ("Nombre", _txt), "enfoque": ("Enfoque", _txt), "meta_grasa_pct": ("MetaGrasaPct", _num),
        "dias_plan_mes": ("DiasPlanMes", _num), "condicion_metabolica": ("CondicionMetabolica", _txt),
        "glp1_molecula": ("GLP1Molecula", _txt), "glp1_dosis": ("GLP1Dosis", _txt),
        "glp1_fecha_inicio": ("GLP1FechaInicio", _txt), "nutriologo": ("Nutriologo", _txt),
        "fecha": ("Fecha", _txt),
    })

    migrar_tabla("Notas", "notas", {
        "nombre": ("Nombre", _txt), "fecha": ("Fecha", _txt), "nota": ("Nota", _txt),
    })

    migrar_tabla("InBody", "inbody", {
        "nombre": ("Nombre", _txt), "fecha": ("Fecha", _txt), "modelo": ("Modelo", _txt),
        "altura_cm": ("Altura_cm", _num), "edad": ("Edad", _num), "sexo": ("Sexo", _txt),
        "peso_kg": ("Peso_kg", _num), "masa_grasa_kg": ("MasaGrasa_kg", _num), "mme_kg": ("MME_kg", _num),
        "grasa_visceral": ("GrasaVisceral", _num), "agua_total_l": ("AguaTotal_L", _num),
        "agua_intra_l": ("AguaIntra_L", _num), "agua_extra_l": ("AguaExtra_L", _num),
        "imc": ("IMC", _num), "pgc_pct": ("PGC_pct", _num), "bmr_kcal": ("BMR_kcal", _num),
    })

    migrar_tabla("Antropometria", "antropometria", {
        "nombre": ("Nombre", _txt), "fecha": ("Fecha", _txt),
        "grasa_faulkner_pct": ("GrasaFaulkner_pct", _num), "grasa_calculado_kg": ("GrasaCalculado_kg", _num),
        "pliegue_supraespinal_mm": ("Pliegue_Supraespinal_mm", _num),
        "pliegue_muslo_frontal_mm": ("Pliegue_MusloFrontal_mm", _num),
        "pliegue_pantorrilla_medial_mm": ("Pliegue_PantorrillaMedial_mm", _num),
        "pliegue_abdominal_mm": ("Pliegue_Abdominal_mm", _num),
        "pliegue_tricipital_mm": ("Pliegue_Tricipital_mm", _num),
        "pliegue_subescapular_mm": ("Pliegue_Subescapular_mm", _num),
        "pliegue_suprailiaco_mm": ("Pliegue_Suprailiaco_mm", _num),
        "pliegue_bicipital_mm": ("Pliegue_Bicipital_mm", _num),
        "circ_cadera_cm": ("Circ_Cadera_cm", _num), "circ_pantorrilla_cm": ("Circ_Pantorrilla_cm", _num),
        "circ_muslo_medio_cm": ("Circ_MusloMedio_cm", _num),
        "circ_brazo_contraido_cm": ("Circ_BrazoContraido_cm", _num),
        "circ_cintura_cm": ("Circ_Cintura_cm", _num),
        "circ_brazo_relajado_cm": ("Circ_BrazoRelajado_cm", _num),
        "circ_muslo_cm": ("Circ_Muslo_cm", _num),
    })

    migrar_tabla(
        "Calorias", "calorias",
        {"nombre": ("Nombre", _txt), "fecha": ("Fecha", _fecha_calorias), "calorias_comidas": ("CaloriasComidas", _num)},
        requerido="fecha",
    )

    migrar_tabla("Estudios", "estudios", {
        "nombre": ("Nombre", _txt), "fecha": ("Fecha", _txt), "laboratorio": ("Laboratorio", _txt),
        "resultados": ("Resultados", _json_o_none),
    }, columnas_jsonb=("resultados",))

    migrar_tabla("LibreVinculo", "libre_vinculo", {
        "nombre": ("Nombre", _txt), "libre_patient_id": ("LibrePatientId", _txt),
        "libre_patient_nombre": ("LibrePatientNombre", _txt),
    })

    migrar_tabla("Usuarios", "usuarios", {
        "usuario": ("Usuario", _txt), "nombre": ("Nombre", _txt), "password_hash": ("PasswordHash", _txt),
        "salt": ("Salt", _txt), "rol": ("Rol", _txt), "fecha": ("Fecha", _txt),
    }, requerido="usuario")

    migrar_tabla("Feedback", "feedback", {
        "fecha": ("Fecha", _txt), "usuario": ("Usuario", _txt), "paciente": ("Paciente", _txt),
        "mensaje": ("Mensaje", _txt),
    }, requerido="mensaje")

    migrar_tabla("TokensGarmin", "tokens_garmin", {
        "nombre": ("Nombre", _txt), "token": ("Token", _txt), "fecha_guardado": ("FechaGuardado", _txt),
        "clave_conexion": ("ClaveConexion", _txt),
    })

    print(f"\nListo -- {resumen} filas migradas en total (contando 'resumen').")


if __name__ == "__main__":
    main()
