"""Cachea gc.open_by_key() para que abrir la misma hoja de Google varias
veces en la misma carga de página (una por cada pestaña -- InBody,
Antropometría, Notas, Enfoque, Calorías, Estudios, LibreVinculo, etc.) no
cuente como una llamada nueva a la API de Sheets cada vez. Google limita
cuántas lecturas por minuto se pueden hacer por usuario, y sin esto se
llega a ese límite muy rápido -- basta con que el nutriólogo le dé clic
a un par de botones seguidos para que la página truene con
"Quota exceeded ... Read requests per minute" (pasó en producción).

abrir_hoja() por sí solo NO es suficiente: gspread.Spreadsheet.worksheet()
vuelve a pedirle los metadatos a Google CADA VEZ que se llama, sin
importar si el objeto Spreadsheet ya estaba en caché -- y cada
*_store.py además hace un ws.row_values(1) para revisar el encabezado.
Eso son 2 llamadas más a la API por cada módulo, en cada rerun de
Streamlit (cada clic), que abrir_hoja() no evitaba. abrir_worksheet()
cachea el Worksheet YA resuelto (hoja abierta + pestaña encontrada +
encabezado verificado/reparado), no solo el Spreadsheet -- así un
módulo entero deja de pesarle a la cuota mientras el caché siga
vigente, sin importar cuántos pacientes tenga la hoja (los datos de
cada paciente se filtran en Python después de leer la hoja completa,
así que el número de pacientes no cambia cuántas llamadas a la API se
hacen -- lo que sí importa es cuántos clics/reruns pasan antes de que
el caché de 5 minutos expire)."""

import gspread
import streamlit as st


@st.cache_resource(ttl=300)
def abrir_hoja(_gc: gspread.Client, sheet_id: str):
    return _gc.open_by_key(sheet_id)


@st.cache_resource(ttl=300)
def abrir_worksheet(_gc: gspread.Client, sheet_id: str, hoja_nombre: str, encabezados: tuple, filas: int = 200):
    """El Worksheet de `hoja_nombre` dentro de la hoja `sheet_id`, ya con
    su encabezado verificado (y reparado si le faltan columnas nuevas) --
    usado por todos los *_store.py en vez de repetir cada uno su propia
    versión de este mismo código. `encabezados` tiene que ser una tupla
    (no lista) para que Streamlit pueda usarla como parte de la llave del
    caché."""
    sh = abrir_hoja(_gc, sheet_id)
    encabezados = list(encabezados)
    try:
        ws = sh.worksheet(hoja_nombre)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=hoja_nombre, rows=filas, cols=len(encabezados))
        ws.append_row(encabezados)
        return ws
    if ws.row_values(1) != encabezados:
        ultima_col = chr(ord("A") + len(encabezados) - 1)
        ws.update(f"A1:{ultima_col}1", [encabezados])
    return ws
