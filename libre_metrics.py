"""Lee glucosa de FreeStyle Libre vía LibreLinkUp, usando la librería de
comunidad `pylibrelinkup` (Abbott no tiene una API pública oficial -- es
la misma situación que garminconnect con Garmin: no oficial, reconstruida
por ingeniería inversa, puede dejar de funcionar si Abbott cambia algo).

A diferencia de Garmin/Oura/Apple (donde cada paciente conecta SU PROPIA
cuenta), aquí funciona al revés: el paciente usa la app LibreLinkUp para
compartir su glucosa contigo como "seguidor" (agregándote con tu correo,
como se comparte con un familiar/cuidador) -- así que quien inicia
sesión aquí es LA CUENTA DEL NUTRIÓLOGO (una sola vez, vía Secrets de
Streamlit), y desde ahí se puede leer la glucosa de TODOS los pacientes
que hayan compartido con ella, no una cuenta por paciente.

Requiere el paquete `pylibrelinkup` (ver requirements.txt) y los Secrets
LIBRE_EMAIL / LIBRE_PASSWORD en Streamlit Cloud -- si no están
configurados, las funciones de aquí lanzan RuntimeError con un mensaje
claro en vez de tronar feo (igual que ai_analisis.generar_analisis con
ANTHROPIC_API_KEY).

NOTA: construido contra la documentación pública de pylibrelinkup, sin
poder probarlo contra una cuenta real de LibreLinkUp todavía -- si algo
no calza exactamente con lo que regresa la librería (nombres de campos,
etc.), avisa con el mensaje de error exacto para ajustarlo."""

RANGO_BAJO_MG_DL = 70
RANGO_ALTO_MG_DL = 180


def conectar(email: str, password: str):
    """Inicia sesión con la cuenta de LibreLinkUp del nutriólogo (la que
    sigue a sus pacientes) -- se hace una sola vez por sesión, no una vez
    por paciente."""
    try:
        from pylibrelinkup import PyLibreLinkUp
    except ImportError:
        raise RuntimeError(
            "Falta instalar el paquete pylibrelinkup (revisa requirements.txt)."
        )

    if not email or not password:
        raise RuntimeError(
            "Faltan configurar los Secrets LIBRE_EMAIL y LIBRE_PASSWORD en Streamlit Cloud "
            "(Settings -> Secrets) -- son el correo y contraseña de TU cuenta de LibreLinkUp "
            "(la que usas para seguir a tus pacientes), no la de ellos."
        )

    client = PyLibreLinkUp(email=email, password=password)
    try:
        client.authenticate()
    except Exception as e:
        raise RuntimeError(
            f"No se pudo iniciar sesión en LibreLinkUp: {e}. Revisa que LIBRE_EMAIL/LIBRE_PASSWORD "
            "sean correctos y que tu cuenta ya tenga al menos un paciente compartiendo contigo."
        )
    return client


def listar_pacientes(client) -> list[dict]:
    """Todos los pacientes que comparten su glucosa contigo -- cada uno
    como {"id": ..., "nombre": ...} para mostrar en un selector y guardar
    el vínculo con el nombre que usas en este dashboard (ver
    libre_store.py)."""
    try:
        pacientes = client.get_patients()
    except Exception as e:
        raise RuntimeError(f"No se pudo obtener la lista de pacientes de LibreLinkUp: {e}")

    resultado = []
    for p in pacientes:
        nombre = getattr(p, "nombre", None) or getattr(p, "name", None) or str(p)
        identificador = getattr(p, "patient_id", None) or getattr(p, "id", None) or p
        resultado.append({"id": identificador, "nombre": nombre, "objeto": p})
    return resultado


def build_glucosa_data(client, patient_identifier) -> dict:
    """Lectura actual + últimas ~12h (graph) de un paciente en concreto,
    ya resumidas: promedio, % de tiempo en rango (70-180 mg/dL, rangos
    clínicos estándar -- ajustables si el nutriólogo lo pide), y conteo
    de picos altos/bajos."""
    try:
        lectura_actual = client.latest(patient_identifier=patient_identifier)
    except Exception:
        lectura_actual = None

    try:
        serie_graph = client.graph(patient_identifier=patient_identifier) or []
    except Exception as e:
        raise RuntimeError(f"No se pudo leer la gráfica de glucosa: {e}")

    valores = [m.value for m in serie_graph if getattr(m, "value", None) is not None]
    serie = {
        m.timestamp.isoformat(): m.value
        for m in serie_graph
        if getattr(m, "value", None) is not None and getattr(m, "timestamp", None) is not None
    }

    promedio = sum(valores) / len(valores) if valores else None
    en_rango = sum(1 for v in valores if RANGO_BAJO_MG_DL <= v <= RANGO_ALTO_MG_DL)
    pct_en_rango = (en_rango / len(valores) * 100) if valores else None
    picos_altos = sum(1 for v in valores if v > RANGO_ALTO_MG_DL)
    picos_bajos = sum(1 for v in valores if v < RANGO_BAJO_MG_DL)

    return {
        "glucosa_actual": getattr(lectura_actual, "value", None),
        "glucosa_promedio_12h": promedio,
        "pct_tiempo_en_rango_12h": pct_en_rango,
        "picos_altos_12h": picos_altos,
        "picos_bajos_12h": picos_bajos,
        "num_lecturas_12h": len(valores),
        "serie_12h": serie,
    }
