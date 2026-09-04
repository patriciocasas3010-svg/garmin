"""Lee datos de un anillo Oura a través de la API pública v2 de Oura
(api.ouraring.com/v2/usercollection/...) y arma el mismo dict que
garmin_metrics.build_runtime_data(), para poder reutilizar
render_dashboard_body(), snapshot_to_json/from_json y push_resumen.py sin
cambios -- el resto del sistema no sabe ni le importa si los datos vinieron
de Garmin, Apple Health o de un anillo Oura.

A diferencia de Garmin (endpoints internos, no documentados, usados aquí por
ingeniería inversa vía la librería garminconnect), la API v2 de Oura SÍ es
pública y está documentada por Oura -- pero este módulo no se pudo probar
contra una cuenta real de Oura durante su desarrollo (no había un token de
prueba disponible), así que los nombres de campo se tomaron de la
documentación pública y de clientes de código abierto ya existentes, no de
una respuesta real verificada. Si algo no cuadra con una cuenta real (un
campo que venga vacío cuando no debería, o un valor con las unidades
cambiadas), es el primer lugar a revisar -- usa el propio requests.get()
de este archivo para inspeccionar la respuesta cruda si algo se ve raro.

Diferencias honestas frente a Garmin (cosas que la API de Oura no da, o no
da con la confianza suficiente para calcularlas igual):

- Body Battery y deriva cardiaca (pestaña "Eficiencia"): Oura no expone una
  serie de FC segundo a segundo por entrenamiento a través de esta API (solo
  un resumen por sesión de sueño), así que -- igual que Apple Health cuando
  no hay ruta GPS -- se dejan vacíos en vez de inventar un cálculo.
- Zonas de FC de la semana y caída de pulso post-esfuerzo (misma pestaña):
  por la misma razón (sin FC minuto a minuto por entrenamiento), también
  quedan vacías.
- Nivel de estrés: el endpoint daily_stress de Oura da una etiqueta
  categórica (restored/normal/stressful), no un número 0-100 como Garmin --
  forzarlo a la misma escala inventaría precisión que no existe, así que
  se deja vacío.
- Frecuencia cardiaca en reposo: Oura no tiene un endpoint de "RHR diario"
  como Garmin -- se usa el pulso más bajo registrado durante el sueño
  principal de cada noche (lowest_heart_rate) como aproximación estándar,
  igual que hacen la mayoría de wearables de anillo/muñeca.
- Peso muerto de entrenamiento (carga/ACWR): los entrenamientos de Oura no
  traen FC promedio por sesión, así que la carga se calcula solo con
  duración (mismo camino de respaldo que ya usa _activity_load cuando
  Garmin tampoco la trae).
"""

from collections import defaultdict
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from garmin_metrics import (
    WELLNESS_DAYS_DEFAULT,
    compute_acwr,
    compute_hrv_zscore,
    fetch_daily_fuerza_minutos,
    fetch_daily_running_km,
    score_range,
    score_ramp,
)
from garmin_reports import _activity_load

API_BASE = "https://api.ouraring.com/v2/usercollection"


# ---------------------------------------------------------------------------
# Llamadas HTTP crudas a la API de Oura (paginada con next_token)
# ---------------------------------------------------------------------------

def _get_all(token: str, endpoint: str, start: date, end: date) -> list[dict]:
    """Trae todas las páginas de un endpoint de usercollection en el rango
    [start, end] (end_date se manda un día después porque Oura trata ese
    límite como exclusivo en algunos endpoints)."""
    out = []
    params = {
        "start_date": start.isoformat(),
        "end_date": (end + timedelta(days=1)).isoformat(),
    }
    while True:
        resp = requests.get(
            f"{API_BASE}/{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json() or {}
        out.extend(body.get("data") or [])
        next_token = body.get("next_token")
        if not next_token:
            break
        params["next_token"] = next_token
    return out


def _date_index(start: date, end: date):
    return pd.to_datetime(pd.date_range(start, end, freq="D"))


def _parse_day(d: dict) -> date | None:
    day_str = d.get("day")
    if not day_str:
        return None
    try:
        return date.fromisoformat(day_str)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Entrenamientos (workout) -- mismo dict "trimmed" que usan Garmin/Apple
# ---------------------------------------------------------------------------

_ACTIVITY_LABELS = {
    "running": "Correr",
    "walking": "Caminata",
    "cycling": "Ciclismo",
    "swimming": "Natación",
    "rowing": "Remo",
    "strength_training": "Fuerza",
    "yoga": "Yoga",
    "pilates": "Pilates",
    "hiit": "HIIT",
    "elliptical": "Elíptica",
    "hiking": "Senderismo",
    "core_training": "Core",
    "cross_training": "Entrenamiento cruzado",
}


def _workout_label(activity_key: str) -> str:
    return _ACTIVITY_LABELS.get(activity_key, (activity_key or "Entrenamiento").replace("_", " ").capitalize())


def _parse_iso(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _build_activities(workouts_raw: list[dict]) -> list[dict]:
    """Oura no reporta FC promedio por entrenamiento en este endpoint (a
    diferencia de Garmin/Apple), así que averageHR queda en None -- ver
    docstring del módulo."""
    out = []
    for w in workouts_raw:
        start_dt = _parse_iso(w.get("start_datetime") or "")
        if start_dt is None:
            continue
        end_dt = _parse_iso(w.get("end_datetime") or "")
        duracion_s = (end_dt - start_dt).total_seconds() if end_dt else None
        activity_key = (w.get("activity") or "").lower()
        out.append({
            "activityId": w.get("id"),
            "activityName": _workout_label(activity_key),
            "startTimeLocal": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "distance": w.get("distance"),
            "duration": duracion_s,
            "movingDuration": duracion_s,
            "averageHR": None,
            "calories": w.get("calories"),
            "activityType": {"typeKey": activity_key or "workout"},
        })
    return out


def _daily_load(activities: list[dict], start: date, end: date) -> pd.Series:
    by_day: dict[date, float] = defaultdict(float)
    for a in activities:
        d = datetime.strptime(a["startTimeLocal"], "%Y-%m-%d %H:%M:%S").date()
        by_day[d] += _activity_load(a)
    idx = _date_index(start, end)
    return pd.Series([by_day.get(d.date(), 0.0) for d in idx], index=idx, name="load")


# ---------------------------------------------------------------------------
# Sueño -- daily_sleep (puntaje) + sleep (duración/etapas/FC/HRV nocturna)
# ---------------------------------------------------------------------------

def _main_sleep_by_day(sleep_sessions: list[dict]) -> dict[date, dict]:
    """Si hubo más de un registro de sueño en el día (por ejemplo una
    siesta), se queda con el más largo como "el sueño principal", igual que
    hace Oura en su propia app."""
    best: dict[date, dict] = {}
    for s in sleep_sessions:
        day = _parse_day(s)
        if day is None:
            continue
        dur = s.get("total_sleep_duration") or 0
        actual = best.get(day)
        if actual is None or dur > (actual.get("total_sleep_duration") or 0):
            best[day] = s
    return best


def _sleep_df(main_sleep: dict[date, dict], daily_scores: dict[date, float], start: date, end: date) -> pd.DataFrame:
    idx = _date_index(start, end)
    rows = []
    for d in idx:
        day = d.date()
        rec = main_sleep.get(day) or {}
        rows.append({
            "date": d,
            "hours": (rec.get("total_sleep_duration") / 3600) if rec.get("total_sleep_duration") else None,
            "deep_min": (rec.get("deep_sleep_duration") / 60) if rec.get("deep_sleep_duration") else None,
            "light_min": (rec.get("light_sleep_duration") / 60) if rec.get("light_sleep_duration") else None,
            "rem_min": (rec.get("rem_sleep_duration") / 60) if rec.get("rem_sleep_duration") else None,
            "awake_min": (rec.get("awake_time") / 60) if rec.get("awake_time") else None,
            "score": daily_scores.get(day),
        })
    return pd.DataFrame(rows).set_index("date")


def _rhr_hrv_series(main_sleep: dict[date, dict], start: date, end: date) -> tuple[pd.Series, pd.Series]:
    """FC en reposo y HRV nocturnas -- ambas aproximadas a partir del sueño
    principal de cada noche (lowest_heart_rate, average_hrv), ver docstring
    del módulo."""
    idx = _date_index(start, end)
    rhr_vals, hrv_vals = [], []
    for d in idx:
        rec = main_sleep.get(d.date()) or {}
        rhr_vals.append(rec.get("lowest_heart_rate"))
        hrv_vals.append(rec.get("average_hrv"))
    rhr = pd.Series(rhr_vals, index=idx, name="rhr", dtype="float64")
    hrv = pd.Series(hrv_vals, index=idx, name="hrv", dtype="float64")
    return rhr, hrv


# ---------------------------------------------------------------------------
# Preparación física (daily_readiness) y calorías (daily_activity)
# ---------------------------------------------------------------------------

def _readiness_series(readiness_daily: list[dict], start: date, end: date) -> pd.Series:
    by_day = {}
    for r in readiness_daily:
        day = _parse_day(r)
        if day is not None:
            by_day[day] = r.get("score")
    idx = _date_index(start, end)
    return pd.Series([by_day.get(d.date()) for d in idx], index=idx, dtype="float64")


def _calories_df(activity_daily: list[dict], start: date, end: date) -> pd.DataFrame:
    by_day = {}
    for a in activity_daily:
        day = _parse_day(a)
        if day is not None:
            by_day[day] = a
    idx = _date_index(start, end)
    rows = []
    for d in idx:
        a = by_day.get(d.date()) or {}
        active = a.get("active_calories")
        total = a.get("total_calories")
        resting = (total - active) if (total is not None and active is not None) else None
        rows.append({"date": d, "resting_kcal": resting, "active_kcal": active, "total_kcal": total})
    return pd.DataFrame(rows).set_index("date")


def _edad_fisica(cardio_age_raw: list[dict]) -> float | None:
    """Oura llama a esto "Cardiovascular Age" -- el nombre exacto del campo
    con el valor no se pudo confirmar contra una respuesta real (ver
    docstring del módulo), así que se prueban varias llaves candidatas."""
    if not cardio_age_raw:
        return None
    ultimo = max(cardio_age_raw, key=lambda r: r.get("day") or "")
    for llave in ("vascular_age", "cardiovascular_age", "age"):
        valor = ultimo.get(llave)
        if valor is not None:
            try:
                return float(valor)
            except (TypeError, ValueError):
                continue
    return None


# ---------------------------------------------------------------------------
# Calificación del mes -- mismo cálculo que garmin_metrics.compute_monthly_score
# ---------------------------------------------------------------------------

def _monthly_score(activities: list[dict], sleep_df: pd.DataFrame, calories_df: pd.DataFrame,
                    readiness_series: pd.Series, rhr_series: pd.Series, days: int) -> dict:
    recovery_score = readiness_series.dropna().mean() if readiness_series.notna().any() else None

    sleep_hours_avg = sleep_df["hours"].dropna().mean() if sleep_df["hours"].notna().any() else None
    sleep_score_oura = sleep_df["score"].dropna().mean() if sleep_df["score"].notna().any() else None
    sleep_score = sleep_score_oura if sleep_score_oura is not None else score_range(sleep_hours_avg, 4, 7, 9, 11)

    active_kcal_avg = calories_df["active_kcal"].dropna().mean() if calories_df["active_kcal"].notna().any() else None
    activity_score = score_ramp(active_kcal_avg, 400)

    sub_scores = [s for s in [recovery_score, sleep_score, activity_score] if s is not None]
    overall_score = sum(sub_scores) / len(sub_scores) if sub_scores else None

    wellness_start = pd.Timestamp(sleep_df.index.min())
    wellness_end = pd.Timestamp(sleep_df.index.max())
    dias_activos = {
        pd.Timestamp(datetime.strptime(a["startTimeLocal"], "%Y-%m-%d %H:%M:%S").date())
        for a in activities
        if wellness_start <= pd.Timestamp(datetime.strptime(a["startTimeLocal"], "%Y-%m-%d %H:%M:%S").date()) <= wellness_end
    }
    total_dias = len(sleep_df)
    dias_inactivos_ts = sorted(set(sleep_df.index) - dias_activos)

    rhr_avg_7d = rhr_series.tail(7).mean()
    rhr_avg_7d = rhr_avg_7d if pd.notna(rhr_avg_7d) else None

    return {
        "overall_score": overall_score,
        "recovery_score": recovery_score,
        "sleep_score": sleep_score,
        "sleep_score_garmin": sleep_score_oura,
        "sleep_hours_avg": sleep_hours_avg,
        "activity_score": activity_score,
        "active_kcal_avg": active_kcal_avg,
        "total_dias": total_dias,
        "dias_con_actividad": len(dias_activos),
        "dias_sin_actividad": total_dias - len(dias_activos),
        "dias_inactivos": [d.date().isoformat() for d in dias_inactivos_ts],
        "rhr_avg_7d": rhr_avg_7d,
    }


# ---------------------------------------------------------------------------
# build_runtime_data: misma forma exacta que garmin_metrics.build_runtime_data
# ---------------------------------------------------------------------------

def build_runtime_data(token: str, lookback_days: int = 90, wellness_days: int = WELLNESS_DAYS_DEFAULT) -> dict:
    end = date.today()
    start90 = end - timedelta(days=lookback_days)
    start30 = end - timedelta(days=wellness_days)
    week_ago = end - timedelta(days=7)

    workouts_raw = _get_all(token, "workout", start90, end)
    sleep_sessions = _get_all(token, "sleep", start90, end)
    sleep_daily_raw = _get_all(token, "daily_sleep", start90, end)
    readiness_daily = _get_all(token, "daily_readiness", start30, end)
    activity_daily = _get_all(token, "daily_activity", start30, end)
    cardio_age_raw = _get_all(token, "daily_cardiovascular_age", start30, end)

    activities = _build_activities(workouts_raw)
    main_sleep = _main_sleep_by_day(sleep_sessions)
    daily_scores = {
        d: r.get("score") for r in sleep_daily_raw if (d := _parse_day(r)) is not None
    }

    load_series = _daily_load(activities, start90, end)
    running_km_series = fetch_daily_running_km(start90, end, activities)
    fuerza_minutos_series = fetch_daily_fuerza_minutos(start90, end, activities)
    rhr_series, hrv_series = _rhr_hrv_series(main_sleep, start90, end)

    sleep_df = _sleep_df(main_sleep, daily_scores, start30, end)
    hydration_df = pd.DataFrame({"value_l": float("nan"), "goal_l": float("nan")}, index=_date_index(start30, end))
    readiness_series = _readiness_series(readiness_daily, start30, end)
    battery_df = pd.DataFrame({"charged": float("nan"), "drained": float("nan")}, index=_date_index(start30, end))
    calories_df = _calories_df(activity_daily, start30, end)
    edad_fisica = _edad_fisica(cardio_age_raw)
    # daily_stress de Oura es una etiqueta (restored/normal/stressful), no
    # un número 0-100 como Garmin -- ver docstring del módulo.
    nivel_estres = None

    activities_last_week = [
        a for a in activities
        if datetime.strptime(a["startTimeLocal"], "%Y-%m-%d %H:%M:%S").date() >= week_ago
    ]
    activities_calorias = [
        a for a in activities
        if datetime.strptime(a["startTimeLocal"], "%Y-%m-%d %H:%M:%S").date() >= start30 and a.get("calories")
    ]

    acwr_df = compute_acwr(load_series)
    hrv_df = compute_hrv_zscore(hrv_series)
    ultimo_acwr = acwr_df["acwr"].dropna().iloc[-1] if acwr_df["acwr"].notna().any() else None
    ultimo_hrv_z = hrv_df["hrv_zscore"].dropna().iloc[-1] if hrv_df["hrv_zscore"].notna().any() else None

    # Eficiencia (deriva cardiaca) y zonas de FC no se calculan -- Oura no
    # da FC segundo a segundo por entrenamiento en esta API. Ver docstring.
    efficiency_df = pd.DataFrame()
    peor_deriva_val = None
    recovery_df = pd.DataFrame()
    peor_caida_min = None
    zone_seconds = None
    max_hr = None

    rhr_recent = rhr_series.dropna()
    rhr_avg = rhr_series.tail(7).mean()
    rhr_avg = rhr_avg if pd.notna(rhr_avg) else None
    rhr_baseline = rhr_series.dropna().iloc[:-7].tail(60).mean() if rhr_series.dropna().shape[0] > 14 else None
    rhr_today = rhr_recent.iloc[-1] if not rhr_recent.empty else None

    alerta_disrupcion = ultimo_acwr is not None and ultimo_hrv_z is not None and ultimo_acwr > 1.4 and ultimo_hrv_z < -1.5
    alerta_eficiencia = False
    alerta_vagal = False

    resumen_mes = _monthly_score(activities, sleep_df, calories_df, readiness_series, rhr_series, wellness_days)

    return {
        "generated_at": datetime.now().isoformat(),
        "lookback_days": lookback_days,
        "wellness_days": wellness_days,
        "activities": activities,
        "load_series": load_series,
        "running_km_series": running_km_series,
        "fuerza_minutos_series": fuerza_minutos_series,
        "rhr_series": rhr_series,
        "hrv_series": hrv_series,
        "sleep_df": sleep_df,
        "hydration_df": hydration_df,
        "readiness_series": readiness_series,
        "battery_df": battery_df,
        "calories_df": calories_df,
        "activities_last_week": activities_last_week,
        "activities_calorias": activities_calorias,
        "acwr_df": acwr_df,
        "hrv_df": hrv_df,
        "ultimo_acwr": ultimo_acwr,
        "ultimo_hrv_z": ultimo_hrv_z,
        "efficiency_df": efficiency_df,
        "peor_deriva_val": peor_deriva_val,
        "rhr_avg": rhr_avg,
        "rhr_baseline": rhr_baseline,
        "rhr_today": rhr_today,
        "max_hr": max_hr,
        "recovery_df": recovery_df,
        "peor_caida_min": peor_caida_min,
        "zone_seconds": zone_seconds,
        "alerta_disrupcion": alerta_disrupcion,
        "alerta_eficiencia": alerta_eficiencia,
        "alerta_vagal": alerta_vagal,
        "alertas_activas": sum([alerta_disrupcion, alerta_eficiencia, alerta_vagal]),
        "resumen_mes": resumen_mes,
        # Oura no trae registro de hidratación (no es un anillo de nutrición) --
        # el dashboard ya sabe mostrar "no disponible" en ese caso.
        "hidratacion_por_tipo": [],
        "hidratacion_diaria": {"promedio_ml_dia": None, "dias_con_actividad": 0, "serie": {}},
        "edad_fisica": edad_fisica,
        "nivel_estres": nivel_estres,
    }
