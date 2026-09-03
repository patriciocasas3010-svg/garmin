#!/usr/bin/env python3
"""Tablero Maestro de Rendimiento - Streamlit.

Uso:
    streamlit run dashboard.py

Requiere haber corrido antes connect_garmin.py (usa la misma sesión guardada).
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

import garmin_metrics as gm
from garmin_session import get_client

st.set_page_config(page_title="Tablero Maestro de Rendimiento", layout="wide")

LOOKBACK_DAYS = 90


@st.cache_resource
def _client():
    return get_client()


@st.cache_data(ttl=3600)
def _load_data():
    client = _client()
    end = date.today()
    start = end - timedelta(days=LOOKBACK_DAYS)

    activities = gm.fetch_activities(client, start, end)
    load_series = gm.fetch_daily_load(client, start, end, activities=activities)
    rhr_series = gm.fetch_rhr_series(client, start, end)
    hrv_series = gm.fetch_hrv_series(client, start, end)

    return {
        "start": start,
        "end": end,
        "activities": activities,
        "load": load_series,
        "rhr": rhr_series,
        "hrv": hrv_series,
    }


st.title("Tablero Maestro de Rendimiento")
st.caption(
    f"Datos de los últimos {LOOKBACK_DAYS} días de tu cuenta Garmin Connect. "
    "Se recalculan cada hora (botón 'Actualizar datos' para forzarlo)."
)

if st.button("Actualizar datos"):
    st.cache_data.clear()

with st.spinner("Descargando y calculando métricas de Garmin Connect..."):
    data = _load_data()

client = _client()
activities = data["activities"]
load_series = data["load"]
rhr_series = data["rhr"]
hrv_series = data["hrv"]

week_ago = pd.Timestamp(date.today() - timedelta(days=7))
activities_last_week = [
    a for a in activities
    if a.get("startTimeLocal") and pd.Timestamp(a["startTimeLocal"][:10]) >= week_ago
]

# ---------------------------------------------------------------------------
# Panel 1: Alerta temprana (ACWR vs HRV)
# ---------------------------------------------------------------------------

st.header("1. Panel de Alerta Temprana — Carga vs. Preparación")
st.caption("ACWR (carga aguda 7d / crónica 28d) cruzado con Z-score de HRV nocturna (7d vs. línea base de 60d).")

acwr_df = gm.compute_acwr(load_series)
hrv_df = gm.compute_hrv_zscore(hrv_series)

col1, col2 = st.columns(2)
with col1:
    st.line_chart(acwr_df[["acwr"]].dropna())
    ultimo_acwr = acwr_df["acwr"].dropna().iloc[-1] if acwr_df["acwr"].notna().any() else None
    st.metric("ACWR actual", f"{ultimo_acwr:.2f}" if ultimo_acwr is not None else "sin datos suficientes")
with col2:
    st.line_chart(hrv_df[["hrv_zscore"]].dropna())
    ultimo_hrv_z = hrv_df["hrv_zscore"].dropna().iloc[-1] if hrv_df["hrv_zscore"].notna().any() else None
    st.metric("Z-score HRV actual", f"{ultimo_hrv_z:.2f} SD" if ultimo_hrv_z is not None else "sin datos suficientes")

if ultimo_hrv_z is None:
    st.info(
        "No hay datos de HRV nocturna suficientes o tu reloj no reporta esta métrica "
        "(HRV Status requiere modelos compatibles y varias semanas de datos)."
    )

# ---------------------------------------------------------------------------
# Panel 2: Eficiencia y economía cardiovascular
# ---------------------------------------------------------------------------

st.header("2. Panel de Eficiencia y Economía Cardiovascular")
st.caption(
    "Deriva cardiaca (%) entre la 1a y 2a mitad de cada actividad sostenida (>20 min) de la última semana: "
    "cuánto sube tu FC para mantener el mismo ritmo."
)

efficiency_df = gm.compute_efficiency_report(client, activities_last_week)
if efficiency_df.empty:
    st.info("No hay actividades sostenidas (>20 min, con datos de ritmo y FC) en la última semana.")
else:
    st.dataframe(
        efficiency_df[["fecha", "nombre", "deriva_pct", "hr_primera_mitad", "hr_segunda_mitad"]]
        .rename(columns={
            "deriva_pct": "Deriva cardiaca (%)",
            "hr_primera_mitad": "FC 1a mitad",
            "hr_segunda_mitad": "FC 2a mitad",
        }),
        width="stretch",
    )
    peor_deriva = efficiency_df["deriva_pct"].max()
    st.metric("Peor deriva cardiaca de la semana", f"{peor_deriva:.1f}%")

# ---------------------------------------------------------------------------
# Panel 3: Distribución de carga (polarización 80/20)
# ---------------------------------------------------------------------------

st.header("3. Panel de Distribución de Carga (Polarización 80/20)")
st.caption("Tiempo en zonas de FC reales (sobre Reserva de FC / Karvonen) en las actividades de la última semana.")

rhr_recent = rhr_series.dropna()
rhr_avg = rhr_recent.tail(7).mean() if not rhr_recent.empty else None
max_hr = gm.estimate_max_hr(client, data["start"], data["end"])

if rhr_avg is None or max_hr is None:
    st.info("No hay suficiente FC en reposo o FC máxima observada para calcular zonas por Reserva de FC.")
else:
    zone_seconds = gm.weekly_zone_distribution(client, activities_last_week, rhr_avg, max_hr)
    total = sum(zone_seconds.values())
    if total == 0:
        st.info("No hay datos de FC detallados en las actividades de la última semana.")
    else:
        zone_df = pd.DataFrame({
            "Zona": [f"Z{i}" for i in range(1, 6)],
            "Minutos": [zone_seconds[i] / 60 for i in range(1, 6)],
            "% del total": [zone_seconds[i] / total * 100 for i in range(1, 6)],
        })
        st.bar_chart(zone_df.set_index("Zona")["Minutos"])
        st.dataframe(zone_df, use_container_width=True)

        pct_bajo = (zone_seconds[1] + zone_seconds[2]) / total * 100
        pct_medio = zone_seconds[3] / total * 100
        pct_alto = (zone_seconds[4] + zone_seconds[5]) / total * 100
        st.metric("Z1+Z2 (base aeróbica)", f"{pct_bajo:.0f}%", help="Meta orientativa del modelo 80/20: ~80%")
        st.metric("Z3 (zona intermedia)", f"{pct_medio:.0f}%")
        st.metric("Z4+Z5 (alta intensidad)", f"{pct_alto:.0f}%")
        if pct_medio > 15:
            st.warning(
                f"Zona 3 en {pct_medio:.0f}% del tiempo: por encima de lo recomendado por el modelo "
                "polarizado 80/20. Riesgo de acumular fatiga sin la adaptación de la alta intensidad."
            )

# ---------------------------------------------------------------------------
# Panel 4: Resiliencia del sistema nervioso autónomo
# ---------------------------------------------------------------------------

st.header("4. Panel de Resiliencia del Sistema Nervioso Autónomo")
st.caption("FC en reposo frente a la velocidad de recuperación (caída de FC en los primeros 2 minutos post-esfuerzo).")

col3, col4 = st.columns(2)
with col3:
    st.line_chart(rhr_series.dropna())
    st.metric("RHR promedio últimos 7 días", f"{rhr_avg:.0f} lpm" if rhr_avg is not None else "sin datos")

recovery_df = gm.compute_recovery_report(client, activities_last_week)
with col4:
    if recovery_df.empty:
        st.info("No se pudo calcular recuperación post-esfuerzo (requiere FC continua del día del entreno).")
    else:
        st.dataframe(
            recovery_df[["fecha", "actividad", "caida_2min", "caida_por_minuto"]].rename(
                columns={"caida_2min": "Caída en 2min (lpm)", "caida_por_minuto": "Caída por minuto (lpm)"}
            ),
            width="stretch",
        )

# ---------------------------------------------------------------------------
# Panel 5: Sueño, hidratación, desgaste físico y recuperación
# ---------------------------------------------------------------------------

WELLNESS_DAYS = 30


@st.cache_data(ttl=3600)
def _load_wellness_data():
    client = _client()
    end = date.today()
    start = end - timedelta(days=WELLNESS_DAYS)
    return {
        "sleep": gm.fetch_sleep_series(client, start, end),
        "hydration": gm.fetch_hydration_series(client, start, end),
        "readiness": gm.fetch_training_readiness_series(client, start, end),
        "battery": gm.fetch_body_battery_series(client, start, end),
    }


st.header("5. Panel de Sueño, Hidratación, Desgaste Físico y Recuperación")
st.caption(f"Últimos {WELLNESS_DAYS} días.")

with st.spinner("Descargando sueño, hidratación, Body Battery y Training Readiness..."):
    wellness = _load_wellness_data()

sleep_df = wellness["sleep"]
hydration_df = wellness["hydration"]
readiness_series = wellness["readiness"]
battery_df = wellness["battery"]

col5, col6 = st.columns(2)
with col5:
    st.subheader("Sueño")
    if sleep_df["hours"].notna().any():
        st.line_chart(sleep_df[["hours"]].dropna())
        st.metric("Promedio", f"{sleep_df['hours'].dropna().mean():.1f} h/noche")
        if sleep_df["score"].notna().any():
            st.metric("Sleep Score promedio", f"{sleep_df['score'].dropna().mean():.0f}/100")
    else:
        st.info("No hay datos de sueño en el periodo.")

with col6:
    st.subheader("Hidratación")
    if hydration_df["value_l"].notna().any():
        st.bar_chart(hydration_df[["value_l"]].dropna())
        st.metric("Promedio", f"{hydration_df['value_l'].dropna().mean():.2f} L/día")
    else:
        st.info(
            "No hay registros de hidratación (solo cuenta si la registras a mano en "
            "la app; el reloj solo no mide cuánta agua tomas)."
        )

col7, col8 = st.columns(2)
with col7:
    st.subheader("Desgaste físico (Body Battery)")
    battery_valid = battery_df.dropna(how="all")
    if not battery_valid.empty:
        st.bar_chart(battery_valid[["charged", "drained"]])
        avg_charged = battery_df["charged"].dropna().mean()
        avg_drained = battery_df["drained"].dropna().mean()
        st.metric("Recarga promedio/día", f"{avg_charged:.0f}" if pd.notna(avg_charged) else "N/D")
        st.metric("Gasto promedio/día", f"{avg_drained:.0f}" if pd.notna(avg_drained) else "N/D")
    else:
        st.info("No hay datos de Body Battery en el periodo.")

with col8:
    st.subheader("Recuperación (Training Readiness)")
    if readiness_series.notna().any():
        st.line_chart(readiness_series.dropna())
        st.metric("Promedio", f"{readiness_series.dropna().mean():.0f}/100")
    else:
        st.info("Tu cuenta/reloj no reporta Training Readiness (requiere modelos más recientes).")

# ---------------------------------------------------------------------------
# Panel 6: Calorías (reposo, actividad y total)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def _load_calories_data():
    client = _client()
    end = date.today()
    start = end - timedelta(days=WELLNESS_DAYS)
    return gm.fetch_calories_series(client, start, end)


st.header("6. Calorías (reposo, actividad y total)")
st.caption(f"Últimos {WELLNESS_DAYS} días.")

with st.spinner("Descargando calorías diarias..."):
    calories_df = _load_calories_data()

if calories_df["total_kcal"].notna().any():
    st.bar_chart(calories_df[["resting_kcal", "active_kcal"]].dropna(how="all"))

    avg_resting = calories_df["resting_kcal"].dropna().mean()
    avg_active = calories_df["active_kcal"].dropna().mean()
    avg_total = calories_df["total_kcal"].dropna().mean()
    sum_resting = calories_df["resting_kcal"].dropna().sum()
    sum_active = calories_df["active_kcal"].dropna().sum()
    sum_total = calories_df["total_kcal"].dropna().sum()

    colc1, colc2, colc3 = st.columns(3)
    colc1.metric(
        "Reposo (BMR)", f"{avg_resting:.0f} kcal/día" if pd.notna(avg_resting) else "N/D",
        help=f"Total en {WELLNESS_DAYS} días: {sum_resting:.0f} kcal" if pd.notna(sum_resting) else None,
    )
    colc2.metric(
        "Por actividad", f"{avg_active:.0f} kcal/día" if pd.notna(avg_active) else "N/D",
        help=f"Total en {WELLNESS_DAYS} días: {sum_active:.0f} kcal" if pd.notna(sum_active) else None,
    )
    colc3.metric(
        "Total", f"{avg_total:.0f} kcal/día" if pd.notna(avg_total) else "N/D",
        help=f"Total en {WELLNESS_DAYS} días: {sum_total:.0f} kcal" if pd.notna(sum_total) else None,
    )
else:
    st.info("No hay datos de calorías disponibles en el periodo.")

wellness_window_start = pd.Timestamp(date.today() - timedelta(days=WELLNESS_DAYS))
activities_calorias = [
    a for a in activities
    if a.get("startTimeLocal")
    and pd.Timestamp(a["startTimeLocal"][:10]) >= wellness_window_start
    and a.get("calories")
]
if activities_calorias:
    cal_activity_df = pd.DataFrame([
        {
            "Fecha": a.get("startTimeLocal", "")[:10],
            "Actividad": a.get("activityName"),
            "Calorías": a.get("calories"),
        }
        for a in activities_calorias
    ]).sort_values("Fecha", ascending=False)
    st.dataframe(cal_activity_df, width="stretch")
    st.metric(
        f"Calorías totales por actividades ({WELLNESS_DAYS}d)",
        f"{cal_activity_df['Calorías'].sum():.0f} kcal",
    )
else:
    st.info(f"No hay actividades con calorías registradas en los últimos {WELLNESS_DAYS} días.")

# ---------------------------------------------------------------------------
# Índice unificado / tabla de alertas
# ---------------------------------------------------------------------------

st.header("Indicadores Unificados")

rhr_baseline = rhr_series.dropna().iloc[:-7].tail(60).mean() if rhr_series.dropna().shape[0] > 14 else None
rhr_today = rhr_series.dropna().iloc[-1] if not rhr_series.dropna().empty else None
peor_deriva_val = efficiency_df["deriva_pct"].max() if not efficiency_df.empty else None
peor_caida_min = recovery_df["caida_por_minuto"].min() if not recovery_df.empty else None

filas = []

alerta_disrupcion = (
    ultimo_acwr is not None and ultimo_hrv_z is not None
    and ultimo_acwr > 1.4 and ultimo_hrv_z < -1.5
)
filas.append({
    "Indicador": "Índice de Disrupción Fisiológica",
    "Métrica cruzada": f"ACWR={ultimo_acwr:.2f}" if ultimo_acwr is not None else "N/D",
    "Umbral crítico": "ACWR > 1.4 y HRV < -1.5 SD",
    "Estado": "🔴 ALERTA" if alerta_disrupcion else "🟢 OK",
    "Acción recomendada": "Sustituir sesión de impacto por recuperación activa o movilidad" if alerta_disrupcion else "-",
})

alerta_eficiencia = peor_deriva_val is not None and peor_deriva_val > 5
filas.append({
    "Indicador": "Pérdida de Eficiencia Aeróbica",
    "Métrica cruzada": f"Deriva={peor_deriva_val:.1f}%" if peor_deriva_val is not None else "N/D",
    "Umbral crítico": "Deriva cardiaca > 5% en mismo ritmo",
    "Estado": "🔴 ALERTA" if alerta_eficiencia else "🟢 OK",
    "Acción recomendada": "Ajustar hidratación/electrolitos o recortar volumen del bloque" if alerta_eficiencia else "-",
})

alerta_vagal = (
    rhr_today is not None and rhr_baseline is not None and peor_caida_min is not None
    and rhr_today > rhr_baseline + 5 and peor_caida_min < 20
)
filas.append({
    "Indicador": "Estatus de Tono Vagal",
    "Métrica cruzada": f"RHR hoy={rhr_today:.0f}" if rhr_today is not None else "N/D",
    "Umbral crítico": "RHR +5 lpm sobre media y caída FC < 20 lpm/min",
    "Estado": "🔴 ALERTA" if alerta_vagal else "🟢 OK",
    "Acción recomendada": "Cancelar alta intensidad; priorizar descanso" if alerta_vagal else "-",
})

st.table(pd.DataFrame(filas))

st.caption(
    "El umbral del Estatus de Tono Vagal usa 'caída FC < 20 lpm/min' interpretado como una caída "
    "promedio menor a 20 lpm por minuto en los primeros 2 minutos post-esfuerzo."
)
