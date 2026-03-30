"""Ingeniería de menú: clasificación de productos por venta y rentabilidad."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.helpers import fmt_ars, fmt_pct

_MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

_CLASS_COLORS = {
    "Estrella": "#2ECC71",
    "Caballo de batalla": "#3498DB",
    "Rompecabezas": "#F39C12",
    "Perro": "#E74C3C",
}

_CLASS_ICONS = {
    "Estrella": "⭐",
    "Caballo de batalla": "🐴",
    "Rompecabezas": "🧩",
    "Perro": "🐶",
}


def render(loader, engine, **kwargs):
    st.header("Ingeniería de menú")

    df_ventas = loader.load_ventas()
    if df_ventas.empty:
        st.info("Sin datos de ventas. Cargá ventas desde la sección correspondiente.")
        return

    tabla = engine.tabla_rentabilidad_productos()

    df_ventas = _add_date_cols(df_ventas)

    # ── Period filter ──
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
    filtro = st.selectbox("Período", opciones_mes, index=0, key="im_filtro_mes")

    if filtro == "Acumulado":
        df_filt = df_ventas
        label_periodo = "Acumulado"
    else:
        parts = filtro.rsplit(" ", 1)
        mes_name, anio_sel = parts[0], int(parts[1])
        mes_num_sel = {v: k for k, v in _MESES_ES.items()}[mes_name]
        df_filt = df_ventas[
            (df_ventas["anio"] == anio_sel) & (df_ventas["mes_num"] == mes_num_sel)
        ]
        label_periodo = filtro

    if df_filt.empty:
        st.warning(f"Sin ventas para el período: {label_periodo}")
        return

    analysis = _build_analysis(df_filt, tabla)
    if analysis.empty:
        st.info("No se pudo cruzar ventas con costos de productos.")
        return

    rubros = sorted(analysis["Rubro"].dropna().unique().tolist())
    rubros = [r for r in rubros if r]

    tab_all, tab_rubro, tab_matriz = st.tabs([
        "Ranking general", "Por rubro", "Matriz",
    ])

    with tab_all:
        _render_ranking(analysis, label_periodo)

    with tab_rubro:
        _render_por_rubro(analysis, rubros, label_periodo)

    with tab_matriz:
        _render_matriz(analysis, label_periodo)


def _add_date_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_fecha_parsed"] = pd.to_datetime(df["fecha_hora"], errors="coerce")
    df["_has_date"] = df["_fecha_parsed"].notna()
    df["anio"] = df["_fecha_parsed"].dt.year
    df["mes_num"] = df["_fecha_parsed"].dt.month
    df["mes"] = df["mes_num"].map(_MESES_ES)
    df["anio_mes"] = (
        df["anio"].astype("Int64").astype(str) + "-"
        + df["mes_num"].apply(lambda x: f"{int(x):02d}" if pd.notna(x) else "00")
    )
    return df


def _build_analysis(df_filt: pd.DataFrame, tabla: pd.DataFrame) -> pd.DataFrame:
    """Cruza ventas filtradas con costos del catálogo para generar el análisis."""
    ventas_agg = df_filt.groupby("producto_norm").agg(
        producto=("producto", "first"),
        rubro=("rubro", "first"),
        subrubro=("subrubro", "first"),
        unidades=("cantidad", "sum"),
        facturacion=("total", "sum"),
        tickets=("numero_pedido", "nunique"),
    ).reset_index()

    if tabla.empty:
        ventas_agg["Costo unit."] = 0
        ventas_agg["Margen %"] = 0
    else:
        cost_map = {}
        for _, row in tabla.iterrows():
            key = str(row["Producto"]).strip().upper()
            cost_map[key] = {
                "costo": float(row.get("Costo", 0) or 0),
                "margen_pct": float(row.get("Margen %", 0) or 0),
                "food_cost_pct": float(row.get("Food Cost %", 0) or 0),
            }
        ventas_agg["Costo unit."] = ventas_agg["producto_norm"].map(
            lambda k: cost_map.get(k, {}).get("costo", 0)
        )
        ventas_agg["Margen %"] = ventas_agg["producto_norm"].map(
            lambda k: cost_map.get(k, {}).get("margen_pct", 0)
        )
        ventas_agg["Food Cost %"] = ventas_agg["producto_norm"].map(
            lambda k: cost_map.get(k, {}).get("food_cost_pct", 0)
        )

    ventas_agg["CMV"] = ventas_agg["Costo unit."] * ventas_agg["unidades"]
    ventas_agg["Margen $"] = ventas_agg["facturacion"] - ventas_agg["CMV"]
    total_fact = ventas_agg["facturacion"].sum()
    ventas_agg["% Facturación"] = (
        ventas_agg["facturacion"] / total_fact * 100 if total_fact > 0 else 0
    )
    total_margen = ventas_agg["Margen $"].sum()
    ventas_agg["% Contribución margen"] = (
        ventas_agg["Margen $"] / total_margen * 100 if total_margen > 0 else 0
    )
    ventas_agg["Precio prom."] = (
        ventas_agg["facturacion"] / ventas_agg["unidades"].replace(0, float("nan"))
    ).fillna(0)

    ventas_agg.rename(columns={
        "producto": "Producto",
        "rubro": "Rubro",
        "subrubro": "Subrubro",
        "unidades": "Unidades",
        "facturacion": "Facturación",
        "tickets": "Tickets",
    }, inplace=True)

    fact_med = ventas_agg["Facturación"].median()
    margen_med = ventas_agg.loc[ventas_agg["Costo unit."] > 0, "Margen %"].median()
    if pd.isna(margen_med):
        margen_med = 50.0

    def _classify(row):
        has_cost = row["Costo unit."] > 0
        alta_venta = row["Facturación"] >= fact_med
        alto_margen = row["Margen %"] >= margen_med if has_cost else False
        if alta_venta and alto_margen:
            return "Estrella"
        if alta_venta and not alto_margen:
            return "Caballo de batalla"
        if not alta_venta and alto_margen:
            return "Rompecabezas"
        return "Perro"

    ventas_agg["Clasificación"] = ventas_agg.apply(_classify, axis=1)
    ventas_agg["_fact_med"] = fact_med
    ventas_agg["_margen_med"] = margen_med

    return ventas_agg.sort_values("Facturación", ascending=False)


def _render_ranking(analysis: pd.DataFrame, label_periodo: str):
    st.subheader(f"Ranking por facturación — {label_periodo}")

    total_fact = analysis["Facturación"].sum()
    total_cmv = analysis["CMV"].sum()
    total_margen = analysis["Margen $"].sum()
    margen_global = total_margen / total_fact * 100 if total_fact > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Productos vendidos", len(analysis))
    c2.metric("Facturación total", fmt_ars(total_fact))
    c3.metric("CMV total", fmt_ars(total_cmv))
    c4.metric("Margen global", fmt_pct(margen_global))

    display_cols = [
        "Producto", "Rubro", "Clasificación", "Unidades", "Facturación",
        "% Facturación", "Costo unit.", "CMV", "Margen %", "Margen $",
        "% Contribución margen",
    ]
    display_cols = [c for c in display_cols if c in analysis.columns]

    st.dataframe(
        analysis[display_cols].style.format({
            "Facturación": "${:,.0f}",
            "% Facturación": "{:.1f}%",
            "Costo unit.": "${:,.0f}",
            "CMV": "${:,.0f}",
            "Margen %": "{:.1f}%",
            "Margen $": "${:,.0f}",
            "% Contribución margen": "{:.1f}%",
            "Unidades": "{:,.0f}",
        }),
        width="stretch",
        hide_index=True,
        height=500,
    )

    st.divider()

    top_n = min(15, len(analysis))
    top = analysis.head(top_n)
    fig = px.bar(
        top, y="Producto", x="Facturación", orientation="h",
        color="Clasificación", color_discrete_map=_CLASS_COLORS,
        hover_data=["Margen %", "Unidades"],
        title=f"Top {top_n} productos por facturación",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)


def _render_por_rubro(analysis: pd.DataFrame, rubros: list, label_periodo: str):
    st.subheader(f"Análisis por rubro — {label_periodo}")

    if not rubros:
        st.info("Sin rubros disponibles.")
        return

    rubro_summary = []
    for rubro in rubros:
        sub = analysis[analysis["Rubro"] == rubro]
        if sub.empty:
            continue
        fact = sub["Facturación"].sum()
        cmv = sub["CMV"].sum()
        margen = (fact - cmv) / fact * 100 if fact > 0 else 0
        rubro_summary.append({
            "Rubro": rubro,
            "Productos": len(sub),
            "Facturación": fact,
            "CMV": cmv,
            "Margen $": fact - cmv,
            "Margen %": margen,
        })

    df_rubro = pd.DataFrame(rubro_summary).sort_values("Facturación", ascending=False)

    st.dataframe(
        df_rubro.style.format({
            "Facturación": "${:,.0f}",
            "CMV": "${:,.0f}",
            "Margen $": "${:,.0f}",
            "Margen %": "{:.1f}%",
        }),
        width="stretch",
        hide_index=True,
    )

    st.divider()

    rubro_sel = st.selectbox("Detalle por rubro", rubros, key="im_rubro_det")
    sub = analysis[analysis["Rubro"] == rubro_sel].copy()
    if sub.empty:
        st.info(f"Sin productos vendidos en {rubro_sel}.")
        return

    fact_rubro = sub["Facturación"].sum()
    cmv_rubro = sub["CMV"].sum()
    margen_rubro = (fact_rubro - cmv_rubro) / fact_rubro * 100 if fact_rubro > 0 else 0

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Productos", len(sub))
    r2.metric("Facturación", fmt_ars(fact_rubro))
    r3.metric("CMV", fmt_ars(cmv_rubro))
    r4.metric("Margen", fmt_pct(margen_rubro))

    sub["% del rubro"] = (sub["Facturación"] / fact_rubro * 100).round(1)
    detail_cols = [
        "Producto", "Clasificación", "Unidades", "Facturación",
        "% del rubro", "Margen %", "Margen $",
    ]
    detail_cols = [c for c in detail_cols if c in sub.columns]

    st.dataframe(
        sub[detail_cols].sort_values("Facturación", ascending=False).style.format({
            "Facturación": "${:,.0f}",
            "% del rubro": "{:.1f}%",
            "Margen %": "{:.1f}%",
            "Margen $": "${:,.0f}",
            "Unidades": "{:,.0f}",
        }),
        width="stretch",
        hide_index=True,
    )

    if len(sub) > 1:
        fig_pie = px.pie(
            sub, values="Facturación", names="Producto",
            title=f"Composición de facturación — {rubro_sel}",
            hole=0.4,
        )
        fig_pie.update_traces(textinfo="label+percent", textposition="outside")
        fig_pie.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_pie, use_container_width=True)


def _render_matriz(analysis: pd.DataFrame, label_periodo: str):
    st.subheader(f"Matriz de ingeniería de menú — {label_periodo}")

    with_cost = analysis[analysis["Costo unit."] > 0].copy()
    if with_cost.empty:
        st.info("No hay productos con costo asignado para graficar la matriz.")
        return

    fact_med = with_cost["_fact_med"].iloc[0]
    margen_med = with_cost["_margen_med"].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    for label, col in zip(
        ["Estrella", "Caballo de batalla", "Rompecabezas", "Perro"],
        [c1, c2, c3, c4],
    ):
        sub = with_cost[with_cost["Clasificación"] == label]
        icon = _CLASS_ICONS[label]
        col.metric(f"{icon} {label}", f"{len(sub)} prod.")

    fig = px.scatter(
        with_cost,
        x="Facturación",
        y="Margen %",
        color="Clasificación",
        size="Margen $",
        hover_data=["Producto", "Unidades", "Costo unit.", "Rubro"],
        title="Facturación vs Margen (tamaño = margen absoluto)",
        color_discrete_map=_CLASS_COLORS,
    )
    fig.add_hline(
        y=margen_med, line_dash="dash", line_color="gray",
        annotation_text=f"Margen mediana: {margen_med:.1f}%",
    )
    fig.add_vline(
        x=fact_med, line_dash="dash", line_color="gray",
        annotation_text=f"Fact. mediana: ${fact_med:,.0f}",
    )
    fig.update_layout(height=550)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown("### Detalle por clasificación")

    for label in ["Estrella", "Caballo de batalla", "Rompecabezas", "Perro"]:
        subset = with_cost[with_cost["Clasificación"] == label]
        if subset.empty:
            continue
        icon = _CLASS_ICONS[label]
        fact_grupo = subset["Facturación"].sum()
        margen_grupo = subset["Margen $"].sum()

        with st.expander(
            f"{icon} {label} — {len(subset)} productos — "
            f"Fact: {fmt_ars(fact_grupo)} — Margen: {fmt_ars(margen_grupo)}"
        ):
            detail_cols = [
                "Producto", "Rubro", "Unidades", "Facturación",
                "Margen %", "Margen $", "% Contribución margen",
            ]
            detail_cols = [c for c in detail_cols if c in subset.columns]
            st.dataframe(
                subset[detail_cols]
                .sort_values("Facturación", ascending=False)
                .style.format({
                    "Facturación": "${:,.0f}",
                    "Margen %": "{:.1f}%",
                    "Margen $": "${:,.0f}",
                    "% Contribución margen": "{:.1f}%",
                    "Unidades": "{:,.0f}",
                }),
                width="stretch",
                hide_index=True,
            )
