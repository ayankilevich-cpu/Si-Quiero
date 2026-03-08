"""Dashboard principal con datos reales de ventas y costeo."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.helpers import fmt_ars, fmt_pct


def render(loader, engine, **kwargs):
    st.header("Dashboard Principal")

    df_ventas = loader.load_ventas()
    df_vr = loader.load_ventas_resumen()
    tabla = engine.tabla_rentabilidad_productos()

    ice_svc = kwargs.get("ice_svc") or engine.ice_svc
    helado_info = ice_svc.costo_ponderado_general()

    # ── KPIs ──
    st.subheader("Indicadores generales")
    col1, col2, col3, col4 = st.columns(4)

    total_facturacion = df_ventas["total"].sum() if not df_ventas.empty else 0
    total_unidades = df_ventas["cantidad"].sum() if not df_ventas.empty else 0
    n_productos = len(df_vr) if not df_vr.empty else 0
    margen_prom = tabla["Margen %"].mean() if not tabla.empty else 0

    col1.metric("Facturación total", fmt_ars(total_facturacion))
    col2.metric("Unidades vendidas", f"{int(total_unidades):,}".replace(",", "."))
    col3.metric("Productos activos", n_productos)
    col4.metric("Margen promedio", fmt_pct(margen_prom))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Costo helado / kg", fmt_ars(helado_info["costo_kg"]))
    col6.metric("Helado comprado", f'{helado_info["total_kg"]:,.1f} kg')
    col7.metric("Remitos cargados", helado_info["n_remitos"])
    ticket_prom = total_facturacion / df_ventas["numero_pedido"].nunique() if not df_ventas.empty and df_ventas["numero_pedido"].nunique() > 0 else 0
    col8.metric("Ticket promedio", fmt_ars(ticket_prom))

    st.divider()

    # ── Facturación por categoría ──
    tab1, tab2, tab3, tab4 = st.tabs([
        "Facturación por rubro", "Top productos", "Rentabilidad", "Alertas",
    ])

    with tab1:
        if not df_ventas.empty and "rubro" in df_ventas.columns:
            fact_rubro = df_ventas.groupby("rubro")["total"].sum().reset_index()
            fact_rubro = fact_rubro.sort_values("total", ascending=False)
            fig = px.bar(
                fact_rubro, x="rubro", y="total",
                title="Facturación por rubro",
                labels={"rubro": "Rubro", "total": "Facturación ($)"},
                color="rubro",
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, width="stretch")

            if "subrubro" in df_ventas.columns:
                fact_sub = df_ventas.groupby(["rubro", "subrubro"])["total"].sum().reset_index()
                fact_sub = fact_sub.sort_values("total", ascending=False).head(15)
                fig2 = px.bar(
                    fact_sub, x="subrubro", y="total", color="rubro",
                    title="Top 15 subrubros por facturación",
                    labels={"subrubro": "Subrubro", "total": "Facturación ($)"},
                )
                st.plotly_chart(fig2, width="stretch")
        else:
            st.info("Sin datos de ventas cargados.")

    with tab2:
        if not df_vr.empty:
            col_total = "facturacion_mes" if "facturacion_mes" in df_vr.columns else "total"
            col_cant = "unidades_vendidas_mes" if "unidades_vendidas_mes" in df_vr.columns else "cantidad"
            col_prod = "producto" if "producto" in df_vr.columns else df_vr.columns[0]

            top_ventas = df_vr.nlargest(15, col_total)
            fig3 = px.bar(
                top_ventas, y=col_prod, x=col_total, orientation="h",
                title="Top 15 productos por facturación",
                labels={col_prod: "Producto", col_total: "Facturación ($)"},
                color=col_total, color_continuous_scale="Tealgrn",
            )
            fig3.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
            st.plotly_chart(fig3, width="stretch")

            top_unidades = df_vr.nlargest(15, col_cant)
            fig4 = px.bar(
                top_unidades, y=col_prod, x=col_cant, orientation="h",
                title="Top 15 productos por unidades",
                labels={col_prod: "Producto", col_cant: "Unidades"},
                color=col_cant, color_continuous_scale="Purp",
            )
            fig4.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
            st.plotly_chart(fig4, width="stretch")
        else:
            st.info("Sin resumen de ventas.")

    with tab3:
        if not tabla.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Top 10 productos con mayor margen %**")
                top_margin = tabla[tabla["Margen %"] > 0].nlargest(10, "Margen %")
                fig5 = px.bar(
                    top_margin, y="Producto", x="Margen %", orientation="h",
                    color="Margen %", color_continuous_scale="Greens",
                )
                fig5.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
                st.plotly_chart(fig5, width="stretch")

            with c2:
                st.markdown("**Top 10 productos con menor margen %**")
                with_cost = tabla[(tabla["Costo"] > 0) & (tabla["Precio venta"] > 0)]
                low_margin = with_cost.nsmallest(10, "Margen %")
                fig6 = px.bar(
                    low_margin, y="Producto", x="Margen %", orientation="h",
                    color="Margen %", color_continuous_scale="Reds_r",
                )
                fig6.update_layout(yaxis={"categoryorder": "total descending"}, showlegend=False)
                st.plotly_chart(fig6, width="stretch")

            st.markdown("**Costo vs Precio de venta**")
            scatter_df = tabla[(tabla["Costo"] > 0) & (tabla["Precio venta"] > 0)]
            if not scatter_df.empty:
                fig7 = px.scatter(
                    scatter_df, x="Costo", y="Precio venta",
                    color="Estado", hover_data=["Producto", "Margen %"],
                    title="Costo vs Precio de venta",
                )
                st.plotly_chart(fig7, width="stretch")
        else:
            st.info("Sin datos de rentabilidad. Complete los componentes de productos.")

    with tab4:
        alert_svc = kwargs.get("alert_svc")
        if alert_svc:
            alertas = alert_svc.todas_las_alertas()
            if alertas:
                for a in alertas[:20]:
                    icon = {"alta": "🔴", "media": "🟡", "baja": "🟢"}.get(a["severidad"], "⚪")
                    st.markdown(f"{icon} **[{a['tipo']}]** {a['mensaje']}")
            else:
                st.success("Sin alertas activas.")
        else:
            st.info("Servicio de alertas no disponible.")
