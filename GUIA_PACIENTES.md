# Conecta tu reloj Garmin para tus consultas

Esto te permite ver tu actividad, sueño y recuperación de Garmin en la
consulta con tu nutriólogo. Se hace **una sola vez** por adelantado (no en la
consulta, para no perder tiempo ahí) y toma unos 10-15 minutos.

**Tu contraseña de Garmin nunca se comparte con tu nutriólogo ni con nadie.**
Se queda guardada únicamente en tu computadora.

## Paso 1: Consigue la carpeta del programa

Tu nutriólogo te va a dar una carpeta (o un archivo .zip). Si es un .zip,
descomprímelo (doble clic en Mac, clic derecho → "Extraer todo" en Windows)
y pon la carpeta resultante en tu Escritorio.

## Paso 2: Instala Python (solo la primera vez)

- **Mac**: ve a https://www.python.org/downloads/macos/, descarga el botón
  amarillo grande, ábrelo e instala con las opciones por defecto.
- **Windows**: ve a https://www.python.org/downloads/windows/, descarga el
  botón amarillo grande. **Muy importante**: en la primera pantalla del
  instalador, marca la casilla que dice "Add python.exe to PATH" antes de
  darle a instalar.

Si ya tenías Python instalado no hace falta reinstalarlo, pero si algo falla
más adelante, prueba instalando la versión de arriba.

## Paso 3: Abre el programa con doble clic

Entra a la carpeta que te dieron y haz doble clic en:

- **Mac**: `iniciar_paciente.command`
- **Windows**: `iniciar_paciente.bat`

Se va a abrir una ventana de texto (Terminal) que instala todo lo necesario
(la primera vez tarda 1-2 minutos, después es más rápido).

### Si Mac no te deja abrirlo ("no se puede abrir porque es de un desarrollador no identificado")

Haz clic derecho (o Ctrl+clic) sobre `iniciar_paciente.command` → "Abrir" →
confirma "Abrir" en la ventana de advertencia. Solo hace falta la primera vez.

## Paso 4: Inicia sesión (solo la primera vez)

La ventana te va a pedir:

1. Tu correo de Garmin Connect.
2. Tu contraseña (no se ve mientras la escribes, es normal).
3. Si Garmin lo pide, un código que te llega por correo o SMS.

Después de esto, tu navegador va a abrir una página con tus datos. Las
próximas veces que abras el programa, ya no te va a pedir nada de esto.

## Paso 5: En la consulta

Simplemente lleva tu computadora con la carpeta del programa. Antes de la
consulta (o al llegar), haz doble clic en `iniciar_paciente.command` /
`iniciar_paciente.bat` de nuevo — como ya iniciaste sesión antes, va a abrir
la página con tus datos actualizados directamente, sin pedirte nada.

Para cerrar el programa cuando termine la consulta, ve a la ventana de
Terminal que se abrió y presiona `Ctrl + C`.

## ¿Problemas?

Avísale a tu nutriólogo qué mensaje de error te salió (una foto de la
pantalla ayuda mucho) para que te pueda ayudar a resolverlo.
