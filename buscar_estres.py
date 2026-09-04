#!/usr/bin/env python3
"""Herramienta de una sola vez: imprime la respuesta real de Garmin para
Fitness Age y Nivel de estrés de hoy, para confirmar (o corregir) los
nombres de campo que asume garmin_metrics.fetch_fitness_age/fetch_nivel_estres.

Uso:
    python3 buscar_estres.py
"""

import json
from datetime import date

from garmin_session import get_client


def main():
    client = get_client()
    hoy = date.today()

    print(f"--- Fitness Age ({hoy.isoformat()}) ---")
    try:
        fitness = client.get_fitnessage_data(hoy.isoformat())
        print(json.dumps(fitness, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

    print(f"\n--- Estrés ({hoy.isoformat()}) ---")
    try:
        estres = client.get_stress_data(hoy.isoformat())
        # el array minuto-a-minuto puede ser larguísimo -- lo recortamos
        # para que la salida sea legible, pero dejamos todo lo demás.
        if isinstance(estres, dict):
            for llave in ("stressValuesArray", "bodyBatteryValuesArray"):
                if llave in estres and isinstance(estres[llave], list):
                    estres[llave] = estres[llave][:3] + ["... (recortado)"]
        print(json.dumps(estres, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
