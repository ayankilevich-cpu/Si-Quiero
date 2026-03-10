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

    _UPDATABLE_FIELDS = [
        "ingrediente", "costo_actual", "alicuota_iva", "unidad_base",
        "unidad_compra", "factor_compra_a_base", "rubro", "subrubro", "proveedor",
    ]

    def importar_completo(
        self,
        uploaded_df: pd.DataFrame,
        agregar_nuevos: bool = False,
    ) -> dict:
        """Importa ingredientes desde un DataFrame: actualiza existentes y opcionalmente agrega nuevos."""
        required = {"ingredient_id", "costo_actual"}
        if not required.issubset(set(uploaded_df.columns)):
            return {
                "ok": False,
                "error": f"Columnas requeridas: {required}. Encontradas: {set(uploaded_df.columns)}",
            }

        df_ing = self.loader.load_ingredientes()
        existing_ids = set(df_ing["ingredient_id"].tolist())

        actualizados = 0
        agregados = 0
        errores: list[str] = []
        historial: list[dict] = []

        for _, row in uploaded_df.iterrows():
            iid = int(row["ingredient_id"])
            nuevo_costo = float(row.get("costo_actual", 0) or 0)

            if iid in existing_ids:
                mask = df_ing["ingredient_id"] == iid
                idx = df_ing[mask].index[0]
                anterior = float(df_ing.at[idx, "costo_actual"] or 0)

                for field in self._UPDATABLE_FIELDS:
                    if field in row.index and pd.notna(row[field]):
                        val = row[field]
                        if field == "costo_actual":
                            val = round(float(val), 4)
                        df_ing.at[idx, field] = val

                df_ing.at[idx, "ultimo_update"] = date.today()
                df_ing.at[idx, "requiere_revision_costo"] = False

                if nuevo_costo > 0 and round(nuevo_costo, 4) != round(anterior, 4):
                    historial.append({
                        "fecha": date.today(),
                        "ingredient_id": iid,
                        "precio_anterior": anterior,
                        "precio_nuevo": round(nuevo_costo, 4),
                        "origen": "excel",
                    })
                actualizados += 1

            elif agregar_nuevos:
                nombre = str(row.get("ingrediente", "")).strip()
                if not nombre:
                    errores.append(f"ID {iid}: sin nombre, ignorado")
                    continue

                new_row = {
                    "ingredient_id": iid,
                    "ingrediente": nombre,
                    "ingrediente_norm": nombre.upper(),
                    "costo_actual": round(nuevo_costo, 4),
                    "alicuota_iva": float(row.get("alicuota_iva", 21.0) or 21.0),
                    "unidad_base": str(row.get("unidad_base", "UNIDAD") or "UNIDAD"),
                    "unidad_compra": str(row.get("unidad_compra", "") or ""),
                    "factor_compra_a_base": float(row.get("factor_compra_a_base", 1.0) or 1.0),
                    "rubro": str(row.get("rubro", "") or ""),
                    "subrubro": str(row.get("subrubro", "") or ""),
                    "proveedor": str(row.get("proveedor", "") or ""),
                    "requiere_revision_costo": True,
                    "notas": "",
                    "activo": True,
                    "ultimo_update": date.today(),
                }
                df_ing = pd.concat([df_ing, pd.DataFrame([new_row])], ignore_index=True)
                existing_ids.add(iid)
                agregados += 1

        self.loader.save_ingredientes(df_ing)
        if historial:
            self.loader.append_historial(historial)

        return {
            "ok": True,
            "actualizados": actualizados,
            "agregados": agregados,
            "errores": errores,
        }
