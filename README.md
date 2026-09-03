# Conectar un reloj Garmin a este equipo

Este proyecto usa la librería [python-garminconnect](https://github.com/cyberjunky/python-garminconnect)
para vincular tu cuenta de Garmin Connect (y por lo tanto tu reloj) a este
equipo.

**Importante:** el script pide tu correo y contraseña directamente en la
terminal (con la contraseña oculta mientras la escribes). Nunca escribas tus
credenciales en el chat de Claude ni las pegues en ningún archivo del
repositorio.

## Requisitos previos

- Tu reloj Garmin debe estar sincronizado al menos una vez con la app
  **Garmin Connect Mobile** (celular) o con **Garmin Express** (PC/Mac), para
  que sus datos existan en tu cuenta de Garmin Connect. Este script no se
  comunica con el reloj por Bluetooth/USB directamente: usa la cuenta en la
  nube de Garmin Connect, que es lo que soporta `python-garminconnect`.
- **Python 3.10 o superior.** El `python3` que trae macOS de fábrica suele ser
  la versión 3.9 de Apple, que es demasiado vieja para esta librería. Si
  `python3 --version` te muestra 3.9.x o menos, instala una versión moderna
  desde https://www.python.org/downloads/macos/ (botón amarillo "Download
  Python 3.x.x"), abre el instalador y sigue los pasos por defecto. Luego
  cierra y vuelve a abrir la Terminal.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Si ya habías creado antes una carpeta `.venv` con una versión vieja de
Python, bórrala primero (`rm -rf .venv`) y vuelve a crearla con el Python
nuevo instalado en el paso anterior.

## Uso

Ejecuta el script y sigue las instrucciones en tu propia terminal:

```bash
python3 connect_garmin.py
```

Se te pedirá:

1. Tu correo de Garmin Connect.
2. Tu contraseña (no se muestra en pantalla mientras la escribes).
3. Si Garmin lo requiere, un código de verificación en dos pasos (MFA) que
   te llegará por correo o SMS.

Si el inicio de sesión es correcto, el script:

- Guarda los tokens de sesión (OAuth) en `~/.garminconnect` (fuera del
  repositorio, puedes cambiar la ruta con la variable de entorno
  `GARMINTOKENS`) para que las próximas ejecuciones no vuelvan a pedir la
  contraseña.
- Muestra tu nombre de usuario y la lista de relojes/dispositivos vinculados
  a tu cuenta, confirmando que la conexión funcionó.

## Reportes y gráficas

Una vez conectado (con `connect_garmin.py` ya corrido al menos una vez),
puedes generar reportes con tus datos reales:

```bash
python3 garmin_reports.py
```

Esto corre los 5 reportes y guarda las gráficas en la carpeta `graficas/`:

- **Frecuencia cardiaca en reposo** (últimos 3 meses), con línea de tendencia
  y si está mejorando o empeorando → `graficas/frecuencia_reposo.png`.
- **Carga de entrenamiento semanal vs horas de sueño** (últimas 12 semanas),
  para ver si las semanas de más carga coinciden con menos sueño →
  `graficas/carga_vs_sueno.png`.
- **Resumen semanal estilo Strava**: kilómetros, tiempo en movimiento,
  desnivel y ritmo promedio, comparado contra la semana pasada.
- **Récords personales del año**: mejor 5K, mejor 10K y salida más larga en
  bici.
- **Sueño, hidratación, desgaste físico y recuperación** (últimos 14 días):
  horas de sueño y etapas (profundo/ligero/REM), Sleep Score, hidratación
  diaria vs meta, Body Battery (cuánto recargas vs. gastas) y Training
  Readiness → `graficas/sueno.png`.

También puedes pedir solo uno:

```bash
python3 garmin_reports.py rhr         # frecuencia cardiaca en reposo
python3 garmin_reports.py carga       # carga de entrenamiento vs sueño
python3 garmin_reports.py semana      # resumen semanal
python3 garmin_reports.py records     # récords personales del año
python3 garmin_reports.py bienestar   # sueño, hidratación, desgaste y recuperación
```

Las gráficas (`.png`) quedan en la carpeta `graficas/` de tu computadora;
ábrelas con doble clic desde el Finder para verlas.

**Nota sobre la carga de entrenamiento:** si tu reloj/cuenta no reporta el
campo oficial de "Training Load" de Garmin para una actividad, el script usa
una estimación propia (minutos en movimiento ponderados por tu frecuencia
cardiaca promedio), así que es un valor aproximado, no el número exacto que
verías en la app de Garmin.

**Nota sobre el reporte de bienestar:** hidratación, Body Battery y Training
Readiness dependen de que tu reloj los soporte y de que los uses (la
hidratación en particular solo cuenta si la registras a mano en la app, el
reloj no mide cuánta agua tomas). Si tu modelo no los reporta, esa sección
del reporte lo indica en vez de fallar.

## Tablero Maestro de Rendimiento (dashboard avanzado)

Un dashboard más avanzado, organizado en pestañas, pensado para entrenamiento
serio:

```bash
streamlit run dashboard.py
```

Esto abre una pestaña en tu navegador (normalmente http://localhost:8501)
con 6 secciones:

1. **📋 Resumen**: tu **calificación del mes** (0-100), un promedio simple de
   tres partes iguales — recuperación (Training Readiness), sueño (Sleep
   Score o tus horas) y actividad física (calorías quemadas por actividad
   vs. una meta de 400 kcal/día) — con el desglose de cada parte, más un
   contador de días con actividad física vs. días sin actividad en el mes.
   Debajo, una foto rápida del día: ACWR, Z-score de HRV, tu FC en reposo de
   hoy vs. tu media, tu sueño de los últimos 7 días y cuántas alertas están
   activas.
2. **⚖️ Carga y Preparación**: ACWR (carga aguda 7 días / crónica 28 días)
   cruzado con el Z-score de tu HRV nocturna (7 días vs. tu línea base de 60
   días). Últimos 90 días.
3. **🎯 Eficiencia y Zonas**: deriva cardiaca (%) de tus actividades
   sostenidas (>20 min) de la última semana, y minutos por zona de FC real
   (Reserva de FC) para auditar la regla 80/20.
4. **😴 Sueño y Bienestar**: FC en reposo y recuperación post-esfuerzo, sueño,
   hidratación, Body Battery y Training Readiness.
5. **🔥 Calorías**: quemadas en reposo (BMR), por actividad y total por día,
   más el desglose de cada actividad individual. Últimos 30 días.
6. **🚦 Alertas**: la tabla de indicadores unificados — Índice de Disrupción
   Fisiológica (ACWR + HRV), Pérdida de Eficiencia Aeróbica (deriva cardiaca)
   y Estatus de Tono Vagal (FC en reposo + recuperación) — con su acción
   recomendada si se dispara.

Usa el botón **"🔄 Actualizar datos"** para recalcular con tus datos más
recientes (por defecto se guardan en caché por 1 hora). Para cerrarlo, vuelve
a la Terminal y presiona `Ctrl+C`.

**Limitaciones a tener en cuenta:**

- El HRV nocturno (paneles 1) solo existe si tu reloj soporta "HRV Status"
  de Garmin; si no, ese panel dirá que no hay datos suficientes.
- La FC máxima se estima como el máximo observado en tus últimos 90 días
  (no hay forma confiable de leer tu "FC máx" configurada en el perfil vía
  esta librería), así que las zonas de FC son una aproximación.
- Estos endpoints de Garmin Connect no son una API pública documentada por
  Garmin; si algo se ve raro, usa `python3 debug_endpoint.py <comando> ...`
  (ver el encabezado del archivo) para ver la respuesta cruda y así poder
  ajustar el cálculo correspondiente.

### Publicar tu dashboard con un link

Si quieres ver tu propio dashboard desde cualquier computadora (no solo la
tuya), sin depender de tenerla prendida, ve a
[`PUBLICAR_DASHBOARD.md`](PUBLICAR_DASHBOARD.md) — usa Streamlit Community
Cloud (gratis) con una contraseña propia para que el link no quede abierto
a cualquiera. Esto es solo para tu propia cuenta; para que cada paciente
tenga su propio link con su propio Garmin hace falta el camino de la Garmin
Health API (ver la sección de abajo).

## Dar esto a tus pacientes (consultorio)

Cada persona (tú o cada paciente) corre esta carpeta **en su propia
computadora, con su propia cuenta de Garmin**. Así nadie más ve ni guarda las
contraseñas de nadie — cada quien es dueño de su propia sesión y sus propios
datos.

Para compartirle esto a un paciente:

1. En GitHub, en este repositorio, usa "Code → Download ZIP" (o haz tú el
   `git clone` una vez y comprime la carpeta) y pásale el `.zip` por el medio
   que uses con pacientes (correo, WhatsApp, USB). No hace falta que el
   paciente tenga cuenta de GitHub ni sepa usar git.
2. Dale el archivo **`GUIA_PACIENTES.md`** — está escrito para alguien sin
   experiencia técnica, sin comandos de terminal. Le explica instalar Python
   una vez y usar `iniciar_paciente.command` (Mac) / `iniciar_paciente.bat`
   (Windows): un archivo de doble clic que instala todo, pide su login de
   Garmin la primera vez, y abre el dashboard.
3. En consulta, el paciente solo necesita traer su computadora y volver a
   hacer doble clic en ese archivo — como ya inició sesión antes, abre
   directo con sus datos actualizados.

Cada paciente termina con su propia copia de la carpeta, su propia sesión
guardada (`~/.garminconnect` en su equipo) y su propio dashboard corriendo
localmente — nada de esto pasa por tu computadora ni por ningún servidor.

### Un link central donde eliges al paciente y ves su dashboard completo

Si además quieres un solo link (para no depender de que cada paciente traiga
su laptop a consulta), cada vez que un paciente abre su dashboard local su
**Tablero Maestro de Rendimiento completo** (las mismas 6 pestañas y
gráficas, no solo un resumen) se manda automáticamente a una hoja de Google
tuya — [`push_resumen.py`](push_resumen.py), ya integrado en los
lanzadores de doble clic. Tú publicas
[`dashboard_pacientes.py`](dashboard_pacientes.py) con un link: el paciente
elige su nombre de una lista (nunca su Garmin) y ve su dashboard completo,
con un botón "Salir" para la siguiente consulta. Tú controlas quién
aparece en la lista (borrar su fila de la hoja le quita el acceso).

Guía paso a paso completa: [`PUBLICAR_DASHBOARD_PACIENTES.md`](PUBLICAR_DASHBOARD_PACIENTES.md).

## Solución de problemas

- **"Credenciales incorrectas"**: revisa que el correo y la contraseña sean
  los de tu cuenta Garmin Connect (no los de Garmin Express si son
  distintos).
- **Bloqueo temporal de Garmin**: si intentas iniciar sesión muchas veces
  seguidas, Garmin puede bloquear los intentos por un rato; espera unos
  minutos y vuelve a intentar.
- **No aparece mi reloj**: asegúrate de haberlo sincronizado antes con la
  app Garmin Connect Mobile o Garmin Express.
- **`ERROR: Could not find a version that satisfies the requirement
  garminconnect...`** o **`ModuleNotFoundError: No module named 'garth'`**:
  tu Python es demasiado viejo (probablemente el 3.9 de Apple). Instala
  Python 3.10+ como se indica arriba, borra `.venv` (`rm -rf .venv`), y
  repite los pasos de instalación con el Python nuevo.
