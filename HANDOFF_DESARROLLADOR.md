# AURA -- Handoff técnico para desarrollador

Este documento es para quien tome el proyecto después de mí (Claude Code). No
reemplaza al `README.md` (ese es para pacientes/nutriólogas, sin jerga
técnica) -- este es el mapa de arquitectura, decisiones y deuda técnica para
alguien que va a seguir escribiendo código aquí.

## 1. Qué es esto, en una frase

Un dashboard clínico para nutriólogas (AURA) que centraliza wearables
(Garmin/Apple Health/Oura/Libre CGM), InBody, estudios de laboratorio y
cruces clínicos entre esos datos, con 3 identidades de marca según el tipo de
paciente (Clinical/Flow/Health). Está en producción, en piloto con pacientes
reales (~250-300), construido y operado por una sola persona no-técnica con
ayuda de Claude Code -- **no por un equipo de ingeniería**. Eso explica varias
decisiones de este documento: se priorizó "funciona hoy, con datos reales" por
encima de "arquitectura ideal".

## 2. Las dos apps que corren en producción

Mismo repo, mismo branch, dos deploys distintos en Streamlit Community Cloud
(se diferencian solo por el "Main file path" configurado en cada uno):

| App | Entry point | Para quién | Qué hace |
|---|---|---|---|
| Dashboard central | `dashboard_pacientes.py` | Nutriólogas | Login, lista de pacientes, las ~10 pestañas de datos por paciente, Settings de admin |
| Conexión de Garmin | `conectar_garmin_web.py` | Pacientes (una sola vez) | El paciente pega usuario/contraseña de Garmin (con MFA) para activar sync automático, sin instalar nada |

Aparte, hay **dashboards personales de un solo paciente** que corren local en
la computadora de cada quien (`dashboard.py` para Garmin, `dashboard_apple.py`
para Apple Health, `dashboard_oura.py` para Oura) -- estos son el producto
original, anteriores al dashboard central, y las guías `GUIA_PACIENTES*.md`
siguen siendo para ellos. El flujo real de producción hoy es: paciente conecta
su Garmin vía `conectar_garmin_web.py` (una vez) → `sync_diario.py` (GitHub
Action diario, `.github/workflows/sync_diario.yml`) jala sus datos solo →
aparecen en `dashboard_pacientes.py`. Apple Health y Oura todavía dependen de
que el paciente exporte/sincronice manual (no tienen equivalente del flujo
web de Garmin todavía).

## 3. Modelo de datos: Google Sheets como base de datos

**No hay base de datos real.** Todo vive en una sola hoja de Google, con una
pestaña por "tabla". Cada pestaña la administra un módulo `*_store.py` que
sabe leer/escribir SU pestaña únicamente (patrón consistente en todo el repo:
`HOJA_NOMBRE`, `ENCABEZADOS`, `_worksheet()`, funciones `guardar_*`/`leer_*`).

| Pestaña (hoja) | Módulo dueño | Qué guarda |
|---|---|---|
| `Hoja1` (la principal) | `push_resumen.py` | Una fila por paciente con su snapshot de wearable completo (JSON en la columna `Datos`) |
| `Enfoque` | `enfoque_store.py` | Perfil: enfoque, meta de grasa, días de plan, condición metabólica/GLP-1, nutriólogo asignado |
| `Notas` | `notas_store.py` | Historial de notas libres del nutriólogo sobre el paciente |
| `InBody` | `inbody_store.py` | Historial de resultados de báscula InBody |
| `Antropometria` | `antropometria_store.py` | Historial de mediciones antropométricas manuales |
| `Calorias` | `calorias_store.py` | Historial de calorías de comidas capturadas |
| `Estudios` | `estudios_store.py` | Estudios de laboratorio (PDF parseado a JSON) |
| `TokensGarmin` | `token_store.py` | Token OAuth de Garmin por paciente + clave de conexión de un solo uso |
| `Usuarios` | `usuarios_store.py` | Cuentas de nutriólogas (usuario, hash+salt de contraseña, rol) |
| `Feedback` | `feedback_store.py` | Reportes de bugs/sugerencias mandados desde el botón flotante |
| `LibreVinculo` | `libre_store.py` | Vínculo con LibreLinkUp (CGM) |

**Por qué Sheets y no una base real:** fue la decisión correcta para
arrancar sin infraestructura ni costo, y sigue funcionando para el volumen
actual. **Ya está mostrando sus límites:** cuotas de lectura/escritura de la
API de Sheets (`sheet_cache.py` existe específicamente para mitigar esto,
cacheando `gc.open_by_key()`), y no hay transacciones reales (dos escrituras
casi simultáneas a la misma fila pueden pisarse). Con 250+ pacientes activos
esto va a doler más, no menos. **Recomendación:** migrar a Postgres
(Supabase es buena opción -- da auth + Postgres + API REST gratis para este
volumen) es el primer proyecto de infraestructura que yo haría.

## 4. Autenticación y roles

Sistema propio, no usa ningún proveedor externo de auth:

- `usuarios_store.py`: contraseñas con hash PBKDF2-SHA256 + sal por usuario
  (200,000 iteraciones), nunca texto plano.
- `"admin"` + el Secret `APP_PASSWORD` es un acceso de emergencia que siempre
  funciona, sin depender de que la pestaña `Usuarios` tenga datos.
- Roles: `"admin"` (ve todo, entra a Settings) / `"nutriologo"` (solo ve
  pacientes que tiene asignados en `Enfoque.Nutriologo`).
- Sesión vive en `st.session_state["_usuario"]` -- se pierde al cerrar la
  pestaña del navegador (no hay cookie persistente ni "recuérdame").

## 5. Los módulos de lógica clínica (el corazón del producto)

- **`marca_aura.py`**: decide qué identidad (Clinical/Flow/Health) le toca a
  un paciente, a partir de su perfil ya capturado (nada de preguntas nuevas).
- **`cruces_clinicos.py`**: 10 paneles que cruzan laboratorio + InBody +
  wearable con fórmulas y umbrales explícitos (ver
  `assets/cruces_clinicos_referencia.html` para la bibliografía completa de
  cada uno -- accesible también desde la pestaña Cruces clínicos con un
  botón). Principio de diseño explícito en el código: **nunca inventa un
  dato faltante** -- si algo no está, dice "sin dato", no lo estima.
- **`glp1_diabetes.py`**: el panel 11, específico para pacientes con
  GLP-1/diabetes (calidad de la pérdida de peso: cuánto fue músculo vs.
  grasa).
- **`garmin_metrics.py` / `apple_health.py` / `oura_metrics.py`**: cada uno
  transforma los datos crudos de su fuente a la MISMA estructura interna
  (`build_runtime_data()`), para que `garmin_dashboard_ui.py` no le importe
  de dónde vino el dato.

## 6. UI: Streamlit, y sus límites reales

Todo el frontend es Streamlit -- sin un framework de JS, sin build step. La
identidad visual (`theme.py`) inyecta CSS/fuentes por encima de los
componentes nativos. Esto tiene un techo real, ya golpeado varias veces en
este proyecto:

- **CSS frágil dependiente de la estructura DOM interna de Streamlit**, no
  documentada y sujeta a cambiar entre versiones (ej. el sticky header de
  `dashboard_pacientes.py` depende de que Streamlit siga envolviendo cada
  bloque en `div[data-testid="stElementContainer"]`/`stHorizontalBlock` como
  hoy). Cualquier upgrade de Streamlit puede romper esto silenciosamente.
- **No hay separación UI/lógica de negocio.** `dashboard_pacientes.py` (~1450
  líneas) mezcla renderizado, reglas de negocio y llamadas directas a
  Google Sheets en el mismo archivo.
- **No es responsive de verdad** ni pensado para móvil.

**Si el objetivo es "profesionalizar" la UX** (Figma, sistema de diseño real,
interacciones finas), la ruta más honesta es: diseñar en Figma sin las
restricciones de Streamlit, y construir esa UI en algo con más control
(React/Next.js) que hable con una API -- no seguir empujando Streamlit más
allá de lo que da. Streamlit fue la decisión correcta para llegar rápido a un
piloto real; no es la base para la versión "de $500 USD/mes" que se quiere
después.

Para arrancar ese trabajo de diseño sin adivinar valores desde capturas de
pantalla, ver [`assets/aura_design_system.html`](assets/aura_design_system.html)
-- los tokens de color, tipografía y los patrones de componentes (botones,
tabs, alertas, chips, KPIs) extraídos directamente de `theme.py` y
`marca_aura.py`, tal como corren hoy en producción. Es el punto de partida
para reconstruir esto en Figma.

## 7. Qué NO tiene (deuda técnica, en orden de prioridad real)

1. **Cero pruebas automatizadas en el repo.** Todo lo probado durante el
   desarrollo (con Claude Code) vivió en scripts sueltos fuera del proyecto
   (fakes de Google Sheets + Playwright), nunca se commitearon. Un cambio
   nuevo no tiene ninguna red de seguridad automática.
2. **Google Sheets como base de datos** (ver sección 3) -- el cuello de
   botella más probable según crezca el piloto.
3. **Streamlit como UI** (ver sección 6) -- el techo de qué tan "profesional"
   se puede ver/sentir sin reescribir el frontend.
4. **Lógica de negocio mezclada con UI** en `dashboard_pacientes.py`.
5. **Sin CI/CD.** No hay lint, type-check ni tests corriendo en cada push --
   `.github/workflows/` solo tiene `sync_diario.yml` (el cron de Garmin), no
   nada de calidad de código.
6. **Rate limits de Garmin.** Ya causaron fallas reales en producción (429
   "Too Many Requests" en el intercambio de token OAuth) -- mitigado
   parcialmente distinguiendo el mensaje de error, pero no resuelto de raíz.

## 8. Qué SÍ está bien pensado (para no deshacerlo sin razón)

- El principio de "nunca inventar un dato faltante" en `cruces_clinicos.py`
  -- es una decisión clínica deliberada, no un descuido.
  - La arquitectura de marca (`marca_aura.py`) calculada del perfil ya
  capturado, no de una pregunta nueva -- evita fricción de onboarding.
- Cada `*_store.py` solo toca su propia pestaña -- patrón consistente,
  fácil de extender (agregar un store nuevo = copiar el patrón de uno
  existente).
- El historial de commits de git tiene mensajes que explican el *por qué*
  de cada cambio, no solo el qué -- vale la pena seguir esa convención.

## 9. Cómo correr esto local / Secrets necesarios

No hay entorno de desarrollo formal (sin Docker, sin `.env.example`). Los
Secrets que usa la app (configurados en Streamlit Cloud → Settings → Secrets,
formato TOML):

```
SHEET_ID = "..."                  # obligatorio -- id de la hoja de Google
GOOGLE_CREDENTIALS_JSON = '''...'''  # obligatorio -- credenciales de service account
APP_PASSWORD = "..."              # login de emergencia como "admin"
ANTHROPIC_API_KEY = "..."         # análisis con IA (ai_analisis.py)
LIBRE_EMAIL = "..."               # cuenta de LibreLinkUp (CGM), una sola para toda la app
LIBRE_PASSWORD = "..."
CONECTAR_GARMIN_URL = "..."       # URL pública de conectar_garmin_web.py
GARMIN_TOKEN_B64 = "..."          # solo para dashboard.py (personal, no el central)
OURA_TOKEN = "..."                # solo para dashboard_oura.py (personal)
```

`requirements.txt` tiene las versiones mínimas -- correr con
`pip install -r requirements.txt` en un venv de Python 3.10+.

## 10. Siguiente paso recomendado si se profesionaliza esto

En este orden, según lo que más duele primero:

1. Agregar pruebas automatizadas mínimas (los `*_store.py` son los más
   fáciles de probar -- lógica pura, sin Streamlit de por medio).
2. Migrar de Google Sheets a una base real (Supabase) -- sin esto, escalar
   el piloto va a seguir doliendo.
3. Separar lógica de negocio de la UI (mover las funciones de
   `dashboard_pacientes.py` que no son puro renderizado a módulos propios).
4. Decidir, con datos reales del piloto (qué pestañas se usan, dónde se
   traban las nutriólogas), si vale la pena reescribir el frontend fuera de
   Streamlit.
