"""Cruza dos mediciones de InBody en el tiempo para estimar el TDEE real,
la tasa de pérdida de grasa, la retención de masa magra, y proyectar el
peso a un % de grasa objetivo -- ver garmin_dashboard_ui.render_composicion_avanzada.

Densidades energéticas usadas (estimación estándar en recomposición
corporal): tejido graso ~9,400 kcal/kg, masa libre de grasa (músculo,
agua, glucógeno) ~1,800 kcal/kg."""

_KCAL_POR_KG_GRASA = 9400.0
_KCAL_POR_KG_MAGRA = 1800.0


def comparar_periodo(
    dias: int,
    peso_inicial: float, peso_final: float,
    grasa_inicial: float, grasa_final: float,
    kcal_promedio_consumidas: float | None = None,
) -> dict:
    """dias: días entre las dos mediciones de InBody. kcal_promedio_consumidas:
    promedio real de kcal/día en ese periodo (Avena o estimado por ti) --
    si no se da, se omiten TDEE real y déficit/superávit."""
    if dias <= 0:
        raise ValueError("El periodo debe ser mayor a 0 días.")

    delta_peso = peso_final - peso_inicial
    delta_grasa = grasa_final - grasa_inicial
    # Conservación de masa: lo que no es cambio de grasa, es cambio de masa
    # libre de grasa (músculo, agua, glucógeno).
    delta_magra = delta_peso - delta_grasa

    cambio_energia_total = (delta_grasa * _KCAL_POR_KG_GRASA) + (delta_magra * _KCAL_POR_KG_MAGRA)
    cambio_energia_diario = cambio_energia_total / dias

    resultado = {
        "dias": dias,
        "delta_peso_kg": round(delta_peso, 2),
        "delta_grasa_kg": round(delta_grasa, 2),
        "delta_magra_kg": round(delta_magra, 2),
        "tasa_perdida_grasa_kg_semana": round((delta_grasa / dias) * 7, 2),
        "retencion_masa_magra_pct": _retencion_masa_magra(delta_peso, delta_magra),
        "tdee_real": None,
        "deficit_diario_real": None,
    }

    if kcal_promedio_consumidas is not None:
        resultado["tdee_real"] = round(kcal_promedio_consumidas - cambio_energia_diario, 2)
        # Positivo = déficit (quemó más de lo que comió); negativo = superávit.
        resultado["deficit_diario_real"] = round(-cambio_energia_diario, 2)

    return resultado


def _retencion_masa_magra(delta_peso: float, delta_magra: float) -> float:
    """% del peso perdido que NO fue masa libre de grasa. Si no hubo
    pérdida de peso o de masa magra, se reporta 100% (nada que retener)."""
    if delta_peso >= 0 or delta_magra >= 0:
        return 100.0
    retencion = (1.0 - (abs(delta_magra) / abs(delta_peso))) * 100.0
    return round(max(0.0, retencion), 1)


def proyeccion_peso_objetivo(
    peso_actual: float, grasa_actual_kg: float,
    objetivos_pct: tuple[float, ...] = (0.25, 0.23, 0.20),
) -> dict[float, float]:
    """Peso al que llegarías a cada % de grasa objetivo SI conservas toda
    tu masa libre de grasa actual (peso - grasa) -- una proyección, no una
    predicción exacta."""
    masa_libre_grasa = peso_actual - grasa_actual_kg
    return {pct: round(masa_libre_grasa / (1.0 - pct), 1) for pct in objetivos_pct}
