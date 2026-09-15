"""Guarda el token de sesión de Garmin de cada paciente (el mismo que
genera export_token.py en su propia computadora, pensado originalmente
solo para publicar TU dashboard personal en Streamlit Cloud) en una
pestaña separada ("TokensGarmin") de la misma hoja de Google -- para que
sync_diario.py pueda jalar el dashboard de cada paciente todos los días
sin que abra nada, igual que enfoque_store.py/notas_store.py guardan sus
propios datos en su propia pestaña.

Ese token equivale a estar conectado a la cuenta de Garmin del paciente
(no es su contraseña, pero da acceso a los mismos datos) -- trátalo con
el mismo cuidado: nunca lo escribas en el chat de Claude ni lo subas a
ningún lado fuera de esta hoja de Google.

A diferencia del resto de los *_store.py, este módulo lo usan tanto
dashboard_pacientes.py (dentro de Streamlit) como sync_diario.py (un
script normal, sin Streamlit corriendo) -- por eso aquí no se usa
sheet_cache.abrir_hoja ni @st.cache_data, solo gspread directo.

También lo usa conectar_garmin_web.py -- la página web donde el propio
paciente pega su correo/contraseña de Garmin una sola vez (sin Python ni
terminal en su computadora) para activar la sincronización automática.
Ese flujo usa una "ClaveConexion" de un solo uso (generar_clave_conexion/
validar_clave_conexion/invalidar_clave_conexion) para que el link que le
mandas por WhatsApp no sirva para nada una vez usado, y para no tener que
exponer ahí la contraseña de tu hoja de Google ni un login compartido."""

import re
import secrets
from datetime import date

import gspread

HOJA_NOMBRE = "TokensGarmin"

ENCABEZADOS = ["Nombre", "Token", "FechaGuardado", "ClaveConexion"]

_DELIMITADOR_RE = re.compile(r"-{10,}\s*\n(.*?)\n\s*-{10,}", re.S)


def _extraer_token(texto_pegado: str) -> str:
    """export_token.py imprime el token entre dos líneas de guiones, con
    instrucciones arriba y abajo -- si el paciente copia "todo el bloque"
    tal cual le dice el mensaje, esto se queda solo con lo de en medio.
    Si en vez de eso pegó solo el token (sin los guiones), se usa tal
    cual, sin tocarlo."""
    m = _DELIMITADOR_RE.search(texto_pegado)
    return (m.group(1) if m else texto_pegado).strip()


def _worksheet(gc: gspread.Client, sheet_id: str):
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(HOJA_NOMBRE)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=HOJA_NOMBRE, rows=200, cols=len(ENCABEZADOS))
        ws.append_row(ENCABEZADOS)
        return ws
    if ws.row_values(1) != ENCABEZADOS:
        ultima_col = chr(ord("A") + len(ENCABEZADOS) - 1)
        ws.update(f"A1:{ultima_col}1", [ENCABEZADOS])
    return ws


def guardar_token(gc: gspread.Client, sheet_id: str, nombre: str, texto_pegado: str) -> None:
    ws = _worksheet(gc, sheet_id)
    token = _extraer_token(texto_pegado)
    fila = [nombre, token, date.today().strftime("%d.%m.%Y")]
    registros = ws.get_all_values()
    for i, row in enumerate(registros):
        if row and row[0] == nombre:
            ws.update(f"A{i + 1}:C{i + 1}", [fila])
            return
    ws.append_row(fila)


def leer_token(gc: gspread.Client, sheet_id: str, nombre: str) -> dict | None:
    """{"token": str, "fecha": str} de este paciente, o None si nunca
    guardó uno (o lo quitó con eliminar_token)."""
    ws = _worksheet(gc, sheet_id)
    for row in ws.get_all_values()[1:]:
        if row and row[0] == nombre and len(row) > 1 and row[1]:
            return {"token": row[1], "fecha": row[2] if len(row) > 2 else None}
    return None


def listar_tokens(gc: gspread.Client, sheet_id: str) -> list[dict]:
    """Todos los pacientes con token guardado -- lo usa sync_diario.py
    para saber a quién sincronizar cada día."""
    ws = _worksheet(gc, sheet_id)
    pacientes = []
    for row in ws.get_all_values()[1:]:
        if row and row[0] and len(row) > 1 and row[1]:
            pacientes.append({"nombre": row[0], "token": row[1], "fecha": row[2] if len(row) > 2 else None})
    return pacientes


def eliminar_token(gc: gspread.Client, sheet_id: str, nombre: str) -> None:
    """Apaga la sincronización automática de este paciente (no borra su
    fila, solo el token -- así no se corre el riesgo de que sync_diario.py
    intente usar un token viejo/inválido para alguien que ya no quiere
    esto activado)."""
    ws = _worksheet(gc, sheet_id)
    registros = ws.get_all_values()
    for i, row in enumerate(registros):
        if row and row[0] == nombre:
            ws.update(f"A{i + 1}:C{i + 1}", [[nombre, "", ""]])
            return


def generar_clave_conexion(gc: gspread.Client, sheet_id: str, nombre: str) -> str:
    """Genera una clave nueva de un solo uso para que este paciente se
    conecte solo desde conectar_garmin_web.py -- reemplaza al flujo de
    export_token.py (Python/terminal en su computadora) con un link que
    abre en cualquier navegador. Sobrescribe cualquier clave anterior sin
    usar (así un link viejo que mandaste por error deja de funcionar)."""
    ws = _worksheet(gc, sheet_id)
    clave = secrets.token_urlsafe(16)
    registros = ws.get_all_values()
    for i, row in enumerate(registros):
        if row and row[0] == nombre:
            actual = row + [""] * (len(ENCABEZADOS) - len(row))
            actual[3] = clave
            ws.update(f"A{i + 1}:D{i + 1}", [actual])
            return clave
    ws.append_row([nombre, "", "", clave])
    return clave


def validar_clave_conexion(gc: gspread.Client, sheet_id: str, nombre: str, clave: str) -> bool:
    """True solo si `clave` es exactamente la que se generó para `nombre`
    y todavía no se usó (ver invalidar_clave_conexion)."""
    if not clave:
        return False
    ws = _worksheet(gc, sheet_id)
    for row in ws.get_all_values()[1:]:
        if row and row[0] == nombre and len(row) > 3 and row[3] and row[3] == clave:
            return True
    return False


def invalidar_clave_conexion(gc: gspread.Client, sheet_id: str, nombre: str) -> None:
    """Se llama justo después de guardar el token con éxito -- para que
    el link de conexión no se pueda volver a usar (por ejemplo si se
    quedó visible en un chat de WhatsApp)."""
    ws = _worksheet(gc, sheet_id)
    registros = ws.get_all_values()
    for i, row in enumerate(registros):
        if row and row[0] == nombre:
            actual = row + [""] * (len(ENCABEZADOS) - len(row))
            actual[3] = ""
            ws.update(f"A{i + 1}:D{i + 1}", [actual])
            return
