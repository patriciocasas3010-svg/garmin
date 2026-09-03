"""Lee un export de Apple Health / Apple Watch (el .zip que genera la app
Salud del iPhone: Ajustes -> Salud -> foto de perfil -> "Exportar todos los
datos de salud") y arma el mismo dict que garmin_metrics.build_runtime_data(),
para poder reutilizar render_dashboard_body(), snapshot_to_json/from_json y
push_resumen.py sin cambios -- el resto del sistema no sabe ni le importa si
los datos vinieron de Garmin o de Apple.

Diferencias honestas frente a Garmin (cosas que Apple Health no tiene o no
da de forma confiable):

- Body Battery y Training Readiness: no existen en Apple, quedan vacíos
  (el dashboard ya sabe mostrar "no hay datos suficientes" en ese caso,
  es el mismo camino que ya usa cuando un reloj Garmin no los soporta).
- Deriva cardiaca (pestaña "Eficiencia"): ese cálculo necesita el ritmo
  (pace) segundo a segundo, que Apple solo guarda si el entrenamiento tiene
  una ruta GPS asociada -- en la práctica, poco frecuente salvo carreras/
  rodadas recientes con el GPS del reloj activado. Por ahora se deja vacío;
  las zonas de FC y la caída de pulso post-esfuerzo de esa misma pestaña sí
  se calculan igual que con Garmin, porque solo necesitan FC.
- Sleep Score y etapas de sueño (profundo/ligero/REM): solo si el iPhone/
  Apple Watch las reporta (requiere seguimiento de etapas de sueño, watchOS
  9+ aprox. en un Apple Watch Series 4 o más nuevo). Si no están, se usan
  solo las horas dormidas -- el mismo camino de respaldo que ya usa Garmin
  cuando el reloj no da un Sleep Score propio.
"""

import glob
import os
import zipfile
import xml.etree.ElementTree as ET
from bisect import bisect_left
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import mkdtemp

import pandas as pd

from garmin_metrics import (
    WELLNESS_DAYS_DEFAULT,
    compute_acwr,
    compute_hrv_zscore,
    hr_zone,
    score_label,
    score_range,
    score_ramp,
)
from garmin_reports import _activity_load

# ---------------------------------------------------------------------------
# Encontrar y parsear el XML dentro del .zip que exporta la app Salud
# ---------------------------------------------------------------------------

def find_export_zip(folder: str = ".") -> str | None:
    """Busca el .zip de exportación de Salud en una carpeta. El nombre
    cambia según el idioma del iPhone (export.zip en inglés, exportar.zip en
    español), así que se busca por patrón en vez de un nombre fijo."""
    candidatos = sorted(
        p for p in glob.glob(os.path.join(folder, "*.zip"))
        if "export" in os.path.basename(p).lower()
    )
    return candidatos[0] if candidatos else None


def _find_export_xml(path: str) -> str:
    """Acepta el .zip que exporta la app Salud, una carpeta ya descomprimida,
    o la ruta directa al .xml -- y devuelve la ruta al .xml real a leer.

    El nombre del archivo cambia según el idioma del iPhone (export.xml en
    inglés, exportar.xml en español), así que se busca por patrón en vez de
    un nombre fijo. export_cda.xml es un documento clínico aparte (formato
    CDA), no lo queremos.
    """
    p = Path(path)

    def _is_health_export(name: str) -> bool:
        base = name.rsplit("/", 1)[-1].lower()
        return base in ("export.xml", "exportar.xml")

    if p.is_file() and p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as zf:
            candidates = [n for n in zf.namelist() if _is_health_export(n)]
            if not candidates:
                raise ValueError(
                    "No encontré 'export.xml' dentro de ese .zip -- ¿es el archivo "
                    "que exportó la app Salud del iPhone?"
                )
            out_dir = mkdtemp(prefix="apple_health_")
            extracted = zf.extract(candidates[0], out_dir)
            return extracted

    if p.is_dir():
        for name in ("export.xml", "exportar.xml"):
            candidate = p / name
            if candidate.exists():
                return str(candidate)
            candidate = p / "apple_health_export" / name
            if candidate.exists():
                return str(candidate)
        raise ValueError(f"No encontré export.xml/exportar.xml dentro de '{path}'.")

    if p.is_file():
        return str(p)

    raise ValueError(f"No encontré el archivo o carpeta '{path}'.")


_SLEEP_ASLEEP_VALUES = {
    "HKCategoryValueSleepAnalysisAsleep",
    "HKCategoryValueSleepAnalysisAsleepUnspecified",
    "HKCategoryValueSleepAnalysisAsleepCore",
    "HKCategoryValueSleepAnalysisAsleepDeep",
    "HKCategoryValueSleepAnalysisAsleepREM",
}
_SLEEP_STAGE_MIN_KEY = {
    "HKCategoryValueSleepAnalysisAsleepCore": "light_min",
    "HKCategoryValueSleepAnalysisAsleepDeep": "deep_min",
    "HKCategoryValueSleepAnalysisAsleepREM": "rem_min",
}

_WORKOUT_LABELS = {
    "HKWorkoutActivityTypeRunning": "Correr",
    "HKWorkoutActivityTypeCycling": "Ciclismo",
    "HKWorkoutActivityTypeSwimming": "Natación",
    "HKWorkoutActivityTypeWalking": "Caminata",
    "HKWorkoutActivityTypeHighIntensityIntervalTraining": "HIIT",
    "HKWorkoutActivityTypeTraditionalStrengthTraining": "Fuerza",
    "HKWorkoutActivityTypeFunctionalStrengthTraining": "Fuerza funcional",
    "HKWorkoutActivityTypeYoga": "Yoga",
    "HKWorkoutActivityTypeBoxing": "Boxeo",
    "HKWorkoutActivityTypeGolf": "Golf",
    "HKWorkoutActivityTypeElliptical": "Elíptica",
    "HKWorkoutActivityTypeRowing": "Remo",
    "HKWorkoutActivityTypeHiking": "Senderismo",
    "HKWorkoutActivityTypeCoreTraining": "Core",
}


def _workout_label(activity_type: str) -> str:
    return _WORKOUT_LABELS.get(activity_type, (activity_type or "Entrenamiento").replace("HKWorkoutActivityType", ""))


def _parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")


class _RawData:
    def __init__(self):
        self.hr: list[tuple[datetime, float]] = []
        self.rhr_daily: dict[date, list[float]] = defaultdict(list)
        self.hrv_daily: dict[date, list[float]] = defaultdict(list)
        self.sleep_hours: dict[date, float] = defaultdict(float)
        self.sleep_stage_min: dict[date, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.hydration_ml: dict[date, float] = defaultdict(float)
        self.active_kcal: dict[date, float] = defaultdict(float)
        self.basal_kcal: dict[date, float] = defaultdict(float)
        self.workouts: list[dict] = []


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_export(xml_path: str, keep_hr_since: datetime) -> _RawData:
    """Un solo recorrido del XML (puede pesar cientos de MB) llenando todos
    los cubos que necesitamos -- evita releer el archivo una vez por métrica."""
    raw = _RawData()

    for _, elem in ET.iterparse(xml_path, events=("end",)):
        tag = elem.tag
        if tag == "Record":
            rtype = elem.get("type")
            start_raw = elem.get("startDate")
            if not start_raw:
                elem.clear()
                continue
            try:
                start_dt = _parse_dt(start_raw)
            except ValueError:
                elem.clear()
                continue
            value = _to_float(elem.get("value"))
            day = start_dt.date()

            if rtype == "HKQuantityTypeIdentifierHeartRate":
                if value is not None and start_dt >= keep_hr_since:
                    raw.hr.append((start_dt, value))
            elif rtype == "HKQuantityTypeIdentifierRestingHeartRate":
                if value is not None:
                    raw.rhr_daily[day].append(value)
            elif rtype == "HKQuantityTypeIdentifierHeartRateVariabilitySDNN":
                if value is not None:
                    raw.hrv_daily[day].append(value)
            elif rtype == "HKQuantityTypeIdentifierActiveEnergyBurned":
                if value is not None:
                    raw.active_kcal[day] += value
            elif rtype == "HKQuantityTypeIdentifierBasalEnergyBurned":
                if value is not None:
                    raw.basal_kcal[day] += value
            elif rtype == "HKQuantityTypeIdentifierDietaryWater":
                if value is not None:
                    unit = elem.get("unit") or "mL"
                    ml = value if unit.lower() in ("ml", "millilitre", "milliliter") else value * 1000
                    raw.hydration_ml[day] += ml
            elif rtype == "HKCategoryTypeIdentifierSleepAnalysis":
                end_raw = elem.get("endDate")
                sleep_value = elem.get("value")
                if end_raw and sleep_value in _SLEEP_ASLEEP_VALUES:
                    try:
                        end_dt = _parse_dt(end_raw)
                    except ValueError:
                        elem.clear()
                        continue
                    wake_day = end_dt.date()
                    hours = (end_dt - start_dt).total_seconds() / 3600
                    raw.sleep_hours[wake_day] += hours
                    stage_key = _SLEEP_STAGE_MIN_KEY.get(sleep_value)
                    if stage_key:
                        raw.sleep_stage_min[wake_day][stage_key] += hours * 60

            elem.clear()

        elif tag == "Workout":
            start_raw, end_raw = elem.get("startDate"), elem.get("endDate")
            if start_raw and end_raw:
                try:
                    start_dt, end_dt = _parse_dt(start_raw), _parse_dt(end_raw)
                    raw.workouts.append({
                        "type": elem.get("workoutActivityType"),
                        "start": start_dt,
                        "end": end_dt,
                        "duration_s": (end_dt - start_dt).total_seconds(),
                        "calories": _to_float(elem.get("totalEnergyBurned")),
                    })
                except ValueError:
                    pass
            elem.clear()
        else:
            elem.clear()

    raw.hr.sort(key=lambda t: t[0])
    return raw


# ---------------------------------------------------------------------------
# Utilidades sobre la lista de muestras de FC ya ordenada por tiempo
# ---------------------------------------------------------------------------

def _hr_window(hr_sorted: list[tuple[datetime, float]], hr_times: list[datetime], start: datetime, end: datetime):
    i = bisect_left(hr_times, start)
    j = bisect_left(hr_times, end)
    return hr_sorted[i:j]


def _hr_at(hr_sorted: list[tuple[datetime, float]], hr_times: list[datetime], target: datetime):
    if not hr_sorted:
        return None
    idx = bisect_left(hr_times, target)
    candidates = [hr_sorted[i] for i in {max(0, idx - 1), min(len(hr_sorted) - 1, idx)}]
    return min(candidates, key=lambda t: abs((t[0] - target).total_seconds()))[1]


def _date_index(start: date, end: date):
    return pd.to_datetime(pd.date_range(start, end, freq="D"))


# ---------------------------------------------------------------------------
# build_runtime_data: misma forma exacta que garmin_metrics.build_runtime_data
# ---------------------------------------------------------------------------

def build_runtime_data(export_path: str, lookback_days: int = 90, wellness_days: int = WELLNESS_DAYS_DEFAULT) -> dict:
    xml_path = _find_export_xml(export_path)

    end = date.today()
    start90 = end - timedelta(days=lookback_days)
    start30 = end - timedelta(days=wellness_days)
    week_ago = end - timedelta(days=7)

    keep_hr_since = datetime.combine(start90, datetime.min.time()).astimezone()
    raw = _parse_export(xml_path, keep_hr_since)
    hr_times = [t for t, _ in raw.hr]

    # --- actividades (solo lo que usa el resto del sistema) ---
    activities = []
    for i, w in enumerate(raw.workouts):
        if w["start"].date() < start90:
            continue
        window = _hr_window(raw.hr, hr_times, w["start"], w["end"])
        avg_hr = sum(v for _, v in window) / len(window) if window else None
        activities.append({
            "activityId": f"apple-{i}-{int(w['start'].timestamp())}",
            "activityName": _workout_label(w["type"]),
            "startTimeLocal": w["start"].strftime("%Y-%m-%d %H:%M:%S"),
            "_start": w["start"],
            "_end": w["end"],
            "duration": w["duration_s"],
            "movingDuration": w["duration_s"],
            "averageHR": avg_hr,
            "calories": w["calories"],
        })

    load_series = _daily_load(activities, start90, end)
    rhr_series = _daily_avg_series(raw.rhr_daily, start90, end, "rhr")
    hrv_series = _daily_avg_series(raw.hrv_daily, start90, end, "hrv")

    sleep_df = _sleep_df(raw, start30, end)
    hydration_df = _hydration_df(raw, start30, end)
    calories_df = _calories_df(raw, start30, end)
    readiness_series = pd.Series(float("nan"), index=_date_index(start30, end), dtype="float64")
    battery_df = pd.DataFrame({"charged": float("nan"), "drained": float("nan")}, index=_date_index(start30, end))

    activities_last_week = [a for a in activities if a["_start"].date() >= week_ago]
    activities_calorias = [
        a for a in activities
        if datetime.strptime(a["startTimeLocal"], "%Y-%m-%d %H:%M:%S").date() >= start30 and a.get("calories")
    ]

    acwr_df = compute_acwr(load_series)
    hrv_df = compute_hrv_zscore(hrv_series)
    ultimo_acwr = acwr_df["acwr"].dropna().iloc[-1] if acwr_df["acwr"].notna().any() else None
    ultimo_hrv_z = hrv_df["hrv_zscore"].dropna().iloc[-1] if hrv_df["hrv_zscore"].notna().any() else None

    # Deriva cardiaca (pace:HR) no se calcula -- Apple no da ritmo confiable
    # sin una ruta GPS asociada a cada entrenamiento. Ver docstring del módulo.
    efficiency_df = pd.DataFrame()
    peor_deriva_val = None

    rhr_recent = rhr_series.dropna()
    # tail(7) sobre la serie completa (no sobre .dropna()) para que sea un
    # promedio de verdad de los últimos 7 días de calendario -- si esos 7
    # días no tienen datos, debe decir que no hay datos, no promediar
    # valores viejos de hace semanas/meses y mostrarlos como si fueran
    # recientes (con Apple Health, donde puede haber huecos, esto importa).
    rhr_avg = rhr_series.tail(7).mean()
    rhr_avg = rhr_avg if pd.notna(rhr_avg) else None
    rhr_baseline = rhr_series.dropna().iloc[:-7].tail(60).mean() if rhr_series.dropna().shape[0] > 14 else None
    rhr_today = rhr_recent.iloc[-1] if not rhr_recent.empty else None
    max_hr = max((v for _, v in raw.hr), default=None)

    recovery_df = _recovery_report(activities_last_week, raw.hr, hr_times)
    peor_caida_min = recovery_df["caida_por_minuto"].min() if not recovery_df.empty else None

    zone_seconds = None
    if rhr_avg is not None and max_hr is not None:
        zone_seconds = _zone_distribution(activities_last_week, raw.hr, hr_times, rhr_avg, max_hr)

    alerta_disrupcion = ultimo_acwr is not None and ultimo_hrv_z is not None and ultimo_acwr > 1.4 and ultimo_hrv_z < -1.5
    alerta_eficiencia = peor_deriva_val is not None and peor_deriva_val > 5
    alerta_vagal = (
        rhr_today is not None and rhr_baseline is not None and peor_caida_min is not None
        and rhr_today > rhr_baseline + 5 and peor_caida_min < 20
    )

    resumen_mes = _monthly_score(activities, sleep_df, calories_df, rhr_series, wellness_days)

    for a in activities:
        a.pop("_end", None)
    for a in activities_last_week:
        a.pop("_end", None)

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
        # Apple Health no calcula pérdida de líquidos estimada por actividad
        # (es un algoritmo propio de Garmin) -- el dashboard muestra "no
        # disponible" cuando esta lista/valor vienen vacíos.
        "hidratacion_por_tipo": [],
        "hidratacion_diaria": {"promedio_ml_dia": None, "dias_con_actividad": 0, "serie": {}},
    }


def _daily_load(activities: list[dict], start: date, end: date) -> pd.Series:
    by_day: dict[date, float] = defaultdict(float)
    for a in activities:
        d = datetime.strptime(a["startTimeLocal"], "%Y-%m-%d %H:%M:%S").date()
        by_day[d] += _activity_load(a)
    idx = _date_index(start, end)
    return pd.Series([by_day.get(d.date(), 0.0) for d in idx], index=idx, name="load")


def _daily_avg_series(daily: dict[date, list[float]], start: date, end: date, name: str) -> pd.Series:
    idx = _date_index(start, end)
    values = [
        (sum(daily[d.date()]) / len(daily[d.date()])) if daily.get(d.date()) else None
        for d in idx
    ]
    return pd.Series(values, index=idx, name=name, dtype="float64")


def _sleep_df(raw: _RawData, start: date, end: date) -> pd.DataFrame:
    idx = _date_index(start, end)
    rows = []
    for d in idx:
        day = d.date()
        hours = raw.sleep_hours.get(day)
        stages = raw.sleep_stage_min.get(day, {})
        rows.append({
            "date": d,
            "hours": hours,
            "deep_min": stages.get("deep_min"),
            "light_min": stages.get("light_min"),
            "rem_min": stages.get("rem_min"),
            "awake_min": None,
            "score": None,
        })
    return pd.DataFrame(rows).set_index("date")


def _hydration_df(raw: _RawData, start: date, end: date) -> pd.DataFrame:
    idx = _date_index(start, end)
    rows = []
    for d in idx:
        ml = raw.hydration_ml.get(d.date())
        rows.append({"date": d, "value_l": ml / 1000 if ml is not None else None, "goal_l": None})
    return pd.DataFrame(rows).set_index("date")


def _calories_df(raw: _RawData, start: date, end: date) -> pd.DataFrame:
    idx = _date_index(start, end)
    rows = []
    for d in idx:
        day = d.date()
        resting = raw.basal_kcal.get(day)
        active = raw.active_kcal.get(day)
        total = (resting or 0) + (active or 0) if (resting is not None or active is not None) else None
        rows.append({"date": d, "resting_kcal": resting, "active_kcal": active, "total_kcal": total})
    return pd.DataFrame(rows).set_index("date")


def _recovery_report(activities_last_week: list[dict], hr_sorted, hr_times) -> pd.DataFrame:
    rows = []
    for a in activities_last_week:
        end_dt = a.get("_end")
        if end_dt is None:
            continue
        hr_end = _hr_at(hr_sorted, hr_times, end_dt)
        hr_2min = _hr_at(hr_sorted, hr_times, end_dt + timedelta(minutes=2))
        if hr_end is None or hr_2min is None:
            continue
        rows.append({
            "fecha": end_dt.date().isoformat(),
            "actividad": a.get("activityName"),
            "hr_fin_esfuerzo": hr_end,
            "hr_2min_despues": hr_2min,
            "caida_2min": hr_end - hr_2min,
            "caida_por_minuto": (hr_end - hr_2min) / 2.0,
        })
    return pd.DataFrame(rows)


def _zone_distribution(activities_last_week: list[dict], hr_sorted, hr_times, rhr: float, max_hr: float) -> dict:
    zone_seconds = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}
    for a in activities_last_week:
        start_dt, end_dt = a.get("_start"), a.get("_end")
        if start_dt is None or end_dt is None:
            continue
        window = _hr_window(hr_sorted, hr_times, start_dt, end_dt)
        prev_ts = None
        for ts, hr in window:
            if prev_ts is not None:
                dt = (ts - prev_ts).total_seconds()
                if 0 < dt < 30:
                    z = hr_zone(hr, rhr, max_hr)
                    if z:
                        zone_seconds[z] += dt
            prev_ts = ts
    return zone_seconds


def _monthly_score(activities: list[dict], sleep_df: pd.DataFrame, calories_df: pd.DataFrame, rhr_series: pd.Series, days: int) -> dict:
    """Igual que garmin_metrics.compute_monthly_score, pero sin recuperación
    (Training Readiness no existe en Apple -- ese subpuntaje simplemente no
    entra al promedio en vez de forzarse a 0)."""
    recovery_score = None  # sin Training Readiness

    sleep_hours_avg = sleep_df["hours"].dropna().mean() if sleep_df["hours"].notna().any() else None
    sleep_score_garmin = None
    sleep_score = score_range(sleep_hours_avg, 4, 7, 9, 11)

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
