# Conecta tu Apple Watch / iPhone para tus consultas

Esto te permite ver tu actividad, sueño y frecuencia cardiaca de tu Apple
Watch (medidos por la app **Salud** de tu iPhone) en la consulta con tu
nutriólogo. Se hace **una sola vez por adelantado** (no en la consulta, para
no perder tiempo ahí) y toma unos 10 minutos.

**No metes ninguna contraseña de Apple en ningún lado.** Solo exportas un
archivo desde tu propio iPhone y lo mueves a esta carpeta — nada de eso pasa
por internet salvo hacia la hoja de tu nutriólogo, y nunca incluye tu Apple
ID ni ninguna contraseña.

## Paso 1: Exporta tus datos desde tu iPhone

1. Abre la app **Salud** en tu iPhone.
2. Toca tu foto de perfil (arriba a la derecha).
3. Baja hasta el final y toca **"Exportar todos los datos de salud"**.
4. Confirma. Puede tardar uno o dos minutos armando el archivo.
5. Te va a ofrecer compartirlo — mándatelo a ti mismo por **AirDrop** (si tu
   computadora es Mac) o por **correo** a una cuenta que revises en tu
   computadora. Es un archivo `.zip` (normalmente se llama `export.zip` o
   `exportar.zip`).

## Paso 2: Consigue la carpeta del programa

Tu nutriólogo te va a dar una carpeta (o un archivo `.zip`). Si es un `.zip`,
descomprímelo (doble clic en Mac, clic derecho → "Extraer todo" en Windows)
y pon la carpeta resultante en tu Escritorio.

## Paso 3: Pon tu archivo de Salud dentro de esa carpeta

Mueve el `.zip` que exportaste en el Paso 1 (el de tu iPhone) **dentro** de
la carpeta del programa, junto a los demás archivos. **No hace falta
descomprimirlo** — el programa lo lee tal cual.

## Paso 4: Abre el programa con doble clic

Entra a la carpeta y haz doble clic en:

- **Mac**: `iniciar_paciente_apple.command`
- **Windows**: `iniciar_paciente_apple.bat`

Se va a abrir una ventana de texto (Terminal). **No necesitas instalar nada
por tu cuenta**: la primera vez que la abres, el programa prepara todo solo
(necesita internet para eso), lo cual tarda 1-2 minutos; después es mucho
más rápido. Solo espera sin cerrar la ventana.

### Si Mac no te deja abrirlo ("no se puede abrir porque es de un desarrollador no identificado")

Haz clic derecho (o Ctrl+clic) sobre `iniciar_paciente_apple.command` →
"Abrir" → confirma "Abrir" en la ventana de advertencia. Solo hace falta la
primera vez.

### Si Mac dice que el archivo "está dañado" y que lo muevas a la basura

No lo muevas a la basura — esto pasa cuando la carpeta viajó por WhatsApp
(a veces recomprime los archivos y eso confunde a macOS). Pide que te la
compartan por Google Drive o correo en vez de WhatsApp. Si ya te la
mandaron por WhatsApp, avísale a tu nutriólogo, hay un arreglo rápido.

## Paso 5: Escribe tu nombre (solo la primera vez)

La ventana te va a preguntar **tu nombre** (para que tu nutriólogo sepa
cuál dashboard es el tuyo) — escríbelo y presiona Enter. Solo te lo pide
esta primera vez.

Enseguida tu navegador va a abrir una página con tus datos.

## Paso 6: En la consulta (o cuando quieras actualizar)

Los datos de Salud de tu iPhone **no se actualizan solos** en esta carpeta
— a diferencia de un reloj Garmin, aquí no hay una sesión que se conecte
sola. Cuando quieras ver datos más recientes:

1. Repite el **Paso 1** (exporta de nuevo desde tu iPhone).
2. Reemplaza el archivo `.zip` viejo en la carpeta por el nuevo (mismo
   nombre o no, no importa, con que sea el único `.zip` que diga "export"
   en la carpeta).
3. Vuelve a hacer doble clic en `iniciar_paciente_apple.command` /
   `iniciar_paciente_apple.bat` — ya no te va a pedir tu nombre otra vez,
   solo va a leer el archivo nuevo y actualizar tu dashboard.

Para cerrar el programa cuando termine la consulta, ve a la ventana de
Terminal que se abrió y presiona `Ctrl + C`.

## ¿Qué se ve distinto a un reloj Garmin?

Tu dashboard se ve prácticamente igual (mismas 6 pestañas), pero dos cosas
que Apple Health no reporta (nadie fuera de Garmin las calcula) van a
aparecer como "no disponible":

- **Desgaste físico (Body Battery)**.
- **Recuperación (Training Readiness)**.

Todo lo demás — sueño, frecuencia cardiaca en reposo, HRV, calorías, zonas
de entrenamiento, entrenamientos individuales — sí se calcula igual.

## ¿Problemas?

Avísale a tu nutriólogo qué mensaje de error te salió (una foto de la
pantalla ayuda mucho) para que te pueda ayudar a resolverlo.
