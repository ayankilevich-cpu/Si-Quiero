"""Gestión de productos: listado, componentes, costeo y fichas de costeo."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.helpers import fmt_ars, fmt_pct, estado_margen, color_estado


def render(loader, engine, **kwargs):
    st.header("Gestión de productos")

    df_prod = loader.load_productos()
    df_comp = loader.load_componentes()

    if df_prod.empty:
        st.warning("No hay productos cargados.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "Fichas de costeo", "Catálogo", "Componentes", "Costeo rápido",
    ])

    with tab1:
        _render_fichas(df_prod, engine)

    with tab2:
        _render_catalogo(df_prod)

    with tab3:
        _render_componentes(df_prod, df_comp)

    with tab4:
        _render_costeo(df_prod, engine)


def _nombre_col(df):
    return "producto" if "producto" in df.columns else "nombre_producto"


# ─────────────────────────────────────────────
# FICHAS DE COSTEO
# ─────────────────────────────────────────────

def _render_fichas(df_prod, engine):
    st.subheader("Fichas de costeo — Productos elaborados")
    st.caption(
        "Vista desagregada de cada producto elaborado (armados y recetas) "
        "con detalle de ingredientes, cantidades, costos unitarios y margen."
    )

    ncol = _nombre_col(df_prod)

    elaborados = df_prod[
        df_prod["tipo_producto"].isin(["armado", "receta"])
    ].copy()

    if elaborados.empty:
        st.info("No hay productos elaborados (armados o recetas).")
        return

    # Filtros
    col1, col2 = st.columns(2)
    categorias = sorted(elaborados["categoria"].dropna().unique().tolist())
    cat = col1.selectbox("Categoría", ["Todas"] + categorias, key="ficha_cat")
    tipos = sorted(elaborados["tipo_producto"].dropna().unique().tolist())
    tipo = col2.selectbox("Tipo", ["Todos"] + tipos, key="ficha_tipo")

    if cat != "Todas":
        elaborados = elaborados[elaborados["categoria"] == cat]
    if tipo != "Todos":
        elaborados = elaborados[elaborados["tipo_producto"] == tipo]

    st.caption(f"{len(elaborados)} productos elaborados")
    st.divider()

    # Calcular todos los costos y ordenar
    fichas = []
    for _, prod in elaborados.iterrows():
        pid = str(prod["product_id"])
        result = engine.costo_producto(pid)
        fichas.append({
            "pid": pid,
            "nombre": str(prod.get(ncol, "")),
            "categoria": str(prod.get("categoria", "") or ""),
            "tipo": str(prod.get("tipo_producto", "")),
            "precio": result.get("precio_venta", 0),
            "costo": result.get("costo", 0),
            "margen_pct": result.get("margen_pct", 0),
            "food_cost_pct": result.get("food_cost_pct", 0),
            "estado": result.get("estado", ""),
            "detalle": result.get("detalle", []),
        })

    fichas.sort(key=lambda x: x["categoria"] + x["nombre"])

    # Resumen rápido en tabla
    resumen_data = [{
        "Producto": f["nombre"],
        "Categoría": f["categoria"],
        "Tipo": f["tipo"],
        "Precio venta": f["precio"],
        "Costo": f["costo"],
        "Margen %": f["margen_pct"],
        "Food Cost %": f["food_cost_pct"],
        "Estado": f["estado"],
    } for f in fichas if f["costo"] > 0]

    if resumen_data:
        with st.expander("Tabla resumen (click para expandir)", expanded=False):
            st.dataframe(
                pd.DataFrame(resumen_data).sort_values("Categoría"),
                width="stretch", hide_index=True,
            )

    st.divider()

    # Fichas individuales
    cat_actual = ""
    for f in fichas:
        if f["costo"] == 0 and not f["detalle"]:
            continue

        if f["categoria"] != cat_actual:
            cat_actual = f["categoria"]
            st.markdown(f"### {cat_actual or 'Sin categoría'}")

        estado_color = color_estado(f["estado"])
        estado_icon = {"Saludable": "🟢", "Atención": "🟡", "Crítico": "🔴"}.get(f["estado"], "⚪")

        with st.expander(
            f"{estado_icon} **{f['nombre']}** — "
            f"Costo: {fmt_ars(f['costo'])} | "
            f"PV: {fmt_ars(f['precio'])} | "
            f"Margen: {f['margen_pct']:.1f}% | "
            f"FC: {f['food_cost_pct']:.1f}%"
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Costo total", fmt_ars(f["costo"]))
            c2.metric("Precio venta", fmt_ars(f["precio"]))
            c3.metric("Margen", fmt_pct(f["margen_pct"]))
            c4.metric("Food Cost", fmt_pct(f["food_cost_pct"]))

            if f["detalle"]:
                st.markdown("**Composición:**")

                rows = []
                for d in f["detalle"]:
                    rows.append({
                        "Tipo": d.get("tipo", ""),
                        "Insumo": d.get("nombre", ""),
                        "Cantidad": d.get("cantidad", 0),
                        "Unidad": d.get("unidad", ""),
                        "Costo unit.": d.get("costo_unitario", 0),
                        "Subtotal": d.get("subtotal", 0),
                        "% del costo": round(
                            d.get("subtotal", 0) / f["costo"] * 100, 1
                        ) if f["costo"] > 0 else 0,
                    })

                df_det = pd.DataFrame(rows)
                st.dataframe(df_det, width="stretch", hide_index=True)

                if f["costo"] > 0 and len(rows) > 1:
                    import plotly.express as px
                    fig = px.pie(
                        df_det, values="Subtotal", names="Insumo",
                        title="Composición del costo",
                        hole=0.4,
                    )
                    fig.update_traces(textinfo="label+percent", textposition="outside")
                    fig.update_layout(height=300, showlegend=False, margin=dict(t=40, b=10))
                    st.plotly_chart(fig, width="stretch", key=f"pie_{f['pid']}")
            else:
                st.caption("Sin detalle de composición disponible.")


# ─────────────────────────────────────────────
# CATÁLOGO
# ─────────────────────────────────────────────

def _render_catalogo(df_prod):
    st.subheader("Catálogo de productos")
    ncol = _nombre_col(df_prod)

    col1, col2 = st.columns(2)
    cat = col1.selectbox(
        "Categoría",
        ["Todas"] + sorted(df_prod["categoria"].dropna().unique().tolist()),
        key="prod_cat",
    )
    tipo = col2.selectbox(
        "Tipo",
        ["Todos"] + sorted(df_prod["tipo_producto"].dropna().unique().tolist()),
        key="prod_tipo",
    )

    filtered = df_prod.copy()
    if cat != "Todas":
        filtered = filtered[filtered["categoria"] == cat]
    if tipo != "Todos":
        filtered = filtered[filtered["tipo_producto"] == tipo]

    cols_show = ["product_id", ncol, "categoria", "subcategoria",
                 "tipo_producto", "precio_venta_actual"]
    cols_show = [c for c in cols_show if c in filtered.columns]

    st.dataframe(
        filtered[cols_show].sort_values(ncol),
        width="stretch", hide_index=True,
    )
    st.caption(f"{len(filtered)} productos")


# ─────────────────────────────────────────────
# COMPONENTES
# ─────────────────────────────────────────────

def _render_componentes(df_prod, df_comp):
    st.subheader("Componentes de un producto")

    elaborados = df_prod[df_prod["tipo_producto"].isin(["armado", "receta"])]
    if elaborados.empty:
        st.info("No hay productos elaborados con componentes.")
        return

    ncol = _nombre_col(elaborados)
    opciones = dict(zip(
        elaborados[ncol].tolist(),
        elaborados["product_id"].astype(str).tolist(),
    ))
    sel = st.selectbox("Producto", sorted(opciones.keys()), key="prod_comp_sel")
    pid = opciones.get(sel)

    if pid:
        comps = df_comp[df_comp["parent_id"].astype(str) == pid]
        if comps.empty:
            st.warning(f"'{sel}' no tiene componentes asignados.")
        else:
            st.dataframe(
                comps[["component_type", "component_name", "cantidad", "unidad", "merma_pct"]],
                width="stretch", hide_index=True,
            )


# ─────────────────────────────────────────────
# COSTEO RÁPIDO
# ─────────────────────────────────────────────

def _render_costeo(df_prod, engine):
    st.subheader("Costeo rápido de producto")

    ncol = _nombre_col(df_prod)
    opciones = dict(zip(
        df_prod[ncol].tolist(),
        df_prod["product_id"].astype(str).tolist(),
    ))
    sel = st.selectbox("Producto", sorted(opciones.keys()), key="prod_cost_sel")
    pid = opciones.get(sel)

    if pid and st.button("Calcular costo", key="btn_cost_prod"):
        result = engine.costo_producto(pid)
        c1, c2, c3 = st.columns(3)
        c1.metric("Costo", fmt_ars(result["costo"]))
        c2.metric("Precio venta", fmt_ars(result["precio_venta"]))
        c3.metric("Margen %", f'{result["margen_pct"]:.1f}%')

        if result.get("detalle"):
            st.markdown("**Detalle de composición:**")
            for d in result["detalle"]:
                st.markdown(
                    f"- **{d['nombre']}** ({d['tipo']}): {d['cantidad']:.2f} {d['unidad']} "
                    f"x {fmt_ars(d['costo_unitario'], 2)} = {fmt_ars(d['subtotal'])}"
                )
        elif result["costo"] == 0:
            st.info("Este producto no tiene componentes asignados. Costo = $0.")
