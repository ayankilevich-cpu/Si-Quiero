"""Funciones auxiliares: formateo de moneda, cálculos de margen."""

from __future__ import annotations

from config import FOOD_COST_OBJETIVO_PCT, MARGEN_OBJETIVO_PCT, MONEDA_SIMBOLO


def fmt_ars(valor: float, decimales: int = 0) -> str:
    """Formatea un número como moneda ARS: $ 1.234"""
    if valor is None:
        return f"{MONEDA_SIMBOLO} 0"
    signo = "-" if valor < 0 else ""
    abs_val = abs(valor)
    entero = int(round(abs_val, decimales))
    if decimales == 0:
        entero_str = f"{entero:,}".replace(",", ".")
        return f"{signo}{MONEDA_SIMBOLO} {entero_str}"
    frac = round(abs_val - int(abs_val), decimales)
    frac_str = f"{frac:.{decimales}f}"[2:]
    entero_str = f"{int(abs_val):,}".replace(",", ".")
    return f"{signo}{MONEDA_SIMBOLO} {entero_str},{frac_str}"


def fmt_pct(valor: float, decimales: int = 1) -> str:
    """Formatea un porcentaje: 65,3%"""
    if valor is None:
        return "0,0%"
    return f"{valor:,.{decimales}f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def estado_margen(margen_pct: float) -> str:
    if margen_pct >= MARGEN_OBJETIVO_PCT:
        return "Saludable"
    elif margen_pct >= MARGEN_OBJETIVO_PCT * 0.7:
        return "Atención"
    return "Crítico"


def estado_food_cost(food_cost_pct: float) -> str:
    if food_cost_pct <= FOOD_COST_OBJETIVO_PCT:
        return "Saludable"
    elif food_cost_pct <= FOOD_COST_OBJETIVO_PCT * 1.3:
        return "Atención"
    return "Crítico"


def color_estado(estado: str) -> str:
    mapping = {"Saludable": "#2ECC71", "Atención": "#F39C12", "Crítico": "#E74C3C"}
    return mapping.get(estado, "#95A5A6")


def safe_div(numerador: float, denominador: float, default: float = 0.0) -> float:
    if not denominador:
        return default
    return numerador / denominador


def calcular_margen_bruto(precio_venta: float, costo: float) -> float:
    return precio_venta - costo


def calcular_margen_pct(precio_venta: float, costo: float) -> float:
    return safe_div((precio_venta - costo), precio_venta) * 100


def calcular_food_cost_pct(costo: float, precio_venta: float) -> float:
    return safe_div(costo, precio_venta) * 100
