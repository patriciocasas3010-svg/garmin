#!/usr/bin/env python3
"""Manda tu resumen (y el dashboard completo) a la hoja de Google de tu
nutriólogo, a partir de tu cuenta de Oura.

Se ejecuta automáticamente cada vez que abres iniciar_paciente_oura.command
/ iniciar_paciente_oura.bat -- no necesitas correrlo a mano.

Requiere haber corrido antes connect_oura.py (guarda tu Personal Access
Token localmente) y, además, los dos archivos que te da tu nutriólogo junto
con el resto de esta carpeta:
  - credenciales_hoja.json  (llave de acceso a la hoja, no es tu contraseña
    de nada -- solo puede escribir en esa hoja de cálculo específica)
  - hoja_id.txt             (el identificador de la hoja de tu nutriólogo)

Si no tienes estos archivos, o si algo falla, este paso simplemente se
omite -- tu dashboard local (dashboard_oura.py) sigue funcionando normal
de todas formas.
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

    import oura_metrics as om
    from oura_session import get_token

    token = get_token()
    if not token:
        print(
            "(No hay un token de Oura guardado todavía; se omite el envío al nutriólogo. "
            "Corre primero `python3 connect_oura.py`.)"
        )
        return

    nombre = _get_nombre()

    print("Descargando y calculando tu dashboard completo de Oura (puede tardar un poco)...")
    runtime_data = om.build_runtime_data(token)
    push_snapshot(nombre, runtime_data, fuente="Oura")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        detalle = str(e) or repr(e)
        print(f"(No se pudo enviar tu resumen al nutriólogo: [{type(e).__name__}] {detalle}")
        print("Tu dashboard local sigue funcionando normal de todas formas.)")
        import traceback
        traceback.print_exc()
