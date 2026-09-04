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
            # --psm 6 ("un solo bloque uniforme de texto") lee muchísimo
            # mejor las tablas densas de InBody que el modo automático por
            # default -- sobre todo evita que se pierdan puntos decimales
            # y que las columnas se mezclen entre sí.
            subprocess.run(
                ["tesseract", str(img), str(out_base), "-l", "spa", "--psm", "6"],
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


def _elige(nums: list[str], primero: bool, preferir_decimal: bool) -> str:
    """Si preferir_decimal=True y hay al menos un número con punto/coma
    entre los candidatos, se ignoran los que no lo tienen -- útil quando
    varios números de columnas vecinas se mezclaron en la misma línea y el
    correcto es justo el único que trae decimales (el resto son enteros
    sueltos de otra fila)."""
    candidatos = nums
    if preferir_decimal:
        decimales = [n for n in nums if "." in n or "," in n]
        if decimales:
            candidatos = decimales
    return candidatos[0] if primero else candidatos[-1]


def _valor_de_fila(
    lineas: list[str], etiqueta_patron: str, primero: bool = False, preferir_decimal: bool = False,
) -> float | None:
    """Busca la primera línea que haga match con etiqueta_patron.

    Las filas de este reporte vienen de dos formas distintas según cómo
    las leyó el OCR:
      - "Peso (kg) — — 58.3"                     (valor en la misma línea)
      - "MME (kg) 100 110 ... 170"                (línea siguiente:)
        "Masa de Musculo Esqueletico ... 21.6"    (el valor real)
    Si la línea de la etiqueta ya trae varios números seguidos (la regla
    de la gráfica de barras), el valor real está en la siguiente línea (o,
    si esa también sale ilegible, dos líneas más abajo).
    """
    for i, linea in enumerate(lineas):
        if re.search(etiqueta_patron, linea, re.IGNORECASE):
            nums = _numeros(linea)
            # 0 números (la etiqueta y el valor cayeron en líneas
            # distintas) o >=6 números (esta línea es la regla de una
            # gráfica de barras, que trae 8-11 valores) -- en ambos casos,
            # el valor real está en una de las siguientes líneas. El corte
            # es 6 (no 4) porque una línea contaminada con la columna
            # vecina puede traer 4-5 números sueltos sin ser una regla de
            # verdad -- con 4 se confundía y agarraba el valor de la
            # columna de al lado en vez de dejar la etiqueta sin match.
            if not nums or len(nums) >= 6:
                for j in (i + 1, i + 2):
                    if j < len(lineas):
                        nums_sig = _numeros(lineas[j])
                        if nums_sig:
                            return _a_float(_elige(nums_sig, primero, preferir_decimal))
                continue
            if nums:
                return _a_float(_elige(nums, primero, preferir_decimal))
    return None


_HEADER_RE = re.compile(
    r"(\d{4,6}-\d+|\d{7,12})\s+"        # ID de perfil (con o sin guion, según el modelo)
    r"(\d{2,3}(?:\.\d+)?)\s*(cm|in|\")\s+"  # altura, cm (normal) o in/" (reporte en unidades imperiales)
    r"(\d{1,3})\s+"                     # edad
    r"(Femenino|Masculino|Female|Male)[^0-9\n]{0,15}"  # sexo, ES o EN (a veces sigue un "|" suelto del OCR)
    r"(\d{2}\.\d{2}\.\d{4}|\d{4}\.\d{2}\.\d{2})",  # fecha, DD.MM.AAAA o AAAA.MM.DD según el modelo
    re.IGNORECASE,
)

_SEXO_A_ESPANOL = {"femenino": "Femenino", "female": "Femenino", "masculino": "Masculino", "male": "Masculino"}

_LB_A_KG = 0.453592
_IN_A_CM = 2.54

# Rangos humanamente posibles -- un valor fuera de esto es casi siempre
# basura del OCR (agarró un número de otra parte del reporte), no un dato
# real. Se usa como última red de seguridad antes de regresar los campos.
_RANGOS_PLAUSIBLES = {
    "altura_cm": (100, 220),
    "edad": (5, 110),
    "peso_kg": (20, 250),
    "masa_grasa_kg": (1, 150),
    "mme_kg": (5, 80),
    "grasa_visceral": (1, 30),
    "agua_total_l": (10, 80),
    "agua_intra_l": (5, 60),
    "agua_extra_l": (2, 30),
    "imc": (10, 70),
    "pgc_pct": (2, 70),
}


def _normaliza_fecha(fecha_cruda: str) -> str:
    """Algunos modelos de InBody imprimen la fecha AAAA.MM.DD en vez de
    DD.MM.AAAA -- se detecta por cuál de los tres grupos trae 4 dígitos, y
    se normaliza siempre a DD.MM.AAAA (el formato que usa el resto de la app)."""
    partes = fecha_cruda.rstrip(".").split(".")
    if len(partes[0]) == 4:
        return f"{partes[2]}.{partes[1]}.{partes[0]}"
    return fecha_cruda


def parse_inbody_text(texto: str) -> dict:
    """Extrae los campos más relevantes. Cualquier campo que no se
    encuentre con confianza queda en None -- se muestra vacío en el
    formulario de revisión, nunca se inventa un valor."""
    lineas = texto.splitlines()

    # La fila de ID/Altura/Edad/Sexo/Fecha suele salir del OCR como una
    # sola línea muy limpia y en un orden fijo -- se intenta como grupo
    # primero porque es mucho más confiable que buscar cada campo por su
    # cuenta (que puede agarrar el número equivocado si el OCR separa las
    # columnas de forma rara). Si no hace match (otro modelo/diseño de
    # reporte), se cae al método campo por campo de antes.
    # Algunos reportes de InBody salen en inglés (p. ej. exportados desde
    # el portal web LookinBody, en vez de impresos del aparato) en lugar de
    # español -- todos los patrones de abajo aceptan ambos idiomas.
    header_m = _HEADER_RE.search(texto)
    if header_m:
        perfil_id_val = header_m.group(1)
        altura = _a_float(header_m.group(2))
        if altura is not None and header_m.group(3) != "cm":
            altura = round(altura * _IN_A_CM, 1)  # in o " -> cm
        edad_val = int(header_m.group(4))
        sexo_val = _SEXO_A_ESPANOL.get(header_m.group(5).lower())
        fecha_val = _normaliza_fecha(header_m.group(6))
    else:
        perfil_id = re.search(r"\b(\d{4,6}-\d+|\d{7,12})\b", texto)
        perfil_id_val = perfil_id.group(1) if perfil_id else None
        altura_m = re.search(r"\b(\d{2,3}(?:\.\d+)?)\s*(cm|in|\")\b", texto, re.IGNORECASE)
        altura = None
        if altura_m:
            altura = _a_float(altura_m.group(1))
            if altura is not None and altura_m.group(2) != "cm":
                altura = round(altura * _IN_A_CM, 1)
        edad_bruta = _valor_de_fila(lineas, r"^(Edad|Age)\b")
        edad_val = int(edad_bruta) if edad_bruta is not None else None
        sexo_m = re.search(r"\b(Femenino|Masculino|Female|Male)\b", texto, re.IGNORECASE)
        sexo_val = _SEXO_A_ESPANOL.get(sexo_m.group(1).lower()) if sexo_m else None
        fecha_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", texto)
        fecha_val = fecha_m.group(1) if fecha_m else None

    modelo_m = re.search(r"\[?(InBody\s?\d{2,4})\]?", texto, re.IGNORECASE)

    # Reporte en unidades imperiales (poco común, pero puede pasar con
    # cuentas configuradas así) -- se detecta por "(lb)"/"(lbs)" junto a
    # alguna etiqueta de peso, y se convierte a kg al final. Sin probar
    # contra un reporte real así -- si algo no cuadra, avisar para ajustar.
    usa_libras = bool(re.search(r"\((?:lbs?)\)", texto, re.IGNORECASE))

    # "(kg)" a veces sale mal leído (p. ej. "(9)" o "(ka)") -- se busca solo
    # la etiqueta al inicio de línea, sin exigir la unidad literal.
    # preferir_decimal=True porque estas filas a veces vienen contaminadas
    # con números enteros sueltos de la columna vecina.
    peso = _valor_de_fila(lineas, r"^(Peso|Weight)\b(?!\s*Control)", preferir_decimal=True)
    mme = _valor_de_fila(lineas, r"\b(MME|SMM)\b", preferir_decimal=True)
    # Nivel de Grasa Visceral es un entero (no trae decimales) que a veces
    # cae en una línea contaminada con números de la columna vecina -- se
    # busca puntual justo entre "Visceral" y el "(" del rango de referencia
    # ("Nivel de Grasa Visceral 14 ( 1-9 )" / "Visceral Fat Level 6 ( 1-9 )"),
    # en vez del método genérico.
    grasa_visceral_m = re.search(
        r"(?:Grasa\s*Visceral|Visceral\s*Fat\s*Level)\D*?(\d{1,3})\s*\(", texto, re.IGNORECASE,
    )
    grasa_visceral = (
        _a_float(grasa_visceral_m.group(1)) if grasa_visceral_m
        else _valor_de_fila(lineas, r"Nivel\s*de\s*Grasa\s*Visceral|Visceral\s*Fat\s*Level", primero=True)
    )
    # preferir_decimal=True: esta fila casi siempre sale con un número
    # entero de sobra pegado (columna vecina) -- si hay un solo candidato
    # con punto decimal entre los números de la línea, es el correcto.
    # "Total Body Water" en inglés SIEMPRE trae "Total" (a diferencia del
    # español, donde se evita esa fila a propósito porque ahí es la
    # columna, no el renglón) -- se intenta primero el patrón en español y,
    # si no hay resultado, el de inglés por separado.
    agua_total = _valor_de_fila(lineas, r"Agua\s*Corporal\b(?!.*Total)", preferir_decimal=True)
    if agua_total is None:
        agua_total = _valor_de_fila(lineas, r"Total\s*Body\s*Water", preferir_decimal=True)
    # Igual que Agua Extracelular: se busca puntual el número justo antes
    # de la "L" de litros, en vez de confiar en el método genérico (que
    # puede caer en una línea contaminada con la columna vecina).
    agua_intra_m = re.search(
        r"(?:Agua\s*Intracelular|Intracellular\s*Water)\D*?(\d{1,3}(?:[.,]\d+)?)\s*L", texto, re.IGNORECASE,
    )
    agua_intra = (
        _a_float(agua_intra_m.group(1)) if agua_intra_m
        else _valor_de_fila(lineas, r"Agua\s*Intracelular|Intracellular\s*Water", primero=True)
    )
    # Agua Extracelular es justo la fila donde más se pierde el punto
    # decimal en el OCR ("19.0L" leído como "190L") -- en vez de confiar en
    # leerla directo, se calcula: Agua Corporal Total = Intracelular +
    # Extracelular siempre (no es una fila más, es una identidad), y
    # agua_total/agua_intra ya se leen de forma confiable arriba.
    if agua_total is not None and agua_intra is not None and agua_total > agua_intra:
        agua_extra = round(agua_total - agua_intra, 2)
    else:
        agua_extra_m = re.search(
            r"(?:Extracelular|Extracellular\s*Water)\D*?(\d{1,3}(?:[.,]\d+)?)\s*L", texto, re.IGNORECASE,
        )
        agua_extra = (
            _a_float(agua_extra_m.group(1)) if agua_extra_m
            else _valor_de_fila(lineas, r"Agua\s*Extracelular|Extracellular\s*Water", primero=True)
        )
    imc = _valor_de_fila(lineas, r"^(IMC|BMI)\b")
    # primero=True: cuando la línea del valor viene contaminada con la
    # sección de al lado (Grasa Segmental), el valor de PGC queda primero,
    # no al final.
    pgc = _valor_de_fila(lineas, r"^(PGC|PBF)\b", primero=True)

    # La etiqueta de "Masa Grasa Corporal (kg)" en la gráfica de barras es
    # justo la fila que casi siempre se lee peor con OCR -- en vez de
    # buscar la etiqueta (que puede salir irreconocible), se busca la fila
    # de la regla de esa gráfica en particular, que es fija en este modelo.
    # \s* (no \s+) porque a veces el OCR pega dos números de la regla sin
    # espacio entre ellos (p. ej. "220280" en vez de "220 280"); y se
    # revisan dos líneas después de la regla, no solo una, por si la
    # inmediata siguiente sale ilegible (basura sin ningún número).
    masa_grasa = None
    for i, linea in enumerate(lineas):
        if re.search(r"60\s*80\s*100\s*160\s*220\s*280", linea):
            for j in (i + 1, i + 2):
                if j < len(lineas):
                    nums_sig = _numeros(lineas[j])
                    if nums_sig:
                        masa_grasa = _a_float(nums_sig[-1])
                        break
            break

    if usa_libras:
        # Ojo: la regla numérica de la gráfica de Masa Grasa Corporal
        # ("60 80 100...") está calibrada en kg -- en un reporte en libras
        # esos números salen distintos, así que esa detección en particular
        # probablemente no encuentre nada (queda en None) en vez de un
        # valor mal convertido.
        peso = round(peso * _LB_A_KG, 1) if peso is not None else None
        masa_grasa = round(masa_grasa * _LB_A_KG, 1) if masa_grasa is not None else None
        mme = round(mme * _LB_A_KG, 1) if mme is not None else None

    # Si el IMC no se pudo leer (o salió fuera de rango humano, señal de
    # que se agarró basura), se calcula con la fórmula normal en vez de
    # dejarlo vacío -- para esto sí es información real, no una lectura.
    if (imc is None or not (10 <= imc <= 70)) and peso is not None and altura is not None and altura > 0:
        imc = round(peso / (altura / 100) ** 2, 1)

    campos = {
        "id": perfil_id_val,
        "modelo": modelo_m.group(1) if modelo_m else None,
        "altura_cm": altura,
        "edad": edad_val,
        "sexo": sexo_val,
        "fecha": fecha_val,
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

    # Última red de seguridad: un valor físicamente imposible (IMC de 1,
    # peso de 2072 kg) es peor que dejarlo vacío -- si el OCR agarró basura
    # de otra parte del reporte (p. ej. una cifra de kcal), es mejor que se
    # note como campo vacío a que se cuele un número absurdo sin revisar.
    for campo, (minimo, maximo) in _RANGOS_PLAUSIBLES.items():
        valor = campos.get(campo)
        if valor is not None and not (minimo <= valor <= maximo):
            campos[campo] = None

    return campos
