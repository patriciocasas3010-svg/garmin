"""Guarda los reportes de problema/sugerencia que manden las nutriólogas
mientras usan el dashboard -- en la tabla "feedback" de Postgres, igual
que notas_store.py. Pensado para el piloto de 250 pacientes: cualquier
fricción real se captura ahí mismo, sin salir de la app ni depender de
un formulario externo."""

from datetime import datetime

import sqlalchemy


def guardar(engine: sqlalchemy.engine.Engine, usuario: str, paciente: str, mensaje: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("INSERT INTO feedback (fecha, usuario, paciente, mensaje) VALUES (:fecha, :usuario, :paciente, :mensaje)"),
            {
                "fecha": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "usuario": usuario, "paciente": paciente or "", "mensaje": mensaje,
            },
        )
