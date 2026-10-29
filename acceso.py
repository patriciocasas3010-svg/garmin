"""Inicio de sesión, registro y cobro de AURA FLOW (pantallas de Streamlit).

dashboard_pacientes.py llama a requerir_cuenta() al principio: si nadie
ha iniciado sesión, o la cuenta no tiene la suscripción al corriente,
esta función dibuja la pantalla que toque (entrar / crear cuenta / pagar)
y detiene la página. Si todo está bien, regresa la cuenta del
profesional -- y con ella el id de SU hoja de Google, que es lo único que
el resto del dashboard usa para leer y escribir pacientes.

Secrets (además de los de billing.py):
    ADMIN_EMAILS  -- correos con acceso al panel de administración, ej.
                     ["tu@correo.com"]. Al registrarse, estas cuentas
                     quedan en "cortesía" (sin cobro) y usan la hoja
                     original (SHEET_ID) con los pacientes que ya tenías.
    DRIVE_FOLDER_ID -- (opcional) carpeta de una Unidad compartida donde
                     se crea la hoja de cada cuenta nueva.
    LANDING_URL   -- (opcional) link de la página de venta, para los
                     links a Términos y Aviso de privacidad.
"""

import time
from datetime import date, datetime, timedelta

import streamlit as st

import billing
import cuentas_store
from theme import render_header

_REVERIFICAR_CADA_S = 3600
_MAX_INTENTOS = 5


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

def _secret(nombre: str, default=None):
    try:
        return st.secrets.get(nombre, default)
    except Exception:
        return default


def admin_emails() -> set[str]:
    valor = _secret("ADMIN_EMAILS", []) or []
    if isinstance(valor, str):
        valor = valor.split(",")
    return {cuentas_store.normalizar_email(e) for e in valor if e.strip()}


def es_admin(cuenta: dict | None) -> bool:
    return bool(cuenta) and cuentas_store.normalizar_email(cuenta.get("Email")) in admin_emails()


def stripe_configurado() -> bool:
    return bool(_secret("STRIPE_SECRET_KEY") and _secret("STRIPE_PRICE_ID") and _secret("APP_URL"))


def _trial_days() -> int:
    try:
        return int(_secret("TRIAL_DAYS", 14))
    except (TypeError, ValueError):
        return 14


def _landing(pagina: str = "") -> str:
    base = (_secret("LANDING_URL") or "").rstrip("/")
    return f"{base}/{pagina}" if base else ""


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def requerir_cuenta(gc, control_sheet_id: str) -> dict:
    _procesar_regreso_de_stripe(gc, control_sheet_id)

    email = st.session_state.get("cuenta_email")
    if not email:
        _pantalla_entrar(gc, control_sheet_id)
        st.stop()

    cuenta = _cuenta_vigente(gc, control_sheet_id, email)
    if cuenta is None:
        cerrar_sesion()
        st.rerun()

    if not cuentas_store.tiene_acceso(cuenta):
        _pantalla_pago(cuenta)
        st.stop()

    if not cuenta.get("SheetId"):
        if es_admin(cuenta):
            cuenta = {**cuenta, "SheetId": control_sheet_id}
        else:
            render_header("Preparando tu espacio")
            st.info(
                "Tu cuenta ya está activa. Estamos terminando de preparar el espacio donde vivirán "
                "tus pacientes -- te escribiremos en cuanto esté listo (normalmente el mismo día)."
            )
            if st.button("Cerrar sesión"):
                cerrar_sesion()
                st.rerun()
            st.stop()

    if cuenta.get("Estado") == "pago_fallido":
        st.warning(
            "No pudimos cobrar tu última mensualidad. Actualiza tu tarjeta desde el menú lateral "
            "(\"Administrar suscripción\") para no perder el acceso."
        )
    return cuenta


def cerrar_sesion() -> None:
    for k in ("cuenta_email", "_cuenta", "_cuenta_verificada", "paciente_actual", "_ver_como"):
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# Estado de la cuenta (con re-verificación periódica contra Stripe)
# ---------------------------------------------------------------------------

def _cuenta_vigente(gc, control_sheet_id: str, email: str) -> dict | None:
    cuenta = st.session_state.get("_cuenta")
    verificada = st.session_state.get("_cuenta_verificada", 0)
    if cuenta and time.time() - verificada < _REVERIFICAR_CADA_S:
        return cuenta

    cuenta = cuentas_store.leer_cuenta(gc, control_sheet_id, email)
    if cuenta is None:
        return None

    sub = cuenta.get("StripeSubscription")
    if sub and stripe_configurado() and cuenta.get("Estado") not in ("cortesia", "suspendida"):
        try:
            estado = billing.estado_suscripcion(_secret("STRIPE_SECRET_KEY"), sub)
            if estado != cuenta.get("Estado"):
                cuenta = cuentas_store.actualizar_cuenta(gc, control_sheet_id, email, Estado=estado)
        except Exception:
            # Si Stripe no responde, se respeta el último estado guardado
            # en vez de dejar fuera al profesional.
            pass

    st.session_state["_cuenta"] = cuenta
    st.session_state["_cuenta_verificada"] = time.time()
    return cuenta


def _procesar_regreso_de_stripe(gc, control_sheet_id: str) -> None:
    checkout = st.query_params.get("checkout")
    if not checkout:
        return
    st.query_params.clear()
    if checkout == "cancelado":
        st.session_state["_aviso"] = ("info", "No se completó el pago. Puedes intentarlo de nuevo cuando quieras.")
        return
    if not stripe_configurado():
        return
    try:
        r = billing.confirmar_checkout(_secret("STRIPE_SECRET_KEY"), checkout)
        cuentas_store.actualizar_cuenta(
            gc, control_sheet_id, r["email"],
            StripeCustomer=r["customer"], StripeSubscription=r["subscription"], Estado=r["estado"],
        )
        # Volver de Stripe abre una sesión nueva de Streamlit: se pide
        # iniciar sesión otra vez en vez de dar acceso solo por el link.
        st.session_state.pop("_cuenta", None)
        st.session_state["_aviso"] = ("success", "¡Listo! Tu suscripción quedó activa. Inicia sesión para entrar.")
    except Exception as e:
        st.session_state["_aviso"] = ("error", f"No pudimos confirmar el pago: {e}. Escríbenos y lo revisamos.")


# ---------------------------------------------------------------------------
# Pantallas
# ---------------------------------------------------------------------------

def _mostrar_aviso() -> None:
    aviso = st.session_state.pop("_aviso", None)
    if aviso:
        getattr(st, aviso[0])(aviso[1])


def _pantalla_entrar(gc, control_sheet_id: str) -> None:
    render_header("Bienvenido", subtitulo="Plataforma para profesionales de la salud")
    _mostrar_aviso()
    pestana_entrar, pestana_registro = st.tabs(["Iniciar sesión", "Crear cuenta"])
    with pestana_entrar:
        _form_entrar(gc, control_sheet_id)
    with pestana_registro:
        _form_registro(gc, control_sheet_id)


def _form_entrar(gc, control_sheet_id: str) -> None:
    intentos = st.session_state.get("_intentos", 0)
    bloqueado_hasta = st.session_state.get("_bloqueado_hasta", 0)
    with st.form("entrar"):
        email = st.text_input("Correo")
        password = st.text_input("Contraseña", type="password")
        enviar = st.form_submit_button("Entrar", type="primary")
    if not enviar:
        return
    if time.time() < bloqueado_hasta:
        st.error("Demasiados intentos. Espera un minuto y vuelve a intentar.")
        return
    cuenta = cuentas_store.leer_cuenta(gc, control_sheet_id, email)
    if not cuenta or not cuentas_store.verificar_password(password, cuenta.get("PasswordHash", "")):
        intentos += 1
        st.session_state["_intentos"] = intentos
        if intentos >= _MAX_INTENTOS:
            st.session_state["_bloqueado_hasta"] = time.time() + 60
            st.session_state["_intentos"] = 0
        time.sleep(1)
        st.error("Correo o contraseña incorrectos.")
        return
    st.session_state["_intentos"] = 0
    st.session_state["cuenta_email"] = cuentas_store.normalizar_email(email)
    st.session_state.pop("_cuenta", None)
    try:
        cuentas_store.actualizar_cuenta(
            gc, control_sheet_id, email, UltimoAcceso=datetime.now().isoformat(timespec="seconds")
        )
    except Exception:
        pass
    st.rerun()


def _form_registro(gc, control_sheet_id: str) -> None:
    if stripe_configurado():
        st.caption(
            f"Prueba gratis de {_trial_days()} días. Te pediremos una tarjeta en la página segura de "
            "Stripe; no se te cobra nada hasta que termine la prueba y puedes cancelar cuando quieras."
        )
    with st.form("registro"):
        nombre = st.text_input("Tu nombre completo")
        consultorio = st.text_input("Consultorio / clínica (opcional)")
        email = st.text_input("Correo")
        password = st.text_input("Contraseña (mínimo 8 caracteres)", type="password")
        password2 = st.text_input("Repite la contraseña", type="password")
        terminos, privacidad = _landing("terminos.html"), _landing("privacidad.html")
        texto_legal = (
            f"Acepto los [Términos y condiciones]({terminos}) y el [Aviso de privacidad]({privacidad})"
            if terminos else "Acepto los Términos y condiciones y el Aviso de privacidad"
        )
        acepto = st.checkbox(texto_legal)
        enviar = st.form_submit_button("Crear cuenta", type="primary")
    if not enviar:
        return

    email = cuentas_store.normalizar_email(email)
    errores = []
    if not nombre.strip():
        errores.append("Escribe tu nombre.")
    if "@" not in email or "." not in email.split("@")[-1]:
        errores.append("Escribe un correo válido.")
    if len(password) < 8:
        errores.append("La contraseña debe tener al menos 8 caracteres.")
    if password != password2:
        errores.append("Las contraseñas no coinciden.")
    if not acepto:
        errores.append("Debes aceptar los términos y el aviso de privacidad.")
    if errores:
        for e in errores:
            st.error(e)
        return
    if cuentas_store.leer_cuenta(gc, control_sheet_id, email):
        st.error("Ya existe una cuenta con ese correo. Inicia sesión.")
        return

    es_fundador = email in admin_emails()
    with st.spinner("Creando tu cuenta..."):
        if es_fundador:
            sheet_id, estado = control_sheet_id, "cortesia"
        else:
            try:
                sheet_id = cuentas_store.crear_hoja_de_cuenta(
                    gc, consultorio.strip() or nombre.strip(), _secret("DRIVE_FOLDER_ID")
                )
            except Exception:
                sheet_id = ""  # se asigna a mano desde el panel de administración
            estado = "pendiente_pago" if stripe_configurado() else "prueba"
        cuentas_store.crear_cuenta(
            gc, control_sheet_id, email=email, nombre=nombre, consultorio=consultorio,
            password=password, sheet_id=sheet_id, estado=estado,
        )
        if estado == "prueba":
            cuentas_store.actualizar_cuenta(
                gc, control_sheet_id, email, PruebaHasta=(date.today() + timedelta(days=_trial_days())).isoformat()
            )
    st.session_state["cuenta_email"] = email
    st.session_state.pop("_cuenta", None)
    st.rerun()


def _pantalla_pago(cuenta: dict) -> None:
    render_header(cuenta.get("Nombre") or "Tu cuenta", subtitulo=cuenta.get("Consultorio", ""))
    _mostrar_aviso()
    estado = cuenta.get("Estado")
    if estado == "suspendida":
        st.error("Esta cuenta está suspendida. Escríbenos para revisarlo.")
    elif not stripe_configurado():
        st.info(
            "Tu periodo de prueba terminó. Escríbenos para activar tu suscripción y seguir usando AURA FLOW "
            "-- tus pacientes y sus datos siguen guardados."
            if estado == "prueba" else
            "Tu cuenta está pendiente de activación. Te escribiremos en cuanto quede lista."
        )
    else:
        if estado == "pendiente_pago":
            st.subheader("Último paso: activa tu prueba gratis")
            st.write(
                f"{_trial_days()} días gratis. Después, se cobra mensualmente a tu tarjeta. Puedes cancelar "
                "en cualquier momento desde tu cuenta."
            )
        else:
            st.subheader("Reactiva tu suscripción")
            st.write("Tus pacientes y sus datos siguen guardados. En cuanto se reactive tu suscripción vuelves a verlos.")
        try:
            url = billing.crear_checkout(
                _secret("STRIPE_SECRET_KEY"), price_id=_secret("STRIPE_PRICE_ID"), email=cuenta["Email"],
                app_url=_secret("APP_URL"),
                trial_days=_trial_days() if estado == "pendiente_pago" and not cuenta.get("StripeCustomer") else 0,
                customer_id=cuenta.get("StripeCustomer", ""),
            )
            st.link_button("Ir a la página de pago segura (Stripe)", url, type="primary")
        except Exception as e:
            st.error(f"No se pudo abrir la página de pago: {e}")
    if st.button("Cerrar sesión"):
        cerrar_sesion()
        st.rerun()


def render_menu_cuenta(cuenta: dict, gc, control_sheet_id: str) -> None:
    """Menú lateral: quién está dentro, estado de su plan, administrar
    la suscripción y cerrar sesión."""
    with st.sidebar:
        st.markdown(f"**{cuenta.get('Nombre', '')}**")
        if cuenta.get("Consultorio"):
            st.caption(cuenta["Consultorio"])
        etiqueta = cuentas_store.ETIQUETA_ESTADO.get(cuenta.get("Estado"), cuenta.get("Estado", ""))
        if cuenta.get("Estado") == "prueba" and cuenta.get("PruebaHasta") and not cuenta.get("StripeSubscription"):
            etiqueta += f" · hasta {cuenta['PruebaHasta']}"
        st.caption(f"Plan: {etiqueta}")
        if cuenta.get("StripeCustomer") and stripe_configurado():
            if st.button("💳 Administrar suscripción", width="stretch"):
                try:
                    url = billing.crear_portal(
                        _secret("STRIPE_SECRET_KEY"), cuenta["StripeCustomer"], _secret("APP_URL")
                    )
                    st.link_button("Abrir portal de Stripe", url, width="stretch")
                except Exception as e:
                    st.error(f"No se pudo abrir el portal: {e}")
        with st.expander("Cambiar contraseña"):
            with st.form("cambiar_password", clear_on_submit=True):
                actual = st.text_input("Contraseña actual", type="password")
                nueva = st.text_input("Nueva (mínimo 8 caracteres)", type="password")
                nueva2 = st.text_input("Repite la nueva", type="password")
                if st.form_submit_button("Guardar"):
                    guardada = cuentas_store.leer_cuenta(gc, control_sheet_id, cuenta["Email"]) or {}
                    if not cuentas_store.verificar_password(actual, guardada.get("PasswordHash", "")):
                        st.error("La contraseña actual no es correcta.")
                    elif len(nueva) < 8 or nueva != nueva2:
                        st.error("La nueva debe tener 8+ caracteres y coincidir en ambos campos.")
                    else:
                        cuentas_store.actualizar_cuenta(
                            gc, control_sheet_id, cuenta["Email"], PasswordHash=cuentas_store.hash_password(nueva)
                        )
                        st.success("Contraseña actualizada.")
        if st.button("🚪 Cerrar sesión", width="stretch"):
            cerrar_sesion()
            st.rerun()
