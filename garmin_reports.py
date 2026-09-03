#!/usr/bin/env python3
"""Reportes y gráficas a partir de tus datos de Garmin Connect.

Requiere haber corrido antes connect_garmin.py (usa la misma sesión guardada).

Uso:
    python3 garmin_reports.py                # corre los 5 reportes
    python3 garmin_reports.py rhr             # solo frecuencia cardiaca en reposo
    python3 garmin_reports.py carga           # solo carga de entrenamiento vs sueño
    python3 garmin_reports.py semana          # solo resumen semanal estilo Strava
    python3 garmin_reports.py records         # solo récords personales del año
    python3 garmin_reports.py bienestar       # sueño, hidratación, desgaste y recuperación
    python3 garmin_reports.py hidratacion     # pérdida de líquidos estimada por tipo de actividad

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


# ---------------------------------------------------------------------------
# 5. Sueño, hidratación, desgaste físico y recuperación
# ---------------------------------------------------------------------------

def wellness_report(client, days: int = 14):
    print("\n--- Sueño, hidratación, desgaste físico y recuperación ---")
    end = date.today()
    start = end - timedelta(days=days - 1)

    sleep_hours = []
    sleep_scores = []
    stage_totals = {"deep": 0, "light": 0, "rem": 0, "awake": 0}
    hydration_ml = []
    hydration_goal_ml = []
    readiness_scores = []

    d = start
    while d <= end:
        cdate = d.isoformat()

        try:
            sleep = client.get_sleep_data(cdate)
        except Exception:
            sleep = None
        dto = (sleep or {}).get("dailySleepDTO") or {}
        secs = dto.get("sleepTimeSeconds")
        if secs:
            sleep_hours.append((d, secs / 3600))
            stage_totals["deep"] += dto.get("deepSleepSeconds") or 0
            stage_totals["light"] += dto.get("lightSleepSeconds") or 0
            stage_totals["rem"] += dto.get("remSleepSeconds") or 0
            stage_totals["awake"] += dto.get("awakeSleepSeconds") or 0
        score = ((sleep or {}).get("sleepScores") or {}).get("overall", {}).get("value")
        if score:
            sleep_scores.append(score)

        try:
            hydration = client.get_hydration_data(cdate)
        except Exception:
            hydration = None
        if hydration:
            v = hydration.get("valueInML")
            g = hydration.get("goalInML")
            if v is not None:
                hydration_ml.append(v)
            if g:
                hydration_goal_ml.append(g)

        try:
            readiness = client.get_training_readiness(cdate)
        except Exception:
            readiness = None
        if readiness and readiness.get("score") is not None:
            readiness_scores.append((d, readiness["score"]))

        d += timedelta(days=1)

    try:
        battery_days = client.get_body_battery(start.isoformat(), end.isoformat()) or []
    except Exception:
        battery_days = []
    body_battery_charged = [b["charged"] for b in battery_days if b.get("charged") is not None]
    body_battery_drained = [b["drained"] for b in battery_days if b.get("drained") is not None]

    # --- Sueño ---
    if sleep_hours:
        avg_hours = sum(h for _, h in sleep_hours) / len(sleep_hours)
        peor = min(sleep_hours, key=lambda x: x[1])
        mejor = max(sleep_hours, key=lambda x: x[1])
        print(f"Sueño: promedio {avg_hours:.1f}h/noche en los últimos {days} días.")
        print(f"  Peor noche: {peor[1]:.1f}h el {peor[0]}.  Mejor noche: {mejor[1]:.1f}h el {mejor[0]}.")
        total_stage_secs = sum(stage_totals.values())
        if total_stage_secs:
            print(
                "  Distribución de etapas: "
                f"profundo {stage_totals['deep'] / total_stage_secs * 100:.0f}%, "
                f"ligero {stage_totals['light'] / total_stage_secs * 100:.0f}%, "
                f"REM {stage_totals['rem'] / total_stage_secs * 100:.0f}%, "
                f"despierto {stage_totals['awake'] / total_stage_secs * 100:.0f}%."
            )
        if sleep_scores:
            print(f"  Sleep Score promedio de Garmin: {sum(sleep_scores) / len(sleep_scores):.0f}/100.")
    else:
        print("Sueño: no hay datos de sueño en el periodo (revisa que duermas con el reloj puesto).")

    # --- Hidratación ---
    if hydration_ml:
        avg_ml = sum(hydration_ml) / len(hydration_ml)
        print(f"\nHidratación: promedio {avg_ml / 1000:.2f} L/día registrados en los últimos {days} días.")
        if hydration_goal_ml:
            avg_goal = sum(hydration_goal_ml) / len(hydration_goal_ml)
            dias_meta = sum(1 for v in hydration_ml if v >= avg_goal)
            print(f"  Meta diaria: ~{avg_goal / 1000:.2f} L. Cumpliste la meta {dias_meta}/{len(hydration_ml)} días.")
    else:
        print(
            "\nHidratación: no encontré registros. Garmin solo la cuenta si la registras a mano "
            "en la app o con un dispositivo conectado (el reloj solo no mide cuánta agua tomas)."
        )

    # --- Desgaste físico (Body Battery) ---
    if body_battery_charged or body_battery_drained:
        avg_charged = sum(body_battery_charged) / len(body_battery_charged) if body_battery_charged else 0
        avg_drained = sum(body_battery_drained) / len(body_battery_drained) if body_battery_drained else 0
        print(
            f"\nDesgaste físico (Body Battery): en promedio recargas {avg_charged:.0f} "
            f"y gastas {avg_drained:.0f} puntos por día."
        )
        if avg_drained > avg_charged:
            print("  Estás gastando más energía de la que recargas en promedio: señal de desgaste acumulado.")
        else:
            print("  Tu recarga promedio cubre lo que gastas: buen balance de energía.")
    else:
        print("\nDesgaste físico (Body Battery): no hay datos disponibles para tu cuenta/reloj en este periodo.")

    # --- Recuperación ---
    if readiness_scores:
        avg_r = sum(s for _, s in readiness_scores) / len(readiness_scores)
        ultimo = readiness_scores[-1][1]
        print(
            f"\nRecuperación (Training Readiness de Garmin): promedio {avg_r:.0f}/100, "
            f"último día disponible: {ultimo}/100."
        )
    else:
        print("\nRecuperación: tu cuenta/reloj no reporta 'Training Readiness' (requiere modelos más recientes).")

    if sleep_hours:
        _ensure_graficas_dir()
        dates_s = [d for d, _ in sleep_hours]
        hours_s = [h for _, h in sleep_hours]
        plt.figure(figsize=(10, 5))
        plt.bar(dates_s, hours_s, color="tab:purple", alpha=0.6, label="Horas de sueño")
        plt.axhline(7, color="gray", linestyle=":", linewidth=1, label="Meta orientativa (7h)")
        plt.title(f"Sueño de los últimos {days} días")
        plt.ylabel("Horas")
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        out_path = f"{GRAFICAS_DIR}/sueno.png"
        plt.savefig(out_path, dpi=150)
        plt.close()
        print(f"\nGráfica guardada en '{out_path}'.")


# ---------------------------------------------------------------------------
# 6. Pérdida de líquidos estimada por tipo de actividad
# ---------------------------------------------------------------------------

_TYPE_LABELS = {
    "running": "Carrera", "street_running": "Carrera", "track_running": "Carrera",
    "trail_running": "Trail running", "treadmill_running": "Entrenamiento en cinta",
    "indoor_cycling": "Ciclismo en sala", "cycling": "Ciclismo", "road_biking": "Ciclismo",
    "mountain_biking": "Ciclismo de montaña", "strength_training": "Fuerza",
    "yoga": "Yoga", "cardio_training": "Cardio", "hiit": "HIIT", "elliptical": "Elíptica",
    "walking": "Caminata", "lap_swimming": "Natación", "open_water_swimming": "Natación",
    "swimming": "Natación", "indoor_rowing": "Remo", "rowing": "Remo", "pilates": "Pilates",
    "stair_climbing": "Escaladora",
}


def _type_label(type_key: str | None) -> str:
    if not type_key:
        return "Otro"
    return _TYPE_LABELS.get(type_key, type_key.replace("_", " ").capitalize())


def _seleccion_reciente(actividades: list, key_fn, max_por_grupo: int) -> dict:
    """Agrupa actividades con key_fn() y regresa, por grupo, las últimas
    max_por_grupo (más recientes primero)."""
    grupos = defaultdict(list)
    for a in actividades:
        key = key_fn(a)
        if key:
            grupos[key].append(a)
    for lista in grupos.values():
        lista.sort(key=lambda a: a.get("startTimeLocal") or "", reverse=True)
    return {key: lista[:max_por_grupo] for key, lista in grupos.items()}


def _resumir_grupo(grupos: dict, cache_ml_por_hora: dict, min_sesiones: int, label_fn) -> list:
    resultados = []
    for key, lista in grupos.items():
        valores = [cache_ml_por_hora[a["activityId"]] for a in lista if a.get("activityId") in cache_ml_por_hora]
        if len(valores) >= min_sesiones:
            resultados.append({"actividad": label_fn(key), "n": len(valores), "ml_por_hora": statistics.mean(valores)})
    resultados.sort(key=lambda r: r["ml_por_hora"], reverse=True)
    return resultados


def _imprimir_y_graficar_hidratacion(resultados: list, titulo: str, out_path: str, min_sesiones: int):
    if not resultados:
        print(
            f"\n{titulo}: no encontré suficientes actividades (mínimo {min_sesiones} del mismo grupo, "
            "con dato de pérdida de líquidos estimada) en el periodo."
        )
        return

    print(f"\n{titulo}:")
    for r in resultados:
        print(f"  {r['actividad']}: {r['ml_por_hora']:.0f} mL/hora estimados (promedio de {r['n']} sesiones)")

    _ensure_graficas_dir()
    nombres = [r["actividad"] for r in resultados]
    valores = [r["ml_por_hora"] for r in resultados]

    plt.figure(figsize=(9, max(3, 0.6 * len(resultados) + 1)))
    barras = plt.barh(nombres, valores, color="#2a78d6")
    for barra, r in zip(barras, resultados):
        plt.text(
            barra.get_width() + max(valores) * 0.01, barra.get_y() + barra.get_height() / 2,
            f"{r['ml_por_hora']:.0f} mL (n={r['n']})", va="center", fontsize=9,
        )
    plt.gca().invert_yaxis()
    plt.xlabel("mL estimados por 60 min de actividad")
    plt.title(titulo)
    plt.tight_layout()

    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Gráfica guardada en '{out_path}'.")


def _diario_desde_cache(client, actividades: list, dias: int, cache_ml_por_hora: dict) -> dict:
    """Suma el agua estimada REAL (sin normalizar a 60 min -- aquí interesa
    el total del día) de todas las actividades del mismo día de calendario,
    en los últimos `dias` -- así un día con varias actividades queda
    reflejado como un solo total, no repartido entre varias barras."""
    corte = (date.today() - timedelta(days=dias)).isoformat()
    por_dia = defaultdict(float)
    for a in actividades:
        start_str = a.get("startTimeLocal") or ""
        if start_str[:10] < corte:
            continue
        activity_id = a.get("activityId")
        duracion_s = a.get("duration") or a.get("movingDuration")
        if activity_id is None:
            continue
        if activity_id in cache_ml_por_hora and duracion_s:
            agua_ml = cache_ml_por_hora[activity_id] * duracion_s / 3600
        else:
            try:
                detalle = client.get_activity(activity_id)
            except Exception:
                continue
            agua_ml = (detalle.get("summaryDTO") or {}).get("waterEstimated")
        if agua_ml is not None:
            por_dia[start_str[:10]] += agua_ml
    return dict(por_dia)


def _imprimir_y_graficar_diario(por_dia: dict, dias: int):
    if not por_dia:
        print(f"\nPor día (últimos {dias} días): no encontré actividades con este dato.")
        return

    promedio = statistics.mean(por_dia.values())
    print(
        f"\nPor día (últimos {dias} días): en promedio pierdes {promedio:.0f} mL en días con "
        f"actividad ({len(por_dia)} días con al menos una actividad -- si haces varias el mismo "
        "día, ya están sumadas en ese día)."
    )

    _ensure_graficas_dir()
    fechas = sorted(por_dia)
    valores = [por_dia[f] for f in fechas]

    plt.figure(figsize=(10, 5))
    plt.bar(fechas, valores, color="#2a78d6", alpha=0.85, label="Pérdida diaria estimada")
    plt.axhline(promedio, color="gray", linestyle=":", linewidth=1, label=f"Promedio ({promedio:.0f} mL)")
    plt.title(f"Pérdida de líquidos estimada por día (últimos {dias} días)")
    plt.ylabel("mL")
    plt.xticks(rotation=45, fontsize=7)
    plt.legend()
    plt.tight_layout()

    out_path = f"{GRAFICAS_DIR}/hidratacion_por_dia.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Gráfica guardada en '{out_path}'.")


def hydration_by_activity(client, days: int = 180, min_sesiones: int = 3, max_por_tipo: int = 10, dias_diario: int = 30):
    """Promedia cuánto líquido estima Garmin que pierdes, normalizado a 60
    minutos, usando tus últimas hasta {max_por_tipo} sesiones -- una vez
    agrupando por el nombre exacto de la actividad (ej. distingue 'Carrera'
    por ciudad si Garmin las nombró distinto) y otra vez agrupando por tipo
    de actividad (todas las corridas juntas, sin importar dónde). Además,
    para los últimos {dias_diario} días, suma el total (sin normalizar) de
    todas las actividades del mismo día y saca un promedio diario -- para
    los días en que se hace más de una actividad, ya quedan juntas.

    Requiere que tu reloj calcule 'pérdida de líquidos estimada' (no todos
    los modelos lo hacen); si no, este reporte no encuentra nada.
    """
    print("\n--- Pérdida de líquidos estimada por actividad ---")
    print("(revisa el detalle de cada actividad, puede tardar un poco)")
    end = date.today()
    start = end - timedelta(days=days)
    actividades = client.get_activities_by_date(start.isoformat(), end.isoformat()) or []

    por_nombre = _seleccion_reciente(actividades, lambda a: (a.get("activityName") or "").strip() or None, max_por_tipo)
    por_tipo = _seleccion_reciente(actividades, lambda a: (a.get("activityType") or {}).get("typeKey"), max_por_tipo)

    # Une las actividades que hace falta consultar en las dos agrupaciones,
    # para no pedirle a Garmin el detalle de una misma actividad dos veces.
    por_id = {}
    for lista in list(por_nombre.values()) + list(por_tipo.values()):
        for a in lista:
            if a.get("activityId") is not None:
                por_id[a["activityId"]] = a

    cache_ml_por_hora = {}
    for activity_id, a in por_id.items():
        duracion_s = a.get("duration") or a.get("movingDuration")
        if not duracion_s:
            continue
        try:
            detalle = client.get_activity(activity_id)
        except Exception:
            continue
        agua_ml = (detalle.get("summaryDTO") or {}).get("waterEstimated")
        if agua_ml is not None:
            cache_ml_por_hora[activity_id] = agua_ml * 3600 / duracion_s

    resultados_nombre = _resumir_grupo(por_nombre, cache_ml_por_hora, min_sesiones, lambda k: k)
    resultados_tipo = _resumir_grupo(por_tipo, cache_ml_por_hora, min_sesiones, _type_label)

    _imprimir_y_graficar_hidratacion(
        resultados_nombre, f"Por nombre de actividad (últimos {days} días)",
        f"{GRAFICAS_DIR}/hidratacion_por_actividad.png", min_sesiones,
    )
    _imprimir_y_graficar_hidratacion(
        resultados_tipo, f"Por tipo de actividad (últimos {days} días)",
        f"{GRAFICAS_DIR}/hidratacion_por_tipo.png", min_sesiones,
    )

    por_dia = _diario_desde_cache(client, actividades, dias_diario, cache_ml_por_hora)
    _imprimir_y_graficar_diario(por_dia, dias_diario)


REPORTES = {
    "rhr": resting_heart_rate_trend,
    "carga": training_load_vs_sleep,
    "semana": weekly_summary,
    "records": personal_records,
    "bienestar": wellness_report,
    "hidratacion": hydration_by_activity,
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
