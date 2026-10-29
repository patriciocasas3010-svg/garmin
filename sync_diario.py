#!/usr/bin/env python3
"""Sincronización automática diaria de Garmin: jala el dashboard de cada
paciente que tenga un token guardado (ver token_store.py, se guarda
desde dashboard_pacientes.py) y lo manda a la hoja de Google -- sin que
el paciente tenga que abrir nada en su computadora.

Pensado para correr como GitHub Actions una vez al día (ver
.github/workflows/sync_diario.yml), no a mano -- pero se puede correr
localmente también, para probar, con estas dos variables de entorno
(los mismos datos que ya están en los Secrets de Streamlit Cloud):

    GOOGLE_CREDENTIALS_JSON  -- contenido completo de credenciales_hoja.json
    SHEET_ID                 -- el id de la hoja de Google

Si el token de un paciente ya venció o Garmin le pide iniciar sesión de
nuevo (pasa cada tantos meses, o si cambia su contraseña), se salta a
ese paciente -- se imprime el error y se sigue con los demás, un token
roto no debe tumbar la sincronización de todos los demás pacientes.

Multi-cuenta: además de la hoja SHEET_ID (la original), recorre la hoja
de cada profesional con suscripción vigente (pestaña "Cuentas" de
SHEET_ID, ver cuentas_store.py). Una cuenta que falle no detiene a las
demás.
"""

import json
import os

import gspread
from google.oauth2.service_account import Credentials

import garmin_metrics as gm
import cuentas_store
import token_store
from garmin_session import client_from_token
from push_resumen import write_snapshot_to_worksheet


def _gc() -> gspread.Client:
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)


def _sincronizar_hoja(gc: gspread.Client, sheet_id: str) -> tuple[list, list]:
    pacientes = token_store.listar_tokens(gc, sheet_id)
    if not pacientes:
        return [], []

    ws_principal = gc.open_by_key(sheet_id).sheet1

    exitosos, fallidos = [], []
    for p in pacientes:
        nombre, token = p["nombre"], p["token"]
        try:
            client = client_from_token(token)
            runtime_data = gm.build_runtime_data(client)
            write_snapshot_to_worksheet(ws_principal, nombre, runtime_data, fuente="Garmin")
            exitosos.append(nombre)
            print(f"  OK: {nombre}")
        except Exception as e:
            fallidos.append((nombre, f"[{type(e).__name__}] {e}"))
            print(f"  FALLÓ: {nombre} -- [{type(e).__name__}] {e}")
    return exitosos, fallidos


def main() -> None:
    control_sheet_id = os.environ["SHEET_ID"]
    gc = _gc()

    # La hoja original primero, luego la de cada cuenta vigente (sin repetir).
    hojas = [("Hoja principal", control_sheet_id)]
    for c in cuentas_store.cuentas_para_sincronizar(gc, control_sheet_id):
        if c["SheetId"] not in {h[1] for h in hojas}:
            hojas.append((c["Email"], c["SheetId"]))

    total_ok, total_fallidos = 0, []
    for etiqueta, sheet_id in hojas:
        print(f"\n== {etiqueta} ==")
        try:
            exitosos, fallidos = _sincronizar_hoja(gc, sheet_id)
        except Exception as e:
            print(f"  No se pudo abrir la hoja: [{type(e).__name__}] {e}")
            continue
        if not exitosos and not fallidos:
            print("  Ningún paciente con token de Garmin guardado.")
        total_ok += len(exitosos)
        total_fallidos += [(etiqueta, n, err) for n, err in fallidos]

    print(f"\nListo: {total_ok} sincronizados, {len(total_fallidos)} fallaron.")
    if total_fallidos:
        print(
            "\nEstos pacientes necesitan volver a correr export_token.py y mandar el token nuevo "
            "(el guardado ya venció o Garmin les pidió iniciar sesión de nuevo):"
        )
        for etiqueta, nombre, error in total_fallidos:
            print(f"  - [{etiqueta}] {nombre}: {error}")


if __name__ == "__main__":
    main()
