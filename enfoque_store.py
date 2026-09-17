"""Guarda y lee el "perfil" de enfoque de cada paciente -- el enfoque
principal (pérdida de peso, rendimiento deportivo, etc.), la meta de
% de grasa corporal, los días de entrenamiento planeados por mes, y
la condición metabólica/GLP-1 -- en una pestaña separada ("Enfoque")
dentro de la misma hoja de Google, igual que notas_store.py/inbody_store.py.

La condición metabólica y el GLP-1 son el prerrequisito de la sección
"GLP-1 y Diabéticos" del dashboard (ver glp1_diabetes.py): sin saber
que el paciente tiene diabetes o toma GLP-1, no hay forma de decidir
si mostrarle esa sección a la nutrióloga.

A diferencia de las notas (que son un historial que se va acumulando),
aquí solo importa el valor ACTUAL de cada campo -- por eso se
sobreescribe en vez de agregarse, para no ir juntando enfoques viejos
que ya no aplican."""

from datetime import date

import gspread
import pandas as pd
import streamlit as st

import sheet_cache

HOJA_NOMBRE = "Enfoque"

ENCABEZADOS = [
    "Nombre", "Enfoque", "MetaGrasaPct", "DiasPlanMes",
    "CondicionMetabolica", "GLP1Molecula", "GLP1Dosis", "GLP1FechaInicio",
    "Nutriologo", "Fecha",
]

OPCIONES = [
    "Pérdida de peso",
    "Ganancia muscular",
    "Rendimiento deportivo / atleta",
    "Control de una condición médica (diabetes, hipertensión, etc.)",
    "Mantenimiento / bienestar general",
]

OPCIONES_CONDICION_METABOLICA = [
    "Ninguna",
    "Prediabetes",
    "Diabetes tipo 2",
    "Diabetes tipo 1",
]

OPCIONES_GLP1 = [
    "No usa",
    "Semaglutida (Ozempic/Wegovy)",
    "Tirzepatida (Mounjaro/Zepbound)",
    "Liraglutida (Saxenda/Victoza)",
    "Otro",
]

# (etiqueta, días de plan por mes equivalentes) -- categorías en vez de
# pedir un número exacto, para que sea más rápido de llenar. El número
# guardado es solo un equivalente aproximado (semana * ~4.3) para poder
# seguir comparando contra los días realmente ejercitados en el resumen.
OPCIONES_DIAS_PLAN = [
    ("Nula", 0),
    ("Sedentario (1-2 días por semana)", 7),
    ("Intermedio (3-5 días por semana)", 17),
    ("Alto (más de 4 días por semana)", 24),
]


def _worksheet(gc: gspread.Client, sheet_id: str):
    return sheet_cache.abrir_worksheet(gc, sheet_id, HOJA_NOMBRE, tuple(ENCABEZADOS))


def guardar_perfil(
    gc: gspread.Client, sheet_id: str, nombre: str,
    enfoque: str | None = None, meta_grasa_pct: float | None = None, dias_plan_mes: int | None = None,
    condicion_metabolica: str | None = None, glp1_molecula: str | None = None,
    glp1_dosis: str | None = None, glp1_fecha_inicio: str | None = None,
    nutriologo: str | None = None,
) -> None:
    """Actualiza solo los campos que no sean None -- así guardar el
    enfoque no borra sin querer la meta de grasa, los días de plan, el
    GLP-1/condición metabólica o el nutriólogo asignado que ya se
    habían capturado antes (y viceversa). `nutriologo` es el "usuario"
    (ver usuarios_store.py) del nutriólogo dueño de este paciente --
    "" (string vacío, a propósito, no None) lo deja sin asignar."""
    ws = _worksheet(gc, sheet_id)
    registros = ws.get_all_values()
    if not registros:
        ws.append_row(ENCABEZADOS)
        registros = [ENCABEZADOS]
    ultima_col = chr(ord("A") + len(ENCABEZADOS) - 1)

    for i, row in enumerate(registros[1:], start=2):
        if row and row[0] == nombre:
            actual = row + [""] * (len(ENCABEZADOS) - len(row))
            nueva_fila = [
                nombre,
                enfoque if enfoque is not None else actual[1],
                meta_grasa_pct if meta_grasa_pct is not None else actual[2],
                dias_plan_mes if dias_plan_mes is not None else actual[3],
                condicion_metabolica if condicion_metabolica is not None else actual[4],
                glp1_molecula if glp1_molecula is not None else actual[5],
                glp1_dosis if glp1_dosis is not None else actual[6],
                glp1_fecha_inicio if glp1_fecha_inicio is not None else actual[7],
                nutriologo if nutriologo is not None else actual[8],
                date.today().strftime("%d.%m.%Y"),
            ]
            ws.update(f"A{i}:{ultima_col}{i}", [nueva_fila])
            return
    ws.append_row([
        nombre, enfoque or "", meta_grasa_pct or "", dias_plan_mes or "",
        condicion_metabolica or "", glp1_molecula or "", glp1_dosis or "", glp1_fecha_inicio or "",
        nutriologo or "", date.today().strftime("%d.%m.%Y"),
    ])


def guardar_enfoque(gc: gspread.Client, sheet_id: str, nombre: str, enfoque: str) -> None:
    """Compatibilidad con el flujo existente -- guarda solo el enfoque,
    sin tocar la meta de grasa ni los días de plan ya guardados."""
    guardar_perfil(gc, sheet_id, nombre, enfoque=enfoque)


def _a_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _a_int(v):
    f = _a_float(v)
    return int(f) if f is not None else None


@st.cache_data(ttl=30, show_spinner=False)
def leer_perfil(_gc: gspread.Client, sheet_id: str, nombre: str) -> dict:
    """{"enfoque", "meta_grasa_pct", "dias_plan_mes", "condicion_metabolica",
    "glp1_molecula", "glp1_dosis", "glp1_fecha_inicio", "nutriologo"}."""
    vacio = {
        "enfoque": None, "meta_grasa_pct": None, "dias_plan_mes": None,
        "condicion_metabolica": "Ninguna", "glp1_molecula": "No usa",
        "glp1_dosis": None, "glp1_fecha_inicio": None, "nutriologo": None,
    }
    ws = _worksheet(_gc, sheet_id)
    registros = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    df = pd.DataFrame(registros)
    if df.empty or "Nombre" not in df.columns:
        return vacio
    fila = df[df["Nombre"] == nombre]
    if fila.empty:
        return vacio
    ultima = fila.iloc[-1]
    return {
        "enfoque": ultima.get("Enfoque") or None,
        "meta_grasa_pct": _a_float(ultima.get("MetaGrasaPct")),
        "dias_plan_mes": _a_int(ultima.get("DiasPlanMes")),
        "condicion_metabolica": ultima.get("CondicionMetabolica") or "Ninguna",
        "glp1_molecula": ultima.get("GLP1Molecula") or "No usa",
        "glp1_dosis": ultima.get("GLP1Dosis") or None,
        "glp1_fecha_inicio": ultima.get("GLP1FechaInicio") or None,
        "nutriologo": ultima.get("Nutriologo") or None,
    }


@st.cache_data(ttl=30, show_spinner=False)
def leer_todas_las_asignaciones(_gc: gspread.Client, sheet_id: str) -> dict:
    """{nombre_paciente: usuario_nutriologo_asignado} de TODOS los
    pacientes de un jalón -- para filtrar el listado de la pantalla de
    selección según quién esté logueado, sin tener que leer_perfil()
    paciente por paciente. "" (sin asignar) para quien no tenga."""
    ws = _worksheet(_gc, sheet_id)
    return {row[0]: (row[8] if len(row) > 8 else "") for row in ws.get_all_values()[1:] if row and row[0]}


def leer_enfoque(_gc: gspread.Client, sheet_id: str, nombre: str) -> str | None:
    """Compatibilidad con el flujo existente (ai_analisis.py, etc.) --
    ver leer_perfil() para los campos nuevos."""
    return leer_perfil(_gc, sheet_id, nombre)["enfoque"]
