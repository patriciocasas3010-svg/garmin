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

**¿Van a usar la misma computadora dos personas de la familia, cada quien
con su propio Garmin?** Cada persona necesita su **propia copia** de esta
carpeta (por ejemplo, cambia el nombre de cada copia a "garmin - Juan",
"garmin - María"). No compartan una sola copia entre dos cuentas de Garmin
distintas, o la sesión de uno se va a sobreescribir con la del otro.

## Paso 2: Abre el programa con doble clic

Entra a la carpeta que te dieron y haz doble clic en:

- **Mac**: `iniciar_paciente.command`
- **Windows**: `iniciar_paciente.bat`

Se va a abrir una ventana de texto (Terminal). **No necesitas instalar nada
por tu cuenta**: la primera vez que la abres, el programa prepara todo solo
(necesita internet para eso), lo cual tarda 1-2 minutos; después es mucho
más rápido. Solo espera sin cerrar la ventana.

### Si Mac no te deja abrirlo ("no se puede abrir porque es de un desarrollador no identificado")

Haz clic derecho (o Ctrl+clic) sobre `iniciar_paciente.command` → "Abrir" →
confirma "Abrir" en la ventana de advertencia. Solo hace falta la primera vez.

### Si Mac dice que el archivo "está dañado" y que lo muevas a la basura

No lo muevas a la basura, no está dañado de verdad — esto pasa cuando el
`.zip` viajó por WhatsApp (a veces lo recomprime y eso confunde a macOS).
Se arregla así:

1. Dale "Cancelar" a ese aviso.
2. Abre la app **Terminal** (Spotlight con Cmd+Espacio, escribe "Terminal").
3. Escribe `xattr -cr ` (con un espacio al final, sin Enter todavía).
4. Arrastra la carpeta del programa desde el Finder hacia la ventana de
   Terminal — se pega sola la ruta.
5. Presiona Enter.
6. Vuelve a intentar abrir `iniciar_paciente.command` como de costumbre.

Si te vuelve a pasar seguido, pide que te compartan la carpeta por Google
Drive o correo en vez de WhatsApp — así no debería volver a pasar.

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
