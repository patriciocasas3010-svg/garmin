#!/usr/bin/env python3
"""Página web donde el PACIENTE conecta su propio anillo Oura -- mismo
patrón que conectar_garmin_web.py (un link único que le manda su
nutrióloga desde la sección Wearable de dashboard_pacientes.py), pero con
OAuth2 en vez de correo/contraseña: desde diciembre de 2025 Oura ya no
permite Personal Access Tokens, la única forma de conectar es mandar al
paciente a autorizar la app directamente en cloud.ouraring.com.

Esta misma página cumple dos roles, según qué traiga la URL:

1. El link que manda la nutrióloga trae "?p=<paciente>&k=<clave>" -- se
   valida la clave (igual que Garmin) y se muestra un botón que lleva al
   paciente a autorizar en cloud.ouraring.com.
2. Oura redirige de regreso a esta misma URL (así quedó registrada en
   cloud.ouraring.com/oauth/applications como Redirect URI) agregando
   "?code=...&state=<clave>" -- aquí se usa ese "state" (la misma clave)
   para saber de qué paciente se trata, se cambia el "code" por el par
   access_token/refresh_token, y se guarda.

Se publica como una app de Streamlit Cloud/Render APARTE (mismo
Secret DATABASE_URL que dashboard_pacientes.py, sin APP_PASSWORD, más los
Secrets propios OURA_CLIENT_ID/OURA_CLIENT_SECRET) -- la URL pública de
esta app es, a la vez, el valor del Secret CONECTAR_OURA_URL y el
"Redirect URI" registrado en la app de Oura. Si cambia una, hay que
actualizar la otra."""

from urllib.parse import urlencode

import streamlit as st

import db
import oura_store
from theme import apply_theme, render_header

st.set_page_config(page_title="Conectar Oura · AURA", page_icon=":material/radio_button_checked:", layout="centered")
apply_theme()

AUTHORIZE_URL = "https://cloud.ouraring.com/oauth/authorize"
SCOPE = "personal daily heartrate workout"


def _engine():
    return db.engine()


def _secrets_ok() -> tuple[str, str, str] | None:
    client_id = st.secrets.get("OURA_CLIENT_ID")
    client_secret = st.secrets.get("OURA_CLIENT_SECRET")
    conectar_url = st.secrets.get("CONECTAR_OURA_URL")
    if not client_id or not client_secret or not conectar_url:
        st.error(
            "Faltan Secrets por configurar (OURA_CLIENT_ID, OURA_CLIENT_SECRET, CONECTAR_OURA_URL) "
            "-- sin ellos esta página no puede completar la conexión."
        )
        return None
    return client_id, client_secret, conectar_url


params = st.query_params
codigo = params.get("code")
state = params.get("state")
paciente = params.get("p")
clave = params.get("k")

render_header("Conectar tu anillo Oura", subtitulo=paciente or "")

# --- Paso 2: Oura ya redirigió de vuelta con el código -------------------
if codigo:
    secretos = _secrets_ok()
    if secretos is None:
        st.stop()
    client_id, client_secret, conectar_url = secretos

    paciente_encontrado = oura_store.paciente_por_clave(_engine(), state)
    if not paciente_encontrado:
        st.error(
            "Este link ya no es válido -- ya se usó antes, o tu nutrióloga generó uno más nuevo. "
            "Pídele que te mande el link vigente."
        )
        st.stop()

    with st.spinner("Terminando de conectar tu anillo Oura..."):
        try:
            body = oura_store.intercambiar_codigo(client_id, client_secret, conectar_url, codigo)
            oura_store.guardar_tokens(
                _engine(), paciente_encontrado, body["access_token"], body["refresh_token"], body["expires_in"],
            )
            oura_store.invalidar_clave_conexion(_engine(), paciente_encontrado)
            st.success(
                ":material/check_circle: ¡Listo! Tu anillo Oura ya quedó conectado. "
                "Ya puedes cerrar esta página -- tus datos se van a sincronizar solos, "
                "sin que tengas que volver a hacer nada."
            )
            st.balloons()
        except Exception as e:
            st.error(f"No se pudo terminar la conexión con Oura: {e}. Pídele a tu nutrióloga un link nuevo.")
    st.stop()

# --- Paso 1: link inicial que mandó la nutrióloga -------------------------
if not paciente or not clave:
    st.error(
        "Este link no está completo o no es válido -- pídele a tu nutrióloga que te mande uno "
        "nuevo desde la sección Wearable de tu perfil."
    )
    st.stop()

if not oura_store.validar_clave_conexion(_engine(), paciente, clave):
    st.error(
        "Este link ya no es válido -- ya se usó antes, o tu nutrióloga generó uno más nuevo. "
        "Pídele que te mande el link vigente."
    )
    st.stop()

secretos = _secrets_ok()
if secretos is None:
    st.stop()
client_id, _client_secret, conectar_url = secretos

st.caption(
    "Vas a salir a la página de Oura para autorizar la conexión con tu cuenta -- inicia sesión "
    "igual que en la app de Oura y dale \"Authorize\". Nunca compartes tu contraseña con nosotros, "
    "solo con Oura directamente."
)

url_autorizacion = (
    f"{AUTHORIZE_URL}?{urlencode({'response_type': 'code', 'client_id': client_id, 'redirect_uri': conectar_url, 'scope': SCOPE, 'state': clave})}"
)
st.link_button(":material/radio_button_checked: Conectar con Oura", url_autorizacion, type="primary")
