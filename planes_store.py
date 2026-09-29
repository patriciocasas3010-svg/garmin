"""Guarda y aprueba los planes nutricionales (tabla "planes_nutricionales"
+ "plan_recetas", ver schema.sql) -- el flujo es: plan_nutricional.py
sugiere macros -> el nutriólogo los ajusta si quiere -> crear_borrador()
guarda el plan con las recetas de la biblioteca que apliquen -> el
nutriólogo revisa y aprobar_plan() lo pasa a "aprobado". Nunca se salta
ese último paso -- un plan en "borrador" es solo una propuesta, no algo
que ya se le compartió al paciente."""

import sqlalchemy


def crear_borrador(
    engine: sqlalchemy.engine.Engine, paciente: str, macros: dict, receta_ids: list[int],
    notas: str, creado_por: str,
) -> int:
    with engine.begin() as conn:
        plan_id = conn.execute(
            sqlalchemy.text("""
                INSERT INTO planes_nutricionales
                    (nombre, kcal_objetivo, proteina_g_objetivo, carbohidratos_g_objetivo,
                     grasa_g_objetivo, notas, estado, creado_por)
                VALUES (:nombre, :kcal, :proteina, :carbos, :grasa, :notas, 'borrador', :creado_por)
                RETURNING id
            """),
            {
                "nombre": paciente, "kcal": macros.get("kcal_objetivo"),
                "proteina": macros.get("proteina_g_objetivo"), "carbos": macros.get("carbohidratos_g_objetivo"),
                "grasa": macros.get("grasa_g_objetivo"), "notas": notas, "creado_por": creado_por,
            },
        ).scalar_one()
        for receta_id in receta_ids:
            conn.execute(
                sqlalchemy.text("""
                    INSERT INTO plan_recetas (nombre, receta_id, plan_id)
                    VALUES (:nombre, :receta_id, :plan_id)
                """),
                {"nombre": paciente, "receta_id": receta_id, "plan_id": plan_id},
            )
    return plan_id


def aprobar_plan(engine: sqlalchemy.engine.Engine, plan_id: int, aprobado_por: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("""
                UPDATE planes_nutricionales
                SET estado = 'aprobado', aprobado_por = :aprobado_por, fecha_aprobacion = now()
                WHERE id = :plan_id
            """),
            {"plan_id": plan_id, "aprobado_por": aprobado_por},
        )


def leer_ultimo_plan(engine: sqlalchemy.engine.Engine, paciente: str) -> dict | None:
    """El plan más reciente de este paciente (borrador o aprobado), con
    los nombres de las recetas que trae -- None si nunca se le creó uno."""
    with engine.connect() as conn:
        fila = conn.execute(
            sqlalchemy.text("""
                SELECT id, fecha, kcal_objetivo, proteina_g_objetivo, carbohidratos_g_objetivo,
                       grasa_g_objetivo, notas, estado, creado_por, aprobado_por, fecha_aprobacion
                FROM planes_nutricionales
                WHERE nombre = :nombre
                ORDER BY fecha DESC
                LIMIT 1
            """),
            {"nombre": paciente},
        ).first()
        if fila is None:
            return None
        plan = dict(fila._mapping)
        recetas = conn.execute(
            sqlalchemy.text("""
                SELECT r.id, r.nombre, r.tipo_comida, r.kcal, r.proteina_g
                FROM plan_recetas pr JOIN recetas r ON r.id = pr.receta_id
                WHERE pr.plan_id = :plan_id AND pr.activa
            """),
            {"plan_id": plan["id"]},
        ).all()
        plan["recetas"] = [dict(r._mapping) for r in recetas]
    return plan
