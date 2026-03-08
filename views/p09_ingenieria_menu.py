"""Ingeniería de menú: clasificación de productos (estrella, caballo, rompecabezas, perro)."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from utils.helpers import fmt_ars, fmt_pct


def render(loader, engine, **kwargs):
    st.header("Ingeniería de menú")

    tabla = engine.tabla_rentabilidad_productos()
    df_vr = loader.load_ventas_resumen()

    if tabla.empty:
        st.info("Sin datos de rentabilidad disponibles.")
        return

    con_costo = tabla[(tabla["Costo"] > 0) & (tabla["Precio venta"] > 0)].copy()

    if not df_vr.empty:
        col_prod = "producto" if "producto" in df_vr.columns else df_vr.columns[0]
        col_cant = "unidades_vendidas_mes" if "unidades_vendidas_mes" in df_vr.columns else "cantidad"
        ventas_map = dict(zip(df_vr[col_prod].str.strip().str.upper(), df_vr[col_cant]))
        con_costo["Unidades vendidas"] = con_costo["Producto"].str.strip().str.upper().map(ventas_map).fillna(0)
    else:
        con_costo["Unidades vendidas"] = 0

    if con_costo.empty:
        st.info("No hay productos con costo y precio para analizar.")
        return

    margen_med = con_costo["Margen %"].median()
    ventas_med = con_costo["Unidades vendidas"].median()

    def clasificar(row):
        alto_margen = row["Margen %"] >= margen_med
        alta_venta = row["Unidades vendidas"] >= ventas_med
        if alto_margen and alta_venta:
            return "Estrella"
        elif not alto_margen and alta_venta:
            return "Caballo de batalla"
        elif alto_margen and not alta_venta:
            return "Rompecabezas"
        else:
            return "Perro"

    con_costo["Clasificación"] = con_costo.apply(clasificar, axis=1)

    # ── KPIs ──
    c1, c2, c3, c4 = st.columns(4)
    for label, col in zip(
        ["Estrella", "Caballo de batalla", "Rompecabezas", "Perro"],
        [c1, c2, c3, c4],
    ):
        n = len(con_costo[con_costo["Clasificación"] == label])
        col.metric(label, n)

    # ── Scatter ──
    color_map = {
        "Estrella": "#2ECC71",
        "Caballo de batalla": "#3498DB",
        "Rompecabezas": "#F39C12",
        "Perro": "#E74C3C",
    }

    fig = px.scatter(
        con_costo, x="Unidades vendidas", y="Margen %",
        color="Clasificación", hover_data=["Producto", "Precio venta", "Costo"],
        title="Matriz de ingeniería de menú",
        color_discrete_map=color_map,
    )
    fig.add_hline(y=margen_med, line_dash="dash", line_color="gray",
                  annotation_text=f"Margen mediana: {margen_med:.1f}%")
    fig.add_vline(x=ventas_med, line_dash="dash", line_color="gray",
                  annotation_text=f"Ventas mediana: {ventas_med:.0f}")
    st.plotly_chart(fig, width="stretch")

    # ── Tabla por clasificación ──
    for label in ["Estrella", "Caballo de batalla", "Rompecabezas", "Perro"]:
        subset = con_costo[con_costo["Clasificación"] == label]
        if not subset.empty:
            with st.expander(f"{label} ({len(subset)} productos)"):
                st.dataframe(
                    subset[["Producto", "Categoría", "Precio venta", "Costo",
                            "Margen %", "Food Cost %", "Unidades vendidas"]].sort_values("Margen %", ascending=False),
                    width="stretch", hide_index=True,
                )
