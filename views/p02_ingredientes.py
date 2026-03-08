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

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Listado", "Editar / Eliminar", "Actualizar costo manual",
        "Importar desde Excel", "Historial",
    ])

    with tab1:
        _render_listado(df, loader)

    with tab2:
        _render_editar_eliminar(df, loader)

    with tab3:
        _render_manual(df, price_svc)

    with tab4:
        _render_excel(price_svc)

    with tab5:
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


def _render_editar_eliminar(df, loader):
    st.subheader("Editar o eliminar ingrediente")

    opciones = dict(zip(
        df["ingrediente"].tolist(),
        df["ingredient_id"].tolist(),
    ))
    nombre = st.selectbox("Seleccionar ingrediente", sorted(opciones.keys()), key="ing_edit_sel")
    ing_id = opciones.get(nombre)
    if ing_id is None:
        return

    idx = df[df["ingredient_id"] == ing_id].index
    if idx.empty:
        return
    row = df.loc[idx[0]]

    # ── Formulario de edición ──
    with st.expander("Modificar datos", expanded=True):
        col_a, col_b = st.columns(2)
        new_nombre = col_a.text_input("Nombre", value=str(row.get("ingrediente", "")), key="ed_nombre")
        new_rubro = col_b.selectbox(
            "Rubro",
            RUBROS_INGREDIENTES,
            index=RUBROS_INGREDIENTES.index(str(row.get("rubro", "")))
            if str(row.get("rubro", "")) in RUBROS_INGREDIENTES else 0,
            key="ed_rubro",
        )

        col_c, col_d = st.columns(2)
        unidades = ["GRAMOS", "MILILITROS", "UNIDAD"]
        new_unidad = col_c.selectbox(
            "Unidad base",
            unidades,
            index=unidades.index(str(row.get("unidad_base", "GRAMOS")))
            if str(row.get("unidad_base", "GRAMOS")) in unidades else 0,
            key="ed_unidad",
        )
        new_costo = col_d.number_input(
            "Costo actual ($)",
            min_value=0.0,
            value=float(row.get("costo_actual", 0)),
            step=10.0,
            format="%.4f",
            key="ed_costo",
        )

        col_e, col_f = st.columns(2)
        new_proveedor = col_e.text_input("Proveedor", value=str(row.get("proveedor", "") or ""), key="ed_prov")
        new_notas = col_f.text_input("Notas", value=str(row.get("notas", "") or ""), key="ed_notas")

        cambios = (
            new_nombre.strip() != str(row.get("ingrediente", "")).strip()
            or new_rubro != str(row.get("rubro", ""))
            or new_unidad != str(row.get("unidad_base", ""))
            or round(new_costo, 4) != round(float(row.get("costo_actual", 0)), 4)
            or new_proveedor.strip() != str(row.get("proveedor", "") or "").strip()
            or new_notas.strip() != str(row.get("notas", "") or "").strip()
        )

        if st.button("Guardar cambios", key="btn_save_ing", disabled=not cambios, type="primary"):
            df.at[idx[0], "ingrediente"] = new_nombre.strip()
            df.at[idx[0], "rubro"] = new_rubro
            df.at[idx[0], "unidad_base"] = new_unidad
            df.at[idx[0], "costo_actual"] = new_costo
            df.at[idx[0], "proveedor"] = new_proveedor.strip()
            df.at[idx[0], "notas"] = new_notas.strip()
            df.at[idx[0], "ultimo_update"] = date.today()
            loader.save_ingredientes(df)
            st.success(f"Ingrediente '{new_nombre.strip()}' actualizado correctamente.")
            st.rerun()

    # ── Eliminar ──
    st.markdown("---")
    with st.expander("Eliminar ingrediente"):
        st.warning(
            f"Vas a eliminar **{row['ingrediente']}** (ID {ing_id}). "
            "Si este ingrediente es usado en recetas o componentes, "
            "el costeo de esos productos dejará de funcionar."
        )
        confirmacion = st.text_input(
            "Escribí el nombre del ingrediente para confirmar:",
            key="confirm_del_ing",
        )
        if st.button("Eliminar", key="btn_del_ing", type="primary"):
            if confirmacion.strip().upper() == str(row["ingrediente"]).strip().upper():
                df = df.drop(index=idx[0]).reset_index(drop=True)
                loader.save_ingredientes(df)
                st.success(f"Ingrediente '{row['ingrediente']}' eliminado.")
                st.rerun()
            else:
                st.error("El nombre no coincide. Escribilo exactamente para confirmar.")


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
