"""Simulador de costos: impacto de cambios en ingredientes y helado."""

from __future__ import annotations

import streamlit as st
import plotly.express as px

from utils.helpers import fmt_ars, fmt_pct


def render(loader, engine, **kwargs):
    st.header("Simulador de costos")

    df_ing = loader.load_ingredientes()
    ice_svc = kwargs.get("ice_svc") or engine.ice_svc
    helado_info = ice_svc.costo_ponderado_general()

    tab1, tab2 = st.tabs(["Simular cambio ingrediente", "Simular cambio helado"])

    with tab1:
        _simular_ingrediente(df_ing, engine)

    with tab2:
        _simular_helado(helado_info, engine)


def _simular_ingrediente(df_ing, engine):
    st.subheader("Impacto de cambio de costo de ingrediente")

    if df_ing.empty:
        st.info("Sin ingredientes cargados.")
        return

    opciones = dict(zip(
        df_ing["ingrediente"].tolist(),
        df_ing["ingredient_id"].astype(str).tolist(),
    ))
    nombre = st.selectbox("Ingrediente a simular", sorted(opciones.keys()), key="sim_ing")
    ing_id = opciones.get(nombre)

    row = df_ing[df_ing["ingredient_id"].astype(str) == ing_id]
    costo_actual = float(row.iloc[0]["costo_actual"]) if not row.empty else 0

    st.caption(f"Costo actual: {fmt_ars(costo_actual, 2)}")

    modo = st.radio("Modo de cambio", ["Porcentaje", "Valor absoluto"], horizontal=True, key="sim_modo")

    if modo == "Porcentaje":
        pct = st.slider("Variación (%)", -50, 100, 10, key="sim_pct")
        nuevo = costo_actual * (1 + pct / 100)
    else:
        nuevo = st.number_input("Nuevo costo", min_value=0.0, value=costo_actual, key="sim_abs")

    if st.button("Simular", type="primary", key="btn_sim_ing"):
        cambios = {ing_id: nuevo}
        result = engine.simular_cambio_precio(cambios)
        _mostrar_resultado(result, f"Costo {nombre}: {fmt_ars(costo_actual, 2)} → {fmt_ars(nuevo, 2)}")


def _simular_helado(helado_info, engine):
    st.subheader("Impacto de cambio de costo del helado")

    costo_actual = helado_info.get("costo_kg", 0)
    st.caption(f"Costo ponderado actual: {fmt_ars(costo_actual)} /kg")

    pct = st.slider("Variación del costo del helado (%)", -30, 50, 10, key="sim_helado_pct")
    nuevo = costo_actual * (1 + pct / 100)
    st.caption(f"Nuevo costo simulado: {fmt_ars(nuevo)} /kg")

    if st.button("Simular impacto", type="primary", key="btn_sim_helado"):
        cambios = {"__helado_kg__": nuevo}
        result = engine.simular_cambio_precio(cambios)
        _mostrar_resultado(result, f"Helado: {fmt_ars(costo_actual)} → {fmt_ars(nuevo)} /kg")


def _mostrar_resultado(df, titulo):
    st.markdown(f"**{titulo}**")
    if df.empty:
        st.info("No hay productos afectados.")
        return

    st.dataframe(df, width="stretch", hide_index=True)
    st.caption(f"{len(df)} productos afectados")

    fig = px.bar(
        df.head(20), y="Producto", x="Delta margen pp", orientation="h",
        title="Impacto en margen (puntos porcentuales)",
        color="Delta margen pp",
        color_continuous_scale="RdYlGn",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, width="stretch")
