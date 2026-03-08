"""Cuadro de rentabilidad de combos."""

from __future__ import annotations

import streamlit as st

from utils.helpers import fmt_ars, fmt_pct


def render(loader, engine, **kwargs):
    st.header("Rentabilidad de combos")

    df_combos = loader.load_combos()
    if df_combos.empty:
        st.info("No hay combos cargados.")
        return

    for _, combo in df_combos.iterrows():
        cid = str(combo["combo_id"])
        result = engine.costo_combo(cid)

        with st.expander(f"{result.get('nombre', cid)} — Precio: {fmt_ars(result.get('precio_combo', 0))} — Margen: {fmt_pct(result.get('margen_pct', 0))}"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Precio combo", fmt_ars(result.get("precio_combo", 0)))
            c2.metric("Costo combo", fmt_ars(result.get("costo_combo", 0)))
            c3.metric("Margen %", fmt_pct(result.get("margen_pct", 0)))
            c4.metric("Food Cost %", fmt_pct(result.get("food_cost_pct", 0)))

            if result.get("items"):
                st.markdown("**Componentes del combo:**")
                for item in result["items"]:
                    st.markdown(
                        f"• **{item['nombre']}** × {item['cantidad']:.0f}: "
                        f"costo {fmt_ars(item['costo_total'])} — "
                        f"precio individual {fmt_ars(item['precio_individual'])}"
                    )
                st.markdown(f"**Suma precios individuales:** {fmt_ars(result.get('precio_individual_total', 0))}")
                st.markdown(f"**Descuento implícito:** {fmt_pct(result.get('descuento_pct', 0))}")
            else:
                st.warning("Este combo no tiene items asignados.")
