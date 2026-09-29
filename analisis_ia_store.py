"""Cuota mensual de "Generar análisis" (ai_analisis.py) por nutriólogo --
Claude lo paga AURA de forma centralizada con un solo Secret
ANTHROPIC_API_KEY (ver ai_analisis.py), así que cada usuario tiene un
número definido de análisis al mes, no acceso ilimitado. El número
default (LIMITE_DEFAULT) es el mismo supuesto que se usó para
presupuestar el costo de Claude (~20 pacientes x 2 análisis/mes) -- se
puede ajustar por usuario en la columna usuarios.limite_analisis_mes."""

import sqlalchemy

LIMITE_DEFAULT = 40


def limite_para(engine: sqlalchemy.engine.Engine, usuario: str) -> int:
    with engine.connect() as conn:
        fila = conn.execute(
            sqlalchemy.text("SELECT limite_analisis_mes FROM usuarios WHERE usuario = :u"),
            {"u": usuario},
        ).first()
    if fila is not None and fila[0] is not None:
        return fila[0]
    return LIMITE_DEFAULT


def uso_este_mes(engine: sqlalchemy.engine.Engine, usuario: str) -> int:
    with engine.connect() as conn:
        fila = conn.execute(
            sqlalchemy.text("""
                SELECT COUNT(*) FROM uso_analisis_ia
                WHERE usuario = :u AND date_trunc('month', fecha) = date_trunc('month', now())
            """),
            {"u": usuario},
        ).first()
    return fila[0] if fila else 0


def puede_generar(engine: sqlalchemy.engine.Engine, usuario: str) -> tuple[bool, int, int]:
    """(puede, usados_este_mes, limite) -- lo que necesita la pantalla
    para decidir si deja generar y qué mensaje mostrar."""
    limite = limite_para(engine, usuario)
    usados = uso_este_mes(engine, usuario)
    return usados < limite, usados, limite


def registrar_uso(engine: sqlalchemy.engine.Engine, usuario: str, paciente: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("INSERT INTO uso_analisis_ia (usuario, paciente) VALUES (:u, :p)"),
            {"u": usuario, "p": paciente},
        )
