"""Cuentas de los profesionales que pagan AURA FLOW (nutriólogos, médicos,
coaches). Cada cuenta tiene SU propia hoja de Google con SUS pacientes --
nunca se mezclan los datos de un profesional con los de otro.

Las cuentas viven en la pestaña "Cuentas" de la hoja de control (la del
Secret SHEET_ID, la misma hoja original de AURA). Esa pestaña solo la
lee la app, nunca se le muestra a ningún cliente.

No usa Streamlit (ni st.cache_*) a propósito: también la usa
sync_diario.py desde GitHub Actions, donde no hay Streamlit corriendo.
"""

import hashlib
import hmac
import secrets
from datetime import date, datetime

import gspread

PESTANA = "Cuentas"

ENCABEZADOS = [
    "Email", "Nombre", "Consultorio", "PasswordHash", "SheetId", "Estado", "Plan",
    "StripeCustomer", "StripeSubscription", "PruebaHasta", "Creada", "UltimoAcceso",
    "AceptoTerminos",
]

# Estados posibles de una cuenta:
#   pendiente_pago -- se registró pero no terminó el pago en Stripe
#   prueba         -- periodo de prueba (en Stripe, o uno manual con PruebaHasta)
#   activa         -- pagando al corriente
#   pago_fallido   -- Stripe no pudo cobrar; sigue entrando mientras Stripe reintenta
#   cancelada      -- canceló o se le acabaron los reintentos de cobro
#   cortesia       -- acceso sin cobro (tú, socios, clientes que pagan por fuera)
#   suspendida     -- bloqueada a mano desde el panel de administración
ESTADOS = ["pendiente_pago", "prueba", "activa", "pago_fallido", "cancelada", "cortesia", "suspendida"]
ESTADOS_CON_ACCESO = {"prueba", "activa", "pago_fallido", "cortesia"}

ETIQUETA_ESTADO = {
    "pendiente_pago": "Pago pendiente",
    "prueba": "Periodo de prueba",
    "activa": "Activa",
    "pago_fallido": "Pago fallido",
    "cancelada": "Cancelada",
    "cortesia": "Cortesía",
    "suspendida": "Suspendida",
}


# ---------------------------------------------------------------------------
# Contraseñas
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def verificar_password(password: str, guardado: str) -> bool:
    try:
        esquema, salt_hex, hash_hex = guardado.split("$")
    except (ValueError, AttributeError):
        return False
    if esquema != "scrypt":
        return False
    h = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(h.hex(), hash_hex)


def normalizar_email(email: str) -> str:
    return (email or "").strip().lower()


# ---------------------------------------------------------------------------
# Hoja de cuentas
# ---------------------------------------------------------------------------

def _worksheet(gc: gspread.Client, control_sheet_id: str):
    sh = gc.open_by_key(control_sheet_id)
    try:
        ws = sh.worksheet(PESTANA)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=PESTANA, rows=200, cols=len(ENCABEZADOS))
        ws.append_row(ENCABEZADOS)
        return ws
    if ws.row_values(1) != ENCABEZADOS:
        ws.update(f"A1:{_col(len(ENCABEZADOS))}1", [ENCABEZADOS])
    return ws


def _col(n: int) -> str:
    """Número de columna (1-indexado) -> letra de Sheets (1 -> A, 27 -> AA)."""
    letras = ""
    while n:
        n, resto = divmod(n - 1, 26)
        letras = chr(ord("A") + resto) + letras
    return letras


def _a_dict(fila: dict) -> dict:
    return {k: ("" if fila.get(k) is None else str(fila.get(k))) for k in ENCABEZADOS}


def listar_cuentas(gc: gspread.Client, control_sheet_id: str) -> list[dict]:
    ws = _worksheet(gc, control_sheet_id)
    return [_a_dict(r) for r in ws.get_all_records(expected_headers=ENCABEZADOS) if r.get("Email")]


def leer_cuenta(gc: gspread.Client, control_sheet_id: str, email: str) -> dict | None:
    email = normalizar_email(email)
    for c in listar_cuentas(gc, control_sheet_id):
        if normalizar_email(c["Email"]) == email:
            return c
    return None


def crear_cuenta(
    gc: gspread.Client, control_sheet_id: str, *, email: str, nombre: str, consultorio: str,
    password: str, sheet_id: str = "", estado: str = "pendiente_pago", plan: str = "profesional",
) -> dict:
    email = normalizar_email(email)
    if leer_cuenta(gc, control_sheet_id, email):
        raise ValueError("Ya existe una cuenta con ese correo.")
    ahora = datetime.now().isoformat(timespec="seconds")
    cuenta = {
        "Email": email, "Nombre": nombre.strip(), "Consultorio": consultorio.strip(),
        "PasswordHash": hash_password(password), "SheetId": sheet_id, "Estado": estado,
        "Plan": plan, "StripeCustomer": "", "StripeSubscription": "", "PruebaHasta": "",
        "Creada": ahora, "UltimoAcceso": "", "AceptoTerminos": ahora,
    }
    _worksheet(gc, control_sheet_id).append_row([cuenta[k] for k in ENCABEZADOS])
    return cuenta


def actualizar_cuenta(gc: gspread.Client, control_sheet_id: str, email: str, **campos) -> dict:
    """Cambia solo los campos dados (ej. Estado="activa") de la cuenta con
    ese correo y regresa la cuenta ya actualizada."""
    desconocidos = set(campos) - set(ENCABEZADOS)
    if desconocidos:
        raise ValueError(f"Campos desconocidos: {sorted(desconocidos)}")
    email = normalizar_email(email)
    ws = _worksheet(gc, control_sheet_id)
    columna_email = ws.col_values(1)
    for i, valor in enumerate(columna_email):
        if i > 0 and normalizar_email(valor) == email:
            fila = i + 1
            actual = dict(zip(ENCABEZADOS, ws.row_values(fila) + [""] * len(ENCABEZADOS)))
            actual.update({k: str(v) for k, v in campos.items()})
            ws.update(f"A{fila}:{_col(len(ENCABEZADOS))}{fila}", [[actual[k] for k in ENCABEZADOS]])
            return actual
    raise ValueError(f"No existe la cuenta {email}.")


# ---------------------------------------------------------------------------
# Reglas de acceso
# ---------------------------------------------------------------------------

def tiene_acceso(cuenta: dict) -> bool:
    estado = cuenta.get("Estado", "")
    if estado not in ESTADOS_CON_ACCESO:
        return False
    # Prueba manual (sin Stripe): vence en PruebaHasta. Las pruebas de
    # Stripe las controla Stripe, que cambia el estado solo al terminar.
    if estado == "prueba" and not cuenta.get("StripeSubscription") and cuenta.get("PruebaHasta"):
        try:
            return date.fromisoformat(cuenta["PruebaHasta"][:10]) >= date.today()
        except ValueError:
            return True
    return True


def cuentas_para_sincronizar(gc: gspread.Client, control_sheet_id: str) -> list[dict]:
    """Cuentas con acceso vigente y hoja asignada -- las que el
    sincronizador diario debe recorrer."""
    try:
        cuentas = listar_cuentas(gc, control_sheet_id)
    except gspread.exceptions.APIError:
        return []
    return [c for c in cuentas if c.get("SheetId") and tiene_acceso(c)]


# ---------------------------------------------------------------------------
# Hoja de datos de cada cuenta
# ---------------------------------------------------------------------------

def crear_hoja_de_cuenta(gc: gspread.Client, nombre: str, folder_id: str | None = None) -> str:
    """Crea la hoja de Google donde vivirán los pacientes de esta cuenta y
    regresa su id. La crea la cuenta de servicio, dentro de la carpeta
    DRIVE_FOLDER_ID si está configurada (debe ser una carpeta de una
    Unidad compartida de Google Workspace: las cuentas de servicio nuevas
    ya no tienen espacio propio en Drive). Si falla, quien llama decide
    qué hacer (normalmente: dejar la cuenta sin hoja para que la asignes
    a mano desde el panel de administración)."""
    sh = gc.create(f"AURA FLOW · {nombre}", folder_id=folder_id or None)
    return sh.id
