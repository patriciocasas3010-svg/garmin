"""Guarda los reportes de problema/sugerencia que manden las nutriólogas
mientras usan el dashboard -- en una pestaña separada ("Feedback") de la
misma hoja de Google, igual que notas_store.py. Pensado para el piloto
de 250 pacientes: cualquier fricción real se captura ahí mismo, sin
salir de la app ni depender de un formulario externo."""

from datetime import datetime

import gspread

HOJA_NOMBRE = "Feedback"

ENCABEZADOS = ["Fecha", "Usuario", "Paciente", "Mensaje"]


def _worksheet(gc: gspread.Client, sheet_id: str):
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(HOJA_NOMBRE)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=HOJA_NOMBRE, rows=500, cols=len(ENCABEZADOS))
        ws.append_row(ENCABEZADOS)
        return ws
    if ws.row_values(1) != ENCABEZADOS:
        ultima_col = chr(ord("A") + len(ENCABEZADOS) - 1)
        ws.update(f"A1:{ultima_col}1", [ENCABEZADOS])
    return ws


def guardar(gc: gspread.Client, sheet_id: str, usuario: str, paciente: str, mensaje: str) -> None:
    ws = _worksheet(gc, sheet_id)
    ws.append_row([datetime.now().strftime("%d.%m.%Y %H:%M"), usuario, paciente or "", mensaje])
