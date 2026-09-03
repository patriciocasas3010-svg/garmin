#!/usr/bin/env python3
"""Herramienta de una sola vez: busca en tus actividades recientes de Garmin
el campo de "pérdida de líquidos estimada" (o como se llame internamente en
la respuesta de Garmin -- no está documentado, así que lo buscamos por
palabras clave en tu cuenta real).

Uso:
    python3 buscar_liquidos.py
"""

import json
from datetime import date, timedelta

from garmin_session import get_client

PALABRAS_CLAVE = ["sweat", "water", "liquid", "fluid", "hydrat", "sudor", "liquido"]


def _buscar(obj, ruta=""):
    """Recorre un dict/list anidado y regresa (ruta, valor) de las llaves
    que contienen alguna de las palabras clave."""
    encontrados = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            nueva_ruta = f"{ruta}.{k}" if ruta else k
            if any(p in k.lower() for p in PALABRAS_CLAVE):
                encontrados.append((nueva_ruta, v))
            encontrados.extend(_buscar(v, nueva_ruta))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:3]):  # solo los primeros 3 de una lista, para no tardar de más
            encontrados.extend(_buscar(v, f"{ruta}[{i}]"))
    return encontrados


def main():
    client = get_client()

    end = date.today()
    start = end - timedelta(days=180)
    print(f"Buscando en tus actividades de los últimos 180 días ({start} a {end})...\n")

    actividades = client.get_activities_by_date(start.isoformat(), end.isoformat()) or []
    if not actividades:
        print("No encontré actividades en ese periodo.")
        return

    print(f"Encontré {len(actividades)} actividades. Revisando el detalle de cada una...\n")

    primera_con_dato = None
    vistos = set()

    for a in actividades:
        activity_id = a.get("activityId")
        nombre = a.get("activityName")
        tipo = (a.get("activityType") or {}).get("typeKey")
        if not activity_id:
            continue
        try:
            detalle = client.get_activity(activity_id)
        except Exception as e:
            print(f"  (no se pudo leer '{nombre}': {e})")
            continue

        encontrados = _buscar(detalle)
        if encontrados:
            claves_unicas = {k for k, _ in encontrados}
            if not claves_unicas.issubset(vistos):
                vistos |= claves_unicas
                print(f"Actividad: {nombre} ({tipo}) -- {a.get('startTimeLocal')}")
                for ruta, valor in encontrados:
                    print(f"    {ruta} = {valor}")
                print()
            if primera_con_dato is None:
                primera_con_dato = (nombre, detalle)

    if primera_con_dato is None:
        print(
            "No encontré ningún campo relacionado a líquidos/sudor en tus actividades recientes.\n"
            "Puede que tu modelo de reloj no calcule esta métrica, o que Garmin la llame de una "
            "forma que no está en mi lista de palabras clave."
        )
        return

    nombre, detalle = primera_con_dato
    with open("ejemplo_actividad.json", "w", encoding="utf-8") as f:
        json.dump(detalle, f, indent=2, ensure_ascii=False)
    print(f"Guardé el detalle completo de '{nombre}' en ejemplo_actividad.json por si hace falta revisarlo.")


if __name__ == "__main__":
    main()
