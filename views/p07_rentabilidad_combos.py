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

    tab1, tab2 = st.tabs(["Rentabilidad", "Modificar precio"])

    with tab1:
        _render_rentabilidad(df_combos, engine)

    with tab2:
        _render_modificar_precio(df_combos, loader, engine)


def _render_rentabilidad(df_combos, engine):
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
                        f"- **{item['nombre']}** x {item['cantidad']:.0f}: "
                        f"costo {fmt_ars(item['costo_total'])} — "
                        f"precio individual {fmt_ars(item['precio_individual'])}"
                    )
                st.markdown(f"**Suma precios individuales:** {fmt_ars(result.get('precio_individual_total', 0))}")
                st.markdown(f"**Descuento implícito:** {fmt_pct(result.get('descuento_pct', 0))}")
            else:
                st.warning("Este combo no tiene items asignados.")


def _render_modificar_precio(df_combos, loader, engine):
    st.subheader("Modificar precio de combo")

    opciones = dict(zip(
        df_combos["combo_name"].tolist(),
        df_combos["combo_id"].tolist(),
    ))
    sel = st.selectbox("Combo", sorted(opciones.keys()), key="mod_combo_sel")
    cid = opciones.get(sel)
    if cid is None:
        return

    result = engine.costo_combo(str(cid))
    precio_actual = result.get("precio_combo", 0)
    costo = result.get("costo_combo", 0)
    margen_actual = result.get("margen_pct", 0)

    c1, c2, c3 = st.columns(3)
    c1.metric("Precio actual", fmt_ars(precio_actual))
    c2.metric("Costo", fmt_ars(costo))
    c3.metric("Margen actual", fmt_pct(margen_actual))

    if result.get("items"):
        st.caption("Composición: " + " + ".join(
            f"{it['nombre']} x{it['cantidad']:.0f}" for it in result["items"]
        ))

    nuevo_precio = st.number_input(
        "Nuevo precio de venta ($)",
        min_value=0.0,
        value=float(precio_actual),
        step=100.0,
        format="%.0f",
        key="mod_combo_input",
    )

    if nuevo_precio != precio_actual and nuevo_precio > 0:
        nuevo_margen = (nuevo_precio - costo) / nuevo_precio * 100 if nuevo_precio > 0 else 0
        nuevo_fc = costo / nuevo_precio * 100 if nuevo_precio > 0 else 0

        st.markdown("**Simulación con nuevo precio:**")
        s1, s2, s3 = st.columns(3)
        delta_precio = nuevo_precio - precio_actual
        delta_margen = nuevo_margen - margen_actual
        s1.metric("Nuevo precio", fmt_ars(nuevo_precio), delta=f"{delta_precio:+,.0f}")
        s2.metric("Nuevo margen", fmt_pct(nuevo_margen), delta=f"{delta_margen:+.1f} pp")
        s3.metric("Nuevo Food Cost", fmt_pct(nuevo_fc))

    if st.button(
        "Guardar nuevo precio",
        type="primary",
        key="btn_save_combo_precio",
        disabled=(nuevo_precio == precio_actual or nuevo_precio <= 0),
    ):
        df_fresh = loader.load_combos()
        df_fresh.loc[df_fresh["combo_id"] == cid, "precio_venta"] = nuevo_precio
        combo_items = loader.load_combo_items()
        loader.save_combos(df_fresh, combo_items)
        st.success(
            f"Precio de **{sel}** actualizado: "
            f"{fmt_ars(precio_actual)} → {fmt_ars(nuevo_precio)}"
        )
        st.rerun()
