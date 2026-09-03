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

## Paso 2: Abre el programa con doble clic

Entra a la carpeta que te dieron y haz doble clic en:

- **Mac**: `iniciar_paciente.command`
- **Windows**: `iniciar_paciente.bat`

Se va a abrir una ventana de texto (Terminal) que instala todo lo necesario
(la primera vez tarda 1-2 minutos, después es más rápido).

**Si no tienes Python instalado**, la ventana te lo va a decir y va a abrir
sola la página correcta para descargarlo. Solo tienes que:

- **Mac**: descargar el botón amarillo grande e instalar con las opciones
  por defecto.
- **Windows**: descargar el botón amarillo grande y, **muy importante**, en
  la primera pantalla del instalador marcar la casilla "Add python.exe to
  PATH" antes de darle a instalar.

Cuando termine de instalar, vuelve a hacer doble clic en
`iniciar_paciente.command` / `iniciar_paciente.bat` para seguir. Si ya
tenías Python instalado, la ventana pasa directo a este paso sin pedirte
nada.

### Si Mac no te deja abrirlo ("no se puede abrir porque es de un desarrollador no identificado")

Haz clic derecho (o Ctrl+clic) sobre `iniciar_paciente.command` → "Abrir" →
confirma "Abrir" en la ventana de advertencia. Solo hace falta la primera vez.

## Paso 3: Inicia sesión (solo la primera vez)

La ventana te va a pedir:

1. Tu correo de Garmin Connect.
2. Tu contraseña (no se ve mientras la escribes, es normal).
3. Si Garmin lo pide, un código que te llega por correo o SMS.

Después de esto, es posible que te pregunte **tu nombre** (para que tu
nutriólogo sepa cuál resumen es el tuyo) — escríbelo y presiona Enter, solo
te lo va a pedir esta primera vez.

Enseguida tu navegador va a abrir una página con tus datos. Las próximas
veces que abras el programa, ya no te va a pedir nada de esto.

## Paso 4: En la consulta

Simplemente lleva tu computadora con la carpeta del programa. Antes de la
consulta (o al llegar), haz doble clic en `iniciar_paciente.command` /
`iniciar_paciente.bat` de nuevo — como ya iniciaste sesión antes, va a abrir
la página con tus datos actualizados directamente, sin pedirte nada.

Para cerrar el programa cuando termine la consulta, ve a la ventana de
Terminal que se abrió y presiona `Ctrl + C`.

## ¿Problemas?

Avísale a tu nutriólogo qué mensaje de error te salió (una foto de la
pantalla ayuda mucho) para que te pueda ayudar a resolverlo.
