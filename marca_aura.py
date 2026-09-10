"""Qué identidad de marca (AURA Clinical / AURA Flow / AURA Health) le
corresponde a un paciente -- calculada del perfil que ya se captura en
Notas del paciente (enfoque + condición metabólica/GLP-1), sin pedir
una pregunta nueva. Así cada página de paciente se identifica sola:

  - Health: bariátrico/diabético/GLP-1 -- lo mismo que ya activa la
    pestaña GLP-1 y Diabéticos (ver glp1_diabetes.activo()).
  - Flow: rendimiento deportivo/atleta.
  - Clinical: todo lo demás -- el caso general (pérdida de peso,
    ganancia muscular, mantenimiento, o sin enfoque declarado todavía)."""

import glp1_diabetes

MARCAS = {
    "clinical": {"nombre": "AURA CLINICAL", "tagline": "Human Coherence System", "acento": "#6B8E78"},
    "flow": {"nombre": "AURA FLOW", "tagline": "Coherence for Performance Data", "acento": "#5A6FA8"},
    "health": {"nombre": "AURA HEALTH", "tagline": "Coherencia Metabólica", "acento": "#3E7CB8"},
}


def calcular(perfil: dict | None) -> str:
    """"clinical" / "flow" / "health" -- ver MARCAS para nombre/tagline/acento."""
    perfil = perfil or {}
    if glp1_diabetes.activo(perfil):
        return "health"
    if perfil.get("enfoque") == "Rendimiento deportivo / atleta":
        return "flow"
    return "clinical"
