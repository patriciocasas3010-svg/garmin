"""Biblioteca de recetas de AURA (tabla "recetas", ver schema.sql) --
antes de pedirle a Claude que invente "ideas de alimentos" desde cero,
ai_analisis.py primero busca aquí recetas ya aprobadas que le queden al
perfil del paciente, y se las pasa como opciones reales. Claude elige y
adapta de esa lista primero; solo complementa con su propio conocimiento
si la biblioteca no tiene nada que aplique -- así el "cerebro de
recetas" vive en nuestra base, no solo en lo que el modelo ya sabía.

_tags_desde_perfil() es una primera versión de mapear el enfoque/condición
del paciente a tags de receta -- ajustar esta lógica en cuanto haya
recetas reales etiquetadas y se vea qué combinaciones hacen falta de
verdad."""

import sqlalchemy


def _tags_desde_perfil(enfoque: str | None, condicion_metabolica: str | None, glp1_molecula: str | None) -> list[str]:
    tags: list[str] = []
    e = (enfoque or "").lower()
    if "pérdida de peso" in e or "perdida de peso" in e:
        tags += ["perdida_peso", "bajo_en_calorias"]
    elif "ganancia muscular" in e:
        tags += ["ganancia_muscular", "alto_en_proteina"]
    elif "rendimiento deportivo" in e or "atleta" in e:
        tags += ["rendimiento", "alto_en_proteina", "pre_entreno"]
    elif "condición médica" in e or "condicion medica" in e:
        tags += ["condicion_medica"]
    elif "mantenimiento" in e:
        tags += ["mantenimiento"]

    cm = (condicion_metabolica or "").lower()
    if "diabetes" in cm or "prediabetes" in cm:
        tags.append("diabetes")

    if glp1_molecula and glp1_molecula != "No usa":
        tags.append("glp1")

    return tags


def buscar_compatibles(
    engine: sqlalchemy.engine.Engine, enfoque: str | None, condicion_metabolica: str | None = None,
    glp1_molecula: str | None = None, limit: int = 15,
) -> list[dict]:
    """Recetas aprobadas cuyos tags_clinicos/tags_deportivos/tags_conductuales
    se traslapan con lo que sugiere el perfil del paciente -- solo
    recetas con estado='aprobada' (nunca una en borrador, sin revisar
    por un nutriólogo, le llega a un paciente). Lista vacía si la
    biblioteca todavía no tiene nada que aplique (o está vacía) -- no es
    un error, ai_analisis.py ya sabe seguir sin ella."""
    tags = _tags_desde_perfil(enfoque, condicion_metabolica, glp1_molecula)
    if not tags:
        return []
    with engine.connect() as conn:
        filas = conn.execute(
            sqlalchemy.text("""
                SELECT id, nombre, ingredientes, kcal, proteina_g, carbohidratos_g, grasa_g, tipo_comida,
                       cocina, tags_clinicos, tags_deportivos, tags_conductuales, tags_culturales, sustituciones
                FROM recetas
                WHERE estado = 'aprobada'
                  AND (tags_clinicos && :tags OR tags_deportivos && :tags OR tags_conductuales && :tags)
                LIMIT :limit
            """),
            {"tags": tags, "limit": limit},
        ).all()
    columnas = [
        "id", "nombre", "ingredientes", "kcal", "proteina_g", "carbohidratos_g", "grasa_g", "tipo_comida",
        "cocina", "tags_clinicos", "tags_deportivos", "tags_conductuales", "tags_culturales", "sustituciones",
    ]
    return [dict(zip(columnas, fila)) for fila in filas]
