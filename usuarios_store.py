"""Usuarios que pueden entrar al dashboard central (tú y las demás
nutriólogas que agregues desde Settings) -- guardados en una pestaña
separada ("Usuarios") de la misma hoja de Google, igual que
enfoque_store.py/notas_store.py.

Reemplaza la contraseña única compartida (APP_PASSWORD) por un login de
usuario/contraseña por persona, con un rol ("admin" o "nutriologo") que
decide si puede entrar a Settings (borrar pacientes/tokens, crear más
usuarios) y si ve a TODOS los pacientes o solo a los que tiene
asignados (ver enfoque_store.OPCIONES_ROL_NUTRIOLOGO / el campo
"nutriologo" del perfil).

La contraseña nunca se guarda en texto plano -- se guarda un hash
(PBKDF2 con una sal distinta por usuario), no reversible.

"admin" + el Secret APP_PASSWORD sigue funcionando siempre como acceso
de emergencia (ver dashboard_pacientes.py) -- así nunca te puedes
quedar fuera aunque esta pestaña esté vacía o algo salga mal aquí."""

import hashlib
import secrets
from datetime import date

import gspread

HOJA_NOMBRE = "Usuarios"

ENCABEZADOS = ["Usuario", "Nombre", "PasswordHash", "Salt", "Rol", "Fecha"]

ROLES = ["nutriologo", "admin"]

_ITERACIONES_HASH = 200_000


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


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERACIONES_HASH).hex()


def crear_usuario(
    gc: gspread.Client, sheet_id: str, usuario: str, nombre: str, password: str, rol: str = "nutriologo",
) -> None:
    """Crea o actualiza (si `usuario` ya existía, por ejemplo para
    cambiarle la contraseña o el rol) la cuenta de un nutriólogo."""
    ws = _worksheet(gc, sheet_id)
    salt = secrets.token_hex(16)
    fila = [usuario, nombre, _hash_password(password, salt), salt, rol, date.today().strftime("%d.%m.%Y")]
    registros = ws.get_all_values()
    for i, row in enumerate(registros):
        if row and row[0] == usuario:
            ws.update(f"A{i + 1}:F{i + 1}", [fila])
            return
    ws.append_row(fila)


def verificar_login(gc: gspread.Client, sheet_id: str, usuario: str, password: str) -> dict | None:
    """{"usuario", "nombre", "rol"} si el usuario existe y la contraseña
    es correcta -- None si no."""
    if not usuario or not password:
        return None
    ws = _worksheet(gc, sheet_id)
    for row in ws.get_all_values()[1:]:
        if row and row[0] == usuario:
            actual = row + [""] * (len(ENCABEZADOS) - len(row))
            hash_guardado, salt = actual[2], actual[3]
            if salt and hash_guardado and _hash_password(password, salt) == hash_guardado:
                return {"usuario": usuario, "nombre": actual[1] or usuario, "rol": actual[4] or "nutriologo"}
            return None
    return None


def listar_usuarios(gc: gspread.Client, sheet_id: str) -> list[dict]:
    """Todos los usuarios ({"usuario", "nombre", "rol"}) -- para el
    listado en Settings y para el desplegable de "a quién se le asigna
    este paciente" al crear/editar uno."""
    ws = _worksheet(gc, sheet_id)
    usuarios = []
    for row in ws.get_all_values()[1:]:
        if row and row[0]:
            actual = row + [""] * (len(ENCABEZADOS) - len(row))
            usuarios.append({"usuario": actual[0], "nombre": actual[1] or actual[0], "rol": actual[4] or "nutriologo"})
    return usuarios
