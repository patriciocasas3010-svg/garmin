"""Lee un resultado de InBody (foto, JPG/PNG, o PDF hecho a partir de una
foto -- no tiene texto real, solo la imagen) usando OCR (Tesseract) y saca
los campos más relevantes con expresiones regulares.

El OCR de una foto de un tiquet impreso NUNCA es 100% confiable (números
que se leen mal, comas en vez de puntos, renglones que se mezclan) -- por
eso esto se usa solo como "primer borrador": el nutriólogo siempre revisa
y corrige los valores antes de guardarlos (ver dashboard_pacientes.py).

Requiere el binario de Tesseract instalado en el sistema (no solo el
paquete de Python `pytesseract`, que aquí ni se usa) -- en Streamlit Cloud
se instala listando 'tesseract-ocr', 'tesseract-ocr-spa' y 'poppler-utils'
en packages.txt.
"""

import re
import subprocess
import tempfile
from pathlib import Path

_NUM_RE = re.compile(r"\d+[.,]\d+|\d+")


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Convierte el archivo (imagen o PDF-de-una-foto) a texto vía OCR."""
    suffix = Path(filename).suffix.lower()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        in_path = tmp / f"input{suffix or '.jpg'}"
        in_path.write_bytes(file_bytes)

        if suffix == ".pdf":
            subprocess.run(
                ["pdftoppm", "-r", "300", "-png", str(in_path), str(tmp / "page")],
                check=True, capture_output=True,
            )
            imagenes = sorted(tmp.glob("page*.png"))
        else:
            imagenes = [in_path]

        texto_completo = []
        for img in imagenes:
            out_base = tmp / (img.stem + "_ocr")
            subprocess.run(
                ["tesseract", str(img), str(out_base), "-l", "spa"],
                check=True, capture_output=True,
            )
            texto_completo.append(out_base.with_suffix(".txt").read_text(encoding="utf-8"))

        return "\n".join(texto_completo)


def _numeros(linea: str) -> list[str]:
    return _NUM_RE.findall(linea)


def _a_float(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _valor_de_fila(lineas: list[str], etiqueta_patron: str, primero: bool = False) -> float | None:
    """Busca la primera línea que haga match con etiqueta_patron.

    Las filas de este reporte vienen de dos formas distintas según cómo
    las leyó el OCR:
      - "Peso (kg) — — 58.3"                     (valor en la misma línea)
      - "MME (kg) 100 110 ... 170"                (línea siguiente:)
        "Masa de Musculo Esqueletico ... 21.6"    (el valor real)
    Si la línea de la etiqueta ya trae varios números seguidos (la regla
    de la gráfica de barras), el valor real está en la siguiente línea.
    """
    for i, linea in enumerate(lineas):
        if re.search(etiqueta_patron, linea, re.IGNORECASE):
            nums = _numeros(linea)
            # 0 números (la etiqueta y el valor cayeron en líneas
            # distintas) o >=4 números (esta línea es la regla de una
            # gráfica de barras) -- en ambos casos, el valor real está en
            # la siguiente línea.
            if (not nums or len(nums) >= 4) and i + 1 < len(lineas):
                nums_sig = _numeros(lineas[i + 1])
                if nums_sig:
                    return _a_float(nums_sig[0] if primero else nums_sig[-1])
            if nums:
                return _a_float(nums[0] if primero else nums[-1])
    return None


def parse_inbody_text(texto: str) -> dict:
    """Extrae los campos más relevantes. Cualquier campo que no se
    encuentre con confianza queda en None -- se muestra vacío en el
    formulario de revisión, nunca se inventa un valor."""
    lineas = texto.splitlines()

    perfil_id = re.search(r"\b(\d{5,6}-\d+)\b", texto)
    altura = _valor_de_fila(lineas, r"\d{2,3}\s*cm")
    edad = _valor_de_fila(lineas, r"^Edad\b")
    sexo_m = re.search(r"\b(Femenino|Masculino)\b", texto, re.IGNORECASE)
    fecha_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", texto)
    modelo_m = re.search(r"\[?(InBody\s?\d{2,4})\]?", texto, re.IGNORECASE)

    peso = _valor_de_fila(lineas, r"^Peso\s*\(kg\)")
    mme = _valor_de_fila(lineas, r"\bMME\s*\(kg\)")
    grasa_visceral = _valor_de_fila(lineas, r"Nivel\s*de\s*Grasa\s*Visceral", primero=True)
    agua_total = _valor_de_fila(lineas, r"Agua\s*Corporal\b(?!.*Total)")
    agua_intra = _valor_de_fila(lineas, r"Agua\s*Intracelular", primero=True)
    agua_extra = _valor_de_fila(lineas, r"Agua\s*Extracelular", primero=True)
    imc = _valor_de_fila(lineas, r"^IMC\b")
    pgc = _valor_de_fila(lineas, r"^PGC\b")

    # La etiqueta de "Masa Grasa Corporal (kg)" en la gráfica de barras es
    # justo la fila que casi siempre se lee peor con OCR -- en vez de
    # buscar la etiqueta (que puede salir irreconocible), se busca la fila
    # de la regla de esa gráfica en particular, que es fija en este modelo.
    masa_grasa = None
    for i, linea in enumerate(lineas):
        if re.search(r"60\s+80\s+100\s+160\s+220\s+280", linea) and i + 1 < len(lineas):
            nums_sig = _numeros(lineas[i + 1])
            if nums_sig:
                masa_grasa = _a_float(nums_sig[-1])
            break

    return {
        "id": perfil_id.group(1) if perfil_id else None,
        "modelo": modelo_m.group(1) if modelo_m else None,
        "altura_cm": altura,
        "edad": int(edad) if edad is not None else None,
        "sexo": sexo_m.group(1).capitalize() if sexo_m else None,
        "fecha": fecha_m.group(1) if fecha_m else None,
        "peso_kg": peso,
        "masa_grasa_kg": masa_grasa,
        "mme_kg": mme,
        "grasa_visceral": int(grasa_visceral) if grasa_visceral is not None else None,
        "agua_total_l": agua_total,
        "agua_intra_l": agua_intra,
        "agua_extra_l": agua_extra,
        "imc": imc,
        "pgc_pct": pgc,
    }
