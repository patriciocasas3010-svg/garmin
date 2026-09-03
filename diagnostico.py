#!/usr/bin/env python3
"""Diagnóstico puntual: revisa por qué una fecha concreta no aparece bien
clasificada como 'día con actividad' en el dashboard.

Uso:
    python3 diagnostico.py 2026-09-02
"""

import sys
from datetime import date, timedelta

import pandas as pd

import garmin_metrics as gm
from garmin_session import get_client


def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: python3 diagnostico.py YYYY-MM-DD")

    fecha_a_revisar = sys.argv[1]

    print("Conectando con Garmin...")
    client = get_client()

    end = date.today()
    start90 = end - timedelta(days=90)
    start30 = end - timedelta(days=30)

    print("Descargando sueño de los últimos 30 días (puede tardar unos segundos)...")
    sleep_df = gm.fetch_sleep_series(client, start30, end)

    print("Descargando actividades de los últimos 90 días...")
    activities = gm.fetch_activities(client, start90, end)

    wellness_start_ts = pd.Timestamp(sleep_df.index.min())
    wellness_end_ts = pd.Timestamp(sleep_df.index.max())
    print(f"\nVentana de bienestar: {wellness_start_ts.date()} a {wellness_end_ts.date()}")

    dias_activos = {
        pd.Timestamp(a["startTimeLocal"][:10])
        for a in activities
        if a.get("startTimeLocal") and wellness_start_ts <= pd.Timestamp(a["startTimeLocal"][:10]) <= wellness_end_ts
    }

    objetivo = pd.Timestamp(fecha_a_revisar)
    print(f"\n¿{fecha_a_revisar} está en dias_activos? {objetivo in dias_activos}")

    acts_ese_dia = [
        (a.get("activityName"), a.get("startTimeLocal"))
        for a in activities
        if str(a.get("startTimeLocal", "")).startswith(fecha_a_revisar)
    ]
    print(f"Actividades encontradas el {fecha_a_revisar}: {acts_ese_dia}")
    print(f"Total de actividades traídas (90 días): {len(activities)}")

    print(f"\nTodos los días con actividad detectados ({len(dias_activos)}):")
    for d in sorted(dias_activos):
        print(" ", d.date())


if __name__ == "__main__":
    main()
