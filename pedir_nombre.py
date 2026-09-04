#!/usr/bin/env python3
"""Pide (y guarda) el nombre del paciente -- se corre PRIMERO, antes de
conectar Garmin/Oura o de buscar el .zip de Apple Health, para que quede
guardado aunque en ese momento el paciente todavía no tenga a la mano su
cuenta o su archivo de exportación.

Si el nombre ya está guardado (de una corrida anterior), no pregunta nada
-- ver push_resumen._get_nombre().
"""

from push_resumen import _get_nombre


def main():
    nombre = _get_nombre()
    print(f"Nombre guardado: {nombre}\n")


if __name__ == "__main__":
    main()
