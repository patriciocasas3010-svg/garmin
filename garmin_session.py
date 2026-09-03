"""Utilidad compartida para reutilizar la sesión de Garmin ya guardada.

Los scripts de reportes (garmin_reports.py) asumen que ya corriste
connect_garmin.py al menos una vez y que hay una sesión válida guardada.
"""

import os
import sys

from garth.exc import GarthHTTPError

from garminconnect import Garmin, GarminConnectAuthenticationError

TOKENSTORE = os.path.expanduser(os.getenv("GARMINTOKENS", "~/.garminconnect"))


def get_client() -> Garmin:
    """Devuelve un cliente Garmin ya autenticado, reutilizando la sesión guardada."""
    try:
        client = Garmin()
        client.login(TOKENSTORE)
        return client
    except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError):
        sys.exit(
            "No hay una sesión de Garmin guardada o ya expiró.\n"
            "Corre primero: python3 connect_garmin.py"
        )
