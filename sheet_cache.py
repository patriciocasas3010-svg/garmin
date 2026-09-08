"""Cachea gc.open_by_key() para que abrir la misma hoja de Google varias
veces en la misma carga de página (una por cada pestaña -- InBody,
Antropometría, Notas, Enfoque, Calorías, Estudios, LibreVinculo, etc.) no
cuente como una llamada nueva a la API de Sheets cada vez. Google limita
cuántas lecturas por minuto se pueden hacer por usuario, y sin esto se
llega a ese límite muy rápido -- basta con que el nutriólogo le dé clic
a un par de botones seguidos para que la página truene con
"Quota exceeded ... Read requests per minute" (pasó en producción)."""

import gspread
import streamlit as st


@st.cache_resource(ttl=300)
def abrir_hoja(_gc: gspread.Client, sheet_id: str):
    return _gc.open_by_key(sheet_id)
