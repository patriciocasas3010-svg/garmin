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
