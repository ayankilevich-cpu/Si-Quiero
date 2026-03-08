"""Generación de plantillas Excel descargables desde la app."""

from __future__ import annotations

import io

import pandas as pd


def generar_plantilla_recetas(df_ing: pd.DataFrame = None, df_prod: pd.DataFrame = None) -> bytes:
    """Genera plantilla Excel para importar recetas con sus ingredientes.

    Hoja 1: 'recetas' — una fila por receta.
    Hoja 2: 'receta_ingredientes' — una fila por ingrediente de cada receta.
    Hoja 3: 'instrucciones' — documentación de cada campo.
    Hoja 4: 'ingredientes_disponibles' — catálogo de referencia.
    """

    df_rec = pd.DataFrame({
        "recipe_name": ["CHOCOTORTA", "MARQUISE"],
        "categoria": ["TORTAS", "TORTAS"],
        "rendimiento_cantidad": [10, 12],
        "unidad_rendimiento": ["porcion", "porcion"],
        "producto_vinculado": ["CHOCOTORTA", "MARQUISE"],
        "notas": ["", ""],
    })

    df_ri = pd.DataFrame({
        "recipe_name": [
            "CHOCOTORTA", "CHOCOTORTA", "CHOCOTORTA",
            "MARQUISE", "MARQUISE",
        ],
        "ingrediente": [
            "QUESO CREMA", "CHOCOLATE POLVO NESQUIK", "GALLETITAS",
            "BARRA CHOCOLATE", "LECHE",
        ],
        "cantidad": [500, 200, 300, 400, 500],
        "unidad": ["GRAMOS", "GRAMOS", "GRAMOS", "GRAMOS", "MILILITROS"],
        "merma_pct": [0, 0, 0, 0, 0],
    })

    instrucciones = pd.DataFrame({
        "Hoja": [
            "recetas", "recetas", "recetas", "recetas", "recetas", "recetas",
            "receta_ingredientes", "receta_ingredientes", "receta_ingredientes",
            "receta_ingredientes", "receta_ingredientes",
        ],
        "Campo": [
            "recipe_name", "categoria", "rendimiento_cantidad",
            "unidad_rendimiento", "producto_vinculado", "notas",
            "recipe_name", "ingrediente", "cantidad", "unidad", "merma_pct",
        ],
        "Descripcion": [
            "Nombre de la receta (debe ser único)",
            "Categoría: TORTAS, CAFETERIA, HELADERIA, OTROS",
            "Cantidad de porciones que rinde la receta",
            "Unidad: porcion, unidad, kg",
            "Nombre exacto del producto en la carta al que se vincula (opcional, dejar vacío si no aplica)",
            "Observaciones (opcional)",
            "Nombre de la receta (debe coincidir con hoja 'recetas')",
            "Nombre exacto del ingrediente (debe existir en la hoja 'ingredientes_disponibles')",
            "Cantidad del ingrediente para la receta completa (no por porción)",
            "Unidad: GRAMOS, MILILITROS o UNIDAD",
            "Porcentaje de merma (0 si no aplica)",
        ],
        "Obligatorio": [
            "Sí", "Sí", "Sí", "Sí", "No", "No",
            "Sí", "Sí", "Sí", "Sí", "No",
        ],
        "Ejemplo": [
            "CHOCOTORTA", "TORTAS", "10", "porcion", "CHOCOTORTA", "",
            "CHOCOTORTA", "QUESO CREMA", "500", "GRAMOS", "0",
        ],
    })

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as w:
        df_rec.to_excel(w, sheet_name="recetas", index=False)
        df_ri.to_excel(w, sheet_name="receta_ingredientes", index=False)
        instrucciones.to_excel(w, sheet_name="instrucciones", index=False)

        if df_ing is not None and not df_ing.empty:
            cols = ["ingredient_id", "ingrediente", "unidad_base", "costo_actual"]
            cols = [c for c in cols if c in df_ing.columns]
            df_ing[cols].sort_values("ingrediente").to_excel(
                w, sheet_name="ingredientes_disponibles", index=False,
            )

        if df_prod is not None and not df_prod.empty:
            ncol = "producto" if "producto" in df_prod.columns else "nombre_producto"
            cols_p = ["product_id", ncol, "categoria", "precio_venta_actual"]
            cols_p = [c for c in cols_p if c in df_prod.columns]
            tortas = df_prod[df_prod["tipo_producto"] == "receta"]
            if not tortas.empty:
                tortas[cols_p].sort_values(ncol).to_excel(
                    w, sheet_name="productos_vinculables", index=False,
                )

    return buffer.getvalue()


def generar_plantilla_actualizacion_precios() -> bytes:
    """Genera plantilla para actualización masiva de precios."""
    df = pd.DataFrame({
        "ingredient_id": [223],
        "costo_actual": [150.0],
    })

    instrucciones = pd.DataFrame({
        "Campo": ["ingredient_id", "costo_actual"],
        "Descripcion": [
            "ID numérico del ingrediente (ver listado en Ingredientes)",
            "Nuevo costo por unidad base (gramo, ml o unidad)",
        ],
        "Obligatorio": ["Sí", "Sí"],
    })

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="precios", index=False)
        instrucciones.to_excel(w, sheet_name="instrucciones", index=False)
    return buffer.getvalue()
