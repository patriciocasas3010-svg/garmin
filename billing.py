"""Cobro de suscripciones de AURA FLOW con Stripe.

No usa webhooks a propósito: Streamlit no puede recibir llamadas de
Stripe. En su lugar:
  1. Al registrarse, el profesional va a Stripe Checkout (página de pago
     hospedada por Stripe, con la prueba gratis incluida).
  2. Stripe lo regresa a la app con ?checkout=<id de sesión>; la app
     consulta esa sesión y guarda el cliente y la suscripción en su cuenta.
  3. Cada vez que el profesional entra (y luego cada hora mientras usa la
     app), se le pregunta a Stripe el estado de su suscripción -- así un
     pago fallido o una cancelación se reflejan solos, sin webhooks.
  4. Para cambiar tarjeta, ver facturas o cancelar, se le abre el Portal
     de cliente de Stripe (también hospedado por Stripe).

Secrets que usa (Streamlit Cloud -> Settings -> Secrets):
    STRIPE_SECRET_KEY  -- sk_live_... (o sk_test_... para probar)
    STRIPE_PRICE_ID    -- price_... del plan mensual
    APP_URL            -- link público de la app (a donde regresa Stripe)
    TRIAL_DAYS         -- días de prueba gratis (opcional, default 14)
"""

import stripe

# Estado de la suscripción en Stripe -> Estado de la cuenta (cuentas_store.ESTADOS)
_ESTADO_DESDE_STRIPE = {
    "trialing": "prueba",
    "active": "activa",
    "past_due": "pago_fallido",
    "unpaid": "cancelada",
    "canceled": "cancelada",
    "incomplete": "pendiente_pago",
    "incomplete_expired": "cancelada",
    "paused": "cancelada",
}


def _cliente(api_key: str) -> stripe.StripeClient:
    return stripe.StripeClient(api_key)


def crear_checkout(
    api_key: str, *, price_id: str, email: str, app_url: str, trial_days: int = 14,
    customer_id: str = "",
) -> str:
    """Crea la sesión de pago y regresa la URL de Stripe a la que hay que
    mandar al profesional."""
    params = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{app_url.rstrip('/')}/?checkout={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{app_url.rstrip('/')}/?checkout=cancelado",
        "client_reference_id": email,
        "metadata": {"cuenta": email},
        "allow_promotion_codes": True,
        "locale": "es",
        "subscription_data": {"metadata": {"cuenta": email}},
    }
    if trial_days > 0:
        params["subscription_data"]["trial_period_days"] = trial_days
    if customer_id:
        params["customer"] = customer_id
    else:
        params["customer_email"] = email
    sesion = _cliente(api_key).v1.checkout.sessions.create(params=params)
    return sesion.url


def confirmar_checkout(api_key: str, session_id: str) -> dict:
    """Lee la sesión de pago a la que Stripe regresó al profesional.
    Regresa {email, customer, subscription, estado} -- estado ya traducido
    a un Estado de cuenta."""
    s = _cliente(api_key).v1.checkout.sessions.retrieve(session_id)
    if s.status != "complete":
        raise ValueError("El pago todavía no está completo.")
    resultado = {
        "email": s.client_reference_id or (s.metadata or {}).get("cuenta", ""),
        "customer": s.customer if isinstance(s.customer, str) else getattr(s.customer, "id", ""),
        "subscription": s.subscription if isinstance(s.subscription, str) else getattr(s.subscription, "id", ""),
    }
    resultado["estado"] = estado_suscripcion(api_key, resultado["subscription"]) if resultado["subscription"] else "activa"
    return resultado


def estado_suscripcion(api_key: str, subscription_id: str) -> str:
    sub = _cliente(api_key).v1.subscriptions.retrieve(subscription_id)
    return _ESTADO_DESDE_STRIPE.get(sub.status, "cancelada")


def crear_portal(api_key: str, customer_id: str, return_url: str) -> str:
    """Link al Portal de cliente de Stripe (cambiar tarjeta, facturas,
    cancelar). Requiere activar el portal una vez en el dashboard de
    Stripe: Settings -> Billing -> Customer portal."""
    p = _cliente(api_key).v1.billing_portal.sessions.create(
        params={"customer": customer_id, "return_url": return_url}
    )
    return p.url
