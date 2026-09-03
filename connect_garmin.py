#!/usr/bin/env python3
"""Conecta un reloj/cuenta Garmin a este equipo usando python-garminconnect.

Uso:
    python3 connect_garmin.py

El script pide el correo, la contraseña (oculta) y, si Garmin lo requiere,
el código de verificación en dos pasos (MFA) directamente en esta terminal.
Nunca se deben escribir las credenciales en el chat de Claude ni en ningún
archivo del repositorio.

Tras iniciar sesión con éxito, los tokens OAuth se guardan de forma local
(fuera del repositorio, en el directorio indicado por GARMINTOKENS) para que
las próximas ejecuciones no vuelvan a pedir la contraseña.
"""

import getpass
import os
import sys

from garth.exc import GarthHTTPError

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from garmin_session import TOKENSTORE


def ask_credentials():
    email = input("Correo de tu cuenta Garmin Connect: ").strip()
    password = getpass.getpass("Contraseña (no se mostrará en pantalla): ")
    return email, password


def ask_mfa_code():
    return input("Código de verificación en dos pasos (MFA) recibido por Garmin: ").strip()


def connect():
    # 1. Intentar reutilizar una sesión guardada previamente.
    try:
        print(f"Buscando una sesión guardada en '{TOKENSTORE}'...")
        client = Garmin()
        client.login(TOKENSTORE)
        print("Sesión previa encontrada y válida, no hace falta volver a iniciar sesión.\n")
        return client
    except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError):
        print("No hay una sesión guardada válida, se pedirá iniciar sesión.\n")

    # 2. Pedir credenciales por terminal (nunca por chat) e iniciar sesión.
    email, password = ask_credentials()
    try:
        client = Garmin(email=email, password=password, prompt_mfa=ask_mfa_code)
        client.login()
    except GarminConnectAuthenticationError:
        sys.exit("Credenciales incorrectas o inicio de sesión rechazado por Garmin.")
    except GarminConnectTooManyRequestsError:
        sys.exit("Garmin ha bloqueado temporalmente los intentos de inicio de sesión. Intenta más tarde.")
    except GarminConnectConnectionError as err:
        sys.exit(f"No se pudo conectar con los servidores de Garmin: {err}")

    os.makedirs(os.path.dirname(TOKENSTORE) or ".", exist_ok=True)
    client.garth.dump(TOKENSTORE)
    print(f"\nInicio de sesión correcto. Tokens guardados en '{TOKENSTORE}' para futuras ejecuciones.\n")
    return client


def show_summary(client: Garmin):
    devices = client.get_devices()

    print("Cuenta Garmin conectada:")
    print(f"  Usuario: {client.get_full_name()}")

    if not devices:
        print("  No se encontró ningún reloj/dispositivo vinculado a esta cuenta.")
        return

    print("  Dispositivos vinculados:")
    for device in devices:
        model = device.get("productDisplayName") or device.get("deviceTypePk")
        serial = device.get("serialNumber", "desconocido")
        print(f"    - {model} (número de serie: {serial})")


def main():
    client = connect()
    show_summary(client)


if __name__ == "__main__":
    main()
