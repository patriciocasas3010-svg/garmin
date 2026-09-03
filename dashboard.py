#!/usr/bin/env python3
"""Tablero Maestro de Rendimiento - Streamlit.

Uso:
    streamlit run dashboard.py

Requiere haber corrido antes connect_garmin.py (usa la misma sesión guardada).
"""

from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import garmin_metrics as gm
from garmin_session import get_client

st.set_page_config(page_title="Tablero Maestro de Rendimiento", layout="wide", page_icon="🏃")

LOOKBACK_DAYS = 90
WELLNESS_DAYS = 30

# ---------------------------------------------------------------------------
# Paleta y helpers de gráficas (colores validados para daltonismo, ver
# dataviz skill / references/palette.md)
# ---------------------------------------------------------------------------

BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"
STATUS_GOOD, STATUS_CRITICAL = "#0ca30c", "#d03b3b"
INK_PRIMARY, INK_SECONDARY, INK_MUTED = "#0b0b0b", "#52514e", "#898781"
GRID_COLOR = "#e1e0d9"
ZONE_RAMP = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # Z1 (suave) -> Z5 (intenso)

alt.themes.enable("none")


def line_with_rule(series: pd.Series, title: str, color: str, rule_value: float | None = None, fmt: str = ".1f", height: int = 220):
    """Línea de una sola serie, con línea de referencia punteada opcional."""
    data = series.dropna().reset_index()
    data.columns = ["fecha", "valor"]
    if data.empty:
        return None

    chart = (
        alt.Chart(data)
        .mark_line(strokeWidth=2, color=color, point=alt.OverlayMarkDef(filled=True, size=45, color=color))
        .encode(
            x=alt.X("fecha:T", title=None),
            y=alt.Y("valor:Q", title=title, scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("fecha:T", title="Fecha"), alt.Tooltip("valor:Q", title=title, format=fmt)],
        )
    )
    layers = [chart]
    if rule_value is not None:
        rule_df = pd.DataFrame({"y": [rule_value]})
        rule = alt.Chart(rule_df).mark_rule(strokeDash=[4, 4], color=INK_MUTED, strokeWidth=1).encode(y="y:Q")
        layers.append(rule)

    return (
        alt.layer(*layers)
        .properties(height=height)
        .configure_axis(gridColor=GRID_COLOR, domainColor=GRID_COLOR, labelColor=INK_SECONDARY, titleColor=INK_SECONDARY)
        .configure_view(strokeWidth=0)
    )


def ordinal_bar_chart(labels: list[str], values: list[float], value_title: str, height: int = 240):
    data = pd.DataFrame({"zona": labels, "valor": values})
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=36)
        .encode(
            x=alt.X("zona:N", title=None, sort=labels),
            y=alt.Y("valor:Q", title=value_title),
            color=alt.Color("zona:N", scale=alt.Scale(domain=labels, range=ZONE_RAMP), legend=None),
            tooltip=[alt.Tooltip("zona:N", title="Zona"), alt.Tooltip("valor:Q", title=value_title, format=".0f")],
        )
        .properties(height=height)
        .configure_axis(gridColor=GRID_COLOR, domainColor=GRID_COLOR, labelColor=INK_SECONDARY, titleColor=INK_SECONDARY)
        .configure_view(strokeWidth=0)
    )
    return chart


def _melt_by_date(df: pd.DataFrame, cols: list[str], names: list[str]) -> pd.DataFrame:
    flat = df[cols].reset_index()
    flat = flat.rename(columns={flat.columns[0]: "fecha"})
    long_df = flat.melt(id_vars="fecha", value_vars=cols, var_name="serie", value_name="valor")
    long_df["serie"] = long_df["serie"].map(dict(zip(cols, names)))
    return long_df


def grouped_bar_chart(df: pd.DataFrame, cols: list[str], names: list[str], colors: list[str], value_title: str, height: int = 240):
    long_df = _melt_by_date(df, cols, names)
    long_df = long_df.dropna(subset=["valor"])
    if long_df.empty:
        return None

    chart = (
        alt.Chart(long_df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("fecha:T", title=None),
            xOffset=alt.XOffset("serie:N", sort=names),
            y=alt.Y("valor:Q", title=value_title),
            color=alt.Color("serie:N", scale=alt.Scale(domain=names, range=colors), legend=alt.Legend(title=None, orient="top")),
            tooltip=[alt.Tooltip("fecha:T", title="Fecha"), alt.Tooltip("serie:N", title=""), alt.Tooltip("valor:Q", title=value_title, format=".0f")],
        )
        .properties(height=height)
        .configure_axis(gridColor=GRID_COLOR, domainColor=GRID_COLOR, labelColor=INK_SECONDARY, titleColor=INK_SECONDARY)
        .configure_view(strokeWidth=0)
    )
    return chart


def stacked_bar_chart(df: pd.DataFrame, cols: list[str], names: list[str], colors: list[str], value_title: str, height: int = 240):
    long_df = _melt_by_date(df, cols, names)
    long_df = long_df.dropna(subset=["valor"])
    if long_df.empty:
        return None

    chart = (
        alt.Chart(long_df)
        .mark_bar()
        .encode(
            x=alt.X("fecha:T", title=None),
            y=alt.Y("valor:Q", title=value_title, stack="zero"),
            order=alt.Order("serie:N", sort="descending"),
            color=alt.Color("serie:N", scale=alt.Scale(domain=names, range=colors), legend=alt.Legend(title=None, orient="top")),
            tooltip=[alt.Tooltip("fecha:T", title="Fecha"), alt.Tooltip("serie:N", title=""), alt.Tooltip("valor:Q", title=value_title, format=".0f")],
        )
        .properties(height=height)
        .configure_axis(gridColor=GRID_COLOR, domainColor=GRID_COLOR, labelColor=INK_SECONDARY, titleColor=INK_SECONDARY)
        .configure_view(strokeWidth=0)
    )
    return chart


def style_estado_table(df: pd.DataFrame):
    def _color(val):
        if isinstance(val, str) and "ALERTA" in val:
            return f"background-color: {STATUS_CRITICAL}1a; color: {STATUS_CRITICAL}; font-weight: 600"
        if isinstance(val, str) and "OK" in val:
            return f"background-color: {STATUS_GOOD}1a; color: {STATUS_GOOD}; font-weight: 600"
        return ""

    styler = df.style
    style_fn = styler.map if hasattr(styler, "map") else styler.applymap
    return style_fn(_color, subset=["Estado"])


# ---------------------------------------------------------------------------
# Carga de datos (cacheada)
# ---------------------------------------------------------------------------


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


@st.cache_data(ttl=3600)
def _load_calories_data():
    client = _client()
    end = date.today()
    start = end - timedelta(days=WELLNESS_DAYS)
    return gm.fetch_calories_series(client, start, end)


# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------

st.title("🏃 Tablero Maestro de Rendimiento")

header_col, button_col = st.columns([5, 1])
with header_col:
    st.caption(
        f"Carga y preparación de los últimos {LOOKBACK_DAYS} días · sueño, calorías y bienestar de los "
        f"últimos {WELLNESS_DAYS}. Los datos se guardan en caché por 1 hora."
    )
with button_col:
    if st.button("🔄 Actualizar datos", width="stretch"):
        st.cache_data.clear()

with st.spinner("Descargando y calculando métricas de Garmin Connect..."):
    data = _load_data()
    wellness = _load_wellness_data()
    calories_df = _load_calories_data()

client = _client()
activities = data["activities"]
load_series = data["load"]
rhr_series = data["rhr"]
hrv_series = data["hrv"]
sleep_df = wellness["sleep"]
hydration_df = wellness["hydration"]
readiness_series = wellness["readiness"]
battery_df = wellness["battery"]

week_ago = pd.Timestamp(date.today() - timedelta(days=7))
wellness_window_start = pd.Timestamp(date.today() - timedelta(days=WELLNESS_DAYS))
activities_last_week = [
    a for a in activities
    if a.get("startTimeLocal") and pd.Timestamp(a["startTimeLocal"][:10]) >= week_ago
]

# ---------------------------------------------------------------------------
# Cálculos compartidos (se usan en varias pestañas)
# ---------------------------------------------------------------------------

acwr_df = gm.compute_acwr(load_series)
hrv_df = gm.compute_hrv_zscore(hrv_series)
ultimo_acwr = acwr_df["acwr"].dropna().iloc[-1] if acwr_df["acwr"].notna().any() else None
ultimo_hrv_z = hrv_df["hrv_zscore"].dropna().iloc[-1] if hrv_df["hrv_zscore"].notna().any() else None

efficiency_df = gm.compute_efficiency_report(client, activities_last_week)
peor_deriva_val = efficiency_df["deriva_pct"].max() if not efficiency_df.empty else None

rhr_recent = rhr_series.dropna()
rhr_avg = rhr_recent.tail(7).mean() if not rhr_recent.empty else None
rhr_baseline = rhr_series.dropna().iloc[:-7].tail(60).mean() if rhr_series.dropna().shape[0] > 14 else None
rhr_today = rhr_series.dropna().iloc[-1] if not rhr_series.dropna().empty else None
max_hr = gm.estimate_max_hr(client, data["start"], data["end"])

recovery_df = gm.compute_recovery_report(client, activities_last_week)
peor_caida_min = recovery_df["caida_por_minuto"].min() if not recovery_df.empty else None

alerta_disrupcion = ultimo_acwr is not None and ultimo_hrv_z is not None and ultimo_acwr > 1.4 and ultimo_hrv_z < -1.5
alerta_eficiencia = peor_deriva_val is not None and peor_deriva_val > 5
alerta_vagal = (
    rhr_today is not None and rhr_baseline is not None and peor_caida_min is not None
    and rhr_today > rhr_baseline + 5 and peor_caida_min < 20
)
alertas_activas = sum([alerta_disrupcion, alerta_eficiencia, alerta_vagal])

# ---------------------------------------------------------------------------
# Pestañas
# ---------------------------------------------------------------------------

tab_resumen, tab_carga, tab_eficiencia, tab_bienestar, tab_calorias, tab_alertas = st.tabs(
    ["📋 Resumen", "⚖️ Carga y Preparación", "🎯 Eficiencia y Zonas", "😴 Sueño y Bienestar", "🔥 Calorías", "🚦 Alertas"]
)

# --- Resumen ---
with tab_resumen:
    st.subheader("¿Cómo vengo hoy?")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ACWR", f"{ultimo_acwr:.2f}" if ultimo_acwr is not None else "—", help="Carga aguda (7d) / crónica (28d). Zona segura: 0.8–1.3")
    c2.metric("HRV (Z-score)", f"{ultimo_hrv_z:.2f}" if ultimo_hrv_z is not None else "—", help="Qué tan lejos está tu HRV de tu línea base de 60 días")
    c3.metric(
        "FC en reposo hoy",
        f"{rhr_today:.0f}" if rhr_today is not None else "—",
        delta=f"{rhr_today - rhr_baseline:+.0f} vs. tu media" if rhr_today is not None and rhr_baseline is not None else None,
        delta_color="inverse",
    )
    c4.metric("Sueño (7d)", f"{sleep_df['hours'].dropna().tail(7).mean():.1f} h" if sleep_df["hours"].notna().any() else "—")
    c5.metric("Alertas activas", str(alertas_activas), delta=None)

    if alertas_activas:
        st.error(f"Hay {alertas_activas} indicador(es) en alerta esta semana — revisa la pestaña 🚦 Alertas.")
    else:
        st.success("Sin alertas activas esta semana. Todo dentro de rango.")

    st.caption(
        "Este resumen cruza los datos de Garmin Connect de los últimos días para dar una foto rápida "
        "antes de entrar al detalle de cada pestaña."
    )

# --- Carga y Preparación ---
with tab_carga:
    st.subheader("Carga vs. Preparación")
    st.caption(
        "ACWR: cuánto has entrenado esta semana comparado con tu promedio de las últimas 4 — muy alto y sin "
        "buena recuperación es la combinación que más se asocia a lesiones. HRV: qué tan lejos está tu "
        "variabilidad cardiaca nocturna de tu línea base."
    )
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**ACWR (carga aguda / crónica)**")
        chart = line_with_rule(acwr_df["acwr"], "ACWR", BLUE, rule_value=1.0)
        if chart is not None:
            st.altair_chart(chart, width="stretch")
        st.metric("Actual", f"{ultimo_acwr:.2f}" if ultimo_acwr is not None else "sin datos suficientes")
    with col2:
        st.markdown("**Z-score de HRV nocturna**")
        chart = line_with_rule(hrv_df["hrv_zscore"], "Z-score", AQUA, rule_value=0)
        if chart is not None:
            st.altair_chart(chart, width="stretch")
        else:
            st.info(
                "No hay datos de HRV nocturna suficientes o tu reloj no reporta esta métrica "
                "(HRV Status requiere modelos compatibles y varias semanas de datos)."
            )
        st.metric("Actual", f"{ultimo_hrv_z:.2f} SD" if ultimo_hrv_z is not None else "sin datos suficientes")

# --- Eficiencia y Zonas ---
with tab_eficiencia:
    st.subheader("Eficiencia cardiovascular")
    st.caption(
        "Deriva cardiaca: cuánto sube tu frecuencia cardiaca en la 2ª mitad de una sesión sostenida (>20 min) "
        "manteniendo el mismo ritmo — un número alto sugiere deshidratación, calor o que faltó base aeróbica."
    )
    if efficiency_df.empty:
        st.info("No hay actividades sostenidas (>20 min, con datos de ritmo y FC) en la última semana.")
    else:
        st.dataframe(
            efficiency_df[["fecha", "nombre", "deriva_pct", "hr_primera_mitad", "hr_segunda_mitad"]].rename(
                columns={
                    "fecha": "Fecha", "nombre": "Actividad",
                    "deriva_pct": "Deriva cardiaca (%)",
                    "hr_primera_mitad": "FC 1ª mitad", "hr_segunda_mitad": "FC 2ª mitad",
                }
            ),
            width="stretch", hide_index=True,
        )
        st.metric("Peor deriva de la semana", f"{peor_deriva_val:.1f}%")

    st.divider()
    st.subheader("Distribución de carga (regla 80/20)")
    st.caption(
        "Minutos por zona de frecuencia cardiaca real (sobre tu Reserva de FC) en la última semana. "
        "La meta orientativa del entrenamiento polarizado: ~80% en Z1-Z2 (suave), poco en Z3, el resto en Z4-Z5 (fuerte)."
    )
    if rhr_avg is None or max_hr is None:
        st.info("No hay suficiente FC en reposo o FC máxima observada para calcular zonas por Reserva de FC.")
    else:
        zone_seconds = gm.weekly_zone_distribution(client, activities_last_week, rhr_avg, max_hr)
        total = sum(zone_seconds.values())
        if total == 0:
            st.info("No hay datos de FC detallados en las actividades de la última semana.")
        else:
            labels = [f"Z{i}" for i in range(1, 6)]
            minutes = [zone_seconds[i] / 60 for i in range(1, 6)]
            st.altair_chart(ordinal_bar_chart(labels, minutes, "Minutos"), width="stretch")

            pct_bajo = (zone_seconds[1] + zone_seconds[2]) / total * 100
            pct_medio = zone_seconds[3] / total * 100
            pct_alto = (zone_seconds[4] + zone_seconds[5]) / total * 100
            m1, m2, m3 = st.columns(3)
            m1.metric("Z1+Z2 (base aeróbica)", f"{pct_bajo:.0f}%", help="Meta orientativa: ~80%")
            m2.metric("Z3 (zona intermedia)", f"{pct_medio:.0f}%")
            m3.metric("Z4+Z5 (alta intensidad)", f"{pct_alto:.0f}%")
            if pct_medio > 15:
                st.warning(
                    f"Zona 3 en {pct_medio:.0f}% del tiempo: por encima de lo recomendado por el modelo "
                    "polarizado 80/20. Riesgo de acumular fatiga sin la adaptación de la alta intensidad."
                )

# --- Sueño y Bienestar ---
with tab_bienestar:
    st.subheader("Resiliencia del sistema nervioso autónomo")
    st.caption("FC en reposo frente a qué tan rápido baja tu FC en los primeros 2 minutos después de esforzarte.")
    col3, col4 = st.columns(2)
    with col3:
        chart = line_with_rule(rhr_series, "FC en reposo (lpm)", VIOLET, rule_value=rhr_baseline, fmt=".0f")
        if chart is not None:
            st.altair_chart(chart, width="stretch")
        st.metric("Promedio últimos 7 días", f"{rhr_avg:.0f} lpm" if rhr_avg is not None else "sin datos")
    with col4:
        if recovery_df.empty:
            st.info("No se pudo calcular recuperación post-esfuerzo (requiere FC continua del día del entreno).")
        else:
            st.dataframe(
                recovery_df[["fecha", "actividad", "caida_2min", "caida_por_minuto"]].rename(
                    columns={"fecha": "Fecha", "actividad": "Actividad", "caida_2min": "Caída en 2min (lpm)", "caida_por_minuto": "Caída por minuto (lpm)"}
                ),
                width="stretch", hide_index=True,
            )

    st.divider()
    st.subheader("Sueño, hidratación y desgaste físico")
    st.caption(f"Últimos {WELLNESS_DAYS} días.")

    col5, col6 = st.columns(2)
    with col5:
        st.markdown("**Sueño**")
        if sleep_df["hours"].notna().any():
            chart = line_with_rule(sleep_df["hours"], "Horas", BLUE, rule_value=7)
            st.altair_chart(chart, width="stretch")
            st.metric("Promedio", f"{sleep_df['hours'].dropna().mean():.1f} h/noche")
            if sleep_df["score"].notna().any():
                st.metric("Sleep Score promedio", f"{sleep_df['score'].dropna().mean():.0f}/100")
        else:
            st.info("No hay datos de sueño en el periodo.")
    with col6:
        st.markdown("**Hidratación**")
        if hydration_df["value_l"].notna().any():
            chart = line_with_rule(hydration_df["value_l"], "Litros", AQUA, rule_value=2.0)
            st.altair_chart(chart, width="stretch")
            st.metric("Promedio", f"{hydration_df['value_l'].dropna().mean():.2f} L/día")
        else:
            st.info(
                "No hay registros de hidratación (solo cuenta si la registras a mano en la app; "
                "el reloj solo no mide cuánta agua tomas)."
            )

    col7, col8 = st.columns(2)
    with col7:
        st.markdown("**Desgaste físico (Body Battery)**")
        battery_valid = battery_df.dropna(how="all")
        if not battery_valid.empty:
            chart = grouped_bar_chart(battery_df, ["charged", "drained"], ["Recarga", "Gasto"], [BLUE, ORANGE], "Puntos")
            if chart is not None:
                st.altair_chart(chart, width="stretch")
            avg_charged = battery_df["charged"].dropna().mean()
            avg_drained = battery_df["drained"].dropna().mean()
            m1, m2 = st.columns(2)
            m1.metric("Recarga promedio/día", f"{avg_charged:.0f}" if pd.notna(avg_charged) else "N/D")
            m2.metric("Gasto promedio/día", f"{avg_drained:.0f}" if pd.notna(avg_drained) else "N/D")
        else:
            st.info("No hay datos de Body Battery en el periodo.")
    with col8:
        st.markdown("**Recuperación (Training Readiness)**")
        if readiness_series.notna().any():
            chart = line_with_rule(readiness_series, "Puntaje", VIOLET)
            st.altair_chart(chart, width="stretch")
            st.metric("Promedio", f"{readiness_series.dropna().mean():.0f}/100")
        else:
            st.info("Tu cuenta/reloj no reporta Training Readiness (requiere modelos más recientes).")

# --- Calorías ---
with tab_calorias:
    st.subheader("Calorías (reposo, actividad y total)")
    st.caption(f"Últimos {WELLNESS_DAYS} días.")

    if calories_df["total_kcal"].notna().any():
        chart = stacked_bar_chart(calories_df, ["resting_kcal", "active_kcal"], ["Reposo", "Actividad"], [BLUE, ORANGE], "kcal")
        if chart is not None:
            st.altair_chart(chart, width="stretch")

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

    activities_calorias = [
        a for a in activities
        if a.get("startTimeLocal")
        and pd.Timestamp(a["startTimeLocal"][:10]) >= wellness_window_start
        and a.get("calories")
    ]
    if activities_calorias:
        st.markdown("**Por actividad**")
        cal_activity_df = pd.DataFrame([
            {"Fecha": a.get("startTimeLocal", "")[:10], "Actividad": a.get("activityName"), "Calorías": a.get("calories")}
            for a in activities_calorias
        ]).sort_values("Fecha", ascending=False)
        st.dataframe(cal_activity_df, width="stretch", hide_index=True)
        st.metric(f"Total por actividades ({WELLNESS_DAYS}d)", f"{cal_activity_df['Calorías'].sum():.0f} kcal")
    else:
        st.info(f"No hay actividades con calorías registradas en los últimos {WELLNESS_DAYS} días.")

# --- Alertas ---
with tab_alertas:
    st.subheader("Indicadores unificados")
    st.caption("Cruces de métricas que se disparan solo cuando varias señales de riesgo coinciden a la vez.")

    filas = [
        {
            "Indicador": "Índice de Disrupción Fisiológica",
            "Métrica cruzada": f"ACWR={ultimo_acwr:.2f}" if ultimo_acwr is not None else "N/D",
            "Umbral crítico": "ACWR > 1.4 y HRV < -1.5 SD",
            "Estado": "🔴 ALERTA" if alerta_disrupcion else "🟢 OK",
            "Acción recomendada": "Sustituir sesión de impacto por recuperación activa o movilidad" if alerta_disrupcion else "-",
        },
        {
            "Indicador": "Pérdida de Eficiencia Aeróbica",
            "Métrica cruzada": f"Deriva={peor_deriva_val:.1f}%" if peor_deriva_val is not None else "N/D",
            "Umbral crítico": "Deriva cardiaca > 5% en mismo ritmo",
            "Estado": "🔴 ALERTA" if alerta_eficiencia else "🟢 OK",
            "Acción recomendada": "Ajustar hidratación/electrolitos o recortar volumen del bloque" if alerta_eficiencia else "-",
        },
        {
            "Indicador": "Estatus de Tono Vagal",
            "Métrica cruzada": f"RHR hoy={rhr_today:.0f}" if rhr_today is not None else "N/D",
            "Umbral crítico": "RHR +5 lpm sobre media y caída FC < 20 lpm/min",
            "Estado": "🔴 ALERTA" if alerta_vagal else "🟢 OK",
            "Acción recomendada": "Cancelar alta intensidad; priorizar descanso" if alerta_vagal else "-",
        },
    ]
    tabla = pd.DataFrame(filas)
    st.dataframe(style_estado_table(tabla), width="stretch", hide_index=True)

    st.caption(
        "El umbral del Estatus de Tono Vagal usa 'caída FC < 20 lpm/min' interpretado como una caída "
        "promedio menor a 20 lpm por minuto en los primeros 2 minutos post-esfuerzo."
    )
