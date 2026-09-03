#!/usr/bin/env python3
"""Manda tu resumen (y el dashboard completo) a la hoja de Google de tu
nutriólogo, a partir del export de la app Salud del iPhone.

Se ejecuta automáticamente cada vez que abres iniciar_paciente_apple.command
/ iniciar_paciente_apple.bat -- no necesitas correrlo a mano.

Requiere que hayas puesto tu archivo de exportación de Salud (el .zip que
genera el iPhone: Ajustes -> Salud -> foto de perfil -> "Exportar todos los
datos de salud") en esta misma carpeta, tal cual como se descarga.

También requiere dos archivos que te da tu nutriólogo junto con el resto de
esta carpeta:
  - credenciales_hoja.json  (llave de acceso a la hoja, no es tu contraseña
    de nada -- solo puede escribir en esa hoja de cálculo específica)
  - hoja_id.txt             (el identificador de la hoja de tu nutriólogo)

Si no tienes estos archivos, o si algo falla, este paso simplemente se
omite -- tu dashboard local (dashboard_apple.py) le explica qué hacer si
sigue faltando el archivo de exportación.
"""

from push_resumen import _get_nombre, push_snapshot, sheet_config_disponible


def main():
    if not sheet_config_disponible():
        print("(No se encontró configuración para enviar tu resumen al nutriólogo; se omite este paso.)")
        return

    try:
        import gspread  # noqa: F401
        from google.oauth2.service_account import Credentials  # noqa: F401
    except ImportError:
        print("(Faltan librerías para enviar tu resumen al nutriólogo; se omite este paso.)")
        return

    import apple_health as ah

    export_zip = ah.find_export_zip()
    if not export_zip:
        print(
            "(No encontré tu archivo de exportación de Salud en esta carpeta; se omite el envío "
            "al nutriólogo. Sigue las instrucciones que te va a mostrar el dashboard.)"
        )
        return

    nombre = _get_nombre()

    print(f"Leyendo tu archivo de Salud ({export_zip})... puede tardar un poco si tienes mucho historial.")
    runtime_data = ah.build_runtime_data(export_zip)
    push_snapshot(nombre, runtime_data, fuente="Apple Health")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        detalle = str(e) or repr(e)
        print(f"(No se pudo enviar tu resumen al nutriólogo: [{type(e).__name__}] {detalle}")
        print("Tu dashboard local sigue funcionando normal de todas formas.)")
        import traceback
        traceback.print_exc()
