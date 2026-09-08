"""Lee un PDF de estudios clínicos de sangre (o de orina) y extrae cada
prueba con su resultado, unidad, rango de referencia y si salió bajo,
normal o alto -- sin importar el laboratorio.

A diferencia de InBody (que es una plantilla fija y usa OCR sobre una
imagen), un estudio de sangre puede venir en decenas de formatos
distintos según el laboratorio (SYNLAB/MédicaSur, Chopo, etc.) -- cada
uno con sus propias columnas, iconos de estatus, y hasta la forma de
mostrar el resultado (algunos laboratorios ni siquiera tienen una
columna de "resultado": el número aparece en una de tres columnas según
si está bajo, normal o alto). Escribir un regex por laboratorio no
escala. En vez de eso, se usa la API de Claude (la misma que ya usa
ai_analisis.py, mismo Secret ANTHROPIC_API_KEY) para leer el PDF
directamente y devolver los resultados ya estructurados -- así funciona
con cualquier formato de laboratorio con el que Claude sepa lidiar, sin
tener que anticipar cada plantilla."""

import base64
import json

MODEL = "claude-opus-5"

_PROMPT = """Este PDF es un estudio clínico de laboratorio (sangre, orina, u \
otro). Extrae CADA prueba/analito que tenga un resultado (ignora texto \
explicativo, metodología, avisos legales, tablas de "límites de referencia" \
que son solo texto informativo sin un resultado del paciente).

Devuelve ÚNICAMENTE un JSON válido (nada de texto antes o después, nada de \
```), con esta forma exacta:

{
  "fecha": "DD.MM.AAAA",
  "laboratorio": "nombre del laboratorio si aparece, o null",
  "resultados": [
    {
      "prueba": "nombre de la prueba tal cual aparece (ej. \\"Glucosa\\", \\"Colesterol LDL\\")",
      "resultado": "el valor tal cual (ej. \\"91\\", \\"NEGATIVO\\", \\"CLARO\\")",
      "unidad": "unidad si aplica (ej. \\"mg/dL\\"), o null si no tiene",
      "rango_min": número o null si no hay mínimo,
      "rango_max": número o null si no hay máximo,
      "estado": "bajo" | "normal" | "alto" | "sin_dato"
    }
  ]
}

Reglas para "estado":
- Compara el resultado contra el rango de referencia del PDF (sin importar \
cómo esté representado ahí -- como una columna de texto, como un ícono, o \
porque el número aparece bajo una columna de "Bajo"/"Dentro"/"Sobre").
- Si el resultado es texto no numérico dentro de lo esperado (ej. \
"NEGATIVO", "AUSENTES", "CLARO" cuando eso es lo normal), usa "normal".
- Si no se puede determinar el estado (no hay rango, o el formato no lo deja \
claro), usa "sin_dato" -- nunca inventes un estado.

"fecha": usa la fecha de toma de muestra si aparece: si no, la fecha de \
registro/recepción. Si un mismo PDF tiene pruebas de fechas de toma \
distintas (poco común), usa la más reciente para "fecha" y no te preocupes \
por separarlas.

No incluyas datos del paciente (nombre, edad, etc.), solo los resultados de \
laboratorio."""


def extraer_estudio(pdf_bytes: bytes, api_key: str | None = None) -> dict:
    """Manda el PDF a la API de Claude y regresa
    {"fecha": ..., "laboratorio": ..., "resultados": [...]} ya parseado.
    Lanza RuntimeError con un mensaje claro si falta la API key, si Claude
    no devuelve JSON válido, o si la llamada falla -- quien lo llama
    decide cómo mostrarlo (ver dashboard_pacientes.py)."""
    import anthropic

    if not api_key:
        raise RuntimeError(
            "Falta configurar el Secret ANTHROPIC_API_KEY en Streamlit Cloud (Settings -> Secrets) "
            "para poder leer estudios clínicos -- es el mismo que usa el análisis con IA."
        )

    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}},
                {"type": "text", "text": _PROMPT},
            ],
        }],
    )
    texto = "".join(block.text for block in response.content if block.type == "text").strip()

    # Por si Claude envuelve el JSON en ```json ... ``` a pesar de que se le
    # pidió que no lo hiciera -- se limpia antes de parsear en vez de fallar.
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto.lower().startswith("json"):
            texto = texto[4:]
        texto = texto.strip()

    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Claude no devolvió un JSON válido al leer el estudio: {e}")

    if not isinstance(datos, dict) or "resultados" not in datos:
        raise RuntimeError("La respuesta de Claude no tiene la forma esperada (falta \"resultados\").")

    return datos
