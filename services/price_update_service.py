"""Servicio de actualización de precios de ingredientes."""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from config import UNIDADES_COMPRA
from services.data_loader import DataLoader


class PriceUpdateService:

    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or DataLoader()

    def actualizar_precio_manual(
        self,
        ingredient_id: int,
        precio_compra: float,
        cantidad_compra: float,
        unidad_compra: str,
        proveedor: str = "",
    ) -> dict:
        """Actualiza el costo de un ingrediente desde una compra manual."""
        df = self.loader.load_ingredientes()
        mask = df["ingredient_id"] == ingredient_id
        if not mask.any():
            return {"ok": False, "error": "Ingrediente no encontrado"}

        idx = df[mask].index[0]
        precio_anterior = float(df.at[idx, "costo_actual"] or 0)

        conversion = UNIDADES_COMPRA.get(unidad_compra, {})
        factor = conversion.get("factor_a_base", 1)
        cantidad_base = cantidad_compra * factor
        nuevo_precio = precio_compra / cantidad_base if cantidad_base > 0 else 0

        df.at[idx, "costo_actual"] = round(nuevo_precio, 4)
        df.at[idx, "ultimo_update"] = date.today()
        df.at[idx, "requiere_revision_costo"] = False
        if proveedor:
            df.at[idx, "proveedor"] = proveedor

        self.loader.save_ingredientes(df)
        self.loader.append_historial([{
            "fecha": date.today(),
            "ingredient_id": ingredient_id,
            "precio_anterior": precio_anterior,
            "precio_nuevo": round(nuevo_precio, 4),
            "origen": "manual",
        }])

        nombre = df.at[idx, "ingrediente"]
        return {"ok": True, "ingrediente": nombre, "precio_nuevo": round(nuevo_precio, 4)}

    def actualizar_desde_excel(self, uploaded_df: pd.DataFrame) -> dict:
        """Actualiza precios de ingredientes desde un DataFrame (importado de Excel)."""
        required = {"ingredient_id", "costo_actual"}
        if not required.issubset(set(uploaded_df.columns)):
            return {
                "ok": False,
                "error": f"Columnas requeridas: {required}. Encontradas: {set(uploaded_df.columns)}",
            }

        df_ing = self.loader.load_ingredientes()
        actualizados = 0
        errores = []
        historial = []

        for _, row in uploaded_df.iterrows():
            iid = row["ingredient_id"]
            mask = df_ing["ingredient_id"] == iid
            if not mask.any():
                errores.append(f"ID {iid}: no encontrado")
                continue

            idx = df_ing[mask].index[0]
            anterior = float(df_ing.at[idx, "costo_actual"] or 0)
            nuevo = float(row["costo_actual"])

            if nuevo <= 0:
                errores.append(f"ID {iid}: costo <= 0 ignorado")
                continue

            df_ing.at[idx, "costo_actual"] = round(nuevo, 4)
            df_ing.at[idx, "ultimo_update"] = date.today()
            df_ing.at[idx, "requiere_revision_costo"] = False

            historial.append({
                "fecha": date.today(),
                "ingredient_id": iid,
                "precio_anterior": anterior,
                "precio_nuevo": round(nuevo, 4),
                "origen": "excel",
            })
            actualizados += 1

        self.loader.save_ingredientes(df_ing)
        if historial:
            self.loader.append_historial(historial)

        return {"ok": True, "actualizados": actualizados, "errores": errores}
