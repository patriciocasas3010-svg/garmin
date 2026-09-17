#!/usr/bin/env python3
"""Sincronización automática diaria de Garmin: jala el dashboard de cada
paciente que tenga un token guardado (ver token_store.py, se guarda
desde dashboard_pacientes.py) y lo manda a la base de datos -- sin que
el paciente tenga que abrir nada en su computadora.

Pensado para correr como GitHub Actions una vez al día (ver
.github/workflows/sync_diario.yml), no a mano -- pero se puede correr
localmente también, para probar, con esta variable de entorno (el mismo
dato que ya está en los Secrets de Streamlit Cloud):

    DATABASE_URL  -- postgresql://usuario:clave@host:puerto/basededatos

Si el token de un paciente ya venció o Garmin le pide iniciar sesión de
nuevo (pasa cada tantos meses, o si cambia su contraseña), se salta a
ese paciente -- se imprime el error y se sigue con los demás, un token
roto no debe tumbar la sincronización de todos los demás pacientes.
"""

import os

import db
import garmin_metrics as gm
import resumen_store
import token_store
from garmin_session import client_from_token


def main() -> None:
    engine = db.crear_engine(os.environ["DATABASE_URL"])

    pacientes = token_store.listar_tokens(engine)
    if not pacientes:
        print("Ningún paciente tiene un token de Garmin guardado todavía -- nada que sincronizar.")
        return

    exitosos, fallidos = [], []
    for p in pacientes:
        nombre, token = p["nombre"], p["token"]
        try:
            client = client_from_token(token)
            runtime_data = gm.build_runtime_data(client)
            resumen_store.guardar_snapshot(engine, nombre, runtime_data, fuente="Garmin")
            exitosos.append(nombre)
            print(f"OK: {nombre}")
        except Exception as e:
            fallidos.append((nombre, f"[{type(e).__name__}] {e}"))
            print(f"FALLÓ: {nombre} -- [{type(e).__name__}] {e}")

    print(f"\nListo: {len(exitosos)} sincronizados, {len(fallidos)} fallaron.")
    if fallidos:
        print(
            "\nEstos pacientes necesitan volver a conectar su Garmin (el token guardado ya venció o "
            "Garmin les pidió iniciar sesión de nuevo) -- mándales un link de conexión nuevo desde el dashboard:"
        )
        for nombre, error in fallidos:
            print(f"  - {nombre}: {error}")


if __name__ == "__main__":
    main()
