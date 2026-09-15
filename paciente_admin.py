"""Borrado en cascada de un paciente -- usado solo desde la sección de
Settings del dashboard central (rol admin). Recorre TODAS las pestañas
de la hoja de Google que puedan tener filas de este paciente (la
principal más cada *_store.py) y borra las que encuentre, para no dejar
historial huérfano de alguien que ya no es paciente."""

import gspread

import antropometria_store
import calorias_store
import enfoque_store
import estudios_store
import inbody_store
import notas_store
import token_store

_MODULOS = (
    enfoque_store, notas_store, inbody_store, antropometria_store, calorias_store, estudios_store, token_store,
)


def _borrar_filas_de(ws, nombre: str) -> int:
    """Borra todas las filas de `ws` cuya columna A sea `nombre` -- de
    abajo hacia arriba, para no invalidar los índices de las filas que
    todavía faltan por revisar. Regresa cuántas borró."""
    registros = ws.get_all_values()
    indices = [i + 1 for i, row in enumerate(registros) if row and row[0] == nombre]
    for idx in reversed(indices):
        ws.delete_rows(idx)
    return len(indices)


def eliminar_paciente(gc: gspread.Client, sheet_id: str, nombre: str) -> dict:
    """Borra al paciente de la hoja principal y de cada pestaña
    relacionada (Enfoque, Notas, InBody, Antropometria, Calorias,
    Estudios, TokensGarmin). Regresa {hoja: filas_borradas}, solo para
    mostrarlo como confirmación en Settings."""
    sh = gc.open_by_key(sheet_id)
    borradas = {"Principal (Garmin/Apple/Oura)": _borrar_filas_de(sh.sheet1, nombre)}
    for modulo in _MODULOS:
        ws = modulo._worksheet(gc, sheet_id)
        borradas[modulo.HOJA_NOMBRE] = _borrar_filas_de(ws, nombre)
    return borradas
