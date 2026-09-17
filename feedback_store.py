"""Guarda los reportes de problema/sugerencia que manden las nutriólogas
mientras usan el dashboard -- en una pestaña separada ("Feedback") de la
misma hoja de Google, igual que notas_store.py. Pensado para el piloto
de 250 pacientes: cualquier fricción real se captura ahí mismo, sin
salir de la app ni depender de un formulario externo."""

from datetime import datetime

import gspread

import sheet_cache

HOJA_NOMBRE = "Feedback"

ENCABEZADOS = ["Fecha", "Usuario", "Paciente", "Mensaje"]


def _worksheet(gc: gspread.Client, sheet_id: str):
    return sheet_cache.abrir_worksheet(gc, sheet_id, HOJA_NOMBRE, tuple(ENCABEZADOS), filas=500)


def guardar(gc: gspread.Client, sheet_id: str, usuario: str, paciente: str, mensaje: str) -> None:
    ws = _worksheet(gc, sheet_id)
    ws.append_row([datetime.now().strftime("%d.%m.%Y %H:%M"), usuario, paciente or "", mensaje])
