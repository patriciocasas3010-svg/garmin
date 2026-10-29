# Lanzar AURA FLOW y empezar a vender

Guía paso a paso para pasar de "mi herramienta" a "producto que otros
profesionales pagan". Lo técnico ya está en el código; aquí van los pasos
que tienes que hacer tú en cada servicio (en orden).

```
Página de venta (GitHub Pages)  ──"Empieza tu prueba"──►  App (Streamlit)
                                                            │
                                    crear cuenta ◄──────────┤
                                    pago con prueba (Stripe)│
                                    entra a SU tablero ◄────┘
                                    (su propia hoja de Google)
```

## Qué cambió en la app

- **Cuentas por profesional.** `dashboard_pacientes.py` ya no usa una sola
  contraseña compartida: cada profesional crea su cuenta con correo y
  contraseña, y ve **solo** los pacientes de su propia hoja de Google.
- **Cobro con Stripe.** Al registrarse, el profesional pasa por la página
  de pago de Stripe con 14 días gratis. La app revisa el estado de su
  suscripción en cada inicio de sesión (y cada hora): si deja de pagar,
  ve una pantalla para reactivar; sus datos no se borran.
- **Tú eres administrador.** Con tu correo en `ADMIN_EMAILS`, te registras
  sin pagar ("cortesía") y sigues viendo tus pacientes de siempre (la
  hoja original). En el menú lateral tienes el **Panel de administración**.
- **Sincronización diaria** de Garmin para todas las cuentas vigentes.

Archivos nuevos: `acceso.py` (pantallas de entrar/registro/pago),
`billing.py` (Stripe), `cuentas_store.py` (cuentas en la pestaña
"Cuentas" de tu hoja), `admin_panel.py`, `landing/` (página de venta y
textos legales).

## Paso 1 — Stripe

1. Crea tu cuenta en https://dashboard.stripe.com y completa la
   activación (datos fiscales, cuenta bancaria). Mientras no la actives
   puedes probar todo en **modo de prueba**.
2. **Products → Add product**: "AURA FLOW Profesional", precio
   recurrente mensual en **MXN** (el borrador de la página dice $990;
   cámbialo donde quieras, pero que coincida en `landing/index.html`).
   Copia el **Price ID** (`price_...`).
3. **Settings → Billing → Customer portal**: actívalo y permite cancelar
   y actualizar tarjeta. Esto es lo que abre el botón "Administrar
   suscripción".
4. **Developers → API keys**: copia la **Secret key** (`sk_test_...`
   para probar, `sk_live_...` para cobrar de verdad).
5. Opcional: **Settings → Customer emails** para que Stripe mande
   recibos y avisos de pago fallido solo.

## Paso 2 — Google (hojas de cada cuenta)

La app crea una hoja de Google nueva para cada profesional que se
registra. Las cuentas de servicio de Google nuevas ya no tienen espacio
propio en Drive, así que hay dos caminos:

- **Recomendado (Google Workspace):** crea una **Unidad compartida**,
  agrega como "Administrador de contenido" el correo de la cuenta de
  servicio (`client_email` de `credenciales_hoja.json`), crea una carpeta
  dentro y copia su id (lo que va después de `/folders/` en la URL) al
  Secret `DRIVE_FOLDER_ID`.
- **Sin Workspace:** si la app no puede crear la hoja, la cuenta queda
  "Sin hoja asignada" en el panel de administración. Crea tú una hoja en
  blanco, compártela como Editor con el correo de la cuenta de servicio y
  pega su id en el panel. El profesional ve "Preparando tu espacio" hasta
  entonces.

## Paso 3 — Secrets de Streamlit Cloud

En tu app de Streamlit → **Settings → Secrets**, además de los que ya
tienes (`SHEET_ID`, `GOOGLE_CREDENTIALS_JSON`, `ANTHROPIC_API_KEY`, ...):

```toml
ADMIN_EMAILS = ["tu@correo.com"]
APP_URL = "https://tu-app.streamlit.app"
STRIPE_SECRET_KEY = "sk_test_..."
STRIPE_PRICE_ID = "price_..."
TRIAL_DAYS = 14
DRIVE_FOLDER_ID = "..."                                   # opcional, ver paso 2
LANDING_URL = "https://<tu-usuario>.github.io/garmin"     # para los links legales
```

Ya no se usa `APP_PASSWORD` en este dashboard.

**Sin Stripe todavía:** si no pones `STRIPE_SECRET_KEY`, la app da una
prueba de `TRIAL_DAYS` días sin tarjeta; al vencer, la cuenta queda
bloqueada hasta que la actives tú en el panel (útil para cobrar por
transferencia los primeros clientes).

## Paso 4 — Primer ingreso (tú)

1. Abre la app → **Crear cuenta** con el correo que pusiste en
   `ADMIN_EMAILS`. Quedas en "Cortesía", con tus pacientes de siempre.
2. Haz una prueba completa como cliente con otro correo y la tarjeta de
   prueba de Stripe `4242 4242 4242 4242` (cualquier fecha futura y CVC):
   registro → pago → regresa a la app → inicia sesión → ve un tablero
   vacío → agrega un paciente. Revisa en el panel de administración que
   aparezca "Periodo de prueba".
3. Cambia a las llaves `sk_live_...` y el `price_...` de modo real.

## Paso 5 — Página de venta

1. En `landing/index.html`, cambia la línea
   `window.AURA_APP_URL = "https://TU-APP.streamlit.app";` por tu link,
   el precio y el correo `hola@auraflow.mx` (es un ejemplo).
2. GitHub → **Settings → Pages → Source: GitHub Actions**.
3. Al fusionar a `main`, el workflow "Publicar página de venta" la
   publica en `https://<tu-usuario>.github.io/garmin/`. Si compras un
   dominio (ej. auraflow.mx), configúralo en la misma pantalla de Pages.

## Paso 6 — Legal (antes de cobrar)

`landing/privacidad.html` y `landing/terminos.html` son **borradores**
(tienen un recuadro rojo que lo dice). Pásalos a un abogado. Puntos clave:

- Los datos de salud son **datos personales sensibles**: cada
  profesional (responsable) necesita el consentimiento expreso de sus
  pacientes; AURA FLOW es el **encargado**.
- Los datos viven en servicios fuera de México (Google, Streamlit,
  Stripe, GitHub, Anthropic).
- Facturación (CFDI): Stripe no emite CFDI; si tus clientes piden
  factura, necesitas un servicio de facturación aparte.

## Riesgos a tener presentes

- **Garmin:** la conexión usa la librería no oficial
  `python-garminconnect` (la cuenta del paciente, no una API de Garmin
  para empresas). Funciona, pero para un producto de pago a escala lo
  correcto es solicitar el **Garmin Connect Developer Program (Health
  API)**. Garmin puede cambiar o bloquear el acceso no oficial.
- **Conectar pacientes de otras cuentas:** hoy un paciente de un cliente
  nuevo conecta Garmin corriendo `export_token.py` en su computadora (pide
  Python) y le manda el token a su profesional. Es la parte con más
  fricción para vender; el siguiente paso natural es una página de
  vinculación. **No** repartas `credenciales_hoja.json` en el kit de
  pacientes a clientes nuevos: esa llave puede leer las hojas de todas
  las cuentas. Apple Health (subir el .zip desde el tablero) sí funciona
  para todas las cuentas.
- **FreeStyle Libre y Oura** quedan solo para tu cuenta por ahora (la
  página de venta los marca como "próximamente").
- **Análisis con IA:** el costo de la API de Anthropic sale de tu llave
  para todas las cuentas. Vigílalo en console.anthropic.com.
- **Streamlit Community Cloud** es gratuito y sirve para arrancar, pero
  con varios clientes conviene moverse a un hospedaje de pago (más
  memoria y sin que la app "se duerma").
- **Google Sheets** como base de datos aguanta los primeros clientes;
  con decenas de cuentas activas conviene migrar a Postgres.
