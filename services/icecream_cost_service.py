"""Servicio de costeo de helado: carga de remitos y cálculo ponderado."""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from services.data_loader import DataLoader


class IceCreamCostService:

    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or DataLoader()

    def costo_ponderado_general(self) -> dict:
        """Calcula costo ponderado general del helado.

        Returns:
            {costo_kg, costo_gramo, total_kg, total_importe, n_remitos, fecha_ultimo}
        """
        df = self.loader.load_helado_compras()
        if df.empty:
            return {
                "costo_kg": 0, "costo_gramo": 0,
                "total_kg": 0, "total_importe": 0,
                "n_remitos": 0, "fecha_ultimo": None,
            }
        total_kg = df["kilos"].sum()
        total_imp = df["importe_total"].sum()
        costo_kg = total_imp / total_kg if total_kg > 0 else 0

        fechas = df["fecha"].dropna()
        fecha_ultimo = fechas.max() if not fechas.empty else None

        n_remitos = df["remito_origen"].nunique() if "remito_origen" in df.columns else len(df)

        return {
            "costo_kg": round(costo_kg, 2),
            "costo_gramo": round(costo_kg / 1000, 4),
            "total_kg": round(total_kg, 1),
            "total_importe": round(total_imp, 0),
            "n_remitos": n_remitos,
            "fecha_ultimo": fecha_ultimo,
        }

    def costo_por_sabor(self) -> pd.DataFrame:
        """Calcula costo ponderado por sabor (fase 2)."""
        df = self.loader.load_helado_compras()
        if df.empty:
            return pd.DataFrame()
        grouped = df.groupby("sabor").agg(
            total_kg=("kilos", "sum"),
            total_importe=("importe_total", "sum"),
            n_compras=("purchase_id", "count"),
        ).reset_index()
        grouped["costo_kg"] = (grouped["total_importe"] / grouped["total_kg"]).round(2)
        grouped["costo_gramo"] = (grouped["costo_kg"] / 1000).round(4)
        return grouped.sort_values("total_kg", ascending=False)

    def agregar_remito_manual(
        self,
        fecha: date,
        proveedor: str,
        lineas: list[dict],
        remito_origen: str = "manual",
        *,
        precio_es_unitario: bool = False,
    ) -> int:
        """Agrega líneas de un remito al historial.

        Args:
            lineas: [{sabor, kilos, importe}, ...]
            precio_es_unitario: Si True, ``importe`` es $/kg y se multiplica por kilos
                para obtener el subtotal de la línea (caso típico de remitos con P.U.).

        Returns:
            Número de líneas agregadas.
        """
        df = self.loader.load_helado_compras()
        next_id = int(df["purchase_id"].max()) + 1 if not df.empty else 1

        nuevas = []
        for linea in lineas:
            kilos = float(linea.get("kilos", 0))
            importe = float(linea.get("importe", 0))
            if precio_es_unitario and kilos > 0:
                importe = importe * kilos
            nuevas.append({
                "purchase_id": next_id,
                "fecha": fecha,
                "proveedor": proveedor,
                "sabor": str(linea.get("sabor", "")).strip().upper(),
                "kilos": kilos,
                "importe_total": importe,
                "costo_kg": round(importe / kilos, 2) if kilos > 0 else 0,
                "remito_origen": remito_origen,
                "observaciones": "",
            })
            next_id += 1

        if nuevas:
            df_new = pd.DataFrame(nuevas)
            df = pd.concat([df, df_new], ignore_index=True)
            self.loader.save_helado_compras(df)

        return len(nuevas)

    def agregar_remito_pdf(
        self,
        parsed: dict,
        filename: str = "pdf",
        *,
        precio_es_unitario: bool = False,
    ) -> int:
        """Agrega un remito parseado desde PDF."""
        if "error" in parsed:
            return 0

        lineas = [
            {"sabor": l["sabor"], "kilos": l["kilos"], "importe": l["importe"]}
            for l in parsed.get("lineas", [])
        ]
        return self.agregar_remito_manual(
            fecha=parsed.get("fecha") or date.today(),
            proveedor=parsed.get("proveedor", "Desconocido"),
            lineas=lineas,
            remito_origen=filename,
            precio_es_unitario=precio_es_unitario,
        )

    def historial_compras(self) -> pd.DataFrame:
        """Retorna historial completo de compras ordenado por fecha."""
        df = self.loader.load_helado_compras()
        if not df.empty:
            df = df.sort_values("fecha", ascending=False)
        return df
