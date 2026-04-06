"""Parseo de números con formato argentino (miles con punto, decimal con coma)."""

from __future__ import annotations

import re


def parse_ar_decimal(raw: str | float | int) -> float:
    """Convierte texto numérico típico de remitos AR a float.

    Evita el error de ``float('1.000') == 1.0`` en Python: en remitos, ``1.000``
    suele ser mil (miles con punto), no uno coma cero.

    Ejemplos:
        - ``1.234.567,89`` → 1234567.89
        - ``10,5`` → 10.5
        - ``10.500`` → 10500.0 (tres dígitos tras el último punto → miles)
        - ``10.5`` → 10.5 (un solo punto y parte decimal corta → US/decimal)
    """
    if isinstance(raw, (int, float)):
        return float(raw)
    if raw is None:
        return 0.0
    s = re.sub(r"[\s\$€]", "", str(raw).strip())
    if not s or s == "-":
        return 0.0

    last_comma = s.rfind(",")
    last_dot = s.rfind(".")

    if last_comma != -1 and last_comma > last_dot:
        entero = s[:last_comma].replace(".", "")
        frac = s[last_comma + 1 :]
        if not frac:
            return float(entero) if entero else 0.0
        return float(f"{entero}.{frac}")

    if last_dot != -1 and last_dot > last_comma:
        frac = s[last_dot + 1 :]
        entero = s[:last_dot].replace(",", "")
        if frac.isdigit() and 1 <= len(frac) <= 2:
            return float(f"{entero}.{frac}")
        return float(s.replace(".", "").replace(",", ""))

    return float(s)
