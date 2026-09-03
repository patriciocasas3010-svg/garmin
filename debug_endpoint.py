#!/usr/bin/env python3
"""Herramienta de diagnóstico: imprime la respuesta cruda de un endpoint de Garmin.

Útil si alguna métrica del dashboard se ve rara o revienta: permite ver
exactamente qué estructura está devolviendo Garmin Connect para tu cuenta.

Uso:
    python3 debug_endpoint.py rhr 2026-06-01 2026-09-01
    python3 debug_endpoint.py hrv 2026-09-01
    python3 debug_endpoint.py heartrates 2026-09-01
    python3 debug_endpoint.py activities 2026-08-01 2026-09-01
    python3 debug_endpoint.py activity_details 123456789
"""

import json
import sys

from garmin_session import get_client

client = get_client()


def rhr(start, end):
    return client.connectapi(
        f"{client.garmin_connect_rhr_url}/{client.display_name}",
        params={"fromDate": start, "untilDate": end, "metricId": 60},
    )


COMANDOS = {
    "rhr": lambda args: rhr(args[0], args[1]),
    "hrv": lambda args: client.get_hrv_data(args[0]),
    "heartrates": lambda args: client.get_heart_rates(args[0]),
    "activities": lambda args: client.get_activities_by_date(args[0], args[1]),
    "activity_details": lambda args: client.get_activity_details(args[0]),
    "sleep": lambda args: client.get_sleep_data(args[0]),
    "userprofile_settings": lambda args: client.get_userprofile_settings(),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMANDOS:
        sys.exit(f"Uso: python3 debug_endpoint.py <{'|'.join(COMANDOS)}> [args...]")

    nombre = sys.argv[1]
    args = sys.argv[2:]
    resultado = COMANDOS[nombre](args)
    print(json.dumps(resultado, indent=2, ensure_ascii=False)[:8000])


if __name__ == "__main__":
    main()
