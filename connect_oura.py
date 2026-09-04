#!/usr/bin/env python3
"""Guarda el Personal Access Token de Oura para este equipo.

Uso:
    python3 connect_oura.py

A diferencia de Garmin (correo + contraseña), Oura usa un "Personal Access
Token" que el propio usuario genera una sola vez desde su cuenta de Oura y
pega aquí -- no hay contraseña ni código MFA que pedir. El token se queda
guardado localmente (fuera del repositorio, en el archivo que indica
oura_session.TOKEN_PATH) para que las próximas ejecuciones no lo vuelvan a
pedir. Nunca se debe escribir el token en el chat de Claude ni en ningún
archivo del repositorio.
"""

import getpass
import sys

import requests

from oura_session import TOKEN_PATH, get_token, save_token

_PERSONAL_INFO_URL = "https://api.ouraring.com/v2/usercollection/personal_info"


def _token_valido(token: str) -> bool:
    try:
        resp = requests.get(
            _PERSONAL_INFO_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def main():
    token_actual = get_token()
    if token_actual and _token_valido(token_actual):
        print("Ya hay un token de Oura guardado y sigue funcionando, no hace falta pedirlo de nuevo.\n")
        return

    print("Necesitas tu Personal Access Token de Oura:")
    print("  1. Entra a https://cloud.ouraring.com/personal-access-tokens (inicia sesión con tu cuenta de Oura).")
    print("  2. Dale a 'Create New Personal Access Token', ponle cualquier nombre y confírmalo.")
    print("  3. Copia el token que te muestra (solo se alcanza a ver esa vez).\n")

    token = getpass.getpass("Pega aquí tu Personal Access Token (no se mostrará en pantalla): ").strip()
    if not token:
        sys.exit("No se recibió ningún token.")

    if not _token_valido(token):
        sys.exit(
            "Ese token no funcionó (Oura lo rechazó). Revisa que lo hayas copiado completo y sin "
            "espacios, y que no lo hayas revocado ya en cloud.ouraring.com/personal-access-tokens."
        )

    save_token(token)
    print(f"\nToken guardado en '{TOKEN_PATH}' para futuras ejecuciones.\n")


if __name__ == "__main__":
    main()
