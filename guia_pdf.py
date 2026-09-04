"""Genera las guías para pacientes (conectar Garmin / Apple Health) en PDF,
con el mismo estilo del resto del proyecto — ver pdf_style.py.

Uso (regenerar los dos PDFs después de editar el contenido de aquí abajo):
    python3 guia_pdf.py
"""

import pdf_style as ps

_NOTE_FILL = (238, 233, 216)
_WARN_FILL = (247, 231, 222)


def _p(pdf, texto, size=10):
    pdf.set_font("Karla", "", size)
    pdf.set_text_color(*ps.INK)
    pdf.multi_cell(0, 6, texto, markdown=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _h2(pdf, texto):
    ps.section_title(pdf, texto, size=14)


def _h3(pdf, texto):
    pdf.ln(1)
    pdf.set_font("Karla", "B", 10.5)
    pdf.set_text_color(*ps.OLIVE_RGB)
    pdf.multi_cell(0, 6, texto, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _ol(pdf, items):
    num_w = 7
    for i, item in enumerate(items, 1):
        x0 = pdf.get_x()
        y0 = pdf.get_y()
        pdf.set_font("Karla", "B", 10)
        pdf.set_text_color(*ps.OLIVE_RGB)
        pdf.cell(num_w, 6, f"{i}.")
        pdf.set_xy(x0 + num_w, y0)
        pdf.set_font("Karla", "", 10)
        pdf.set_text_color(*ps.INK)
        pdf.multi_cell(ps.CONTENT_W - num_w, 6, item, markdown=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _box(pdf, texto, fill_rgb, accent_rgb):
    pdf.ln(1)
    inset = 4
    y0 = pdf.get_y()
    pdf.set_x(ps.MARGIN + inset)
    pdf.set_fill_color(*fill_rgb)
    pdf.set_font("Karla", "", 9.5)
    pdf.set_text_color(*ps.INK)
    pdf.multi_cell(ps.CONTENT_W - 2 * inset, 6, texto, markdown=True, fill=True, new_x="LMARGIN", new_y="NEXT")
    y1 = pdf.get_y()
    pdf.set_fill_color(*accent_rgb)
    pdf.rect(ps.MARGIN, y0, 1.2, y1 - y0, style="F")
    pdf.ln(3)


def _note(pdf, texto):
    _box(pdf, texto, _NOTE_FILL, ps.OLIVE_RGB)


def _warn(pdf, texto):
    _box(pdf, texto, _WARN_FILL, ps.TERRACOTTA_RGB)


def _files(pdf, pares):
    """pares: [(sistema, nombre_archivo), ...] — se ve como una lista de
    "Mac: iniciar_paciente.command" en tipografía mono."""
    for sistema, archivo in pares:
        pdf.set_font("Karla", "B", 10)
        pdf.set_text_color(*ps.INK)
        pdf.cell(22, 6.5, f"{sistema}:")
        pdf.set_font("MonoSemiBold", "", 10)
        pdf.set_text_color(*ps.OLIVE_RGB)
        pdf.cell(0, 6.5, archivo, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _render(pdf, bloques):
    for tipo, contenido in bloques:
        if tipo == "p":
            _p(pdf, contenido)
        elif tipo == "h2":
            _h2(pdf, contenido)
        elif tipo == "h3":
            _h3(pdf, contenido)
        elif tipo == "ol":
            _ol(pdf, contenido)
        elif tipo == "note":
            _note(pdf, contenido)
        elif tipo == "warn":
            _warn(pdf, contenido)
        elif tipo == "files":
            _files(pdf, contenido)
    ps.pinned_footer(pdf, "Tablero Maestro de Rendimiento")
    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Guía Garmin
# ---------------------------------------------------------------------------

_CONTENIDO_GARMIN = [
    ("p",
     "Esto te permite ver tu actividad, sueño y recuperación de Garmin en la "
     "consulta con tu nutriólogo. Se hace **una sola vez** por adelantado (no "
     "en la consulta, para no perder tiempo ahí) y toma unos 10-15 minutos."),
    ("note",
     "**Tu contraseña de Garmin nunca se comparte con tu nutriólogo ni con "
     "nadie.** Se queda guardada únicamente en tu computadora."),

    ("h2", "Paso 1: Consigue la carpeta del programa"),
    ("p",
     "Tu nutriólogo te va a dar una carpeta (o un archivo .zip). Si es un "
     ".zip, descomprímelo (doble clic en Mac, clic derecho -> \"Extraer "
     "todo\" en Windows) y pon la carpeta resultante en tu Escritorio."),
    ("p",
     "**¿Van a usar la misma computadora dos personas de la familia, cada "
     "quien con su propio Garmin?** Cada persona necesita su **propia "
     "copia** de esta carpeta (por ejemplo, cambia el nombre de cada copia "
     "a \"garmin - Juan\", \"garmin - María\"). No compartan una sola copia "
     "entre dos cuentas de Garmin distintas, o la sesión de uno se va a "
     "sobreescribir con la del otro."),

    ("h2", "Paso 2: Abre el programa con doble clic"),
    ("p", "Entra a la carpeta que te dieron y haz doble clic en:"),
    ("files", [("Mac", "iniciar_paciente.command"), ("Windows", "iniciar_paciente.bat")]),
    ("p",
     "Se va a abrir una ventana de texto (Terminal). **No necesitas "
     "instalar nada por tu cuenta**: la primera vez que la abres, el "
     "programa prepara todo solo (necesita internet para eso), lo cual "
     "tarda 1-2 minutos; después es mucho más rápido. Solo espera sin "
     "cerrar la ventana."),

    ("h3", "Si Mac no te deja abrirlo (\"no se puede abrir porque es de un desarrollador no identificado\")"),
    ("p",
     "Haz clic derecho (o Ctrl+clic) sobre **iniciar_paciente.command** -> "
     "\"Abrir\" -> confirma \"Abrir\" en la ventana de advertencia. Solo "
     "hace falta la primera vez."),

    ("h3", "Si Mac dice que el archivo \"está dañado\" y que lo muevas a la basura"),
    ("p",
     "No lo muevas a la basura, no está dañado de verdad — esto pasa "
     "cuando el .zip viajó por WhatsApp (a veces lo recomprime y eso "
     "confunde a macOS). Se arregla así:"),
    ("ol", [
        "Dale \"Cancelar\" a ese aviso.",
        "Abre la app **Terminal** (Spotlight con Cmd+Espacio, escribe \"Terminal\").",
        "Escribe **xattr -cr ** (con un espacio al final, sin Enter todavía).",
        "Arrastra la carpeta del programa desde el Finder hacia la ventana de Terminal — se pega sola la ruta.",
        "Presiona Enter.",
        "Vuelve a intentar abrir **iniciar_paciente.command** como de costumbre.",
    ]),
    ("p",
     "Si te vuelve a pasar seguido, pide que te compartan la carpeta por "
     "Google Drive o correo en vez de WhatsApp — así no debería volver a "
     "pasar."),

    ("h3", "Si Windows te avisa \"Windows protegió su PC\""),
    ("p",
     "Es normal la primera vez que abres un programa nuevo — no significa "
     "que esté dañado ni que tenga virus, solo que Windows todavía no lo "
     "reconoce."),
    ("ol", [
        "En esa ventana azul, busca el texto pequeño que dice **\"Más información\"** y dale clic.",
        "Va a aparecer un botón nuevo, **\"Ejecutar de todas formas\"** — dale clic ahí.",
        "El programa va a abrir normal. Esto solo hace falta la primera vez.",
    ]),
    ("warn",
     "Si en vez de eso tu antivirus (Windows Defender u otro) borra el "
     "archivo o dice que es una amenaza, avísale a tu nutriólogo con una "
     "foto de ese mensaje — puede que tengas que restaurarlo desde la "
     "\"Cuarentena\" del antivirus o pedir la carpeta de nuevo."),

    ("h2", "Paso 3: Inicia sesión (solo la primera vez)"),
    ("p", "La ventana te va a pedir:"),
    ("ol", [
        "Tu correo de Garmin Connect.",
        "Tu contraseña (no se ve mientras la escribes, es normal).",
        "Si Garmin lo pide, un código que te llega por correo o SMS.",
    ]),
    ("p",
     "Después de esto, es posible que te pregunte **tu nombre** (para que "
     "tu nutriólogo sepa cuál resumen es el tuyo) — escríbelo y presiona "
     "Enter, solo te lo va a pedir esta primera vez."),
    ("p",
     "Enseguida tu navegador va a abrir una página con tus datos. Las "
     "próximas veces que abras el programa, ya no te va a pedir nada de "
     "esto."),

    ("h2", "Paso 4: En la consulta"),
    ("p",
     "Simplemente lleva tu computadora con la carpeta del programa. Antes "
     "de la consulta (o al llegar), haz doble clic en "
     "**iniciar_paciente.command** / **iniciar_paciente.bat** de nuevo — como "
     "ya iniciaste sesión antes, va a abrir la página con tus datos "
     "actualizados directamente, sin pedirte nada."),
    ("p",
     "Para cerrar el programa cuando termine la consulta, ve a la ventana "
     "de Terminal que se abrió y presiona **Ctrl + C**."),

    ("h2", "¿Problemas?"),
    ("p",
     "Avísale a tu nutriólogo qué mensaje de error te salió (una foto de "
     "la pantalla ayuda mucho) para que te pueda ayudar a resolverlo."),
]


def build_guia_garmin_pdf() -> bytes:
    pdf = ps.new_branded_pdf()
    ps.draw_header(pdf, "Conecta tu reloj Garmin", "Guía para tus consultas")
    return _render(pdf, _CONTENIDO_GARMIN)


# ---------------------------------------------------------------------------
# Guía Apple Health
# ---------------------------------------------------------------------------

_CONTENIDO_APPLE = [
    ("p",
     "Esto te permite ver tu actividad, sueño y frecuencia cardiaca de tu "
     "Apple Watch (medidos por la app **Salud** de tu iPhone) en la "
     "consulta con tu nutriólogo. Se hace **una sola vez por adelantado** "
     "(no en la consulta, para no perder tiempo ahí) y toma unos 10 "
     "minutos."),
    ("note",
     "**No metes ninguna contraseña de Apple en ningún lado.** Solo "
     "exportas un archivo desde tu propio iPhone y lo mueves a esta "
     "carpeta — nada de eso pasa por internet salvo hacia la hoja de tu "
     "nutriólogo, y nunca incluye tu Apple ID ni ninguna contraseña."),

    ("h2", "Paso 1: Exporta tus datos desde tu iPhone"),
    ("ol", [
        "Abre la app **Salud** en tu iPhone.",
        "Toca tu foto de perfil (arriba a la derecha).",
        "Baja hasta el final y toca **\"Exportar todos los datos de salud\"**.",
        "Confirma. Puede tardar uno o dos minutos armando el archivo.",
        "Te va a ofrecer compartirlo — mándatelo a ti mismo por **AirDrop** "
        "(si tu computadora es Mac) o por **correo** a una cuenta que "
        "revises en tu computadora. Es un archivo **.zip** (normalmente se "
        "llama **export.zip** o **exportar.zip**).",
    ]),

    ("h2", "Paso 2: Consigue la carpeta del programa"),
    ("p",
     "Tu nutriólogo te va a dar una carpeta (o un archivo **.zip**). Si es un "
     "**.zip**, descomprímelo (doble clic en Mac, clic derecho -> \"Extraer "
     "todo\" en Windows) y pon la carpeta resultante en tu Escritorio."),

    ("h2", "Paso 3: Pon tu archivo de Salud dentro de esa carpeta"),
    ("p",
     "Mueve el **.zip** que exportaste en el Paso 1 (el de tu iPhone) "
     "**dentro** de la carpeta del programa, junto a los demás archivos. "
     "**No hace falta descomprimirlo** — el programa lo lee tal cual."),

    ("h2", "Paso 4: Abre el programa con doble clic"),
    ("p", "Entra a la carpeta y haz doble clic en:"),
    ("files", [("Mac", "iniciar_paciente_apple.command"), ("Windows", "iniciar_paciente_apple.bat")]),
    ("p",
     "Se va a abrir una ventana de texto (Terminal). **No necesitas "
     "instalar nada por tu cuenta**: la primera vez que la abres, el "
     "programa prepara todo solo (necesita internet para eso), lo cual "
     "tarda 1-2 minutos; después es mucho más rápido. Solo espera sin "
     "cerrar la ventana."),

    ("h3", "Si Mac no te deja abrirlo (\"no se puede abrir porque es de un desarrollador no identificado\")"),
    ("p",
     "Haz clic derecho (o Ctrl+clic) sobre **iniciar_paciente_apple.command** "
     "-> \"Abrir\" -> confirma \"Abrir\" en la ventana de advertencia. Solo "
     "hace falta la primera vez."),

    ("h3", "Si Mac dice que el archivo \"está dañado\" y que lo muevas a la basura"),
    ("p",
     "No lo muevas a la basura — esto pasa cuando la carpeta viajó por "
     "WhatsApp (a veces recomprime los archivos y eso confunde a macOS). "
     "Pide que te la compartan por Google Drive o correo en vez de "
     "WhatsApp. Si ya te la mandaron por WhatsApp, avísale a tu "
     "nutriólogo, hay un arreglo rápido."),

    ("h3", "Si Windows te avisa \"Windows protegió su PC\""),
    ("p",
     "Es normal la primera vez que abres un programa nuevo — no significa "
     "que esté dañado ni que tenga virus, solo que Windows todavía no lo "
     "reconoce."),
    ("ol", [
        "En esa ventana azul, busca el texto pequeño que dice **\"Más información\"** y dale clic.",
        "Va a aparecer un botón nuevo, **\"Ejecutar de todas formas\"** — dale clic ahí.",
        "El programa va a abrir normal. Esto solo hace falta la primera vez.",
    ]),
    ("warn",
     "Si en vez de eso tu antivirus (Windows Defender u otro) borra el "
     "archivo o dice que es una amenaza, avísale a tu nutriólogo con una "
     "foto de ese mensaje — puede que tengas que restaurarlo desde la "
     "\"Cuarentena\" del antivirus o pedir la carpeta de nuevo."),

    ("h2", "Paso 5: Escribe tu nombre (solo la primera vez)"),
    ("p",
     "La ventana te va a preguntar **tu nombre** (para que tu nutriólogo "
     "sepa cuál dashboard es el tuyo) — escríbelo y presiona Enter. Solo "
     "te lo pide esta primera vez."),
    ("p", "Enseguida tu navegador va a abrir una página con tus datos."),

    ("h2", "Paso 6: En la consulta (o cuando quieras actualizar)"),
    ("p",
     "Los datos de Salud de tu iPhone **no se actualizan solos** en esta "
     "carpeta — a diferencia de un reloj Garmin, aquí no hay una sesión "
     "que se conecte sola. Cuando quieras ver datos más recientes:"),
    ("ol", [
        "Repite el **Paso 1** (exporta de nuevo desde tu iPhone).",
        "Reemplaza el archivo **.zip** viejo en la carpeta por el nuevo "
        "(mismo nombre o no, no importa, con que sea el único **.zip** que "
        "diga \"export\" en la carpeta).",
        "Vuelve a hacer doble clic en **iniciar_paciente_apple.command** / "
        "**iniciar_paciente_apple.bat** — ya no te va a pedir tu nombre "
        "otra vez, solo va a leer el archivo nuevo y actualizar tu "
        "dashboard.",
    ]),
    ("p",
     "Para cerrar el programa cuando termine la consulta, ve a la ventana "
     "de Terminal que se abrió y presiona **Ctrl + C**."),

    ("h2", "¿Qué se ve distinto a un reloj Garmin?"),
    ("p",
     "Tu dashboard se ve prácticamente igual (mismas pestañas), pero dos "
     "cosas que Apple Health no reporta (nadie fuera de Garmin las "
     "calcula) van a aparecer como \"no disponible\": **Desgaste físico "
     "(Body Battery)** y **Recuperación (Training Readiness)**. Todo lo "
     "demás — sueño, frecuencia cardiaca en reposo, HRV, calorías, zonas "
     "de entrenamiento, entrenamientos individuales — sí se calcula "
     "igual."),

    ("h2", "¿Problemas?"),
    ("p",
     "Avísale a tu nutriólogo qué mensaje de error te salió (una foto de "
     "la pantalla ayuda mucho) para que te pueda ayudar a resolverlo."),
]


def build_guia_apple_pdf() -> bytes:
    pdf = ps.new_branded_pdf()
    ps.draw_header(pdf, "Conecta tu Apple Watch", "Guía para tus consultas")
    return _render(pdf, _CONTENIDO_APPLE)


if __name__ == "__main__":
    with open("GUIA_PACIENTES.pdf", "wb") as f:
        f.write(build_guia_garmin_pdf())
    with open("GUIA_PACIENTES_APPLE.pdf", "wb") as f:
        f.write(build_guia_apple_pdf())
    print("Listo: GUIA_PACIENTES.pdf y GUIA_PACIENTES_APPLE.pdf")
