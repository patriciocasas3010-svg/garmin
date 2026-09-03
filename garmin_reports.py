#!/usr/bin/env python3
"""Reportes y gráficas a partir de tus datos de Garmin Connect.

Requiere haber corrido antes connect_garmin.py (usa la misma sesión guardada).

Uso:
    python3 garmin_reports.py                # corre los 4 reportes
    python3 garmin_reports.py rhr             # solo frecuencia cardiaca en reposo
    python3 garmin_reports.py carga           # solo carga de entrenamiento vs sueño
    python3 garmin_reports.py semana          # solo resumen semanal estilo Strava
    python3 garmin_reports.py records         # solo récords personales del año

Las gráficas se guardan como archivos .png en la carpeta 'graficas/'.
"""

import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from garmin_session import get_client

GRAFICAS_DIR = "graficas"


def _ensure_graficas_dir():
    import os

    os.makedirs(GRAFICAS_DIR, exist_ok=True)


def _parse_date(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# 1. Frecuencia cardiaca en reposo (últimos 3 meses)
# ---------------------------------------------------------------------------

def resting_heart_rate_trend(client, months: int = 3):
    print("\n--- Frecuencia cardiaca en reposo ---")
    end = date.today()
    start = end - timedelta(days=30 * months)

    data = client.connectapi(
        f"{client.garmin_connect_rhr_url}/{client.display_name}",
        params={
            "fromDate": start.isoformat(),
            "untilDate": end.isoformat(),
            "metricId": 60,
        },
    )
    entries = (
        (data or {})
        .get("allMetrics", {})
        .get("metricsMap", {})
        .get("WELLNESS_RESTING_HEART_RATE", [])
        or []
    )

    points = [
        (e["calendarDate"], e["value"])
        for e in entries
        if e.get("value") is not None and e.get("calendarDate")
    ]
    points.sort()

    if len(points) < 5:
        print(
            "No hay suficientes datos de frecuencia cardiaca en reposo en los "
            "últimos 3 meses para hacer un análisis (revisa que tu reloj mida FC "
            "en reposo y se sincronice seguido)."
        )
        return

    dates = [_parse_date(d) for d, _ in points]
    values = [v for _, v in points]

    xs = [(d - dates[0]).days for d in dates]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = (
        sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values)) / den
        if den
        else 0.0
    )
    trend_per_month = slope * 30

    _ensure_graficas_dir()
    plt.figure(figsize=(10, 5))
    plt.plot(dates, values, marker="o", markersize=3, linewidth=1, label="FC en reposo diaria")
    trend_line = [mean_y + slope * (x - mean_x) for x in xs]
    plt.plot(dates, trend_line, linestyle="--", color="red", label="Tendencia")
    plt.title(f"Frecuencia cardiaca en reposo - últimos {months} meses")
    plt.xlabel("Fecha")
    plt.ylabel("FC en reposo (lpm)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    out_path = f"{GRAFICAS_DIR}/frecuencia_reposo.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Gráfica guardada en '{out_path}'.")

    if abs(trend_per_month) < 0.3:
        veredicto = "se mantiene bastante estable"
    elif trend_per_month < 0:
        veredicto = f"está MEJORANDO (baja aproximadamente {abs(trend_per_month):.1f} lpm por mes)"
    else:
        veredicto = f"está EMPEORANDO (sube aproximadamente {trend_per_month:.1f} lpm por mes)"

    print(f"Tu frecuencia cardiaca en reposo {veredicto}.")
    print(
        f"Promedio del periodo: {mean_y:.1f} lpm "
        f"(mínimo {min(values)} lpm, máximo {max(values)} lpm)."
    )


# ---------------------------------------------------------------------------
# 2. Carga de entrenamiento semanal vs horas de sueño
# ---------------------------------------------------------------------------

def _activity_load(activity: dict) -> float:
    """Estima la 'carga' de una actividad.

    Usa el campo oficial de Garmin si está disponible; si no, aproxima con
    duración en movimiento ponderada por frecuencia cardiaca promedio.
    """
    load = activity.get("activityTrainingLoad")
    if load:
        return float(load)

    duration_min = (activity.get("movingDuration") or activity.get("duration") or 0) / 60
    avg_hr = activity.get("averageHR")
    if avg_hr:
        return duration_min * (avg_hr / 100)
    return duration_min


def training_load_vs_sleep(client, weeks: int = 12):
    print("\n--- Carga de entrenamiento semanal vs horas de sueño ---")
    end = date.today()
    start = end - timedelta(weeks=weeks)

    activities = client.get_activities_by_date(start.isoformat(), end.isoformat()) or []

    weekly_load = defaultdict(float)
    for a in activities:
        start_str = a.get("startTimeLocal")
        if not start_str:
            continue
        d = _parse_date(start_str)
        year, week, _ = d.isocalendar()
        weekly_load[(year, week)] += _activity_load(a)

    weekly_sleep_hours = defaultdict(list)
    day = start
    while day <= end:
        try:
            sleep = client.get_sleep_data(day.isoformat())
        except Exception:
            sleep = None
        seconds = ((sleep or {}).get("dailySleepDTO") or {}).get("sleepTimeSeconds")
        if seconds:
            year, week, _ = day.isocalendar()
            weekly_sleep_hours[(year, week)].append(seconds / 3600)
        day += timedelta(days=1)

    weeks_keys = sorted(set(weekly_load) | set(weekly_sleep_hours))
    if not weeks_keys:
        print("No encontré actividades ni datos de sueño en el rango analizado.")
        return

    labels = [f"{y}-S{w:02d}" for y, w in weeks_keys]
    loads = [weekly_load.get(k, 0.0) for k in weeks_keys]
    sleep_avgs = [
        (sum(weekly_sleep_hours[k]) / len(weekly_sleep_hours[k])) if weekly_sleep_hours.get(k) else None
        for k in weeks_keys
    ]

    _ensure_graficas_dir()
    fig, ax1 = plt.subplots(figsize=(11, 5))
    ax1.bar(labels, loads, color="tab:blue", alpha=0.6, label="Carga de entrenamiento")
    ax1.set_ylabel("Carga de entrenamiento (estimada)", color="tab:blue")
    ax1.tick_params(axis="x", rotation=60)

    ax2 = ax1.twinx()
    valid_labels = [l for l, s in zip(labels, sleep_avgs) if s is not None]
    valid_sleep = [s for s in sleep_avgs if s is not None]
    ax2.plot(valid_labels, valid_sleep, color="tab:red", marker="o", label="Horas de sueño promedio")
    ax2.axhline(7, color="gray", linestyle=":", linewidth=1)
    ax2.set_ylabel("Horas de sueño promedio", color="tab:red")

    plt.title("Carga de entrenamiento semanal vs horas de sueño (semana lunes-domingo)")
    fig.tight_layout()
    out_path = f"{GRAFICAS_DIR}/carga_vs_sueno.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Gráfica guardada en '{out_path}'.")

    pairs = [(l, s) for l, s in zip(loads, sleep_avgs) if s is not None]
    if len(pairs) >= 3:
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        try:
            r = statistics.correlation(xs, ys)
        except (statistics.StatisticsError, ValueError):
            r = None
        if r is not None:
            if r <= -0.3:
                print(
                    f"Sí se nota: las semanas de más carga de entrenamiento tienden a "
                    f"tener menos horas de sueño (correlación {r:.2f})."
                )
            elif r >= 0.3:
                print(
                    f"No parece que entrenar más te quite sueño: de hecho más carga "
                    f"coincide con más horas dormidas (correlación {r:.2f})."
                )
            else:
                print(f"No se nota una relación clara entre carga y sueño (correlación {r:.2f}).")

    semanas_sueno_bajo = [l for l, s in zip(labels, sleep_avgs) if s is not None and s < 6.5]
    if semanas_sueno_bajo:
        print(f"Semanas con sueño bajo (menos de 6.5h en promedio): {', '.join(semanas_sueno_bajo)}")


# ---------------------------------------------------------------------------
# 3. Resumen semanal estilo Strava
# ---------------------------------------------------------------------------

def _week_totals(client, start_d: date, end_d: date) -> dict:
    activities = client.get_activities_by_date(start_d.isoformat(), end_d.isoformat()) or []
    distance_km = sum((a.get("distance") or 0) for a in activities) / 1000
    moving_s = sum((a.get("movingDuration") or a.get("duration") or 0) for a in activities)
    elev_m = sum((a.get("elevationGain") or 0) for a in activities)
    pace_min_per_km = (moving_s / 60) / distance_km if distance_km else None
    return {
        "n": len(activities),
        "distance_km": distance_km,
        "moving_s": moving_s,
        "elev_m": elev_m,
        "pace": pace_min_per_km,
    }


def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m:02d}min"


def _fmt_pace(pace_min_per_km):
    if pace_min_per_km is None:
        return "N/A"
    m = int(pace_min_per_km)
    s = int(round((pace_min_per_km - m) * 60))
    return f"{m}:{s:02d} min/km"


def _fmt_delta(current: float, previous: float) -> str:
    if not previous:
        return "sin dato comparable"
    pct = (current - previous) / previous * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.0f}% vs semana pasada"


def weekly_summary(client):
    print("\n--- Resumen de tu semana (estilo Strava) ---")
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    last_monday = this_monday - timedelta(days=7)
    last_sunday = this_monday - timedelta(days=1)

    this_week = _week_totals(client, this_monday, today)
    last_week = _week_totals(client, last_monday, last_sunday)

    print(f"(Semana actual: {this_monday} a hoy {today}. Semana pasada completa: {last_monday} a {last_sunday}.)")
    print(f"Actividades: {this_week['n']}  (semana pasada: {last_week['n']})")
    print(
        f"Distancia: {this_week['distance_km']:.1f} km "
        f"({_fmt_delta(this_week['distance_km'], last_week['distance_km'])}, "
        f"semana pasada {last_week['distance_km']:.1f} km)"
    )
    print(
        f"Tiempo en movimiento: {_fmt_time(this_week['moving_s'])} "
        f"({_fmt_delta(this_week['moving_s'], last_week['moving_s'])}, "
        f"semana pasada {_fmt_time(last_week['moving_s'])})"
    )
    print(
        f"Desnivel acumulado: {this_week['elev_m']:.0f} m "
        f"({_fmt_delta(this_week['elev_m'], last_week['elev_m'])}, "
        f"semana pasada {last_week['elev_m']:.0f} m)"
    )
    print(
        f"Ritmo promedio: {_fmt_pace(this_week['pace'])} "
        f"(semana pasada: {_fmt_pace(last_week['pace'])})"
    )
    if today.weekday() < 6:
        print(
            "Nota: la semana actual todavía no termina (va de lunes a hoy), así "
            "que es normal que se vea más baja que la semana pasada completa."
        )


# ---------------------------------------------------------------------------
# 4. Récords personales del año
# ---------------------------------------------------------------------------

def _type_key(activity: dict) -> str:
    return ((activity.get("activityType") or {}).get("typeKey") or "").lower()


def personal_records(client, year: int = None):
    year = year or date.today().year
    print(f"\n--- Récords personales {year} ---")

    start = f"{year}-01-01"
    end = date.today().isoformat()
    activities = client.get_activities_by_date(start, end) or []

    best_5k = None
    best_10k = None
    longest_ride = None

    for a in activities:
        dist = a.get("distance") or 0  # metros
        dur = a.get("movingDuration") or a.get("duration") or 0
        t = _type_key(a)

        if "run" in t and dur > 0:
            if 4800 <= dist <= 5200 and (best_5k is None or dur < best_5k["duration"]):
                best_5k = {"duration": dur, "date": a.get("startTimeLocal"), "name": a.get("activityName")}
            if 9800 <= dist <= 10200 and (best_10k is None or dur < best_10k["duration"]):
                best_10k = {"duration": dur, "date": a.get("startTimeLocal"), "name": a.get("activityName")}

        if ("cycl" in t or "bik" in t or "ride" in t) and "indoor" not in t:
            if longest_ride is None or dist > longest_ride["distance"]:
                longest_ride = {"distance": dist, "date": a.get("startTimeLocal"), "name": a.get("activityName")}

    def fmt_duration(seconds):
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}:{s:02d}"

    if best_5k:
        print(
            f"Mejor 5K: {fmt_duration(best_5k['duration'])} "
            f"el {best_5k['date'][:10]} ({best_5k['name']})"
        )
    else:
        print("No encontré ninguna carrera de ~5K este año.")

    if best_10k:
        print(
            f"Mejor 10K: {fmt_duration(best_10k['duration'])} "
            f"el {best_10k['date'][:10]} ({best_10k['name']})"
        )
    else:
        print("No encontré ninguna carrera de ~10K este año.")

    if longest_ride:
        print(
            f"Salida más larga en bici: {longest_ride['distance'] / 1000:.1f} km "
            f"el {longest_ride['date'][:10]} ({longest_ride['name']})"
        )
    else:
        print("No encontré ninguna salida en bici este año.")

    print(
        "Nota: estos récords se calculan a partir de actividades registradas como "
        "esa distancia aproximada (±200m), no de splits dentro de actividades más largas."
    )


REPORTES = {
    "rhr": resting_heart_rate_trend,
    "carga": training_load_vs_sleep,
    "semana": weekly_summary,
    "records": personal_records,
}


def main():
    client = get_client()
    args = sys.argv[1:]

    if not args:
        for fn in REPORTES.values():
            fn(client)
        return

    for name in args:
        fn = REPORTES.get(name)
        if fn is None:
            sys.exit(f"Reporte desconocido: '{name}'. Opciones: {', '.join(REPORTES)}")
        fn(client)


if __name__ == "__main__":
    main()
