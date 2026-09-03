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

Esto corre los 4 reportes y guarda las gráficas en la carpeta `graficas/`:

- **Frecuencia cardiaca en reposo** (últimos 3 meses), con línea de tendencia
  y si está mejorando o empeorando → `graficas/frecuencia_reposo.png`.
- **Carga de entrenamiento semanal vs horas de sueño** (últimas 12 semanas),
  para ver si las semanas de más carga coinciden con menos sueño →
  `graficas/carga_vs_sueno.png`.
- **Resumen semanal estilo Strava**: kilómetros, tiempo en movimiento,
  desnivel y ritmo promedio, comparado contra la semana pasada.
- **Récords personales del año**: mejor 5K, mejor 10K y salida más larga en
  bici.

También puedes pedir solo uno:

```bash
python3 garmin_reports.py rhr       # frecuencia cardiaca en reposo
python3 garmin_reports.py carga     # carga de entrenamiento vs sueño
python3 garmin_reports.py semana    # resumen semanal
python3 garmin_reports.py records   # récords personales del año
```

Las gráficas (`.png`) quedan en la carpeta `graficas/` de tu computadora;
ábrelas con doble clic desde el Finder para verlas.

**Nota sobre la carga de entrenamiento:** si tu reloj/cuenta no reporta el
campo oficial de "Training Load" de Garmin para una actividad, el script usa
una estimación propia (minutos en movimiento ponderados por tu frecuencia
cardiaca promedio), así que es un valor aproximado, no el número exacto que
verías en la app de Garmin.

## Tablero Maestro de Rendimiento (dashboard avanzado)

Un dashboard más avanzado, con 4 paneles y una tabla de alertas automáticas,
pensado para entrenamiento serio:

```bash
streamlit run dashboard.py
```

Esto abre una pestaña en tu navegador (normalmente http://localhost:8501)
con datos de tus últimos 90 días:

1. **Alerta temprana (Carga vs. Preparación)**: ACWR (carga aguda 7 días /
   crónica 28 días) cruzado con el Z-score de tu HRV nocturna (7 días vs. tu
   línea base de 60 días).
2. **Eficiencia y economía cardiovascular**: deriva cardiaca (%) entre la
   primera y segunda mitad de tus actividades sostenidas (>20 min) de la
   última semana — cuántos latidos de más te cuesta sostener el mismo ritmo.
3. **Distribución de carga (polarización 80/20)**: minutos por zona de FC
   real (calculada sobre tu Reserva de FC / fórmula de Karvonen) en la
   última semana, para auditar si estás entrenando demasiado en la "zona
   gris" intermedia.
4. **Resiliencia del sistema nervioso autónomo**: tu FC en reposo frente a
   qué tan rápido baja tu FC en los primeros 2 minutos después de esforzarte.

Al final hay una **tabla de indicadores unificados** que marca 🔴 ALERTA o
🟢 OK para: Índice de Disrupción Fisiológica (ACWR + HRV), Pérdida de
Eficiencia Aeróbica (deriva cardiaca) y Estatus de Tono Vagal (FC en reposo +
recuperación), cada uno con su acción recomendada si se dispara la alerta.

Usa el botón **"Actualizar datos"** dentro del dashboard para recalcular con
tus datos más recientes (por defecto se guardan en caché por 1 hora). Para
cerrarlo, vuelve a la Terminal y presiona `Ctrl+C`.

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
