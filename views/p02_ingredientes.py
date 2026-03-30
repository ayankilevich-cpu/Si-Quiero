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


_SYSTEM_COL_MAP = {
    "Código": "ingredient_id",
    "Nombre": "ingrediente",
    "Costo": "costo_actual",
    "Alicuota": "alicuota_iva",
    "U. de medida": "unidad_base",
    "U. medida de compra": "unidad_compra",
    "Rubro": "rubro",
    "Sub Rubro": "subrubro",
    "Conversión": "factor_compra_a_base",
    "Proveedor": "proveedor",
}


def _parse_system_export(uploaded) -> pd.DataFrame | None:
    """Lee un Excel exportado por el sistema de gestión.

    Auto-detecta la fila de encabezados buscando 'Código' en la primera columna.
    Mapea las columnas del sistema a nombres internos y parsea decimales con coma.
    """
    raw = pd.read_excel(uploaded, engine="openpyxl", header=None)

    header_row = None
    for i in range(min(15, len(raw))):
        vals = [str(v).strip() for v in raw.iloc[i].values if pd.notna(v)]
        if "Código" in vals or "Codigo" in vals:
            header_row = i
            break

    if header_row is None:
        return None

    df = pd.read_excel(uploaded, engine="openpyxl", header=header_row)
    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]

    rename = {k: v for k, v in _SYSTEM_COL_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    if "ingredient_id" not in df.columns:
        return None

    def _parse_comma_number(val):
        if pd.isna(val):
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    for col in ("alicuota_iva", "factor_compra_a_base"):
        if col in df.columns:
            df[col] = df[col].apply(_parse_comma_number)

    if "costo_actual" in df.columns:
        df["costo_actual"] = pd.to_numeric(df["costo_actual"], errors="coerce").fillna(0)

    df["ingredient_id"] = pd.to_numeric(df["ingredient_id"], errors="coerce")
    df = df.dropna(subset=["ingredient_id"])
    df["ingredient_id"] = df["ingredient_id"].astype(int)

    return df


def _render_excel(price_svc):
    st.subheader("Importar ingredientes desde Excel")

    if not price_svc:
        st.warning("Servicio de precios no disponible.")
        return

    st.markdown(
        "Acepta el archivo exportado por el sistema de gestión "
        "(formato con encabezados: Código, Nombre, Costo, etc.) "
        "o cualquier Excel con columnas `ingredient_id` y `costo_actual`."
    )

    uploaded = st.file_uploader("Subir archivo Excel", type=["xlsx", "xls"], key="excel_precios")
    if not uploaded:
        return

    try:
        df_parsed = _parse_system_export(uploaded)

        if df_parsed is not None:
            st.success("Formato del sistema detectado correctamente.")
            df_up = df_parsed
        else:
            uploaded.seek(0)
            df_up = pd.read_excel(uploaded, engine="openpyxl")

        if "ingredient_id" not in df_up.columns or "costo_actual" not in df_up.columns:
            st.error("El archivo no contiene las columnas requeridas: `ingredient_id`, `costo_actual`.")
            return

        df_existing = price_svc.loader.load_ingredientes()
        existing_ids = set(df_existing["ingredient_id"].tolist())
        import_ids = set(df_up["ingredient_id"].tolist())

        ids_update = import_ids & existing_ids
        ids_new = import_ids - existing_ids

        df_updates = df_up[df_up["ingredient_id"].isin(ids_update)].copy()
        df_nuevos = df_up[df_up["ingredient_id"].isin(ids_new)].copy()

        st.markdown("---")
        col_k1, col_k2, col_k3 = st.columns(3)
        col_k1.metric("Total en archivo", len(df_up))
        col_k2.metric("Actualizarán", len(df_updates))
        col_k3.metric("Nuevos", len(df_nuevos))

        preview_cols = [c for c in ["ingredient_id", "ingrediente", "costo_actual",
                                     "unidad_base", "rubro", "proveedor"] if c in df_up.columns]

        if not df_updates.empty:
            with st.expander(f"Vista previa: {len(df_updates)} ingredientes a actualizar", expanded=True):
                merged = df_updates[preview_cols].merge(
                    df_existing[["ingredient_id", "costo_actual"]].rename(
                        columns={"costo_actual": "costo_anterior"}
                    ),
                    on="ingredient_id", how="left",
                )
                if "costo_anterior" in merged.columns and "costo_actual" in merged.columns:
                    merged["diferencia"] = merged["costo_actual"] - merged["costo_anterior"]
                st.dataframe(merged, width="stretch", hide_index=True, height=300)

        if not df_nuevos.empty:
            with st.expander(f"Vista previa: {len(df_nuevos)} ingredientes nuevos"):
                st.dataframe(df_nuevos[preview_cols], width="stretch", hide_index=True)

        st.markdown("---")
        modo = st.radio(
            "Acción al importar",
            ["Solo actualizar existentes", "Actualizar existentes + agregar nuevos"],
            key="import_modo",
        )

        if st.button("Importar", type="primary", key="btn_import"):
            result = price_svc.importar_completo(
                df_up,
                agregar_nuevos=(modo == "Actualizar existentes + agregar nuevos"),
            )
            if result["ok"]:
                partes = []
                if result["actualizados"] > 0:
                    partes.append(f"{result['actualizados']} actualizados")
                if result["agregados"] > 0:
                    partes.append(f"{result['agregados']} nuevos agregados")
                st.success(f"Importación exitosa: {', '.join(partes)}")
                if result.get("errores"):
                    for e in result["errores"][:20]:
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
