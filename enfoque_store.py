"""Guarda y lee el "perfil" de enfoque de cada paciente -- el enfoque
principal (pérdida de peso, rendimiento deportivo, etc.), la meta de
% de grasa corporal, los días de entrenamiento planeados por mes, y
la condición metabólica/GLP-1 -- en la tabla "enfoque" de Postgres,
igual que notas_store.py/inbody_store.py.

La condición metabólica y el GLP-1 son el prerrequisito de la sección
"GLP-1 y Diabéticos" del dashboard (ver glp1_diabetes.py): sin saber
que el paciente tiene diabetes o toma GLP-1, no hay forma de decidir
si mostrarle esa sección a la nutrióloga.

A diferencia de las notas (que son un historial que se va acumulando),
aquí solo importa el valor ACTUAL de cada campo -- por eso se
sobreescribe en vez de agregarse. El upsert (INSERT ... ON CONFLICT)
actualiza solo los campos que llegaron con un valor (COALESCE contra el
valor ya guardado) en una sola instrucción atómica -- reemplaza al
"leer toda la hoja, buscar la fila, armar la fila completa a mano,
escribir" que hacía esto mismo en gspread."""

import sqlalchemy

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


def guardar_perfil(
    engine: sqlalchemy.engine.Engine, nombre: str,
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
    from datetime import date
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                INSERT INTO enfoque (
                    nombre, enfoque, meta_grasa_pct, dias_plan_mes, condicion_metabolica,
                    glp1_molecula, glp1_dosis, glp1_fecha_inicio, nutriologo, fecha
                ) VALUES (
                    :nombre, :enfoque, :meta_grasa_pct, :dias_plan_mes, :condicion_metabolica,
                    :glp1_molecula, :glp1_dosis, :glp1_fecha_inicio, :nutriologo, :fecha
                )
                ON CONFLICT (nombre) DO UPDATE SET
                    enfoque = COALESCE(EXCLUDED.enfoque, enfoque.enfoque),
                    meta_grasa_pct = COALESCE(EXCLUDED.meta_grasa_pct, enfoque.meta_grasa_pct),
                    dias_plan_mes = COALESCE(EXCLUDED.dias_plan_mes, enfoque.dias_plan_mes),
                    condicion_metabolica = COALESCE(EXCLUDED.condicion_metabolica, enfoque.condicion_metabolica),
                    glp1_molecula = COALESCE(EXCLUDED.glp1_molecula, enfoque.glp1_molecula),
                    glp1_dosis = COALESCE(EXCLUDED.glp1_dosis, enfoque.glp1_dosis),
                    glp1_fecha_inicio = COALESCE(EXCLUDED.glp1_fecha_inicio, enfoque.glp1_fecha_inicio),
                    nutriologo = COALESCE(EXCLUDED.nutriologo, enfoque.nutriologo),
                    fecha = EXCLUDED.fecha
            """),
            {
                "nombre": nombre, "enfoque": enfoque, "meta_grasa_pct": meta_grasa_pct,
                "dias_plan_mes": dias_plan_mes, "condicion_metabolica": condicion_metabolica,
                "glp1_molecula": glp1_molecula, "glp1_dosis": glp1_dosis, "glp1_fecha_inicio": glp1_fecha_inicio,
                "nutriologo": nutriologo, "fecha": date.today().strftime("%d.%m.%Y"),
            },
        )


def guardar_enfoque(engine: sqlalchemy.engine.Engine, nombre: str, enfoque: str) -> None:
    """Compatibilidad con el flujo existente -- guarda solo el enfoque,
    sin tocar la meta de grasa ni los días de plan ya guardados."""
    guardar_perfil(engine, nombre, enfoque=enfoque)


def _a_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _a_int(v):
    f = _a_float(v)
    return int(f) if f is not None else None


def leer_perfil(engine: sqlalchemy.engine.Engine, nombre: str) -> dict:
    """{"enfoque", "meta_grasa_pct", "dias_plan_mes", "condicion_metabolica",
    "glp1_molecula", "glp1_dosis", "glp1_fecha_inicio", "nutriologo"}."""
    vacio = {
        "enfoque": None, "meta_grasa_pct": None, "dias_plan_mes": None,
        "condicion_metabolica": "Ninguna", "glp1_molecula": "No usa",
        "glp1_dosis": None, "glp1_fecha_inicio": None, "nutriologo": None,
    }
    with engine.connect() as conn:
        fila = conn.execute(
            sqlalchemy.text("SELECT * FROM enfoque WHERE nombre = :nombre"), {"nombre": nombre},
        ).mappings().first()
    if fila is None:
        return vacio
    return {
        "enfoque": fila["enfoque"] or None,
        "meta_grasa_pct": _a_float(fila["meta_grasa_pct"]),
        "dias_plan_mes": _a_int(fila["dias_plan_mes"]),
        "condicion_metabolica": fila["condicion_metabolica"] or "Ninguna",
        "glp1_molecula": fila["glp1_molecula"] or "No usa",
        "glp1_dosis": fila["glp1_dosis"] or None,
        "glp1_fecha_inicio": fila["glp1_fecha_inicio"] or None,
        "nutriologo": fila["nutriologo"] or None,
    }


def leer_todas_las_asignaciones(engine: sqlalchemy.engine.Engine) -> dict:
    """{nombre_paciente: usuario_nutriologo_asignado} de TODOS los
    pacientes de un jalón -- para filtrar el listado de la pantalla de
    selección según quién esté logueado, sin tener que leer_perfil()
    paciente por paciente. "" (sin asignar) para quien no tenga."""
    with engine.connect() as conn:
        filas = conn.execute(sqlalchemy.text("SELECT nombre, nutriologo FROM enfoque")).all()
    return {nombre: (nutriologo or "") for nombre, nutriologo in filas}


def leer_enfoque(engine: sqlalchemy.engine.Engine, nombre: str) -> str | None:
    """Compatibilidad con el flujo existente (ai_analisis.py, etc.) --
    ver leer_perfil() para los campos nuevos."""
    return leer_perfil(engine, nombre)["enfoque"]
