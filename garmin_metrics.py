"""Cálculos avanzados para el Tablero Maestro de Rendimiento.

Todas las funciones son defensivas: si a tu reloj/cuenta le falta algún dato
(por ejemplo HRV, si tu modelo no lo soporta), devuelven None/NaN en vez de
reventar, para que el resto del tablero se pueda seguir mostrando.

Nota importante: estas funciones dependen de endpoints internos de Garmin
Connect que no están oficialmente documentados por Garmin (los usa la propia
app web, no hay una "API pública" para esto). Si Garmin cambia el formato de
sus respuestas, alguna métrica puede dejar de calcularse bien; usa
debug_endpoint.py para inspeccionar la respuesta cruda si algo se ve raro.
"""

import bisect
from datetime import date, datetime, timedelta

import pandas as pd

from garmin_reports import _activity_load

# ---------------------------------------------------------------------------
# Series de tiempo básicas
# ---------------------------------------------------------------------------

def _date_index(start: date, end: date):
    return pd.to_datetime(pd.date_range(start, end, freq="D"))


def fetch_activities(client, start: date, end: date) -> list:
    return client.get_activities_by_date(start.isoformat(), end.isoformat()) or []


def fetch_daily_load(client, start: date, end: date, activities=None) -> pd.Series:
    """Carga de entrenamiento diaria (suma de _activity_load por día)."""
    if activities is None:
        activities = fetch_activities(client, start, end)

    by_day: dict[date, float] = {}
    for a in activities:
        start_str = a.get("startTimeLocal")
        if not start_str:
            continue
        try:
            d = datetime.strptime(start_str[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        by_day[d] = by_day.get(d, 0.0) + _activity_load(a)

    idx = _date_index(start, end)
    values = [by_day.get(d.date(), 0.0) for d in idx]
    return pd.Series(values, index=idx, name="load")


def fetch_rhr_series(client, start: date, end: date) -> pd.Series:
    """Frecuencia cardiaca en reposo diaria, un solo llamado para todo el rango."""
    data = client.connectapi(
        f"{client.garmin_connect_rhr_url}/{client.display_name}",
        params={
            "fromDate": start.isoformat(),
            "untilDate": end.isoformat(),
            "metricId": 60,
        },
    )
    entries = (
        (data or {}).get("allMetrics", {}).get("metricsMap", {}).get(
            "WELLNESS_RESTING_HEART_RATE", []
        )
        or []
    )
    by_day = {e.get("calendarDate"): e.get("value") for e in entries if e.get("calendarDate")}

    idx = _date_index(start, end)
    values = [by_day.get(d.date().isoformat()) for d in idx]
    return pd.Series(values, index=idx, name="rhr", dtype="float64")


def fetch_hrv_series(client, start: date, end: date) -> pd.Series:
    """Promedio de HRV nocturna, un llamado por día (no hay endpoint de rango)."""
    values = {}
    d = start
    while d <= end:
        v = None
        try:
            data = client.get_hrv_data(d.isoformat())
        except Exception:
            data = None
        if data:
            summary = data.get("hrvSummary") or {}
            v = summary.get("lastNightAvg") or summary.get("weeklyAvg")
        values[d] = v
        d += timedelta(days=1)

    idx = _date_index(start, end)
    series_values = [values.get(d.date()) for d in idx]
    return pd.Series(series_values, index=idx, name="hrv", dtype="float64")


def fetch_day_hr_summary(client, day: date) -> dict | None:
    """restingHeartRate / maxHeartRate / heartRateValues de un día concreto."""
    try:
        return client.get_heart_rates(day.isoformat())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Sueño, hidratación, desgaste físico (Body Battery) y recuperación
# ---------------------------------------------------------------------------

def fetch_sleep_series(client, start: date, end: date) -> pd.DataFrame:
    rows = []
    d = start
    while d <= end:
        try:
            sleep = client.get_sleep_data(d.isoformat())
        except Exception:
            sleep = None
        dto = (sleep or {}).get("dailySleepDTO") or {}
        secs = dto.get("sleepTimeSeconds")
        score = ((sleep or {}).get("sleepScores") or {}).get("overall", {}).get("value")
        rows.append({
            "date": d,
            "hours": secs / 3600 if secs else None,
            "deep_min": (dto.get("deepSleepSeconds") or 0) / 60,
            "light_min": (dto.get("lightSleepSeconds") or 0) / 60,
            "rem_min": (dto.get("remSleepSeconds") or 0) / 60,
            "awake_min": (dto.get("awakeSleepSeconds") or 0) / 60,
            "score": score,
        })
        d += timedelta(days=1)

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


def fetch_hydration_series(client, start: date, end: date) -> pd.DataFrame:
    rows = []
    d = start
    while d <= end:
        try:
            hydration = client.get_hydration_data(d.isoformat())
        except Exception:
            hydration = None
        value = (hydration or {}).get("valueInML")
        goal = (hydration or {}).get("goalInML")
        rows.append({
            "date": d,
            "value_l": value / 1000 if value is not None else None,
            "goal_l": goal / 1000 if goal else None,
        })
        d += timedelta(days=1)

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


def fetch_training_readiness_series(client, start: date, end: date) -> pd.Series:
    rows = []
    d = start
    while d <= end:
        try:
            readiness = client.get_training_readiness(d.isoformat())
        except Exception:
            readiness = None
        rows.append({"date": d, "score": (readiness or {}).get("score")})
        d += timedelta(days=1)

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["score"]


def fetch_calories_series(client, start: date, end: date) -> pd.DataFrame:
    """Calorías diarias: reposo (BMR), actividad y total, según el resumen diario de Garmin."""
    rows = []
    d = start
    while d <= end:
        try:
            summary = client.get_user_summary(d.isoformat())
        except Exception:
            summary = None
        summary = summary or {}
        rows.append({
            "date": d,
            "resting_kcal": summary.get("bmrKilocalories"),
            "active_kcal": summary.get("activeKilocalories"),
            "total_kcal": summary.get("totalKilocalories"),
        })
        d += timedelta(days=1)

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


WELLNESS_DAYS_DEFAULT = 30


def score_range(value, low_bad, low_ok, high_ok, high_bad):
    """100 dentro de [low_ok, high_ok], baja a 0 conforme se acerca a los límites *_bad."""
    if value is None or pd.isna(value):
        return None
    if low_ok <= value <= high_ok:
        return 100.0
    if value < low_ok:
        if value <= low_bad:
            return 0.0
        return (value - low_bad) / (low_ok - low_bad) * 100
    if value >= high_bad:
        return 0.0
    return (high_bad - value) / (high_bad - high_ok) * 100


def score_ramp(value, target):
    """0 en 0, 100 al llegar (o pasar) la meta."""
    if value is None or pd.isna(value):
        return None
    return max(0.0, min(100.0, value / target * 100))


def score_label(score: float) -> str:
    if score >= 85:
        return "Excelente"
    if score >= 70:
        return "Buena"
    if score >= 50:
        return "Regular"
    return "Baja"


def compute_monthly_score(client, days: int = WELLNESS_DAYS_DEFAULT) -> dict:
    """Calificación del mes (0-100) y su desglose: recuperación, sueño y
    actividad física, más el conteo de días con/sin actividad.

    Es el mismo cálculo que usa el panel 'Resumen' del dashboard personal,
    factorizado aquí para poder reutilizarlo también en push_resumen.py
    (lo que se manda a la hoja de Google del nutriólogo).
    """
    end = date.today()
    start = end - timedelta(days=days)

    activities = fetch_activities(client, start, end)
    sleep_df = fetch_sleep_series(client, start, end)
    readiness_series = fetch_training_readiness_series(client, start, end)
    calories_df = fetch_calories_series(client, start, end)
    rhr_series = fetch_rhr_series(client, start, end)

    recovery_score = readiness_series.dropna().mean() if readiness_series.notna().any() else None

    sleep_hours_avg = sleep_df["hours"].dropna().mean() if sleep_df["hours"].notna().any() else None
    sleep_score_garmin = sleep_df["score"].dropna().mean() if sleep_df["score"].notna().any() else None
    sleep_score = sleep_score_garmin if sleep_score_garmin is not None else score_range(sleep_hours_avg, 4, 7, 9, 11)

    active_kcal_avg = calories_df["active_kcal"].dropna().mean() if calories_df["active_kcal"].notna().any() else None
    activity_score = score_ramp(active_kcal_avg, 400)

    sub_scores = [s for s in [recovery_score, sleep_score, activity_score] if s is not None]
    overall_score = sum(sub_scores) / len(sub_scores) if sub_scores else None

    wellness_start_ts = pd.Timestamp(sleep_df.index.min())
    wellness_end_ts = pd.Timestamp(sleep_df.index.max())
    dias_activos = {
        pd.Timestamp(a["startTimeLocal"][:10])
        for a in activities
        if a.get("startTimeLocal") and wellness_start_ts <= pd.Timestamp(a["startTimeLocal"][:10]) <= wellness_end_ts
    }
    total_dias = len(sleep_df)
    dias_inactivos_ts = sorted(set(sleep_df.index) - dias_activos)

    rhr_recent = rhr_series.dropna()
    rhr_avg_7d = rhr_recent.tail(7).mean() if not rhr_recent.empty else None

    return {
        "overall_score": overall_score,
        "recovery_score": recovery_score,
        "sleep_score": sleep_score,
        "sleep_score_garmin": sleep_score_garmin,
        "sleep_hours_avg": sleep_hours_avg,
        "activity_score": activity_score,
        "active_kcal_avg": active_kcal_avg,
        "total_dias": total_dias,
        "dias_con_actividad": len(dias_activos),
        "dias_sin_actividad": total_dias - len(dias_activos),
        "dias_inactivos": [d.date().isoformat() for d in dias_inactivos_ts],
        "rhr_avg_7d": rhr_avg_7d,
    }


def fetch_body_battery_series(client, start: date, end: date) -> pd.DataFrame:
    try:
        days_data = client.get_body_battery(start.isoformat(), end.isoformat()) or []
    except Exception:
        days_data = []

    idx = _date_index(start, end)
    by_day = {d.get("date"): d for d in days_data if d.get("date")}
    rows = []
    for d in idx:
        entry = by_day.get(d.date().isoformat(), {})
        rows.append({"charged": entry.get("charged"), "drained": entry.get("drained")})

    return pd.DataFrame(rows, index=idx)


# ---------------------------------------------------------------------------
# Panel 1: ACWR vs HRV (Z-score)
# ---------------------------------------------------------------------------

def compute_acwr(load_series: pd.Series, acute_days=7, chronic_days=28) -> pd.DataFrame:
    acute = load_series.rolling(acute_days, min_periods=1).mean()
    chronic = load_series.rolling(chronic_days, min_periods=acute_days).mean()
    acwr = acute / chronic.replace(0, pd.NA)
    return pd.DataFrame({"carga_diaria": load_series, "agudo_7d": acute, "cronico_28d": chronic, "acwr": acwr})


def compute_hrv_zscore(hrv_series: pd.Series, short_window=7, baseline_window=60) -> pd.DataFrame:
    short_avg = hrv_series.rolling(short_window, min_periods=3).mean()
    baseline_mean = hrv_series.rolling(baseline_window, min_periods=14).mean()
    baseline_std = hrv_series.rolling(baseline_window, min_periods=14).std()
    z = (short_avg - baseline_mean) / baseline_std.replace(0, pd.NA)
    return pd.DataFrame({"hrv_diaria": hrv_series, "hrv_7d": short_avg, "hrv_baseline_60d": baseline_mean, "hrv_zscore": z})


# ---------------------------------------------------------------------------
# Panel 2: Eficiencia (Pace:HR) y deriva cardiaca
# ---------------------------------------------------------------------------

def compute_cardiac_drift(client, activity: dict) -> dict | None:
    """Deriva cardiaca (%) entre la 1a y 2a mitad de una actividad sostenida.

    Requiere >= 20 minutos de duración y datos de HR + velocidad por segundo.
    """
    activity_id = activity.get("activityId")
    duration = activity.get("movingDuration") or activity.get("duration") or 0
    if not activity_id or duration < 1200:
        return None

    try:
        details = client.get_activity_details(activity_id)
    except Exception:
        return None

    descriptors = details.get("metricDescriptors") or []
    idx_map = {d.get("key"): d.get("metricsIndex") for d in descriptors}
    ts_idx, hr_idx, speed_idx = (
        idx_map.get("directTimestamp"),
        idx_map.get("directHeartRate"),
        idx_map.get("directSpeed"),
    )
    if ts_idx is None or hr_idx is None or speed_idx is None:
        return None

    rows = []
    for m in details.get("activityDetailMetrics") or []:
        vals = m.get("metrics") or []
        if len(vals) <= max(ts_idx, hr_idx, speed_idx):
            continue
        ts, hr, speed = vals[ts_idx], vals[hr_idx], vals[speed_idx]
        if hr and speed and hr > 0 and speed > 0:
            rows.append((ts, hr, speed))

    if len(rows) < 20:
        return None

    mid = len(rows) // 2
    first, second = rows[:mid], rows[mid:]

    def block_avg(block):
        avg_hr = sum(r[1] for r in block) / len(block)
        avg_speed = sum(r[2] for r in block) / len(block)
        return avg_speed / avg_hr, avg_hr, avg_speed

    ratio1, hr1, speed1 = block_avg(first)
    ratio2, hr2, speed2 = block_avg(second)
    drift_pct = (ratio1 - ratio2) / ratio1 * 100 if ratio1 else None

    return {
        "activity_id": activity_id,
        "nombre": activity.get("activityName"),
        "fecha": (activity.get("startTimeLocal") or "")[:10],
        "deriva_pct": drift_pct,
        "hr_primera_mitad": hr1,
        "hr_segunda_mitad": hr2,
        "ritmo_kmh_primera_mitad": speed1 * 3.6,
        "ritmo_kmh_segunda_mitad": speed2 * 3.6,
    }


def compute_efficiency_report(client, activities: list) -> pd.DataFrame:
    rows = []
    for a in activities:
        result = compute_cardiac_drift(client, a)
        if result:
            rows.append(result)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Panel 3: Distribución de carga por zonas de FC (Reserva de FC / Karvonen)
# ---------------------------------------------------------------------------

ZONE_BOUNDS_PCT = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.5]  # límites Z1..Z5 (%HRR)


def hr_zone(hr: float, rhr: float, max_hr: float) -> int | None:
    if not hr or not rhr or not max_hr or max_hr <= rhr:
        return None
    pct_hrr = (hr - rhr) / (max_hr - rhr)
    if pct_hrr < 0:
        return 1
    for i in range(5):
        if ZONE_BOUNDS_PCT[i] <= pct_hrr < ZONE_BOUNDS_PCT[i + 1]:
            return i + 1
    return 5


def weekly_zone_distribution(client, activities: list, rhr: float, max_hr: float) -> dict:
    zone_seconds = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}

    for a in activities:
        activity_id = a.get("activityId")
        if not activity_id:
            continue
        try:
            details = client.get_activity_details(activity_id)
        except Exception:
            continue

        descriptors = details.get("metricDescriptors") or []
        idx_map = {d.get("key"): d.get("metricsIndex") for d in descriptors}
        ts_idx, hr_idx = idx_map.get("directTimestamp"), idx_map.get("directHeartRate")
        if ts_idx is None or hr_idx is None:
            continue

        prev_ts = None
        for m in details.get("activityDetailMetrics") or []:
            vals = m.get("metrics") or []
            if len(vals) <= max(ts_idx, hr_idx):
                continue
            ts, hr = vals[ts_idx], vals[hr_idx]
            if ts is None:
                continue
            if prev_ts is not None and hr:
                dt = (ts - prev_ts) / 1000.0
                if 0 < dt < 30:
                    z = hr_zone(hr, rhr, max_hr)
                    if z:
                        zone_seconds[z] += dt
            prev_ts = ts

    return zone_seconds


def estimate_max_hr(client, start: date, end: date) -> float | None:
    """Máximo de FC observado en el periodo (mejor esfuerzo empírico)."""
    best = None
    d = start
    while d <= end:
        summary = fetch_day_hr_summary(client, d)
        if summary:
            v = summary.get("maxHeartRate")
            if v and (best is None or v > best):
                best = v
        d += timedelta(days=1)
    return best


# ---------------------------------------------------------------------------
# Panel 4: Resiliencia del sistema nervioso autónomo (RHR + recuperación)
# ---------------------------------------------------------------------------

def compute_recovery_for_activity(client, activity: dict) -> dict | None:
    start_str = activity.get("startTimeLocal")
    duration = activity.get("duration") or activity.get("movingDuration") or 0
    if not start_str or not duration:
        return None

    try:
        start_dt = datetime.strptime(start_str[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    end_dt = start_dt + timedelta(seconds=duration)
    day = end_dt.date()

    summary = fetch_day_hr_summary(client, day)
    if not summary:
        return None
    values = [v for v in (summary.get("heartRateValues") or []) if v and v[1] is not None]
    if not values:
        return None

    times = [v[0] for v in values]
    end_ms = int(end_dt.timestamp() * 1000)

    def hr_at(offset_seconds):
        target = end_ms + offset_seconds * 1000
        idx = bisect.bisect_left(times, target)
        candidates = [values[i] for i in {max(0, idx - 1), min(len(values) - 1, idx)}]
        return min(candidates, key=lambda v: abs(v[0] - target))[1]

    hr_end = hr_at(0)
    hr_2min = hr_at(120)
    if hr_end is None or hr_2min is None:
        return None

    return {
        "fecha": day.isoformat(),
        "actividad": activity.get("activityName"),
        "hr_fin_esfuerzo": hr_end,
        "hr_2min_despues": hr_2min,
        "caida_2min": hr_end - hr_2min,
        "caida_por_minuto": (hr_end - hr_2min) / 2.0,
    }


def compute_recovery_report(client, activities: list) -> pd.DataFrame:
    rows = []
    for a in activities:
        r = compute_recovery_for_activity(client, a)
        if r:
            rows.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Snapshot completo del dashboard: junta todo lo que necesita
# garmin_dashboard_ui.render_dashboard_body() en un solo diccionario.
#
# build_runtime_data(client) lo arma en vivo (dashboard.py, tu propia
# cuenta). snapshot_to_json()/snapshot_from_json() lo convierten a/desde un
# formato guardable como texto (push_resumen.py lo manda a la hoja de
# Google; dashboard_pacientes.py lo reconstruye para dibujar el mismo
# dashboard con los datos ya guardados de un paciente, sin necesitar una
# sesión de Garmin en vivo).
# ---------------------------------------------------------------------------

_ACTIVITY_FIELDS_TO_KEEP = [
    "activityId", "activityName", "startTimeLocal", "distance", "duration",
    "movingDuration", "elevationGain", "averageHR", "calories",
]


def _trim_activity(a: dict) -> dict:
    """Solo los campos que usa el dashboard -- las actividades de Garmin
    traen decenas de campos (roles, URLs de imágenes, etc.) que no hacen
    falta y solo inflan el tamaño al guardar."""
    out = {k: a.get(k) for k in _ACTIVITY_FIELDS_TO_KEEP}
    out["activityType"] = {"typeKey": (a.get("activityType") or {}).get("typeKey")}
    return out


def build_runtime_data(client, lookback_days: int = 90, wellness_days: int = WELLNESS_DAYS_DEFAULT) -> dict:
    """Junta en un solo dict todo lo que necesita render_dashboard_body()."""
    end = date.today()
    start90 = end - timedelta(days=lookback_days)
    start30 = end - timedelta(days=wellness_days)

    activities = fetch_activities(client, start90, end)
    load_series = fetch_daily_load(client, start90, end, activities=activities)
    rhr_series = fetch_rhr_series(client, start90, end)
    hrv_series = fetch_hrv_series(client, start90, end)

    sleep_df = fetch_sleep_series(client, start30, end)
    hydration_df = fetch_hydration_series(client, start30, end)
    readiness_series = fetch_training_readiness_series(client, start30, end)
    battery_df = fetch_body_battery_series(client, start30, end)
    calories_df = fetch_calories_series(client, start30, end)

    week_ago = pd.Timestamp(end - timedelta(days=7))
    wellness_window_start = pd.Timestamp(start30)
    activities_last_week = [
        a for a in activities
        if a.get("startTimeLocal") and pd.Timestamp(a["startTimeLocal"][:10]) >= week_ago
    ]
    activities_calorias = [
        a for a in activities
        if a.get("startTimeLocal")
        and pd.Timestamp(a["startTimeLocal"][:10]) >= wellness_window_start
        and a.get("calories")
    ]

    acwr_df = compute_acwr(load_series)
    hrv_df = compute_hrv_zscore(hrv_series)
    ultimo_acwr = acwr_df["acwr"].dropna().iloc[-1] if acwr_df["acwr"].notna().any() else None
    ultimo_hrv_z = hrv_df["hrv_zscore"].dropna().iloc[-1] if hrv_df["hrv_zscore"].notna().any() else None

    efficiency_df = compute_efficiency_report(client, activities_last_week)
    peor_deriva_val = efficiency_df["deriva_pct"].max() if not efficiency_df.empty else None

    rhr_recent = rhr_series.dropna()
    rhr_avg = rhr_recent.tail(7).mean() if not rhr_recent.empty else None
    rhr_baseline = rhr_series.dropna().iloc[:-7].tail(60).mean() if rhr_series.dropna().shape[0] > 14 else None
    rhr_today = rhr_series.dropna().iloc[-1] if not rhr_series.dropna().empty else None
    max_hr = estimate_max_hr(client, start90, end)

    recovery_df = compute_recovery_report(client, activities_last_week)
    peor_caida_min = recovery_df["caida_por_minuto"].min() if not recovery_df.empty else None

    zone_seconds = None
    if rhr_avg is not None and max_hr is not None:
        zone_seconds = weekly_zone_distribution(client, activities_last_week, rhr_avg, max_hr)

    alerta_disrupcion = ultimo_acwr is not None and ultimo_hrv_z is not None and ultimo_acwr > 1.4 and ultimo_hrv_z < -1.5
    alerta_eficiencia = peor_deriva_val is not None and peor_deriva_val > 5
    alerta_vagal = (
        rhr_today is not None and rhr_baseline is not None and peor_caida_min is not None
        and rhr_today > rhr_baseline + 5 and peor_caida_min < 20
    )

    resumen_mes = compute_monthly_score(client, days=wellness_days)

    return {
        "generated_at": datetime.now().isoformat(),
        "lookback_days": lookback_days,
        "wellness_days": wellness_days,
        "activities": activities,
        "load_series": load_series,
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
    }


def _num(v):
    """A float nativo de Python (o None) -- numpy.float64 no siempre se
    puede mandar tal cual a JSON / a la API de Google Sheets."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return float(v)


def _series_to_json(s: pd.Series) -> dict:
    out = {}
    for idx, v in s.items():
        key = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
        out[key] = _num(v)
    return out


def _series_from_json(d: dict | None, name: str | None = None) -> pd.Series:
    if not d:
        return pd.Series(dtype="float64", name=name)
    idx = pd.to_datetime(list(d.keys()))
    return pd.Series(list(d.values()), index=idx, name=name, dtype="float64").sort_index()


def _df_to_json(df: pd.DataFrame, cols: list[str] | None = None) -> dict:
    """cols limita qué columnas se guardan -- render_dashboard_body no usa
    todas las que trae cada DataFrame, y cada columna extra de 90 días pesa
    varios miles de caracteres (el límite real de una celda de Sheets es
    50,000)."""
    use_cols = cols if cols is not None else list(df.columns)
    return {col: _series_to_json(df[col]) for col in use_cols if col in df.columns}


def _df_from_json(d: dict | None) -> pd.DataFrame:
    if not d:
        return pd.DataFrame()
    cols = {col: _series_from_json(vals, name=col) for col, vals in d.items()}
    return pd.DataFrame(cols)


def _trim_activity_calorias(a: dict) -> dict:
    """Solo lo que usa la tabla de calorías por actividad."""
    return {
        "activityName": a.get("activityName"),
        "startTimeLocal": a.get("startTimeLocal"),
        "calories": a.get("calories"),
    }


_SCALAR_KEYS = [
    "ultimo_acwr", "ultimo_hrv_z", "peor_deriva_val", "rhr_avg",
    "rhr_baseline", "rhr_today", "max_hr", "peor_caida_min",
]

_RESUMEN_MES_NUM_KEYS = [
    "overall_score", "recovery_score", "sleep_score", "sleep_score_garmin",
    "sleep_hours_avg", "activity_score", "active_kcal_avg", "rhr_avg_7d",
]


def snapshot_to_json(data: dict) -> dict:
    """Convierte el dict de build_runtime_data() a algo 100% serializable a
    JSON (para guardarlo como texto en una celda de Google Sheets)."""
    out = dict(data)

    # La lista completa de 90 días, y algunas columnas de varios DataFrames,
    # no las usa render_dashboard_body -- se calculan server-side nada más
    # para llegar a ultimo_acwr/ultimo_hrv_z/etc, que ya se guardan aparte.
    # Omitirlas ahorra espacio real: el límite de una celda de Sheets es
    # 50,000 caracteres, y para alguien muy activo cada columna de sobra
    # de 90 días pesa varios miles.
    out.pop("activities", None)
    out.pop("activities_last_week", None)
    out["activities_calorias"] = [_trim_activity_calorias(a) for a in data["activities_calorias"]]

    out["load_series"] = _series_to_json(data["load_series"])
    out["rhr_series"] = _series_to_json(data["rhr_series"])
    out["hrv_series"] = _series_to_json(data["hrv_series"])
    out["readiness_series"] = _series_to_json(data["readiness_series"])
    out["sleep_df"] = _df_to_json(data["sleep_df"], cols=["hours", "score"])
    out["hydration_df"] = _df_to_json(data["hydration_df"], cols=["value_l"])
    out["battery_df"] = _df_to_json(data["battery_df"])
    out["calories_df"] = _df_to_json(data["calories_df"])
    out["acwr_df"] = _df_to_json(data["acwr_df"], cols=["acwr"])
    out["hrv_df"] = _df_to_json(data["hrv_df"], cols=["hrv_zscore"])
    out["efficiency_df"] = data["efficiency_df"].to_dict(orient="records")
    out["recovery_df"] = data["recovery_df"].to_dict(orient="records")

    for k in _SCALAR_KEYS:
        out[k] = _num(out.get(k))

    # bool()/int() explícitos -- comparaciones sobre numpy.float64 dan
    # numpy.bool_/numpy.int64, que json.dumps no acepta.
    out["alerta_disrupcion"] = bool(out["alerta_disrupcion"])
    out["alerta_eficiencia"] = bool(out["alerta_eficiencia"])
    out["alerta_vagal"] = bool(out["alerta_vagal"])
    out["alertas_activas"] = int(out["alertas_activas"])

    if out.get("zone_seconds"):
        out["zone_seconds"] = {str(int(k)): _num(v) for k, v in out["zone_seconds"].items()}

    if out.get("resumen_mes"):
        rm = dict(out["resumen_mes"])
        for k in _RESUMEN_MES_NUM_KEYS:
            rm[k] = _num(rm.get(k))
        out["resumen_mes"] = rm

    return out


def snapshot_from_json(d: dict) -> dict:
    """El inverso de snapshot_to_json(): reconstruye DataFrames/Series a
    partir del dict guardado, listo para render_dashboard_body()."""
    out = dict(d)

    out["load_series"] = _series_from_json(d.get("load_series"), name="load")
    out["rhr_series"] = _series_from_json(d.get("rhr_series"), name="rhr")
    out["hrv_series"] = _series_from_json(d.get("hrv_series"), name="hrv")
    out["readiness_series"] = _series_from_json(d.get("readiness_series"))
    out["sleep_df"] = _df_from_json(d.get("sleep_df"))
    out["hydration_df"] = _df_from_json(d.get("hydration_df"))
    out["battery_df"] = _df_from_json(d.get("battery_df"))
    out["calories_df"] = _df_from_json(d.get("calories_df"))
    out["acwr_df"] = _df_from_json(d.get("acwr_df"))
    out["hrv_df"] = _df_from_json(d.get("hrv_df"))
    out["efficiency_df"] = pd.DataFrame(d.get("efficiency_df") or [])
    out["recovery_df"] = pd.DataFrame(d.get("recovery_df") or [])

    zone_seconds = d.get("zone_seconds")
    out["zone_seconds"] = {int(k): v for k, v in zone_seconds.items()} if zone_seconds else None

    return out
