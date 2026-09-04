# Conecta tu anillo Oura para tus consultas

Esto te permite ver tu actividad, sueño y recuperación de tu anillo Oura en
la consulta con tu nutriólogo. Se hace **una sola vez** por adelantado (no en
la consulta, para no perder tiempo ahí) y toma unos 10 minutos.

**No metes tu correo ni tu contraseña de Oura en ningún lado.** En vez de
eso generas un "token" (una llave de acceso) desde tu propia cuenta de Oura,
que solo permite leer tus datos -- nunca tu contraseña se comparte con tu
nutriólogo ni con nadie.

## Paso 1: Genera tu Personal Access Token

1. Entra a **cloud.ouraring.com/personal-access-tokens** desde el navegador
   de tu computadora e inicia sesión con tu cuenta de Oura (la misma que
   usas en la app del teléfono).
2. Dale clic a **"Create New Personal Access Token"**.
3. Ponle cualquier nombre (por ejemplo "Nutriólogo") y confirma.
4. Te va a mostrar un código largo de letras y números -- **cópialo**. Solo
   se alcanza a ver esa vez; si lo pierdes, puedes generar uno nuevo
   repitiendo este paso.

## Paso 2: Consigue la carpeta del programa

Tu nutriólogo te va a dar una carpeta (o un archivo `.zip`). Si es un `.zip`,
descomprímelo (doble clic en Mac, clic derecho → "Extraer todo" en Windows)
y pon la carpeta resultante en tu Escritorio.

**¿Van a usar la misma computadora dos personas de la familia, cada quien
con su propio anillo Oura?** Cada persona necesita su **propia copia** de
esta carpeta (por ejemplo, cambia el nombre de cada copia a "oura - Juan",
"oura - María"). No compartan una sola copia entre dos cuentas de Oura
distintas.

## Paso 3: Abre el programa con doble clic

Entra a la carpeta y haz doble clic en:

- **Mac**: `iniciar_paciente_oura.command`
- **Windows**: `iniciar_paciente_oura.bat`

Se va a abrir una ventana de texto (Terminal). **No necesitas instalar nada
por tu cuenta**: la primera vez que la abres, el programa prepara todo solo
(necesita internet para eso), lo cual tarda 1-2 minutos; después es mucho
más rápido. Solo espera sin cerrar la ventana.

### Si Mac no te deja abrirlo ("no se puede abrir porque es de un desarrollador no identificado")

Haz clic derecho (o Ctrl+clic) sobre `iniciar_paciente_oura.command` →
"Abrir" → confirma "Abrir" en la ventana de advertencia. Solo hace falta la
primera vez.

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
6. Vuelve a intentar abrir `iniciar_paciente_oura.command` como de costumbre.

Si te vuelve a pasar seguido, pide que te compartan la carpeta por Google
Drive o correo en vez de WhatsApp — así no debería volver a pasar.

### Si Windows te avisa "Windows protegió su PC"

Es normal la primera vez que abres un programa nuevo — no significa que
esté dañado ni que tenga virus, solo que Windows todavía no lo reconoce.

1. En esa ventana azul, busca el texto pequeño que dice **"Más información"**
   (o "More info") y dale clic.
2. Va a aparecer un botón nuevo, **"Ejecutar de todas formas"** (o "Run
   anyway") — dale clic ahí.
3. El programa va a abrir normal. Esto solo hace falta la primera vez.

Si en vez de eso tu antivirus (Windows Defender u otro) borra el archivo o
dice que es una amenaza, avísale a tu nutriólogo con una foto de ese
mensaje — puede que tengas que restaurarlo desde la "Cuarentena" del
antivirus o pedir la carpeta de nuevo.

## Paso 4: Pega tu token (solo la primera vez)

La ventana te va a pedir que **pegues el token** que copiaste en el Paso 1
(no se ve mientras lo pegas, es normal) y presiones Enter.

Después de esto, es posible que te pregunte **tu nombre** (para que tu
nutriólogo sepa cuál dashboard es el tuyo) — escríbelo y presiona Enter,
solo te lo va a pedir esta primera vez.

Enseguida tu navegador va a abrir una página con tus datos. Las próximas
veces que abras el programa, ya no te va a pedir nada de esto.

## Paso 5: En la consulta (o antes, para llegar con datos frescos)

Tu anillo sincroniza automáticamente con la app de Oura en tu teléfono por
Bluetooth cuando están cerca, y la app sube esos datos a tu cuenta de Oura
en cuanto tiene internet. Para llegar con tus datos lo más actualizados
posible a la consulta:

1. Trae puesto el anillo normalmente los días antes (entre más días de
   registro, mejor lectura de tu recuperación y tendencias).
2. Abre la app de Oura en tu teléfono un momento antes de la consulta (con
   internet, wifi o datos) para forzar que sincronice lo más reciente.
3. Al llegar, haz doble clic en `iniciar_paciente_oura.command` /
   `iniciar_paciente_oura.bat` de nuevo — como ya guardaste tu token antes,
   va a abrir la página con tus datos actualizados directamente, sin
   pedirte nada.

Para cerrar el programa cuando termine la consulta, ve a la ventana de
Terminal que se abrió y presiona `Ctrl + C`.

## ¿Qué se ve distinto a un reloj Garmin?

Tu dashboard se ve prácticamente igual (mismas 6 pestañas), pero algunas
cosas que Oura no reporta (o no de forma confiable a través de su
aplicación) van a aparecer como "no disponible":

- **Desgaste físico (Body Battery)**.
- **Eficiencia de carrera (deriva cardiaca) y zonas de FC de la semana** --
  Oura no da la frecuencia cardiaca segundo a segundo de cada entrenamiento.
- **Hidratación** -- Oura no registra cuánto tomas de agua.
- **Nivel de estrés** en número (0-100) -- Oura solo lo reporta como
  categoría, no como número comparable al de Garmin.

Todo lo demás — sueño, HRV, calorías, preparación física ("recuperación"),
entrenamientos individuales — sí se calcula.

## ¿Problemas?

Avísale a tu nutriólogo qué mensaje de error te salió (una foto de la
pantalla ayuda mucho) para que te pueda ayudar a resolverlo.
