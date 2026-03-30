"""Dashboard principal con datos reales de ventas y costeo."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.helpers import fmt_ars, fmt_pct

_MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def _add_date_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas de fecha parseada, año y mes. No descarta filas."""
    df = df.copy()
    if df.empty or "fecha_hora" not in df.columns:
        return df
    df["_fecha_parsed"] = pd.to_datetime(df["fecha_hora"], dayfirst=True, errors="coerce")
    df["_has_date"] = df["_fecha_parsed"].notna()
    df["anio"] = df["_fecha_parsed"].dt.year
    df["mes_num"] = df["_fecha_parsed"].dt.month
    df["mes"] = df["mes_num"].map(_MESES_ES)
    df["anio_mes"] = (
        df["anio"].astype("Int64").astype(str) + "-" +
        df["mes_num"].apply(lambda x: f"{int(x):02d}" if pd.notna(x) else "00")
    )
    return df


def _build_resumen_from_detail(df: pd.DataFrame) -> pd.DataFrame:
    """Genera un resumen por producto a partir del detalle filtrado."""
    if df.empty or "producto_norm" not in df.columns:
        return pd.DataFrame()
    agg = df.groupby("producto_norm").agg(
        producto=("producto", "first"),
        codigo_venta=("codigo_venta", "first"),
        rubro=("rubro", "first"),
        subrubro=("subrubro", "first"),
        area=("area", "first"),
        tickets=("numero_pedido", "nunique"),
        unidades_vendidas_mes=("cantidad", "sum"),
        facturacion_mes=("total", "sum"),
    ).reset_index()
    agg["precio_promedio_realizado"] = (
        agg["facturacion_mes"] / agg["unidades_vendidas_mes"].replace(0, float("nan"))
    ).fillna(0).round(2)
    return agg


def render(loader, engine, **kwargs):
    st.header("Dashboard Principal")

    df_raw = loader.load_ventas()
    df_ventas = _add_date_columns(df_raw)
    tabla = engine.tabla_rentabilidad_productos()

    ice_svc = kwargs.get("ice_svc") or engine.ice_svc
    helado_info = ice_svc.costo_ponderado_general()

    # ── Filtro de período ──
    is_acumulado = True
    label_periodo = "Acumulado"

    if not df_ventas.empty:
        df_with_dates = df_ventas[df_ventas["_has_date"]]
        meses_disponibles = (
            df_with_dates[["anio_mes", "anio", "mes_num", "mes"]]
            .drop_duplicates()
            .sort_values("anio_mes")
        )
        opciones_mes = ["Acumulado"] + [
            f"{row['mes']} {row['anio']:.0f}"
            for _, row in meses_disponibles.iterrows()
        ]
        filtro = st.selectbox("Período", opciones_mes, index=0, key="dash_filtro_mes")

        if filtro == "Acumulado":
            df_filt = df_ventas
        else:
            is_acumulado = False
            parts = filtro.rsplit(" ", 1)
            mes_name, anio_sel = parts[0], int(parts[1])
            mes_num_sel = {v: k for k, v in _MESES_ES.items()}[mes_name]
            df_filt = df_ventas[
                (df_ventas["anio"] == anio_sel) & (df_ventas["mes_num"] == mes_num_sel)
            ]
            label_periodo = filtro
    else:
        df_filt = df_ventas
        label_periodo = "Sin datos"

    df_vr = _build_resumen_from_detail(df_filt)

    # ── KPIs ──
    st.subheader(f"Indicadores — {label_periodo}")
    col1, col2, col3, col4 = st.columns(4)

    total_facturacion = df_filt["total"].sum() if not df_filt.empty else 0
    total_unidades = df_filt["cantidad"].sum() if not df_filt.empty else 0
    n_productos = df_filt["producto_norm"].nunique() if not df_filt.empty else 0
    margen_prom = tabla["Margen %"].mean() if not tabla.empty else 0

    col1.metric("Facturación total", fmt_ars(total_facturacion))
    col2.metric("Unidades vendidas", f"{int(total_unidades):,}".replace(",", "."))
    col3.metric("Productos vendidos", n_productos)
    col4.metric("Margen promedio", fmt_pct(margen_prom))

    n_tickets = df_filt["numero_pedido"].nunique() if not df_filt.empty else 0
    ticket_prom = total_facturacion / n_tickets if n_tickets > 0 else 0

    fact_helado = 0
    if not df_filt.empty and "rubro" in df_filt.columns:
        fact_helado = df_filt.loc[
            df_filt["rubro"].str.upper().str.contains("HELAD", na=False), "total"
        ].sum()
    pct_helado = (fact_helado / total_facturacion * 100) if total_facturacion > 0 else 0

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Tickets", f"{n_tickets:,}".replace(",", "."))
    col6.metric("Ticket promedio", fmt_ars(ticket_prom))
    col7.metric("Facturación helado", fmt_ars(fact_helado))
    col8.metric("Participación helado", fmt_pct(pct_helado))

    col9, col10, col11, col12 = st.columns(4)
    col9.metric("Costo helado / kg", fmt_ars(helado_info["costo_kg"]))
    col10.metric("Helado comprado", f'{helado_info["total_kg"]:,.1f} kg')
    col11.metric("Remitos cargados", helado_info["n_remitos"])
    fact_no_helado = total_facturacion - fact_helado
    col12.metric("Fact. sin helado", fmt_ars(fact_no_helado))

    st.divider()

    # ── Tabs ──
    tab1, tab2, tab3, tab4 = st.tabs([
        "Facturación por rubro", "Top productos", "Rentabilidad", "Alertas",
    ])

    with tab1:
        _render_facturacion_rubro(df_filt, total_facturacion)

    with tab2:
        _render_top_productos(df_vr)

    with tab3:
        _render_rentabilidad(tabla)

    with tab4:
        _render_alertas(kwargs.get("alert_svc"))


def _render_facturacion_rubro(df_ventas: pd.DataFrame, total_facturacion: float):
    if df_ventas.empty or "rubro" not in df_ventas.columns:
        st.info("Sin datos de ventas cargados.")
        return

    fact_rubro = df_ventas.groupby("rubro")["total"].sum().reset_index()
    fact_rubro = fact_rubro.sort_values("total", ascending=False)
    fact_rubro["participacion"] = (fact_rubro["total"] / total_facturacion * 100).round(1)

    col_chart, col_pie = st.columns(2)

    with col_chart:
        fig = px.bar(
            fact_rubro, x="rubro", y="total",
            title="Facturación por rubro",
            labels={"rubro": "Rubro", "total": "Facturación ($)"},
            color="rubro",
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_pie:
        fig_pie = px.pie(
            fact_rubro, values="total", names="rubro",
            title="Participación por rubro",
            hole=0.4,
        )
        fig_pie.update_traces(textinfo="percent+label", textposition="outside")
        fig_pie.update_layout(showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

    if "subrubro" in df_ventas.columns:
        fact_sub = df_ventas.groupby(["rubro", "subrubro"])["total"].sum().reset_index()
        fact_sub = fact_sub.sort_values("total", ascending=False).head(15)
        fig2 = px.bar(
            fact_sub, x="subrubro", y="total", color="rubro",
            title="Top 15 subrubros por facturación",
            labels={"subrubro": "Subrubro", "total": "Facturación ($)"},
        )
        st.plotly_chart(fig2, use_container_width=True)


def _render_top_productos(df_vr: pd.DataFrame):
    if df_vr.empty:
        st.info("Sin resumen de ventas.")
        return

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
    st.plotly_chart(fig3, use_container_width=True)

    top_unidades = df_vr.nlargest(15, col_cant)
    fig4 = px.bar(
        top_unidades, y=col_prod, x=col_cant, orientation="h",
        title="Top 15 productos por unidades",
        labels={col_prod: "Producto", col_cant: "Unidades"},
        color=col_cant, color_continuous_scale="Purp",
    )
    fig4.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
    st.plotly_chart(fig4, use_container_width=True)


def _render_rentabilidad(tabla: pd.DataFrame):
    if tabla.empty:
        st.info("Sin datos de rentabilidad. Complete los componentes de productos.")
        return

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Top 10 productos con mayor margen %**")
        top_margin = tabla[tabla["Margen %"] > 0].nlargest(10, "Margen %")
        fig5 = px.bar(
            top_margin, y="Producto", x="Margen %", orientation="h",
            color="Margen %", color_continuous_scale="Greens",
        )
        fig5.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
        st.plotly_chart(fig5, use_container_width=True)

    with c2:
        st.markdown("**Top 10 productos con menor margen %**")
        with_cost = tabla[(tabla["Costo"] > 0) & (tabla["Precio venta"] > 0)]
        low_margin = with_cost.nsmallest(10, "Margen %")
        fig6 = px.bar(
            low_margin, y="Producto", x="Margen %", orientation="h",
            color="Margen %", color_continuous_scale="Reds_r",
        )
        fig6.update_layout(yaxis={"categoryorder": "total descending"}, showlegend=False)
        st.plotly_chart(fig6, use_container_width=True)

    st.markdown("**Costo vs Precio de venta**")
    scatter_df = tabla[(tabla["Costo"] > 0) & (tabla["Precio venta"] > 0)]
    if not scatter_df.empty:
        fig7 = px.scatter(
            scatter_df, x="Costo", y="Precio venta",
            color="Estado", hover_data=["Producto", "Margen %"],
            title="Costo vs Precio de venta",
        )
        st.plotly_chart(fig7, use_container_width=True)


def _render_alertas(alert_svc):
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
