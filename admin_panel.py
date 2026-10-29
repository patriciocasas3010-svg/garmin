"""Panel de administración de AURA FLOW -- solo lo ven los correos de
ADMIN_EMAILS. Sirve para dar soporte a las cuentas de los profesionales
sin abrir la hoja de Google a mano: ver quién está registrado y en qué
estado, activar cuentas que pagan por fuera de Stripe, dar más días de
prueba, asignar la hoja de una cuenta y restablecer contraseñas.

No permite ver los pacientes de otra cuenta, a propósito: esos datos de
salud son del profesional, no de AURA (ver el Aviso de privacidad)."""

import secrets
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import cuentas_store
from theme import render_header


def render_panel_admin(gc, control_sheet_id: str) -> None:
    render_header("Administración", subtitulo="Cuentas de profesionales")
    try:
        cuentas = cuentas_store.listar_cuentas(gc, control_sheet_id)
    except Exception as e:
        st.error(f"No se pudo leer la pestaña de cuentas: {e}")
        return

    if not cuentas:
        st.info("Todavía no hay cuentas registradas.")
        return

    conteo = pd.Series([c["Estado"] for c in cuentas]).value_counts()
    cols = st.columns(5)
    cols[0].metric("Cuentas", len(cuentas))
    cols[1].metric("Activas", int(conteo.get("activa", 0)))
    cols[2].metric("En prueba", int(conteo.get("prueba", 0)))
    cols[3].metric("Pago fallido", int(conteo.get("pago_fallido", 0)))
    cols[4].metric("Sin hoja asignada", sum(1 for c in cuentas if not c["SheetId"]))

    tabla = pd.DataFrame(cuentas)[
        ["Email", "Nombre", "Consultorio", "Estado", "PruebaHasta", "Creada", "UltimoAcceso", "SheetId"]
    ]
    tabla["Estado"] = tabla["Estado"].map(lambda e: cuentas_store.ETIQUETA_ESTADO.get(e, e))
    tabla["SheetId"] = tabla["SheetId"].map(lambda s: "✅" if s else "⚠️ falta")
    st.dataframe(tabla, hide_index=True, width="stretch")

    st.divider()
    st.subheader("Editar una cuenta")
    email = st.selectbox("Cuenta", [c["Email"] for c in cuentas], index=None, placeholder="Elige un correo...")
    if not email:
        return
    cuenta = next(c for c in cuentas if c["Email"] == email)

    with st.form(f"editar_{email}"):
        estado = st.selectbox(
            "Estado", cuentas_store.ESTADOS,
            index=cuentas_store.ESTADOS.index(cuenta["Estado"]) if cuenta["Estado"] in cuentas_store.ESTADOS else 0,
            format_func=lambda e: cuentas_store.ETIQUETA_ESTADO.get(e, e),
            help="Si la cuenta paga con Stripe, Stripe vuelve a poner su estado real la próxima vez que entre. "
                 "Usa \"Cortesía\" para quien paga por fuera (transferencia) o no paga.",
        )
        sheet_id = st.text_input(
            "Id de la hoja de Google de esta cuenta", value=cuenta["SheetId"],
            help="Si la app no pudo crear la hoja sola: crea una hoja en blanco, compártela como Editor con el "
                 "correo de la cuenta de servicio y pega aquí su id (lo que va entre /d/ y /edit en la URL).",
        )
        prueba_hasta = st.text_input(
            "Prueba manual hasta (AAAA-MM-DD)", value=cuenta["PruebaHasta"],
            placeholder=(date.today() + timedelta(days=14)).isoformat(),
            help="Solo aplica a pruebas sin Stripe (Estado = Periodo de prueba y sin suscripción de Stripe).",
        )
        guardar = st.form_submit_button("Guardar cambios", type="primary")
    if guardar:
        cuentas_store.actualizar_cuenta(
            gc, control_sheet_id, email, Estado=estado, SheetId=sheet_id.strip(), PruebaHasta=prueba_hasta.strip()
        )
        st.success("Cuenta actualizada.")
        st.rerun()

    with st.expander("Restablecer contraseña"):
        st.caption(
            "Genera una contraseña temporal. Mándasela al profesional por un canal privado y pídele que la "
            "cambie al entrar (menú lateral → \"Cambiar contraseña\")."
        )
        if st.button("Generar contraseña temporal", key=f"reset_{email}"):
            temporal = secrets.token_urlsafe(9)
            cuentas_store.actualizar_cuenta(
                gc, control_sheet_id, email, PasswordHash=cuentas_store.hash_password(temporal)
            )
            st.code(temporal, language=None)
            st.caption("Cópiala ahora: no se vuelve a mostrar.")

    if cuenta.get("StripeCustomer"):
        st.caption(
            f"Cliente en Stripe: `{cuenta['StripeCustomer']}` · Suscripción: `{cuenta.get('StripeSubscription') or '—'}` "
            "-- búscalo en dashboard.stripe.com para ver pagos, reembolsos o cancelar."
        )
