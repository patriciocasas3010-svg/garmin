# Publicar tu dashboard con un link (Streamlit Community Cloud)

Esto pone tu propio dashboard (tu cuenta de Garmin, no la de pacientes) en
internet con un link tipo `https://tu-app.streamlit.app`, para que no
dependa de tener tu computadora prendida.

**Importante:** este link es solo para **tu propia cuenta**. No sirve para
que cada paciente vea la suya — eso necesita el camino de la Garmin Health
API que hablamos aparte (autorización oficial por paciente).

## Paso 1: Genera tu token de sesión (en tu computadora)

```bash
source .venv/bin/activate
python3 export_token.py
```

Te va a imprimir un bloque largo de texto entre líneas de guiones. Cópialo
completo (todo el bloque, sin las líneas de guiones). **Es como una
contraseña — no lo pegues en ningún lado más que en Streamlit Cloud (paso
3).**

## Paso 2: Sube tu código a GitHub

Si ya tienes el repositorio en GitHub (como hasta ahora), no hace falta
nada extra aquí — solo asegúrate de que esté actualizado (`git push`).

## Paso 3: Crea la app en Streamlit Community Cloud

1. Ve a https://share.streamlit.io e inicia sesión con tu cuenta de GitHub.
2. Botón **"New app"** (o "Create app").
3. Elige tu repositorio y la rama, y en "Main file path" pon `dashboard.py`.
4. Antes de darle a "Deploy", entra a **"Advanced settings" → "Secrets"** y
   pega esto (reemplazando los valores):

   ```toml
   GARMIN_TOKEN_B64 = """PEGA_AQUI_EL_TOKEN_DEL_PASO_1"""
   APP_PASSWORD = "elige-una-contraseña-para-el-link"
   ```

   - `GARMIN_TOKEN_B64`: el bloque que copiaste con `export_token.py`.
   - `APP_PASSWORD`: una contraseña que tú inventes — sin esto, cualquiera
     con el link vería tus datos; con esto, el dashboard pide esa
     contraseña antes de mostrar nada.

5. Dale **"Deploy"**. Tarda uno o dos minutos la primera vez.

Al terminar tienes tu link (algo como
`https://tu-usuario-garmin-abc123.streamlit.app`) que puedes abrir desde
cualquier computadora o celular — te va a pedir la contraseña que pusiste
en `APP_PASSWORD`.

## Para "quitar el acceso" más adelante

- **Cambiar o quitar la contraseña**: entra a tu app en share.streamlit.io →
  Settings → Secrets, cambia `APP_PASSWORD` y guarda — el link sigue igual,
  pero ya nadie con la contraseña vieja puede entrar.
- **Apagar la app por completo**: en share.streamlit.io, botón de opciones
  de tu app → "Delete app" (o "Pause"). El link deja de funcionar.

## Actualizar el dashboard publicado

Cada vez que hagas `git push` a la rama que conectaste, Streamlit Cloud
vuelve a desplegar solo con los cambios nuevos — no hay que repetir estos
pasos, solo el `git push`.

## Si el token deja de funcionar

Las sesiones de Garmin eventualmente pueden expirar. Si el dashboard
publicado empieza a fallar con errores de sesión, repite el Paso 1 en tu
computadora y actualiza el valor de `GARMIN_TOKEN_B64` en Secrets con el
token nuevo.
