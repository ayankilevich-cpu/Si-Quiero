"""Gestión de ingredientes: listado, edición y actualización de costos."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from config import RUBROS_INGREDIENTES, UNIDADES_COMPRA
from utils.helpers import fmt_ars


def render(loader, engine, **kwargs):
    st.header("Gestión de ingredientes")
    price_svc = kwargs.get("price_svc")

    df = loader.load_ingredientes()
    if df.empty:
        st.warning("No hay ingredientes cargados.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "Listado", "Actualizar costo manual", "Importar desde Excel", "Historial",
    ])

    with tab1:
        _render_listado(df, loader)

    with tab2:
        _render_manual(df, price_svc)

    with tab3:
        _render_excel(price_svc)

    with tab4:
        _render_historial(loader)


def _render_listado(df, loader):
    st.subheader("Catálogo de ingredientes")

    rubro = st.selectbox("Filtrar por rubro", ["Todos"] + sorted(df["rubro"].dropna().unique().tolist()))
    if rubro != "Todos":
        df = df[df["rubro"] == rubro]

    revision = st.checkbox("Solo ingredientes pendientes de revisión", value=False)
    if revision and "requiere_revision_costo" in df.columns:
        df = df[df["requiere_revision_costo"] == True]

    cols_show = ["ingredient_id", "ingrediente", "rubro", "unidad_base", "costo_actual",
                 "proveedor", "requiere_revision_costo", "ultimo_update"]
    cols_show = [c for c in cols_show if c in df.columns]

    st.dataframe(
        df[cols_show].sort_values("ingrediente"),
        width="stretch",
        hide_index=True,
    )
    st.caption(f"{len(df)} ingredientes")


def _render_manual(df, price_svc):
    st.subheader("Actualización manual de costo")

    if not price_svc:
        st.warning("Servicio de precios no disponible.")
        return

    opciones = dict(zip(
        df["ingrediente"].tolist(),
        df["ingredient_id"].tolist(),
    ))
    nombre = st.selectbox("Ingrediente", sorted(opciones.keys()), key="ing_manual")
    ing_id = opciones.get(nombre)

    row = df[df["ingredient_id"] == ing_id]
    if not row.empty:
        st.caption(f"Costo actual: {fmt_ars(float(row.iloc[0]['costo_actual']), 2)} / {row.iloc[0]['unidad_base']}")

    col1, col2 = st.columns(2)
    precio_compra = col1.number_input("Precio de compra ($)", min_value=0.0, step=100.0, key="pc_m")
    cantidad_compra = col2.number_input("Cantidad comprada", min_value=0.01, step=0.5, value=1.0, key="cc_m")
    unidad_compra = st.selectbox("Unidad de compra", list(UNIDADES_COMPRA.keys()), key="uc_m")
    proveedor = st.text_input("Proveedor (opcional)", key="prov_m")

    if st.button("Actualizar costo", type="primary", key="btn_upd_manual"):
        if precio_compra > 0 and cantidad_compra > 0:
            result = price_svc.actualizar_precio_manual(
                ing_id, precio_compra, cantidad_compra, unidad_compra, proveedor,
            )
            if result["ok"]:
                st.success(f"✅ {result['ingrediente']}: nuevo costo = {fmt_ars(result['precio_nuevo'], 4)}")
                st.rerun()
            else:
                st.error(result.get("error", "Error desconocido"))
        else:
            st.warning("Ingrese precio y cantidad válidos.")


def _render_excel(price_svc):
    st.subheader("Importar costos desde Excel")

    if not price_svc:
        st.warning("Servicio de precios no disponible.")
        return

    st.markdown("El archivo debe tener al menos las columnas: `ingredient_id`, `costo_actual`")

    uploaded = st.file_uploader("Subir archivo Excel", type=["xlsx", "xls"], key="excel_precios")
    if uploaded:
        try:
            df_up = pd.read_excel(uploaded, engine="openpyxl")
            st.dataframe(df_up.head(10), width="stretch")

            if st.button("Importar precios", type="primary", key="btn_import"):
                result = price_svc.actualizar_desde_excel(df_up)
                if result["ok"]:
                    st.success(f"✅ {result['actualizados']} ingredientes actualizados")
                    if result.get("errores"):
                        for e in result["errores"]:
                            st.warning(e)
                    st.rerun()
                else:
                    st.error(result.get("error", "Error de importación"))
        except Exception as e:
            st.error(f"Error leyendo archivo: {e}")


def _render_historial(loader):
    st.subheader("Historial de precios")
    df_hist = loader.load_historial_precios()
    if df_hist.empty:
        st.info("Sin historial registrado.")
        return

    df_ing = loader.load_ingredientes()
    if not df_ing.empty:
        map_nombre = dict(zip(df_ing["ingredient_id"], df_ing["ingrediente"]))
        df_hist["Ingrediente"] = df_hist["ingredient_id"].map(map_nombre)
    else:
        df_hist["Ingrediente"] = df_hist["ingredient_id"]

    st.dataframe(
        df_hist.sort_values("fecha", ascending=False),
        width="stretch",
        hide_index=True,
    )
