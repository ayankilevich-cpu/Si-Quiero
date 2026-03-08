"""Cuadro de rentabilidad de productos."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from utils.helpers import fmt_ars, fmt_pct


def render(loader, engine, **kwargs):
    st.header("Rentabilidad de productos")

    tabla = engine.tabla_rentabilidad_productos()

    if tabla.empty:
        st.info("Sin datos de rentabilidad. Asegúrese de tener componentes y costos cargados.")
        return

    # ── Filtros ──
    col1, col2, col3, col4 = st.columns(4)
    cat = col1.selectbox(
        "Categoría", ["Todas"] + sorted(tabla["Categoría"].dropna().unique().tolist()),
        key="rent_cat",
    )
    tipo = col2.selectbox(
        "Tipo", ["Todos"] + sorted(tabla["Tipo"].dropna().unique().tolist()),
        key="rent_tipo",
    )
    estado = col3.selectbox(
        "Estado", ["Todos", "Saludable", "Atención", "Crítico", "Sin precio"],
        key="rent_estado",
    )
    ver_sin_costo = col4.selectbox(
        "Mostrar", ["Solo con costo", "Todos", "Solo sin costo"],
        key="rent_ver",
    )

    filtered = tabla.copy()
    if cat != "Todas":
        filtered = filtered[filtered["Categoría"] == cat]
    if tipo != "Todos":
        filtered = filtered[filtered["Tipo"] == tipo]
    if estado != "Todos":
        filtered = filtered[filtered["Estado"] == estado]
    if ver_sin_costo == "Solo con costo":
        filtered = filtered[filtered["Costo"] > 0]
    elif ver_sin_costo == "Solo sin costo":
        filtered = filtered[filtered["Costo"] == 0]

    # ── KPIs ──
    solo_con_costo = filtered[(filtered["Costo"] > 0) & (filtered["Precio venta"] > 0)]
    total_con_costo = tabla[tabla["Costo"] > 0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Productos", len(filtered))
    c2.metric("Con costeo", f"{len(total_con_costo)} / {len(tabla)}")
    c3.metric("Margen prom.", fmt_pct(solo_con_costo["Margen %"].mean()) if not solo_con_costo.empty else "—")
    c4.metric("Food cost prom.", fmt_pct(solo_con_costo["Food Cost %"].mean()) if not solo_con_costo.empty else "—")

    # ── Tabla ──
    st.dataframe(
        filtered.sort_values("Costo", ascending=False),
        width="stretch",
        hide_index=True,
    )

    # ── Exportar ──
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar CSV", csv, "rentabilidad_productos.csv", "text/csv")

    # ── Visualizaciones ──
    if not solo_con_costo.empty:
        st.divider()

        tab_hist, tab_fc, tab_scatter = st.tabs(["Distribución margen", "Food Cost por categoría", "Costo vs Precio"])

        with tab_hist:
            fig = px.histogram(
                solo_con_costo, x="Margen %", nbins=20,
                title="Distribución de márgenes (%)",
                color="Estado",
                color_discrete_map={"Saludable": "#2ECC71", "Atención": "#F39C12", "Crítico": "#E74C3C"},
            )
            st.plotly_chart(fig, width="stretch")

        with tab_fc:
            fc_cat = solo_con_costo.groupby("Categoría").agg(
                food_cost_prom=("Food Cost %", "mean"),
                n_productos=("Producto", "count"),
            ).reset_index().sort_values("food_cost_prom", ascending=False)
            fig2 = px.bar(
                fc_cat, x="Categoría", y="food_cost_prom",
                title="Food Cost promedio por categoría",
                labels={"food_cost_prom": "Food Cost %", "Categoría": ""},
                text="n_productos",
                color="food_cost_prom", color_continuous_scale="RdYlGn_r",
            )
            fig2.update_traces(texttemplate="%{text} prod.", textposition="outside")
            st.plotly_chart(fig2, width="stretch")

        with tab_scatter:
            fig3 = px.scatter(
                solo_con_costo, x="Costo", y="Precio venta",
                color="Estado", hover_data=["Producto", "Margen %", "Food Cost %"],
                title="Costo vs Precio de venta",
                color_discrete_map={"Saludable": "#2ECC71", "Atención": "#F39C12", "Crítico": "#E74C3C"},
            )
            st.plotly_chart(fig3, width="stretch")
