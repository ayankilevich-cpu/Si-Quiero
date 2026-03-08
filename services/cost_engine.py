"""Motor de costeo: calcula costos propagando desde ingredientes y helado hasta combos."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from services.data_loader import DataLoader
from services.icecream_cost_service import IceCreamCostService
from utils.helpers import (
    calcular_food_cost_pct,
    calcular_margen_bruto,
    calcular_margen_pct,
    estado_margen,
    safe_div,
)


def _norm_id(val) -> str:
    """Normaliza un ID que puede ser int, float, string o NaN a string limpio."""
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return ""
    try:
        return str(int(float(val)))
    except (ValueError, TypeError):
        return str(val).strip()


class CostEngine:

    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or DataLoader()
        self.ice_svc = IceCreamCostService(self.loader)
        self._refresh()

    def _refresh(self):
        self._ingredientes = self.loader.load_ingredientes()
        self._productos = self.loader.load_productos()
        self._componentes = self.loader.load_componentes()
        self._recetas = self.loader.load_recetas()
        self._combos = self.loader.load_combos()
        self._combo_items = self.loader.load_combo_items()
        self._helado = self.ice_svc.costo_ponderado_general()

        self._costo_ing = {}
        self._nombre_ing = {}
        if not self._ingredientes.empty:
            self._costo_ing = dict(zip(
                self._ingredientes["ingredient_id"].astype(str),
                self._ingredientes["costo_actual"].fillna(0),
            ))
            self._nombre_ing = dict(zip(
                self._ingredientes["ingredient_id"].astype(str),
                self._ingredientes["ingrediente"],
            ))

    def refresh(self):
        self._refresh()

    # ── Costo de un producto ──

    def costo_producto(self, product_id) -> dict:
        """Calcula el costo de un producto a partir de sus componentes.

        Soporta component_type: ingrediente, helado_base, receta, producto.
        """
        pid = str(product_id)
        prod_row = self._productos[self._productos["product_id"].astype(str) == pid]
        if prod_row.empty:
            return {"product_id": pid, "costo": 0, "error": "Producto no encontrado"}

        prod = prod_row.iloc[0]
        nombre = str(prod.get("producto", "") or prod.get("nombre_producto", ""))
        tipo = str(prod.get("tipo_producto", "producto"))
        precio = float(prod.get("precio_venta_actual", 0) or 0)
        cat = str(prod.get("categoria", "") or "")

        comps = self._componentes[self._componentes["parent_id"].astype(str) == pid]

        if comps.empty and tipo == "receta":
            rec_vinc = self._recetas[
                self._recetas["product_id_vinculado"].apply(_norm_id) == pid
            ]
            if not rec_vinc.empty:
                rid = str(rec_vinc.iloc[0]["recipe_id"])
                rec_result = self.costo_receta(rid)
                costo_porcion = rec_result.get("costo_porcion", 0)
                costo_total_receta = rec_result.get("costo_total", 0)
                rendimiento = rec_result.get("rendimiento", 1)

                subcat = str(prod.get("subcategoria", "") or "").upper()
                if subcat == "ENTERAS":
                    costo_prod = costo_total_receta
                    cant_label = rendimiento
                    unidad_label = "porcion (entera)"
                elif subcat == "MEDIANAS":
                    costo_prod = round(costo_total_receta * 0.6, 2)
                    cant_label = round(rendimiento * 0.6, 1)
                    unidad_label = "porcion (mediana ~60%)"
                else:
                    costo_prod = costo_porcion
                    cant_label = 1
                    unidad_label = "porcion"

                detalle_rec = [{
                    "tipo": "receta",
                    "nombre": rec_result.get("recipe_name", rid),
                    "cantidad": cant_label,
                    "unidad": unidad_label,
                    "costo_unitario": costo_porcion,
                    "subtotal": round(costo_prod, 2),
                }]
                return self._build_result(pid, nombre, tipo, cat, costo_prod, precio, detalle_rec)

        if comps.empty:
            return self._build_result(pid, nombre, tipo, cat, 0, precio, [])

        costo = 0.0
        detalle = []

        for _, comp in comps.iterrows():
            ctype = str(comp["component_type"])
            cid = str(comp["component_id"])
            cant = float(comp["cantidad"])
            merma = float(comp.get("merma_pct", 0) or 0)
            cant_real = cant * (1 + merma / 100)

            if ctype == "ingrediente":
                precio_unit = float(self._costo_ing.get(cid, 0))
                sub = precio_unit * cant_real
                costo += sub
                detalle.append({
                    "tipo": "ingrediente",
                    "nombre": self._nombre_ing.get(cid, cid),
                    "cantidad": cant,
                    "unidad": str(comp.get("unidad", "")),
                    "costo_unitario": precio_unit,
                    "subtotal": round(sub, 2),
                })

            elif ctype == "helado_base":
                costo_gramo = self._helado.get("costo_gramo", 0)
                sub = costo_gramo * cant_real
                costo += sub
                detalle.append({
                    "tipo": "helado_base",
                    "nombre": "Helado (ponderado)",
                    "cantidad": cant,
                    "unidad": "g",
                    "costo_unitario": costo_gramo,
                    "subtotal": round(sub, 2),
                })

            elif ctype == "receta":
                rec_cost = self.costo_receta(cid)
                sub = rec_cost.get("costo_porcion", 0) * cant_real
                costo += sub
                detalle.append({
                    "tipo": "receta",
                    "nombre": rec_cost.get("recipe_name", cid),
                    "cantidad": cant,
                    "unidad": "porcion",
                    "costo_unitario": rec_cost.get("costo_porcion", 0),
                    "subtotal": round(sub, 2),
                })

            elif ctype == "producto":
                prod_cost = self.costo_producto(cid)
                sub = prod_cost.get("costo", 0) * cant_real
                costo += sub
                detalle.append({
                    "tipo": "producto",
                    "nombre": prod_cost.get("nombre", cid),
                    "cantidad": cant,
                    "unidad": "unidad",
                    "costo_unitario": prod_cost.get("costo", 0),
                    "subtotal": round(sub, 2),
                })

        return self._build_result(pid, nombre, tipo, cat, costo, precio, detalle)

    def _build_result(self, pid, nombre, tipo, cat, costo, precio, detalle):
        margen = calcular_margen_bruto(precio, costo)
        margen_p = calcular_margen_pct(precio, costo)
        fc = calcular_food_cost_pct(costo, precio)
        return {
            "product_id": pid,
            "nombre": nombre,
            "tipo": tipo,
            "categoria": cat,
            "costo": round(costo, 2),
            "precio_venta": precio,
            "margen_bruto": round(margen, 2),
            "margen_pct": round(margen_p, 2),
            "food_cost_pct": round(fc, 2),
            "estado": estado_margen(margen_p) if precio > 0 else "Sin precio",
            "detalle": detalle,
        }

    # ── Costo de una receta ──

    def costo_receta(self, recipe_id: str) -> dict:
        rec_row = self._recetas[self._recetas["recipe_id"].astype(str) == str(recipe_id)]
        rendimiento = int(rec_row["rendimiento_cantidad"].iloc[0]) if not rec_row.empty else 1
        recipe_name = rec_row["recipe_name"].iloc[0] if not rec_row.empty else recipe_id

        comps = self._componentes[
            (self._componentes["parent_id"].astype(str) == str(recipe_id)) &
            (self._componentes["parent_type"] == "receta")
        ]

        costo_total = 0.0
        detalle = []
        for _, comp in comps.iterrows():
            cid = str(comp["component_id"])
            cant = float(comp["cantidad"])
            ctype = str(comp["component_type"])

            if ctype == "ingrediente":
                precio_unit = float(self._costo_ing.get(cid, 0))
                sub = precio_unit * cant
            elif ctype == "helado_base":
                sub = self._helado.get("costo_gramo", 0) * cant
                precio_unit = self._helado.get("costo_gramo", 0)
            else:
                precio_unit = 0
                sub = 0

            costo_total += sub
            detalle.append({
                "componente": comp.get("component_name", cid),
                "cantidad": cant,
                "costo_unit": precio_unit,
                "subtotal": round(sub, 2),
            })

        return {
            "recipe_id": recipe_id,
            "recipe_name": recipe_name,
            "costo_total": round(costo_total, 2),
            "rendimiento": rendimiento,
            "costo_porcion": round(safe_div(costo_total, rendimiento), 2),
            "detalle": detalle,
        }

    # ── Costo de un combo ──

    def costo_combo(self, combo_id: str) -> dict:
        combo_row = self._combos[self._combos["combo_id"].astype(str) == str(combo_id)]
        if combo_row.empty:
            return {"combo_id": combo_id, "error": "Combo no encontrado"}

        combo = combo_row.iloc[0]
        precio_combo = float(combo.get("precio_venta", 0) or 0)
        items = self._combo_items[self._combo_items["combo_id"].astype(str) == str(combo_id)]

        costo_total = 0.0
        precio_individual_total = 0.0
        detalle_items = []

        for _, item in items.iterrows():
            pid = str(item["product_id"])
            cant = float(item.get("cantidad", 1))
            prod_cost = self.costo_producto(pid)

            costo_item = prod_cost.get("costo", 0) * cant
            precio_item = prod_cost.get("precio_venta", 0) * cant
            costo_total += costo_item
            precio_individual_total += precio_item

            detalle_items.append({
                "product_id": pid,
                "nombre": prod_cost.get("nombre", pid),
                "cantidad": cant,
                "costo_unitario": prod_cost.get("costo", 0),
                "costo_total": round(costo_item, 2),
                "precio_individual": prod_cost.get("precio_venta", 0),
            })

        margen = calcular_margen_bruto(precio_combo, costo_total)
        margen_p = calcular_margen_pct(precio_combo, costo_total)
        fc = calcular_food_cost_pct(costo_total, precio_combo)
        desc = safe_div(precio_individual_total - precio_combo, precio_individual_total) * 100

        return {
            "combo_id": combo_id,
            "nombre": str(combo.get("combo_name", "")),
            "precio_combo": precio_combo,
            "costo_combo": round(costo_total, 2),
            "margen_bruto": round(margen, 2),
            "margen_pct": round(margen_p, 2),
            "food_cost_pct": round(fc, 2),
            "precio_individual_total": round(precio_individual_total, 2),
            "descuento_pct": round(desc, 2),
            "estado": estado_margen(margen_p) if precio_combo > 0 else "Sin precio",
            "items": detalle_items,
        }

    # ── Tabla de rentabilidad completa ──

    def tabla_rentabilidad_productos(self) -> pd.DataFrame:
        if self._productos.empty:
            return pd.DataFrame()

        activo_col = "activo" if "activo" in self._productos.columns else None
        if activo_col:
            prod_activos = self._productos[
                (self._productos[activo_col] != False) &
                (self._productos["tipo_producto"] != "combo")
            ]
        else:
            prod_activos = self._productos[self._productos["tipo_producto"] != "combo"]

        rows = []
        for _, prod in prod_activos.iterrows():
            r = self.costo_producto(str(prod["product_id"]))
            nombre = r.get("nombre") or prod.get("producto") or prod.get("nombre_producto", "")
            rows.append({
                "product_id": r["product_id"],
                "Producto": nombre,
                "Tipo": r.get("tipo", ""),
                "Categoría": r.get("categoria", ""),
                "Precio venta": r.get("precio_venta", 0),
                "Costo": r.get("costo", 0),
                "Margen $": r.get("margen_bruto", 0),
                "Margen %": r.get("margen_pct", 0),
                "Food Cost %": r.get("food_cost_pct", 0),
                "Estado": r.get("estado", ""),
            })
        return pd.DataFrame(rows)

    # ── Simulación ──

    def simular_cambio_precio(self, cambios: dict[str, float]) -> pd.DataFrame:
        """Simula cambios de precio en ingredientes y/o helado."""
        precios_orig = self._costo_ing.copy()
        helado_orig = self._helado.copy()

        actual = self.tabla_rentabilidad_productos()

        for ing_id, nuevo in cambios.items():
            if ing_id == "__helado_kg__":
                self._helado["costo_kg"] = nuevo
                self._helado["costo_gramo"] = nuevo / 1000
            else:
                self._costo_ing[str(ing_id)] = nuevo

        nuevo = self.tabla_rentabilidad_productos()

        self._costo_ing = precios_orig
        self._helado = helado_orig

        if actual.empty or nuevo.empty:
            return pd.DataFrame()

        merged = actual[["product_id", "Producto", "Categoría", "Precio venta",
                         "Costo", "Margen %"]].merge(
            nuevo[["product_id", "Costo", "Margen %"]],
            on="product_id", suffixes=("_actual", "_nuevo"),
        )
        merged.rename(columns={
            "Costo_actual": "Costo actual", "Costo_nuevo": "Costo simulado",
            "Margen %_actual": "Margen % actual", "Margen %_nuevo": "Margen % simulado",
        }, inplace=True)
        merged["Delta margen pp"] = (merged["Margen % simulado"] - merged["Margen % actual"]).round(2)
        merged["Impactado"] = merged["Delta margen pp"].abs() > 0.01
        return merged[merged["Impactado"]].sort_values("Delta margen pp")
