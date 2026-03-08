"""Validaciones de datos del negocio."""

from __future__ import annotations

import pandas as pd


def validar_productos_sin_precio(df_prod: pd.DataFrame) -> list[str]:
    sin_precio = df_prod[
        (df_prod["precio_venta_actual"].isna()) |
        (df_prod["precio_venta_actual"] == 0)
    ]
    return [f"{r['nombre_producto'] if 'nombre_producto' in r else r.get('producto', '?')}: sin precio de venta"
            for _, r in sin_precio.iterrows()]


def validar_ingredientes_sin_costo(df_ing: pd.DataFrame) -> list[str]:
    sin_costo = df_ing[
        (df_ing["costo_actual"].isna()) | (df_ing["costo_actual"] == 0)
    ]
    return [f"{r['ingrediente']}: sin costo asignado" for _, r in sin_costo.iterrows()]


def validar_productos_sin_componentes(
    df_prod: pd.DataFrame,
    df_comp: pd.DataFrame,
) -> list[str]:
    armados = df_prod[df_prod["tipo_producto"] == "armado"]
    if armados.empty or df_comp.empty:
        return []
    ids_con_comp = set(df_comp["parent_id"].astype(str).unique())
    alertas = []
    for _, r in armados.iterrows():
        pid = str(r["product_id"])
        if pid not in ids_con_comp:
            nombre = r.get("producto") or r.get("nombre_producto", "?")
            alertas.append(f"{nombre}: producto armado sin componentes")
    return alertas


def validar_helado_costo_disponible(df_helado: pd.DataFrame) -> list[str]:
    if df_helado.empty:
        return ["No hay remitos de helado cargados — costo ponderado no disponible"]
    return []


def validar_combos_sin_items(
    df_combos: pd.DataFrame,
    df_ci: pd.DataFrame,
) -> list[str]:
    if df_combos.empty:
        return []
    if df_ci.empty:
        return [f"{r['combo_name']}: combo sin items" for _, r in df_combos.iterrows()]
    ids_con_items = set(df_ci["combo_id"].unique())
    return [
        f"{r['combo_name']}: combo sin items"
        for _, r in df_combos.iterrows()
        if r["combo_id"] not in ids_con_items
    ]


def todas_las_validaciones(loader) -> list[dict]:
    """Ejecuta todas las validaciones y retorna lista de alertas."""
    alertas = []

    df_ing = loader.load_ingredientes()
    df_prod = loader.load_productos()
    df_comp = loader.load_componentes()
    df_helado = loader.load_helado_compras()
    df_combos = loader.load_combos()
    df_ci = loader.load_combo_items()

    for msg in validar_ingredientes_sin_costo(df_ing):
        alertas.append({"tipo": "ingrediente", "severidad": "media", "mensaje": msg})

    for msg in validar_productos_sin_componentes(df_prod, df_comp):
        alertas.append({"tipo": "producto", "severidad": "media", "mensaje": msg})

    for msg in validar_helado_costo_disponible(df_helado):
        alertas.append({"tipo": "helado", "severidad": "alta", "mensaje": msg})

    for msg in validar_combos_sin_items(df_combos, df_ci):
        alertas.append({"tipo": "combo", "severidad": "baja", "mensaje": msg})

    return alertas
