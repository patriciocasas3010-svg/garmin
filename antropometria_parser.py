"""Lee un reporte de mediciones antropométricas (ej. exportado desde Avena)
en PDF -- a diferencia de InBody, este PDF sí trae texto real (no es una
foto), así que se extrae directo con `pdftotext` (parte de poppler-utils,
ya requerido en packages.txt para InBody) y no hace falta OCR.

Aun así, el formato de estos reportes puede variar entre software o entre
plantillas -- por eso el nutriólogo siempre revisa y corrige los valores
en un formulario antes de guardarlos (ver dashboard_pacientes.py), igual
que con InBody."""

import re
import subprocess
import tempfile
from pathlib import Path


def extract_text(file_bytes: bytes) -> str:
    """Extrae el texto de un PDF con texto real, conservando el orden por
    columnas/renglones (-layout) para que cada etiqueta quede junto a su
    valor "Actual: ..." tal como aparece impreso."""
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "input.pdf"
        pdf_path.write_bytes(file_bytes)
        resultado = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            check=True, capture_output=True,
        )
        return resultado.stdout.decode("utf-8", errors="replace")


def _a_float(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _bloque(texto: str, etiqueta_exacta: str) -> float | None:
    """Busca un bloque de la forma:
        <etiqueta>
        Actual: <numero> <unidad opcional>
        Inicial: <numero>
    y regresa el valor "Actual". La etiqueta debe ocupar su propio renglón
    completo -- así "Grasa calculado" no hace match con "Grasa calculado (%)",
    y "Muslo" no hace match con "Muslo medio"."""
    patron = rf"^\s*{re.escape(etiqueta_exacta)}\s*$\r?\n\s*Actual:\s*([\d.,]+)"
    m = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
    return _a_float(m.group(1)) if m else None


def parse_antropometria_text(texto: str) -> dict:
    """Extrae los campos pedidos: fecha, Grasa - Faulkner (%), Grasa
    calculado (kg), los 8 pliegues cutáneos y las 7 circunferencias. No
    incluye peso/IMC/edad/estatura -- eso ya se lleva desde InBody.
    Cualquier campo no encontrado queda en None -- nunca se inventa un
    valor, se revisa a mano en el formulario."""
    fecha_m = re.search(r"(\d{1,2}\s+[A-Za-zÁÉÍÓÚáéíóú]+\.?\s+\d{4})", texto)

    return {
        "fecha": fecha_m.group(1) if fecha_m else None,
        "grasa_faulkner_pct": _bloque(texto, "Grasa - Faulkner"),
        "grasa_calculado_kg": _bloque(texto, "Grasa calculado"),
        "pliegue_supraespinal_mm": _bloque(texto, "Supraespinal"),
        "pliegue_muslo_frontal_mm": _bloque(texto, "Muslo frontal"),
        "pliegue_pantorrilla_medial_mm": _bloque(texto, "Pantorrilla medial"),
        "pliegue_abdominal_mm": _bloque(texto, "Abdominal"),
        "pliegue_tricipital_mm": _bloque(texto, "Tríceps / Tricipital"),
        "pliegue_subescapular_mm": _bloque(texto, "Subescapular"),
        "pliegue_suprailiaco_mm": _bloque(texto, "Suprailíaco / Ileocrestal"),
        "pliegue_bicipital_mm": _bloque(texto, "Bíceps / Bicipital"),
        "circ_cadera_cm": _bloque(texto, "Cadera"),
        "circ_pantorrilla_cm": _bloque(texto, "Pantorrilla"),
        "circ_muslo_medio_cm": _bloque(texto, "Muslo medio"),
        "circ_brazo_contraido_cm": _bloque(texto, "Brazo contraído"),
        "circ_cintura_cm": _bloque(texto, "Cintura"),
        "circ_brazo_relajado_cm": _bloque(texto, "Brazo relajado"),
        "circ_muslo_cm": _bloque(texto, "Muslo"),
    }
