"""Carga y actualización de datos de ventas desde el sistema POS."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.helpers import fmt_ars, fmt_pct


_POS_COL_MAP = {
    "Fecha": "fecha_hora",
    "Numero": "numero_pedido",
    "Codigo": "codigo_venta",
    "Producto": "producto",
    "Cantidad": "cantidad",
    "Total": "total",
    "Rubro": "rubro",
    "SubRubro": "subrubro",
    "Area": "area",
    "Sector": "sector",
}

_COLS_DROP = ["Dia", "Mes", "Hora"]


def _find_header_row(raw: pd.DataFrame, max_scan: int = 20) -> int | None:
    """Busca la fila de encabezados buscando 'Numero' y 'Producto'."""
    for i in range(min(max_scan, len(raw))):
        vals = [str(v).strip() for v in raw.iloc[i].values if pd.notna(v)]
        if "Numero" in vals and "Producto" in vals:
            return i
    return None


def _parse_comma_number(val) -> float:
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


def _parse_pos_export(uploaded) -> pd.DataFrame | None:
    """Parsea un Excel exportado del sistema POS de Si Quiero."""
    raw = pd.read_excel(uploaded, engine="openpyxl", header=None)
    header_row = _find_header_row(raw)

    if header_row is None:
        return None

    uploaded.seek(0)
    df = pd.read_excel(uploaded, engine="openpyxl", header=header_row)
    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]

    for col in _COLS_DROP:
        if col in df.columns:
            df = df.drop(columns=[col])

    rename = {k: v for k, v in _POS_COL_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    if "producto" not in df.columns or "numero_pedido" not in df.columns:
        return None

    if "fecha_hora" in df.columns:
        df["fecha_hora"] = pd.to_datetime(
            df["fecha_hora"], dayfirst=True, errors="coerce",
        ).dt.strftime("%Y-%m-%d %H:%M:%S")

    for col in ("cantidad", "total"):
        if col in df.columns:
            df[col] = df[col].apply(_parse_comma_number)

    if "numero_pedido" in df.columns:
        df["numero_pedido"] = pd.to_numeric(df["numero_pedido"], errors="coerce").fillna(0).astype(int)

    if "codigo_venta" in df.columns:
        df["codigo_venta"] = pd.to_numeric(df["codigo_venta"], errors="coerce").fillna(0).astype(int)

    df["producto_norm"] = df["producto"].astype(str).str.strip().str.upper()

    for col in ("rubro", "subrubro", "area", "sector"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("")

    col_order = [
        "fecha_hora", "numero_pedido", "codigo_venta", "producto",
        "producto_norm", "cantidad", "total", "rubro", "subrubro",
        "area", "sector",
    ]
    col_order = [c for c in col_order if c in df.columns]
    return df[col_order]


def _build_resumen(df: pd.DataFrame) -> pd.DataFrame:
    """Genera ventas_resumen a partir del detalle de ventas."""
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

    agg["vendido_ultimo_mes"] = "Sí"
    agg["codigo_venta"] = agg["codigo_venta"].astype(str)
    return agg


def _update_productos_with_sales(loader, df_resumen: pd.DataFrame) -> int:
    """Actualiza campos de ventas en la tabla de productos.
    Devuelve la cantidad de productos actualizados."""
    df_prod = loader.load_productos()
    if df_prod.empty or df_resumen.empty:
        return 0

    if "producto_norm" not in df_prod.columns:
        df_prod["producto_norm"] = df_prod["producto"].astype(str).str.strip().str.upper()

    sales_map = df_resumen.set_index("producto_norm")
    updated = 0

    for idx, row in df_prod.iterrows():
        pn = str(row.get("producto_norm", "")).strip().upper()
        if pn in sales_map.index:
            s = sales_map.loc[pn]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[0]
            df_prod.at[idx, "unidades_vendidas_mes"] = s["unidades_vendidas_mes"]
            df_prod.at[idx, "facturacion_mes"] = s["facturacion_mes"]
            df_prod.at[idx, "tickets"] = s["tickets"]
            df_prod.at[idx, "precio_promedio_realizado"] = s["precio_promedio_realizado"]
            df_prod.at[idx, "vendido_ultimo_mes"] = "Sí"
            updated += 1

    if updated > 0:
        loader.save_productos(df_prod)
    return updated


def render(loader, engine, **kwargs):
    st.header("Carga de ventas")

    tab1, tab2, tab3 = st.tabs([
        "Importar desde POS", "Datos actuales", "Análisis de tickets",
    ])

    with tab1:
        _render_importar(loader)

    with tab2:
        _render_datos_actuales(loader)

    with tab3:
        _render_analisis_tickets(loader)


def _render_importar(loader):
    st.subheader("Importar ventas del sistema")
    st.markdown(
        "Subí el archivo **Detalle de productos vendidos por pedido** "
        "exportado desde el sistema de ventas (formato `.xlsx`)."
    )

    uploaded = st.file_uploader(
        "Subir archivo Excel del POS", type=["xlsx", "xls"], key="pos_ventas_upload",
    )
    if not uploaded:
        return

    try:
        df_parsed = _parse_pos_export(uploaded)
    except Exception as e:
        st.error(f"Error leyendo archivo: {e}")
        return

    if df_parsed is None:
        st.error(
            "No se pudo detectar el formato del archivo. "
            "Asegurate de que contenga las columnas **Numero**, **Producto**, **Cantidad** y **Total**."
        )
        return

    st.success(f"Archivo parseado: **{len(df_parsed):,}** líneas de venta detectadas.")

    n_tickets = df_parsed["numero_pedido"].nunique()
    total_fact = df_parsed["total"].sum()
    total_unidades = df_parsed["cantidad"].sum()
    ticket_prom = total_fact / n_tickets if n_tickets > 0 else 0
    items_por_ticket = len(df_parsed) / n_tickets if n_tickets > 0 else 0

    fecha_min = df_parsed["fecha_hora"].min() if "fecha_hora" in df_parsed.columns else "?"
    fecha_max = df_parsed["fecha_hora"].max() if "fecha_hora" in df_parsed.columns else "?"

    st.markdown("### Resumen del archivo")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tickets", f"{n_tickets:,}".replace(",", "."))
    c2.metric("Facturación total", fmt_ars(total_fact))
    c3.metric("Ticket promedio", fmt_ars(ticket_prom))
    c4.metric("Unidades totales", f"{total_unidades:,.0f}".replace(",", "."))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Líneas de detalle", f"{len(df_parsed):,}".replace(",", "."))
    c6.metric("Ítems/ticket (prom)", f"{items_por_ticket:.1f}")
    c7.metric("Desde", str(fecha_min)[:10] if fecha_min != "?" else "?")
    c8.metric("Hasta", str(fecha_max)[:10] if fecha_max != "?" else "?")

    n_productos = df_parsed["producto_norm"].nunique()
    n_rubros = df_parsed["rubro"].nunique() if "rubro" in df_parsed.columns else 0
    st.caption(f"{n_productos} productos distintos · {n_rubros} rubros")

    with st.expander("Vista previa de datos", expanded=False):
        st.dataframe(df_parsed.head(50), width="stretch", hide_index=True, height=350)

    df_resumen = _build_resumen(df_parsed)

    with st.expander("Resumen por producto (se generará automáticamente)", expanded=False):
        display_cols = [
            "producto", "rubro", "tickets", "unidades_vendidas_mes",
            "facturacion_mes", "precio_promedio_realizado",
        ]
        display_cols = [c for c in display_cols if c in df_resumen.columns]
        st.dataframe(
            df_resumen[display_cols].sort_values("facturacion_mes", ascending=False),
            width="stretch", hide_index=True, height=350,
        )

    st.divider()

    df_existing = loader.load_ventas()
    n_existing = len(df_existing)

    if n_existing > 0:
        st.info(f"Actualmente hay **{n_existing:,}** registros de ventas en la base de datos.")
        modo = st.radio(
            "¿Qué querés hacer con los datos existentes?",
            [
                "Reemplazar todo (borra lo anterior y carga lo nuevo)",
                "Agregar (mantiene lo anterior y suma lo nuevo)",
            ],
            key="ventas_import_mode",
        )
    else:
        modo = "Reemplazar todo (borra lo anterior y carga lo nuevo)"
        st.info("No hay datos de ventas previos. Se cargarán los nuevos.")

    col_a, col_b = st.columns(2)
    update_productos = col_a.checkbox(
        "Actualizar tabla de productos con datos de venta",
        value=True, key="upd_prod_check",
    )

    if col_b.button("Importar ventas", type="primary", key="btn_import_ventas"):
        with st.spinner("Importando ventas..."):
            if "Reemplazar" in modo:
                loader.save_ventas(df_parsed)
                loader.save_ventas_resumen(df_resumen)
                msg_ventas = f"{len(df_parsed):,} registros cargados (reemplazo completo)"
            else:
                inserted = loader.append_ventas(df_parsed)
                all_ventas = loader.load_ventas()
                new_resumen = _build_resumen(all_ventas)
                loader.save_ventas_resumen(new_resumen)
                msg_ventas = f"{inserted:,} registros agregados (total: {len(all_ventas):,})"

            msg_prod = ""
            if update_productos:
                final_resumen = loader.load_ventas_resumen()
                n_upd = _update_productos_with_sales(loader, final_resumen)
                msg_prod = f" · {n_upd} productos actualizados con datos de venta"

        st.success(f"Importación exitosa: {msg_ventas}{msg_prod}")
        st.rerun()


def _render_datos_actuales(loader):
    st.subheader("Datos de ventas actuales")

    df = loader.load_ventas()
    df_vr = loader.load_ventas_resumen()

    if df.empty:
        st.info("No hay datos de ventas cargados. Usá la pestaña **Importar desde POS** para cargar datos.")
        return

    n_tickets = df["numero_pedido"].nunique() if "numero_pedido" in df.columns else 0
    total = df["total"].sum() if "total" in df.columns else 0
    ticket_prom = total / n_tickets if n_tickets > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros", f"{len(df):,}".replace(",", "."))
    c2.metric("Tickets únicos", f"{n_tickets:,}".replace(",", "."))
    c3.metric("Facturación total", fmt_ars(total))
    c4.metric("Ticket promedio", fmt_ars(ticket_prom))

    with st.expander("Detalle de ventas", expanded=False):
        st.dataframe(df.tail(100), width="stretch", hide_index=True, height=350)

    if not df_vr.empty:
        st.subheader("Resumen por producto")
        col_sort = "facturacion_mes" if "facturacion_mes" in df_vr.columns else df_vr.columns[0]
        st.dataframe(
            df_vr.sort_values(col_sort, ascending=False),
            width="stretch", hide_index=True, height=400,
        )

    st.divider()
    if st.button("Borrar todos los datos de ventas", type="secondary", key="btn_clear_ventas"):
        st.session_state["confirm_clear_ventas"] = True

    if st.session_state.get("confirm_clear_ventas"):
        st.warning("¿Estás seguro? Esta acción eliminará **todos** los datos de ventas.")
        ca, cb = st.columns(2)
        if ca.button("Sí, borrar todo", type="primary", key="btn_confirm_clear"):
            loader.save_ventas(pd.DataFrame(columns=[
                "fecha_hora", "numero_pedido", "codigo_venta", "producto",
                "producto_norm", "cantidad", "total", "rubro", "subrubro",
                "area", "sector",
            ]))
            loader.save_ventas_resumen(pd.DataFrame(columns=[
                "producto_norm", "producto", "codigo_venta", "rubro", "subrubro",
                "area", "tickets", "unidades_vendidas_mes", "facturacion_mes",
                "precio_promedio_realizado", "vendido_ultimo_mes",
            ]))
            st.session_state["confirm_clear_ventas"] = False
            st.success("Datos de ventas eliminados.")
            st.rerun()
        if cb.button("Cancelar", key="btn_cancel_clear"):
            st.session_state["confirm_clear_ventas"] = False
            st.rerun()


def _render_analisis_tickets(loader):
    st.subheader("Análisis de tickets")

    df = loader.load_ventas()
    if df.empty:
        st.info("Sin datos de ventas para analizar.")
        return

    tickets = df.groupby("numero_pedido").agg(
        items=("producto", "count"),
        total_ticket=("total", "sum"),
        productos_distintos=("producto_norm", "nunique"),
    ).reset_index()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total tickets", f"{len(tickets):,}".replace(",", "."))
    c2.metric("Ticket promedio", fmt_ars(tickets["total_ticket"].mean()))
    c3.metric("Ticket mediano", fmt_ars(tickets["total_ticket"].median()))
    c4.metric("Ítems/ticket (prom)", f"{tickets['items'].mean():.1f}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Ticket máximo", fmt_ars(tickets["total_ticket"].max()))
    c6.metric("Ticket mínimo", fmt_ars(tickets["total_ticket"].min()))
    pct_multi = (tickets["items"] > 1).mean() * 100
    c7.metric("Tickets multi-ítem", fmt_pct(pct_multi))
    c8.metric("Productos distintos/ticket", f"{tickets['productos_distintos'].mean():.1f}")

    st.divider()
    col_left, col_right = st.columns(2)

    with col_left:
        fig_hist = px.histogram(
            tickets, x="total_ticket", nbins=30,
            title="Distribución del valor de tickets",
            labels={"total_ticket": "Total del ticket ($)", "count": "Cantidad"},
            color_discrete_sequence=["#E85D75"],
        )
        fig_hist.update_layout(showlegend=False)
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_right:
        fig_items = px.histogram(
            tickets, x="items", nbins=int(max(tickets["items"].max(), 1)),
            title="Cantidad de ítems por ticket",
            labels={"items": "Ítems en el ticket", "count": "Cantidad de tickets"},
            color_discrete_sequence=["#6C5B7B"],
        )
        fig_items.update_layout(showlegend=False)
        st.plotly_chart(fig_items, use_container_width=True)

    if "rubro" in df.columns:
        rubro_ticket = df.groupby(["numero_pedido", "rubro"])["total"].sum().reset_index()
        rubro_avg = rubro_ticket.groupby("rubro")["total"].mean().reset_index()
        rubro_avg.columns = ["Rubro", "Ticket promedio"]
        rubro_avg = rubro_avg.sort_values("Ticket promedio", ascending=False)

        fig_rubro = px.bar(
            rubro_avg, x="Rubro", y="Ticket promedio",
            title="Ticket promedio por rubro",
            color="Rubro",
        )
        fig_rubro.update_layout(showlegend=False)
        st.plotly_chart(fig_rubro, use_container_width=True)

    if "fecha_hora" in df.columns:
        df_ts = df.copy()
        df_ts["fecha_hora"] = pd.to_datetime(df_ts["fecha_hora"], errors="coerce")
        df_ts = df_ts.dropna(subset=["fecha_hora"])

        if not df_ts.empty:
            df_ts["fecha"] = df_ts["fecha_hora"].dt.date
            daily = df_ts.groupby("fecha").agg(
                facturacion=("total", "sum"),
                tickets=("numero_pedido", "nunique"),
            ).reset_index()

            fig_daily = px.bar(
                daily, x="fecha", y="facturacion",
                title="Facturación diaria",
                labels={"fecha": "Fecha", "facturacion": "Facturación ($)"},
                color_discrete_sequence=["#3498DB"],
            )
            fig_daily.update_layout(showlegend=False)
            st.plotly_chart(fig_daily, use_container_width=True)

            fig_tickets = px.line(
                daily, x="fecha", y="tickets",
                title="Tickets por día",
                labels={"fecha": "Fecha", "tickets": "Cantidad de tickets"},
                color_discrete_sequence=["#2ECC71"],
            )
            st.plotly_chart(fig_tickets, use_container_width=True)
