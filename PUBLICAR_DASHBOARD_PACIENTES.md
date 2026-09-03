# Dashboard central de pacientes (un link, cada quien ve lo suyo)

Esto te da **un solo link** donde cada paciente elige su nombre de una
lista y ve su **Tablero Maestro de Rendimiento completo** — las mismas 6
pestañas y gráficas de tu propio dashboard (ACWR, zonas, eficiencia, sueño,
calorías, alertas) — sin que nadie escriba su contraseña de Garmin en
ninguna página web. Cada paciente sigue conectando su Garmin en su propio
equipo (como ya hacen); lo único nuevo es que, al abrir su dashboard local,
todo ese dashboard se manda solo a una hoja de Google que tu dashboard
central lee y vuelve a dibujar igual.

```
Paciente hace doble clic (como siempre)
        │
        ├─► conecta con SU Garmin (local, sin cambios)
        ├─► push_resumen.py manda su dashboard completo a tu hoja de Google (nuevo, automático)
        └─► abre su dashboard local (sin cambios)

Tu hoja de Google  ──►  dashboard_pacientes.py (publicado, un link)
                         el paciente elige su nombre → ve su dashboard completo → "Salir"
```

## Parte 1: Crear la hoja de Google y las credenciales

**1.** Ve a https://sheets.google.com y crea una hoja nueva en blanco.
Ponle un nombre, por ejemplo "Pacientes - Garmin". Dale clic a **"Compartir"**
más adelante (paso 6), no todavía.

**2.** Copia el **ID de la hoja**: está en la URL, la parte larga entre
`/d/` y `/edit`:
```
https://docs.google.com/spreadsheets/d/EL_ID_VA_AQUI/edit
```
Guárdalo, lo vas a necesitar dos veces.

**3.** Ve a https://console.cloud.google.com/ (con tu cuenta de Google).
Si te pide crear un proyecto, dale **"Nuevo proyecto"**, ponle un nombre
(ej. "garmin-pacientes") y créalo.

**4.** Con el proyecto seleccionado, ve a **"APIs y servicios" → "Biblioteca"**,
busca **"Google Sheets API"** y dale **"Habilitar"**.

**5.** Ve a **"APIs y servicios" → "Credenciales"** → **"Crear credenciales"**
→ **"Cuenta de servicio"**. Ponle un nombre (ej. "garmin-bot") y créala. Una
vez creada, entra a esa cuenta de servicio → pestaña **"Claves"** → **"Agregar
clave"** → **"Crear clave nueva"** → tipo **JSON** → Crear. Se descarga un
archivo `.json` a tu computadora — este es tu `credenciales_hoja.json`.

**6.** Abre ese archivo `.json` con un editor de texto y busca el campo
`"client_email"` — copia ese correo (algo como
`garmin-bot@tu-proyecto.iam.gserviceaccount.com`). Regresa a tu hoja de
Google (paso 1) → **"Compartir"** → pega ese correo → dale permiso de
**"Editor"** → Enviar.

## Parte 2: Preparar la carpeta que le das a cada paciente

En la carpeta del proyecto (la que le compartes a cada paciente en zip):

1. Copia el archivo `credenciales_hoja.json` del paso 5 dentro de la carpeta.
2. Crea un archivo de texto llamado `hoja_id.txt` (sin extensión .txt visible
   si tu sistema las oculta) que contenga solo el ID de la hoja del paso 2,
   una sola línea, nada más.

La carpeta que compartas con pacientes debe verse así (además de lo que ya
tenía):
```
garmin/
├── credenciales_hoja.json   <- nuevo
├── hoja_id.txt              <- nuevo
├── iniciar_paciente.command
├── iniciar_paciente.bat
├── dashboard.py
├── push_resumen.py
└── ... (el resto de siempre)
```

**Importante:** `credenciales_hoja.json` **solo** puede escribir en esa hoja
de cálculo específica — no es tu contraseña de nada ni da acceso a Garmin,
así que es seguro incluirlo en la carpeta que compartes. Aun así, no lo
subas a un repositorio público de GitHub (en este repo ya está en
`.gitignore` para evitarlo por accidente).

Desde este momento, cada vez que un paciente haga doble clic en
`iniciar_paciente.command`/`.bat`, su resumen se manda solo a tu hoja.

## Parte 3: Publicar tu dashboard central

1. Ve a https://share.streamlit.io (inicia sesión con GitHub).
2. **"Create app"** → tu repositorio → tu rama → en **"Main file path"** pon:
   ```
   dashboard_pacientes.py
   ```
3. **"Advanced settings" → "Secrets"**, pega esto:

   ```toml
   SHEET_ID = "EL_ID_DE_TU_HOJA"
   GOOGLE_CREDENTIALS_JSON = '''
   PEGA_AQUI_TODO_EL_CONTENIDO_DEL_ARCHIVO_credenciales_hoja.json
   '''
   APP_PASSWORD = "UNA_CONTRASEÑA_QUE_TU_ELIJAS"
   ```

   Para el segundo valor, abre `credenciales_hoja.json` con un editor de
   texto, selecciona todo su contenido (es un bloque `{ ... }`), y pégalo
   completo entre las comillas triples.

   **`APP_PASSWORD` es muy importante aquí** — a diferencia de tu dashboard
   personal, este junta la información de *todos* tus pacientes en un solo
   link. Sin esta contraseña, cualquiera que consiga el link puede ver todo.
   Ponle una contraseña que tú vayas a recordar; te la va a pedir cada vez
   que abras el link (o cuando reinicies la sesión del navegador).

4. **Deploy**. En un par de minutos tienes tu link
   (`https://tu-app.streamlit.app`) — ese es el que abres tú en consulta.

## Cómo se ve en consulta

1. El paciente ya corrió `iniciar_paciente.command`/`.bat` antes de llegar
   (o lo corre ahí mismo si trae su laptop) — su dashboard completo ya está
   en la hoja.
2. Tú abres tu link, el paciente (o tú) selecciona su nombre de la lista.
3. Revisan juntos las 6 pestañas (Resumen, Carga y Preparación, Eficiencia
   y Zonas, Sueño y Bienestar, Calorías, Alertas) — lo mismo que vería el
   paciente en su propia computadora.
4. Le das a **"🚪 Salir"** arriba a la derecha antes de la siguiente consulta.

## Quitarle el acceso a un paciente

Borra su fila de la hoja de Google directamente (ábrela en
sheets.google.com, clic derecho en la fila → "Eliminar fila"). Ya no
aparecerá en la lista de nombres del dashboard.

## Ver los datos crudos

Como es una hoja de Google normal, en cualquier momento puedes abrirla tú
mismo en sheets.google.com para revisar, exportar o respaldar los datos.
