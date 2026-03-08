"""Parser de remitos PDF de helado (formato proveedor Capuano)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional


def parse_remito_text(text: str) -> dict:
    """Parsea el texto extraído de un PDF de remito de helado.

    Returns:
        {
            "fecha": date,
            "proveedor": str,
            "lineas": [{sabor, kilos, importe, costo_kg}, ...],
            "total": float,
        }
    """
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

    fecha = _extract_fecha(lines)
    proveedor = _extract_proveedor(lines)
    lineas = _extract_lineas(lines)
    total = _extract_total(lines)

    return {
        "fecha": fecha,
        "proveedor": proveedor,
        "lineas": lineas,
        "total": total,
    }


def _extract_fecha(lines: list[str]) -> Optional[date]:
    for line in lines[:5]:
        m = re.search(r"FECHA:\s*(\d{4}-\d{2}-\d{2})", line)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y-%m-%d").date()
            except ValueError:
                pass
        m2 = re.search(r"(\d{2}[/-]\d{2}[/-]\d{4})", line)
        if m2:
            try:
                return datetime.strptime(m2.group(1).replace("/", "-"), "%d-%m-%Y").date()
            except ValueError:
                pass
    return None


def _extract_proveedor(lines: list[str]) -> str:
    for line in lines[:5]:
        if "CLIENTE:" in line.upper():
            parts = line.split(":", 1)
            if len(parts) > 1:
                nombre = parts[1].strip().split("(")[0].strip()
                return nombre
    return "Desconocido"


def _extract_lineas(lines: list[str]) -> list[dict]:
    """Extrae líneas de detalle: CANT SABOR PRECIO"""
    resultado = []
    pattern = re.compile(
        r"^(\d+[.,]\d+)\s+(.+?)\s+([\d.]+[.,]\d+)\s*\$?\s*$"
    )

    for line in lines:
        m = pattern.match(line)
        if m:
            kilos = float(m.group(1).replace(",", "."))
            sabor = m.group(2).strip()
            importe = float(m.group(3).replace(".", "").replace(",", "."))

            if importe > 1000 and kilos > 0:
                costo_kg = round(importe / kilos, 2)
                resultado.append({
                    "sabor": sabor,
                    "kilos": kilos,
                    "importe": importe,
                    "costo_kg": costo_kg,
                })

    return resultado


def _extract_total(lines: list[str]) -> float:
    for line in reversed(lines):
        m = re.search(r"TOTAL:\s*([\d.]+[.,]\d+)", line)
        if m:
            return float(m.group(1).replace(".", "").replace(",", "."))
    return 0.0


def parse_remito_pdf(file_bytes: bytes) -> dict:
    """Extrae texto de un PDF y lo parsea.

    Intenta con pdfplumber primero, luego PyPDF2.
    """
    text = ""
    try:
        import pdfplumber
        import io
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except ImportError:
        try:
            import PyPDF2
            import io
            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
        except ImportError:
            return {"error": "Instalar pdfplumber o PyPDF2 para leer PDFs"}

    if not text.strip():
        return {"error": "No se pudo extraer texto del PDF"}

    return parse_remito_text(text)
