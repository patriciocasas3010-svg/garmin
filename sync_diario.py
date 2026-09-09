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
"""

import json
import os

import gspread
from garminconnect import Garmin
from google.oauth2.service_account import Credentials

import garmin_metrics as gm
import token_store
from push_resumen import write_snapshot_to_worksheet


def _gc() -> gspread.Client:
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)


def main() -> None:
    sheet_id = os.environ["SHEET_ID"]
    gc = _gc()

    pacientes = token_store.listar_tokens(gc, sheet_id)
    if not pacientes:
        print("Ningún paciente tiene un token de Garmin guardado todavía -- nada que sincronizar.")
        return

    ws_principal = gc.open_by_key(sheet_id).sheet1

    exitosos, fallidos = [], []
    for p in pacientes:
        nombre, token = p["nombre"], p["token"]
        try:
            client = Garmin()
            client.login(token)
            runtime_data = gm.build_runtime_data(client)
            write_snapshot_to_worksheet(ws_principal, nombre, runtime_data, fuente="Garmin")
            exitosos.append(nombre)
            print(f"OK: {nombre}")
        except Exception as e:
            fallidos.append((nombre, f"[{type(e).__name__}] {e}"))
            print(f"FALLÓ: {nombre} -- [{type(e).__name__}] {e}")

    print(f"\nListo: {len(exitosos)} sincronizados, {len(fallidos)} fallaron.")
    if fallidos:
        print(
            "\nEstos pacientes necesitan volver a correr export_token.py y mandarte el token nuevo "
            "(el guardado ya venció o Garmin les pidió iniciar sesión de nuevo):"
        )
        for nombre, error in fallidos:
            print(f"  - {nombre}: {error}")


if __name__ == "__main__":
    main()
