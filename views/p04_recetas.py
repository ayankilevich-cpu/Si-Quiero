"""Gestión de recetas: carga manual, importación Excel, edición y costeo."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.helpers import fmt_ars
from utils.excel_templates import generar_plantilla_recetas


def render(loader, engine, **kwargs):
    st.header("Recetas — Elaboraciones propias")
    st.caption(
        "Aquí se gestionan las recetas de tortas, pastelería y cualquier elaboración propia. "
        "Cada receta se compone de ingredientes con sus cantidades, y puede vincularse "
        "a un producto de la carta para calcular automáticamente su costo y margen."
    )

    df_rec = loader.load_recetas()
    df_comp = loader.load_componentes()
    df_ing = loader.load_ingredientes()
    df_prod = loader.load_productos()

    tab_manual, tab_excel, tab_editar, tab_lista, tab_costeo = st.tabs([
        "Carga manual",
        "Importar desde Excel",
        "Editar receta",
        "Listado de recetas",
        "Costeo de recetas",
    ])

    with tab_manual:
        _render_carga_manual(loader, df_rec, df_comp, df_ing, df_prod)

    with tab_excel:
        _render_importar_excel(loader, df_rec, df_comp, df_ing, df_prod)

    with tab_editar:
        _render_editar_receta(loader, df_rec, df_comp, df_ing, df_prod)

    with tab_lista:
        _render_listado(df_rec, df_comp)

    with tab_costeo:
        _render_costeo(df_rec, engine)


# ─────────────────────────────────────────────
# CARGA MANUAL
# ─────────────────────────────────────────────

def _render_carga_manual(loader, df_rec, df_comp, df_ing, df_prod):
    st.subheader("Crear receta manualmente")

    with st.form("form_nueva_receta", clear_on_submit=False):
        st.markdown("**Datos de la receta**")

        col1, col2 = st.columns(2)
        recipe_name = col1.text_input("Nombre de la receta", placeholder="Ej: Chocotorta")
        categoria = col2.selectbox("Categoría", ["TORTAS", "CAFETERIA", "HELADERIA", "OTROS"], key="nr_cat")

        col3, col4 = st.columns(2)
        rendimiento = col3.number_input("Rendimiento (porciones)", min_value=1, value=10, key="nr_rend")
        unidad_rend = col4.selectbox("Unidad de rendimiento", ["porcion", "unidad", "kg"], key="nr_urend")

        ncol = "producto" if "producto" in df_prod.columns else "nombre_producto"
        prod_opciones = ["(ninguno)"] + sorted(df_prod[ncol].dropna().tolist()) if not df_prod.empty else ["(ninguno)"]
        prod_vinculado = st.selectbox(
            "Vincular a producto existente (opcional)",
            prod_opciones, key="nr_prod",
        )

        st.markdown("---")
        st.markdown("**Ingredientes de la receta**")

        ing_nombres = sorted(df_ing["ingrediente"].tolist()) if not df_ing.empty else []
        nombre_a_id = dict(zip(df_ing["ingrediente"], df_ing["ingredient_id"])) if not df_ing.empty else {}
        id_a_unidad = dict(zip(df_ing["ingredient_id"], df_ing["unidad_base"])) if not df_ing.empty else {}

        n_lineas = st.number_input("Cantidad de ingredientes", min_value=1, max_value=30, value=5, key="nr_nlin")

        ingredientes_data = []
        for i in range(int(n_lineas)):
            cols = st.columns([3, 2, 2])
            ing_sel = cols[0].selectbox(f"Ingrediente {i+1}", [""] + ing_nombres, key=f"nr_ing_{i}")
            cantidad = cols[1].number_input(f"Cantidad {i+1}", min_value=0.0, step=10.0, key=f"nr_cant_{i}")
            ing_id = nombre_a_id.get(ing_sel, "")
            unidad = id_a_unidad.get(ing_id, "GRAMOS") if ing_id else "GRAMOS"
            cols[2].text_input(f"Unidad {i+1}", value=unidad, disabled=True, key=f"nr_uni_{i}")

            if ing_sel and cantidad > 0:
                ingredientes_data.append({
                    "ing_id": ing_id, "ing_nombre": ing_sel,
                    "cantidad": cantidad, "unidad": unidad,
                })

        submitted = st.form_submit_button("Guardar receta", type="primary")

    if submitted:
        _guardar_receta_manual(
            loader, df_rec, df_comp, df_prod,
            recipe_name, categoria, rendimiento, unidad_rend,
            prod_vinculado, ingredientes_data, ncol,
        )


def _guardar_receta_manual(
    loader, df_rec, df_comp, df_prod,
    recipe_name, categoria, rendimiento, unidad_rend,
    prod_vinculado, ingredientes_data, ncol,
):
    if not recipe_name.strip():
        st.error("Ingrese un nombre para la receta.")
        return
    if not ingredientes_data:
        st.error("Agregue al menos un ingrediente con cantidad > 0.")
        return

    existentes = df_rec["recipe_name"].str.upper().tolist() if not df_rec.empty else []
    if recipe_name.strip().upper() in existentes:
        st.error(f"Ya existe una receta con el nombre '{recipe_name}'.")
        return

    next_id = _next_recipe_id(df_rec)

    prod_id_vinc = ""
    if prod_vinculado and prod_vinculado != "(ninguno)":
        match = df_prod[df_prod[ncol] == prod_vinculado]
        if not match.empty:
            prod_id_vinc = str(match.iloc[0]["product_id"])

    nueva = pd.DataFrame([{
        "recipe_id": next_id,
        "recipe_name": recipe_name.strip(),
        "categoria": categoria,
        "subcategoria": "",
        "rendimiento_cantidad": int(rendimiento),
        "unidad_rendimiento": unidad_rend,
        "product_id_vinculado": prod_id_vinc,
        "notas": "",
    }])
    loader.save_recetas(pd.concat([df_rec, nueva], ignore_index=True))

    nuevos_comp = [{
        "parent_id": next_id, "parent_type": "receta",
        "component_type": "ingrediente",
        "component_id": str(it["ing_id"]),
        "component_name": it["ing_nombre"],
        "cantidad": it["cantidad"], "unidad": it["unidad"],
        "merma_pct": 0, "notas": "",
    } for it in ingredientes_data]
    loader.save_componentes(pd.concat([df_comp, pd.DataFrame(nuevos_comp)], ignore_index=True))

    if prod_id_vinc:
        _marcar_producto_como_receta(loader, prod_id_vinc)

    st.success(f"Receta '{recipe_name}' guardada con {len(ingredientes_data)} ingredientes.")
    st.rerun()


# ─────────────────────────────────────────────
# IMPORTAR DESDE EXCEL
# ─────────────────────────────────────────────

def _render_importar_excel(loader, df_rec, df_comp, df_ing, df_prod):
    st.subheader("Importar recetas desde Excel")

    st.markdown("""
**El archivo Excel debe tener dos hojas:**

**Hoja 1: `recetas`** — una fila por cada receta

| Campo | Descripción | Obligatorio |
|---|---|---|
| `recipe_name` | Nombre único de la receta | Sí |
| `categoria` | TORTAS, CAFETERIA, HELADERIA u OTROS | Sí |
| `rendimiento_cantidad` | Cantidad de porciones que rinde | Sí |
| `unidad_rendimiento` | porcion, unidad o kg | Sí |
| `producto_vinculado` | Nombre exacto del producto de la carta (para vincular) | No |
| `notas` | Observaciones | No |

**Hoja 2: `receta_ingredientes`** — una fila por cada ingrediente de cada receta

| Campo | Descripción | Obligatorio |
|---|---|---|
| `recipe_name` | Nombre de la receta (debe coincidir con hoja 1) | Sí |
| `ingrediente` | Nombre exacto del ingrediente (debe existir en la base) | Sí |
| `cantidad` | Cantidad para la receta **completa** (no por porción) | Sí |
| `unidad` | GRAMOS, MILILITROS o UNIDAD | Sí |
| `merma_pct` | Porcentaje de merma, 0 si no aplica | No |
""")

    st.markdown("---")

    # Descargar plantilla
    plantilla = generar_plantilla_recetas(df_ing, df_prod)
    st.download_button(
        "Descargar plantilla Excel con ejemplos y catálogos",
        plantilla,
        file_name="plantilla_recetas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.caption(
        "La plantilla incluye hojas de referencia con los ingredientes disponibles "
        "y los productos vinculables para que copies los nombres exactos."
    )

    st.markdown("---")

    # Subir archivo
    uploaded = st.file_uploader("Subir archivo Excel con recetas", type=["xlsx"], key="rec_excel_up")
    if not uploaded:
        return

    try:
        xls = pd.ExcelFile(uploaded, engine="openpyxl")
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        return

    # Validar hojas
    if "recetas" not in xls.sheet_names:
        st.error("El archivo debe tener una hoja llamada `recetas`.")
        return
    if "receta_ingredientes" not in xls.sheet_names:
        st.error("El archivo debe tener una hoja llamada `receta_ingredientes`.")
        return

    df_rec_up = pd.read_excel(xls, sheet_name="recetas")
    df_ri_up = pd.read_excel(xls, sheet_name="receta_ingredientes")

    # Validar columnas obligatorias
    cols_rec_req = {"recipe_name", "categoria", "rendimiento_cantidad", "unidad_rendimiento"}
    cols_ri_req = {"recipe_name", "ingrediente", "cantidad", "unidad"}

    faltantes_rec = cols_rec_req - set(df_rec_up.columns)
    faltantes_ri = cols_ri_req - set(df_ri_up.columns)

    if faltantes_rec:
        st.error(f"Hoja `recetas`: faltan columnas obligatorias: {faltantes_rec}")
        return
    if faltantes_ri:
        st.error(f"Hoja `receta_ingredientes`: faltan columnas obligatorias: {faltantes_ri}")
        return

    # Preview
    st.markdown("**Vista previa — Recetas:**")
    st.dataframe(df_rec_up, width="stretch", hide_index=True)

    st.markdown("**Vista previa — Ingredientes por receta:**")
    st.dataframe(df_ri_up, width="stretch", hide_index=True)

    # Validaciones cruzadas
    errores = []
    warnings = []

    nombres_receta_excel = df_rec_up["recipe_name"].dropna().str.strip().str.upper().tolist()
    existentes = df_rec["recipe_name"].str.upper().tolist() if not df_rec.empty else []
    duplicados = [n for n in nombres_receta_excel if n in existentes]
    if duplicados:
        errores.append(f"Recetas que ya existen y serán omitidas: {', '.join(duplicados)}")

    ing_disponibles = set(df_ing["ingrediente"].str.strip().str.upper()) if not df_ing.empty else set()
    ing_en_excel = set(df_ri_up["ingrediente"].dropna().str.strip().str.upper())
    ing_no_encontrados = ing_en_excel - ing_disponibles
    if ing_no_encontrados:
        errores.append(
            f"Ingredientes no encontrados en la base (revise nombres exactos): "
            f"{', '.join(sorted(ing_no_encontrados))}"
        )

    recetas_sin_ingredientes = set(nombres_receta_excel) - set(
        df_ri_up["recipe_name"].dropna().str.strip().str.upper()
    )
    if recetas_sin_ingredientes:
        warnings.append(f"Recetas sin ingredientes en la hoja 2: {', '.join(recetas_sin_ingredientes)}")

    if errores:
        for e in errores:
            st.error(e)
    if warnings:
        for w in warnings:
            st.warning(w)

    if ing_no_encontrados:
        st.warning("Corrija los nombres de ingredientes antes de importar.")
        return

    # Botón importar
    n_nuevas = len([n for n in nombres_receta_excel if n not in existentes])
    n_ings = len(df_ri_up[df_ri_up["recipe_name"].str.strip().str.upper().isin(
        [n for n in nombres_receta_excel if n not in existentes]
    )])

    st.info(f"Se importarán **{n_nuevas} recetas** con **{n_ings} líneas de ingredientes**.")

    if st.button("Importar recetas", type="primary", key="btn_import_rec"):
        resultado = _ejecutar_importacion(
            loader, df_rec, df_comp, df_ing, df_prod,
            df_rec_up, df_ri_up, existentes,
        )
        st.success(
            f"Importación completada: {resultado['recetas_ok']} recetas, "
            f"{resultado['ingredientes_ok']} líneas de ingredientes."
        )
        if resultado["errores"]:
            for e in resultado["errores"]:
                st.warning(e)
        st.rerun()


def _ejecutar_importacion(loader, df_rec, df_comp, df_ing, df_prod, df_rec_up, df_ri_up, existentes):
    nombre_a_id_ing = dict(zip(
        df_ing["ingrediente"].str.strip().str.upper(),
        df_ing["ingredient_id"],
    )) if not df_ing.empty else {}
    id_a_unidad = dict(zip(df_ing["ingredient_id"], df_ing["unidad_base"])) if not df_ing.empty else {}

    ncol = "producto" if "producto" in df_prod.columns else "nombre_producto"
    nombre_a_pid = dict(zip(
        df_prod[ncol].str.strip().str.upper(),
        df_prod["product_id"].astype(str),
    )) if not df_prod.empty else {}

    recetas_ok = 0
    ingredientes_ok = 0
    errores = []

    nuevas_recetas = []
    nuevos_componentes = []

    for _, row in df_rec_up.iterrows():
        name = str(row["recipe_name"]).strip()
        if name.upper() in existentes:
            continue

        rid = _next_recipe_id(df_rec, offset=recetas_ok)

        prod_vinc = ""
        pv_raw = row.get("producto_vinculado", "")
        if pd.notna(pv_raw) and str(pv_raw).strip():
            pv_key = str(pv_raw).strip().upper()
            prod_vinc = nombre_a_pid.get(pv_key, "")
            if not prod_vinc:
                errores.append(f"Receta '{name}': producto vinculado '{pv_raw}' no encontrado")

        nuevas_recetas.append({
            "recipe_id": rid,
            "recipe_name": name,
            "categoria": str(row.get("categoria", "OTROS")).strip(),
            "subcategoria": str(row.get("subcategoria", "")).strip() if pd.notna(row.get("subcategoria")) else "",
            "rendimiento_cantidad": int(row.get("rendimiento_cantidad", 1)),
            "unidad_rendimiento": str(row.get("unidad_rendimiento", "porcion")).strip(),
            "product_id_vinculado": prod_vinc,
            "notas": str(row.get("notas", "")).strip() if pd.notna(row.get("notas")) else "",
        })

        ings_receta = df_ri_up[df_ri_up["recipe_name"].str.strip().str.upper() == name.upper()]
        for _, ri in ings_receta.iterrows():
            ing_name_raw = str(ri["ingrediente"]).strip()
            ing_id = nombre_a_id_ing.get(ing_name_raw.upper(), "")
            if not ing_id:
                errores.append(f"Receta '{name}': ingrediente '{ing_name_raw}' no encontrado, omitido")
                continue

            unidad = str(ri.get("unidad", "")).strip().upper()
            if not unidad:
                unidad = id_a_unidad.get(ing_id, "GRAMOS")

            nuevos_componentes.append({
                "parent_id": rid,
                "parent_type": "receta",
                "component_type": "ingrediente",
                "component_id": str(ing_id),
                "component_name": ing_name_raw,
                "cantidad": float(ri["cantidad"]),
                "unidad": unidad,
                "merma_pct": float(ri.get("merma_pct", 0)) if pd.notna(ri.get("merma_pct")) else 0,
                "notas": "",
            })
            ingredientes_ok += 1

        if prod_vinc:
            _marcar_producto_como_receta(loader, prod_vinc)

        recetas_ok += 1

    if nuevas_recetas:
        df_rec_new = pd.concat([df_rec, pd.DataFrame(nuevas_recetas)], ignore_index=True)
        loader.save_recetas(df_rec_new)

    if nuevos_componentes:
        df_comp_new = pd.concat([df_comp, pd.DataFrame(nuevos_componentes)], ignore_index=True)
        loader.save_componentes(df_comp_new)

    return {"recetas_ok": recetas_ok, "ingredientes_ok": ingredientes_ok, "errores": errores}


# ─────────────────────────────────────────────
# EDITAR RECETA
# ─────────────────────────────────────────────

def _render_editar_receta(loader, df_rec, df_comp, df_ing, df_prod):
    st.subheader("Editar receta existente")

    if df_rec.empty:
        st.info("No hay recetas para editar. Cree una primero desde 'Carga manual' o 'Importar desde Excel'.")
        return

    rec_opciones = dict(zip(df_rec["recipe_name"].tolist(), df_rec["recipe_id"].tolist()))
    sel_name = st.selectbox("Seleccione receta", sorted(rec_opciones.keys()), key="edit_rec_sel")
    rid = rec_opciones.get(sel_name)
    if not rid:
        return

    rec_row = df_rec[df_rec["recipe_id"] == rid].iloc[0]
    rec_idx = df_rec[df_rec["recipe_id"] == rid].index[0]
    comps = df_comp[
        (df_comp["parent_id"].astype(str) == str(rid)) &
        (df_comp["parent_type"] == "receta")
    ]

    st.markdown(
        f"**Receta:** {rec_row['recipe_name']} | "
        f"**Categoría:** {rec_row.get('categoria', '')} | "
        f"**Rendimiento:** {rec_row.get('rendimiento_cantidad', 1)} {rec_row.get('unidad_rendimiento', '')}"
    )

    # ── Editar datos generales de la receta ──
    with st.expander("Modificar datos generales (rendimiento, categoría, nombre)"):
        col_a, col_b = st.columns(2)
        new_rend = col_a.number_input(
            "Rendimiento (porciones)",
            min_value=1, value=int(rec_row.get("rendimiento_cantidad", 1)),
            key="edit_rend",
        )
        new_rend_unit = col_b.selectbox(
            "Unidad de rendimiento",
            ["porcion", "unidad", "kg"],
            index=["porcion", "unidad", "kg"].index(
                str(rec_row.get("unidad_rendimiento", "porcion"))
            ) if str(rec_row.get("unidad_rendimiento", "porcion")) in ["porcion", "unidad", "kg"] else 0,
            key="edit_rend_unit",
        )

        col_c, col_d = st.columns(2)
        new_name = col_c.text_input(
            "Nombre de la receta",
            value=str(rec_row.get("recipe_name", "")),
            key="edit_rec_name",
        )
        new_cat = col_d.selectbox(
            "Categoría",
            ["TORTAS", "CAFETERIA", "HELADERIA", "OTROS"],
            index=["TORTAS", "CAFETERIA", "HELADERIA", "OTROS"].index(
                str(rec_row.get("categoria", "OTROS"))
            ) if str(rec_row.get("categoria", "OTROS")) in ["TORTAS", "CAFETERIA", "HELADERIA", "OTROS"] else 3,
            key="edit_rec_cat",
        )

        cambios = (
            new_rend != int(rec_row.get("rendimiento_cantidad", 1)) or
            new_rend_unit != str(rec_row.get("unidad_rendimiento", "porcion")) or
            new_name.strip() != str(rec_row.get("recipe_name", "")).strip() or
            new_cat != str(rec_row.get("categoria", "OTROS"))
        )

        if st.button("Guardar cambios", key="btn_save_rec_general", disabled=not cambios):
            df_rec.at[rec_idx, "rendimiento_cantidad"] = new_rend
            df_rec.at[rec_idx, "unidad_rendimiento"] = new_rend_unit
            df_rec.at[rec_idx, "recipe_name"] = new_name.strip()
            df_rec.at[rec_idx, "categoria"] = new_cat
            loader.save_recetas(df_rec)
            st.success(f"Receta actualizada: rendimiento = {new_rend} {new_rend_unit}")
            st.rerun()

    if not comps.empty:
        st.markdown("**Ingredientes actuales:**")
        st.dataframe(
            comps[["component_name", "cantidad", "unidad", "merma_pct"]],
            width="stretch", hide_index=True,
        )
    else:
        st.warning("Esta receta no tiene ingredientes asignados.")

    st.markdown("---")
    st.markdown("**Agregar ingrediente:**")

    ing_nombres = sorted(df_ing["ingrediente"].tolist()) if not df_ing.empty else []
    nombre_a_id = dict(zip(df_ing["ingrediente"], df_ing["ingredient_id"])) if not df_ing.empty else {}
    id_a_unidad = dict(zip(df_ing["ingredient_id"], df_ing["unidad_base"])) if not df_ing.empty else {}

    col1, col2 = st.columns([3, 2])
    ing_add = col1.selectbox("Ingrediente", [""] + ing_nombres, key="edit_ing_add")
    cant_add = col2.number_input("Cantidad", min_value=0.0, step=10.0, key="edit_cant_add")

    if st.button("Agregar ingrediente", key="btn_add_comp"):
        if ing_add and cant_add > 0:
            ing_id = nombre_a_id.get(ing_add, "")
            unidad = id_a_unidad.get(ing_id, "GRAMOS")
            nuevo = pd.DataFrame([{
                "parent_id": str(rid), "parent_type": "receta",
                "component_type": "ingrediente",
                "component_id": str(ing_id), "component_name": ing_add,
                "cantidad": cant_add, "unidad": unidad,
                "merma_pct": 0, "notas": "",
            }])
            loader.save_componentes(pd.concat([df_comp, nuevo], ignore_index=True))
            st.success(f"'{ing_add}' agregado a '{sel_name}'.")
            st.rerun()
        else:
            st.warning("Seleccione un ingrediente y cantidad > 0.")

    if not comps.empty:
        st.markdown("---")
        st.markdown("**Eliminar ingrediente:**")
        comp_del = st.selectbox("Ingrediente a eliminar", comps["component_name"].tolist(), key="edit_comp_del")
        if st.button("Eliminar", key="btn_del_comp"):
            mask = (
                (df_comp["parent_id"].astype(str) == str(rid)) &
                (df_comp["parent_type"] == "receta") &
                (df_comp["component_name"] == comp_del)
            )
            idx = df_comp[mask].index[:1]
            if not idx.empty:
                loader.save_componentes(df_comp.drop(idx))
                st.success(f"'{comp_del}' eliminado de '{sel_name}'.")
                st.rerun()

    st.markdown("---")
    st.markdown("**Eliminar receta completa:**")
    if st.button(f"Eliminar receta '{sel_name}'", key="btn_del_receta", type="secondary"):
        df_rec_new = df_rec[df_rec["recipe_id"] != rid]
        loader.save_recetas(df_rec_new)
        mask_comp = ~(
            (df_comp["parent_id"].astype(str) == str(rid)) &
            (df_comp["parent_type"] == "receta")
        )
        loader.save_componentes(df_comp[mask_comp])
        st.success(f"Receta '{sel_name}' y sus ingredientes eliminados.")
        st.rerun()


# ─────────────────────────────────────────────
# LISTADO
# ─────────────────────────────────────────────

def _render_listado(df_rec, df_comp):
    st.subheader("Catálogo de recetas")

    if df_rec.empty:
        st.info("No hay recetas cargadas.")
        return

    st.dataframe(df_rec, width="stretch", hide_index=True)
    st.caption(f"{len(df_rec)} recetas")

    st.markdown("---")
    sel_name = st.selectbox("Ver ingredientes de:", sorted(df_rec["recipe_name"].tolist()), key="list_rec_sel")
    rid = df_rec[df_rec["recipe_name"] == sel_name]["recipe_id"].iloc[0]

    comps = df_comp[
        (df_comp["parent_id"].astype(str) == str(rid)) &
        (df_comp["parent_type"] == "receta")
    ]
    if comps.empty:
        st.warning(f"'{sel_name}' no tiene ingredientes asignados.")
    else:
        st.dataframe(
            comps[["component_type", "component_name", "cantidad", "unidad", "merma_pct"]],
            width="stretch", hide_index=True,
        )


# ─────────────────────────────────────────────
# COSTEO
# ─────────────────────────────────────────────

def _render_costeo(df_rec, engine):
    st.subheader("Costeo detallado de recetas")

    if df_rec.empty:
        st.info("No hay recetas para costear.")
        return

    for _, rec in df_rec.iterrows():
        rid = str(rec["recipe_id"])
        result = engine.costo_receta(rid)
        costo_total = result.get("costo_total", 0)
        rendimiento = result.get("rendimiento", 1)
        costo_porcion = result.get("costo_porcion", 0)

        with st.expander(
            f"{rec['recipe_name']} — Costo total: {fmt_ars(costo_total)} — "
            f"Costo/porción ({rendimiento} porc.): {fmt_ars(costo_porcion)}"
        ):
            if result.get("detalle"):
                for d in result["detalle"]:
                    st.markdown(
                        f"- **{d['componente']}**: {d['cantidad']:.1f} × "
                        f"{fmt_ars(d['costo_unit'], 2)} = **{fmt_ars(d['subtotal'])}**"
                    )
                st.divider()
                c1, c2, c3 = st.columns(3)
                c1.metric("Costo total receta", fmt_ars(costo_total))
                c2.metric("Rendimiento", f"{rendimiento} porciones")
                c3.metric("Costo por porción", fmt_ars(costo_porcion))

                prod_vinc = rec.get("product_id_vinculado", "")
                if prod_vinc and str(prod_vinc).strip():
                    prod_data = engine.costo_producto(str(prod_vinc))
                    precio = prod_data.get("precio_venta", 0)
                    if precio > 0:
                        st.markdown(
                            f"**Producto vinculado:** {prod_data.get('nombre', '')} — "
                            f"Precio venta: {fmt_ars(precio)} — "
                            f"Margen: {prod_data.get('margen_pct', 0):.1f}%"
                        )
            else:
                st.caption("Sin ingredientes — agregue desde la pestaña 'Editar receta'.")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _next_recipe_id(df_rec, offset=0):
    if df_rec.empty:
        n = 1 + offset
    else:
        nums = df_rec["recipe_id"].str.extract(r"(\d+)", expand=False).dropna().astype(int)
        n = (nums.max() + 1 + offset) if not nums.empty else (1 + offset)
    return f"REC_{int(n):03d}"


def _marcar_producto_como_receta(loader, prod_id_str):
    df_productos = loader.load_productos()
    mask = df_productos["product_id"].astype(str) == prod_id_str
    if mask.any():
        df_productos.loc[mask, "tipo_producto"] = "receta"
        loader.save_productos(df_productos)
