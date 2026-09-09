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
Médico PROA), Laboratorio Clínico RIO. El estado (bajo/normal/alto) no
se lee de ningún ícono o columna de color del PDF -- se calcula
comparando el resultado contra el rango de referencia impreso, que es
lo mismo que hace el laboratorio para poner su propio ícono, así que da
el mismo resultado."""

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
# Laboratorio Clínico RIO
# ---------------------------------------------------------------------------
#
# El PDF de RIO trae, para cada prueba, un renglón "Nombre  valor  unidad
# rango" pegado al margen izquierdo (4 espacios de sangría) -- pero varias
# pruebas (Glucosa, Ácido Úrico, Creatinina, Colesterol, HbA1C, Vitamina D,
# PCR...) traen una minigráfica o una tabla de categorías de riesgo (Ideal/
# Límite Alto/Alto, Sin Riesgo/Riesgo Medio/Riesgo Alto, etc.) en vez de un
# rango simple "min - max", y esa tabla queda impresa en renglones aparte,
# sangrados mucho más a la derecha (alineados bajo la columna REFERENCIA).
# Esa diferencia de sangría es la señal que se usa para distinguir "aquí
# empieza una prueba nueva" de "esto es parte de la tabla de la prueba
# anterior". El nombre de la prueba a veces se corta a la mitad por texto
# largo y su cierre de paréntesis cae en el siguiente renglón (ej. "(TGO /
# AST)") -- eso se vuelve a pegar al nombre porque cruces_clinicos.py
# necesita esas siglas para reconocer la prueba.

_VALOR_RIO_RE = re.compile(r"(?<![\w.,])(?:[<>]=?\s*)?\d+(?:[.,]\d+)?(?=\s|$)")

_HEADER_RIO_PREFIXES = (
    "Paciente | Patient:",
    "Estudio | Test:",
    "Referido por | Refered by:",
    "Institución | Institution:",
)
_STOP_RIO_PREFIXES = (
    "Método:",
    "Tipo de muestra:",
    "Fecha de toma de muestra:",
    "Observaciones:",
    "OBSERVACION",
)


def _es_rio(texto: str) -> bool:
    return "F.N. | DOB:" in texto and "ESTUDIO ACREDITADO" in texto


def _ruido_rio(linea: str) -> bool:
    l = linea.strip()
    if not l:
        return True
    if l.startswith(_HEADER_RIO_PREFIXES):
        return True
    if re.match(r"^EXAMEN\s+RESULTADO\s+UNIDADES\s+REFERENCIA", l):
        return True
    if "RESULTADO FUERA DE RANGO" in l or "RESULTADO CRÍTICO" in l or "ESTUDIO ACREDITADO" in l:
        return True
    if re.match(r"^Página\s+\d+\s+de\s+\d+$", l):
        return True
    return False


def _inicio_fila_rio(linea: str) -> re.Match | None:
    """None si la línea está sangrada de más (>8 espacios) -- ahí solo
    viven las tablas de categorías de riesgo, nunca una prueba nueva."""
    sangria = len(linea) - len(linea.lstrip(" "))
    if sangria > 8:
        return None
    return _VALOR_RIO_RE.search(linea)


def _continuacion_nombre_rio(linea: str) -> str | None:
    l = linea.strip()
    if not l or any(ch.isdigit() for ch in l):
        return None
    if l.startswith("("):
        idx = l.find(")")
        return l[: idx + 1] if idx != -1 else None
    if l.endswith(")"):
        return l
    return None


def _rango_generico_rio(texto: str) -> tuple[float | None, float | None]:
    compacto = " ".join(texto.split())
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)", compacto)
    if m:
        return _a_float(m.group(1)), _a_float(m.group(2))
    m = re.search(r"Menor de\s*(\d+(?:[.,]\d+)?)", compacto, re.I)
    if m:
        return None, _a_float(m.group(1))
    m = re.search(r"Mayor de\s*(\d+(?:[.,]\d+)?)", compacto, re.I)
    if m:
        return _a_float(m.group(1)), None
    return None, None


def _numero_tras_etiqueta_rio(etiqueta: str, texto: str) -> float | None:
    compacto = " ".join(texto.split())
    m = re.search(re.escape(etiqueta) + r"\s*[:]?\s*[<>]=?\s*(\d+(?:[.,]\d+)?)", compacto, re.I)
    return _a_float(m.group(1)) if m else None


def _rango_multitier_rio(nombre: str, sexo: str | None, texto: str) -> tuple[float | None, float | None] | None:
    """Para las pruebas que en vez de un rango simple traen una tabla de
    categorías de riesgo -- se usa la categoría "buena" (Ideal/Óptimo/Sin
    Riesgo/Suficiencia/Riesgo Bajo) como si fuera el rango de referencia,
    para no perder estas pruebas (varias son clínicamente clave: LDL,
    triglicéridos, PCR...). Ninguna otra prueba de este laboratorio
    necesita esto, así que se resuelve por nombre en vez de tratar de
    generalizar el formato de la tabla."""
    low = nombre.lower()
    if "colesterol total" in low:
        v = _numero_tras_etiqueta_rio("Ideal", texto)
        return (None, v) if v is not None else None
    if "alta densidad" in low or "hdl" in low:
        compacto = " ".join(texto.split())
        if sexo == "M":
            m = re.search(r"Hombre:(.*)", compacto, re.I)
        else:
            m = re.search(r"Mujer:(.*?)(?:Hombre:|$)", compacto, re.I)
        bloque = m.group(1) if m else texto
        v = _numero_tras_etiqueta_rio("Sin Riesgo", bloque)
        return (v, None) if v is not None else None
    if "baja densidad" in low and "muy baja" not in low:
        v = _numero_tras_etiqueta_rio("Óptimo", texto)
        return (None, v) if v is not None else None
    if "reactiva" in low:
        v = _numero_tras_etiqueta_rio("Riesgo Bajo", texto)
        return (None, v) if v is not None else None
    if "vitamina d" in low:
        vmin = _numero_tras_etiqueta_rio("Suficiencia", texto)
        vmax = _numero_tras_etiqueta_rio("Exceso", texto)
        return (vmin, vmax) if (vmin is not None or vmax is not None) else None
    return None


def _parse_rio(texto: str) -> list[dict]:
    m_sexo = re.search(r"Sexo \| Sex:\s*([A-Za-z])", texto)
    sexo = m_sexo.group(1).upper() if m_sexo else None

    lineas = texto.splitlines()
    n = len(lineas)
    filas = []
    i = 0
    while i < n:
        linea = lineas[i]
        if _ruido_rio(linea) or linea.strip().startswith(_STOP_RIO_PREFIXES):
            i += 1
            continue

        m = _inicio_fila_rio(linea)
        if not m:
            i += 1
            continue
        nombre = linea[: m.start()].strip()
        if len(nombre) < 3 or nombre.endswith("-"):
            i += 1
            continue

        valor = m.group().replace(" ", "")
        resto = linea[m.end():].strip()
        tokens = resto.split(None, 1)
        es_numero_o_rango = bool(tokens) and (tokens[0][0].isdigit() or tokens[0][0] in "<>-–")
        if tokens and not es_numero_o_rango:
            unidad = tokens[0]
            resto_cola = tokens[1] if len(tokens) > 1 else ""
        else:
            unidad = None
            resto_cola = resto

        extra = [resto_cola] if resto_cola else []
        j = i + 1
        while j < n:
            siguiente = lineas[j]
            if siguiente.strip().startswith(_STOP_RIO_PREFIXES):
                break
            if not _ruido_rio(siguiente):
                m2 = _inicio_fila_rio(siguiente)
                if m2 and len(siguiente[: m2.start()].strip()) >= 3:
                    break
            if _ruido_rio(siguiente):
                j += 1
                continue
            fragmento = _continuacion_nombre_rio(siguiente)
            if fragmento is not None:
                nombre = f"{nombre} {fragmento}"
            else:
                extra.append(siguiente)
            j += 1
        i = j

        texto_extra = "\n".join(extra)
        rango = _rango_multitier_rio(nombre, sexo, texto_extra)
        rango_min, rango_max = rango if rango is not None else _rango_generico_rio(texto_extra)

        filas.append({
            "prueba": nombre,
            "resultado": valor,
            "unidad": unidad,
            "rango_min": rango_min,
            "rango_max": rango_max,
            "estado": _calcular_estado(valor, rango_min, rango_max),
        })
    return filas


def _fecha_rio(texto: str) -> str | None:
    return _fecha_normalizada(texto, r"Fecha de toma de muestra:\s*(\d{1,2}/\d{1,2}/\d{4})")


# ---------------------------------------------------------------------------

_LABORATORIOS = [
    ("SYNLAB/MédicaSur", _es_synlab, _parse_synlab, _fecha_synlab),
    ("Chopo", _es_chopo, _parse_chopo, _fecha_chopo),
    ("Laboratorio Clínico RIO", _es_rio, _parse_rio, _fecha_rio),
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
