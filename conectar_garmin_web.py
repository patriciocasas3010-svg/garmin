#!/usr/bin/env python3
"""Página web donde el PACIENTE conecta su propio reloj Garmin -- sin
Python, sin terminal, sin carpetas en su computadora. Reemplaza al flujo
de connect_garmin.py/export_token.py (pensado para gente técnica) para
el caso normal: el paciente abre un link único que le manda su
nutrióloga desde el botón "Generar link de conexión" (ver Wearable en
dashboard_pacientes.py), escribe su correo y contraseña de Garmin
Connect UNA SOLA VEZ, y desde ahí su dashboard se sincroniza solo todos
los días -- exactamente el mismo mecanismo de fondo (token guardado en
la hoja de Google, leído por sync_diario.py) que ya existía, solo que
ahora se genera desde el navegador en vez de un script local.

Se publica como una app de Streamlit Cloud APARTE (mismo repositorio,
mismos Secrets GOOGLE_CREDENTIALS_JSON/SHEET_ID que dashboard_pacientes.py,
pero SIN el Secret APP_PASSWORD -- esta página es la única pensada para
que la abra directamente el paciente, protegida por la clave de un solo
uso en el link, no por una contraseña compartida).

Seguridad: el correo/contraseña del paciente NUNCA se guardan ni se
escriben en ningún lado (ni en la hoja de Google, ni en logs) -- viven
solo en memoria durante esta sesión de Streamlit, el tiempo que tarda en
completarse el login contra los servidores de Garmin. Lo único que se
guarda es el token de sesión resultante (client.garth.dumps()), igual
que ya hacía export_token.py."""

import json

import gspread
import streamlit as st
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
from google.oauth2.service_account import Credentials

import token_store
from theme import apply_theme, render_header

st.set_page_config(page_title="Conectar Garmin · AURA", page_icon=":material/watch:", layout="centered")
apply_theme()


@st.cache_resource
def _gc() -> gspread.Client:
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)


def _guardar_y_confirmar(client: Garmin, paciente: str) -> None:
    token = client.garth.dumps()
    token_store.guardar_token(_gc(), st.secrets["SHEET_ID"], paciente, token)
    token_store.invalidar_clave_conexion(_gc(), st.secrets["SHEET_ID"], paciente)
    st.session_state["mfa_pendiente"] = None
    st.success(
        ":material/check_circle: ¡Listo! Tu reloj Garmin ya quedó conectado. "
        "Ya puedes cerrar esta página -- tus datos se van a sincronizar solos todos los días, "
        "sin que tengas que volver a hacer nada."
    )
    st.balloons()
    st.stop()


params = st.query_params
paciente = params.get("p")
clave = params.get("k")

if not paciente or not clave:
    render_header("Conectar tu reloj Garmin")
    st.error(
        "Este link no está completo o no es válido -- pídele a tu nutrióloga que te mande uno "
        "nuevo desde la sección Wearable de tu perfil."
    )
    st.stop()

if not token_store.validar_clave_conexion(_gc(), st.secrets["SHEET_ID"], paciente, clave):
    render_header("Conectar tu reloj Garmin")
    st.error(
        "Este link ya no es válido -- ya se usó antes, o tu nutrióloga generó uno más nuevo. "
        "Pídele que te mande el link vigente."
    )
    st.stop()

render_header("Conectar tu reloj Garmin", subtitulo=paciente)
st.caption(
    "Escribe el correo y la contraseña con los que abres la app de Garmin Connect en tu "
    "teléfono -- es exactamente lo mismo que iniciar sesión ahí. Tu contraseña nunca se guarda "
    "en ningún lado, solo se usa aquí mismo, una sola vez, para activar la sincronización "
    "automática con tu nutrióloga."
)

if "mfa_pendiente" not in st.session_state:
    st.session_state["mfa_pendiente"] = None

if st.session_state["mfa_pendiente"] is None:
    with st.form("login_garmin"):
        email = st.text_input("Correo de tu cuenta Garmin Connect")
        password = st.text_input("Contraseña", type="password")
        enviar = st.form_submit_button(":material/watch: Conectar mi reloj", type="primary")

    if enviar:
        if not email.strip() or not password:
            st.error("Escribe tu correo y tu contraseña.")
        else:
            with st.spinner("Conectando con Garmin (puede tardar unos segundos)..."):
                try:
                    client = Garmin(email=email.strip(), password=password, return_on_mfa=True)
                    resultado1, resultado2 = client.login()
                    if resultado1 == "needs_mfa":
                        st.session_state["mfa_pendiente"] = {"client": client, "client_state": resultado2}
                        st.rerun()
                    else:
                        _guardar_y_confirmar(client, paciente)
                except GarminConnectAuthenticationError:
                    st.error("Correo o contraseña incorrectos -- revisa bien e intenta de nuevo.")
                except GarminConnectTooManyRequestsError:
                    st.error(
                        "Garmin bloqueó temporalmente los intentos de conexión desde aquí -- "
                        "espera unos 15-20 minutos e intenta de nuevo."
                    )
                except GarminConnectConnectionError as e:
                    st.error(f"No se pudo conectar con los servidores de Garmin: {e}")
                except Exception as e:
                    st.error(f"Algo salió mal y no se pudo completar la conexión: {e}")
else:
    st.info(
        ":material/sms: Garmin te mandó un código de verificación (a tu correo o por SMS) -- "
        "escríbelo aquí abajo para terminar."
    )
    with st.form("mfa_garmin"):
        codigo = st.text_input("Código de verificación")
        confirmar = st.form_submit_button(":material/check: Confirmar", type="primary")

    if confirmar:
        if not codigo.strip():
            st.error("Escribe el código que te mandó Garmin.")
        else:
            pendiente = st.session_state["mfa_pendiente"]
            with st.spinner("Confirmando..."):
                try:
                    pendiente["client"].resume_login(pendiente["client_state"], codigo.strip())
                    _guardar_y_confirmar(pendiente["client"], paciente)
                except Exception as e:
                    st.error(f"No se pudo confirmar el código: {e}. Revisa que sea el más reciente que te mandó Garmin.")

    if st.button("Cancelar y volver a intentar desde el inicio"):
        st.session_state["mfa_pendiente"] = None
        st.rerun()
