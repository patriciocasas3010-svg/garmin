#!/usr/bin/env python3
"""Herramienta de una sola vez: revisa tus actividades de fuerza recientes
en Garmin Connect para ver si de verdad traen series/repeticiones/peso
(no solo duración y frecuencia cardiaca) -- y de paso confirma que el
ritmo (pace) de tus carreras sí viene en el detalle de cada actividad,
como en cualquier otro reporte de este proyecto.

Uso:
    python3 buscar_fuerza.py
"""

import json
from datetime import date, timedelta

from garmin_session import get_client

PALABRAS_FUERZA = ["strength", "fuerza", "weight", "gym", "training"]


def main():
    client = get_client()

    end = date.today()
    start = end - timedelta(days=180)
    print(f"Buscando en tus actividades de los últimos 180 días ({start} a {end})...\n")

    actividades = client.get_activities_by_date(start.isoformat(), end.isoformat()) or []
    if not actividades:
        print("No encontré actividades en ese periodo.")
        return

    tipos_vistos = {}
    for a in actividades:
        tipo = (a.get("activityType") or {}).get("typeKey") or "sin_tipo"
        tipos_vistos[tipo] = tipos_vistos.get(tipo, 0) + 1

    print("Tipos de actividad encontrados en estos 180 días:")
    for tipo, n in sorted(tipos_vistos.items(), key=lambda x: -x[1]):
        print(f"  {tipo}: {n}")
    print()

    # ---------------------------------------------------------------
    # 1. Actividades de fuerza -- ¿traen series/repeticiones/peso?
    # ---------------------------------------------------------------
    de_fuerza = [
        a for a in actividades
        if any(p in ((a.get("activityType") or {}).get("typeKey") or "").lower() for p in PALABRAS_FUERZA)
        or any(p in (a.get("activityName") or "").lower() for p in PALABRAS_FUERZA)
    ]

    print(f"Encontré {len(de_fuerza)} actividades que parecen de fuerza.\n")

    revisadas = 0
    con_series = 0
    for a in de_fuerza[:8]:  # no hace falta revisar más de un puñado
        activity_id = a.get("activityId")
        nombre = a.get("activityName")
        fecha = a.get("startTimeLocal")
        if not activity_id:
            continue
        revisadas += 1
        print(f"--- {nombre} ({fecha}) ---")
        try:
            sets = client.get_activity_exercise_sets(activity_id)
        except Exception as e:
            print(f"  No se pudo leer exerciseSets: {e}")
            continue

        ejercicios = (sets or {}).get("exerciseSets") or (sets or {}).get("sets") or []
        if not ejercicios and isinstance(sets, dict):
            # por si la respuesta viene con otra llave -- mostramos las
            # llaves de primer nivel para saber cómo está armada.
            print(f"  Respuesta sin 'exerciseSets'/'sets' reconocible. Llaves: {list(sets.keys())}")
        elif not ejercicios:
            print("  Sin datos de series (la actividad no trae ese detalle).")
        else:
            con_series += 1
            print(f"  {len(ejercicios)} serie(s) encontradas. Primeras 3:")
            for s in ejercicios[:3]:
                print(f"    {json.dumps(s, ensure_ascii=False)}")
        print()

    if revisadas and con_series == 0:
        print(
            "Ninguna de las actividades de fuerza revisadas trae series/peso/repeticiones -- "
            "puede que se hayan registrado sin capturar el peso en el reloj/app durante el entrenamiento.\n"
        )
    elif con_series:
        print(f"{con_series} de {revisadas} actividades de fuerza revisadas sí traen series con datos.\n")

    if de_fuerza:
        activity_id = de_fuerza[0].get("activityId")
        try:
            detalle_completo = client.get_activity_exercise_sets(activity_id)
            with open("ejemplo_fuerza.json", "w", encoding="utf-8") as f:
                json.dump(detalle_completo, f, indent=2, ensure_ascii=False)
            print("Guardé el detalle completo de la primera actividad de fuerza en ejemplo_fuerza.json.\n")
        except Exception:
            pass

    # ---------------------------------------------------------------
    # 2. Una carrera reciente -- ¿trae pace/velocidad?
    # ---------------------------------------------------------------
    carreras = [
        a for a in actividades
        if "running" in ((a.get("activityType") or {}).get("typeKey") or "").lower()
    ]
    print(f"Encontré {len(carreras)} actividades de carrera.")
    if carreras:
        a = carreras[0]
        print(f"Ejemplo -- {a.get('activityName')} ({a.get('startTimeLocal')}):")
        print(f"  distance: {a.get('distance')} m")
        print(f"  duration: {a.get('duration')} s")
        print(f"  averageSpeed: {a.get('averageSpeed')} m/s")
        print(f"  averageHR: {a.get('averageHR')}")


if __name__ == "__main__":
    main()
