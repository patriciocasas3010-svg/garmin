"""Lee un PDF de estudios clínicos de sangre/orina y extrae cada prueba
con su resultado, unidad, rango de referencia y si salió bajo/normal/alto.

A diferencia de la primera versión de este archivo, esto NO usa la API
de Claude (tiene costo, y se decidió no usarla para esto) -- en vez de
eso, cada laboratorio conocido tiene su propio lector con expresiones
regulares, igual que antropometria_parser.py (el PDF trae texto real,
no es una foto, así que no hace falta OCR). Es gratis, pero solo
funciona con los laboratorios que ya se agregaron aquí -- si llega un
PDF de un laboratorio nuevo, hay que mandarlo para agregar su lector.

Laboratorios soportados: SYNLAB/MédicaSur, Chopo (Grupo Diagnóstico
Médico PROA). El estado (bajo/normal/alto) no se lee de ningún ícono o
columna de color del PDF -- se calcula comparando el resultado contra
el rango de referencia impreso, que es lo mismo que hace el laboratorio
para poner su propio ícono, así que da el mismo resultado."""

import io
import re

import pdfplumber


def extract_text(pdf_bytes: bytes) -> str:
    """Extrae el texto de un PDF con texto real, conservando el orden por
    columnas/renglones (layout=True) -- usa pdfplumber (paquete de Python
    normal vía pip), no la herramienta pdftotext del sistema, para no
    depender de apt-get -- mismo mecanismo que antropometria_parser.py."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(pagina.extract_text(layout=True) or "" for pagina in pdf.pages)


def _a_float(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r"-?\d+(?:[.,]\d+)?", s)
    if not m:
        return None
    return float(m.group().replace(",", "."))


def _parsear_rango(rango: str | None) -> tuple[float | None, float | None]:
    if not rango:
        return None, None
    rango = rango.strip()
    m = re.match(r"^(-?\d+(?:[.,]\d+)?)\s*[-–]\s*(-?\d+(?:[.,]\d+)?)$", rango)
    if m:
        return _a_float(m.group(1)), _a_float(m.group(2))
    if rango.startswith(">="):
        return _a_float(rango[2:]), None
    if rango.startswith("<="):
        return None, _a_float(rango[2:])
    if rango.startswith(">"):
        return _a_float(rango[1:]), None
    if rango.startswith("<"):
        return None, _a_float(rango[1:])
    return None, None


def _calcular_estado(resultado: str, rango_min: float | None, rango_max: float | None) -> str:
    valor = _a_float(resultado)
    if valor is None or (rango_min is None and rango_max is None):
        return "sin_dato"
    if rango_min is not None and valor < rango_min:
        return "bajo"
    if rango_max is not None and valor > rango_max:
        return "alto"
    return "normal"


def _fila(prueba: str, resultado: str, unidad: str | None, rango: str | None) -> dict:
    rango_min, rango_max = _parsear_rango(rango)
    return {
        "prueba": prueba.strip(),
        "resultado": resultado.strip(),
        "unidad": (unidad or "").strip() or None,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "estado": _calcular_estado(resultado, rango_min, rango_max),
    }


def _fecha_normalizada(texto: str, *patrones: str) -> str | None:
    for patron in patrones:
        m = re.search(patron, texto)
        if m:
            return m.group(1).replace("/", ".")
    return None


# ---------------------------------------------------------------------------
# SYNLAB / MédicaSur
# ---------------------------------------------------------------------------

_FILA_SYNLAB_RE = re.compile(
    r"^[ ]*(?P<nombre>[A-Za-zÁÉÍÓÚÑáéíóúñ][^\n]*?)[ ]{2,}"
    r"(?P<valor>[<>]=?[ ]*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)[ ]{2,}"
    r"(?P<resto>\S.*\S)[ ]*$"
)
_RANGO_TOKEN_RE = re.compile(r"^[<>]=?[ ]*\d|^\d+(?:[.,]\d+)?[ ]*-[ ]*\d")


def _es_synlab(texto: str) -> bool:
    return "SYNLAB" in texto


def _parse_synlab(texto: str) -> list[dict]:
    filas = []
    for linea in texto.splitlines():
        if linea.strip().startswith("_"):
            continue
        m = _FILA_SYNLAB_RE.match(linea)
        if not m:
            continue
        nombre = m.group("nombre").strip()
        if nombre.endswith(":") or len(nombre) < 3:
            continue
        resto = m.group("resto").strip()
        tokens = [t.strip() for t in re.split(r"[ ]{2,}", resto) if t.strip()]
        if tokens and tokens[-1].upper() == "LMS":
            tokens = tokens[:-1]
        rango = unidad = None
        for t in tokens:
            if _RANGO_TOKEN_RE.match(t):
                rango = t
            elif unidad is None:
                unidad = t
        filas.append(_fila(nombre, m.group("valor"), unidad, rango))
    return filas


def _fecha_synlab(texto: str) -> str | None:
    return _fecha_normalizada(texto, r"FECHA TOMA MUESTRA:\s*(\d{1,2}/\d{1,2}/\d{4})")


# ---------------------------------------------------------------------------
# Chopo (Grupo Diagnóstico Médico PROA)
# ---------------------------------------------------------------------------

_FILA_CHOPO_RE = re.compile(
    r"^[ ]*(?P<nombre>[A-Za-zÁÉÍÓÚÑáéíóúñ][^\n]*?)[ ]{2,}"
    r"(?P<valor>[<>]=?[ ]*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)[ ]{1,}"
    r"(?P<resto>\S.*\S)[ ]*$"
)
_RANGO_CON_UNIDAD_RE = re.compile(
    r"^(?P<rango>(?:[<>]=?[ ]*)?\d+(?:[.,]\d+)?(?:[ ]*[-–][ ]*\d+(?:[.,]\d+)?)?)[ ]*(?P<unidad>.*)$"
)


def _es_chopo(texto: str) -> bool:
    return "chopo" in texto.lower() or "GRUPO DIAGNÓSTICO MÉDICO PROA" in texto


def _parse_chopo(texto: str) -> list[dict]:
    filas = []
    for linea in texto.splitlines():
        m = _FILA_CHOPO_RE.match(linea)
        if not m:
            continue
        nombre = m.group("nombre").strip()
        if nombre.endswith(":") or len(nombre) < 3:
            continue
        resto = m.group("resto").strip()
        if resto == "___":
            continue
        m2 = _RANGO_CON_UNIDAD_RE.match(resto)
        if m2:
            rango, unidad = m2.group("rango").strip(), m2.group("unidad").strip() or None
        else:
            rango, unidad = None, resto or None
        filas.append(_fila(nombre, m.group("valor"), unidad, rango))
    return filas


def _fecha_chopo(texto: str) -> str | None:
    return _fecha_normalizada(
        texto,
        r"Fecha de toma:\s*(\d{1,2}/\d{1,2}/\d{4})",
        r"Fecha de Registro:\s*(\d{1,2}/\d{1,2}/\d{4})",
    )


# ---------------------------------------------------------------------------

_LABORATORIOS = [
    ("SYNLAB/MédicaSur", _es_synlab, _parse_synlab, _fecha_synlab),
    ("Chopo", _es_chopo, _parse_chopo, _fecha_chopo),
]


def extraer_estudio(pdf_bytes: bytes) -> dict:
    """Regresa {"fecha": ..., "laboratorio": ..., "resultados": [...]}.
    Lanza RuntimeError con un mensaje claro si el PDF no es de ninguno de
    los laboratorios ya soportados -- quien lo llama decide cómo
    mostrarlo (ver dashboard_pacientes.py)."""
    texto = extract_text(pdf_bytes)

    for nombre, es_de_este_lab, parsear, sacar_fecha in _LABORATORIOS:
        if es_de_este_lab(texto):
            resultados = parsear(texto)
            if not resultados:
                raise RuntimeError(
                    f"Se reconoció el formato de {nombre}, pero no se pudo leer ninguna prueba -- "
                    "puede que el PDF venga distinto a lo esperado. Avisa para revisarlo."
                )
            return {"fecha": sacar_fecha(texto), "laboratorio": nombre, "resultados": resultados}

    raise RuntimeError(
        "Este PDF no es de ningún laboratorio que ya sepamos leer (por ahora: SYNLAB/MédicaSur, "
        "Chopo). Mándalo para agregar su formato."
    )
