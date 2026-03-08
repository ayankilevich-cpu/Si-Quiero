"""Gestión de remitos de helado: carga manual, carga PDF, historial y costo vigente."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.helpers import fmt_ars
from utils.pdf_parser import parse_remito_pdf, parse_remito_text


def render(loader, engine, **kwargs):
    st.header("Gestión de remitos de helado")

    ice_svc = kwargs.get("ice_svc") or engine.ice_svc
    info = ice_svc.costo_ponderado_general()

    # ── KPIs ──
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Costo ponderado / kg", fmt_ars(info["costo_kg"]))
    c2.metric("Costo / gramo", fmt_ars(info["costo_gramo"], 2))
    c3.metric("Total comprado", f'{info["total_kg"]:,.1f} kg')
    c4.metric("Total invertido", fmt_ars(info["total_importe"]))

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "Carga manual", "Carga desde PDF", "Historial de compras", "Costo por sabor",
    ])

    with tab1:
        _render_carga_manual(ice_svc)

    with tab2:
        _render_carga_pdf(ice_svc)

    with tab3:
        _render_historial(ice_svc)

    with tab4:
        _render_costo_sabor(ice_svc)


def _render_carga_manual(ice_svc):
    st.subheader("Cargar remito manualmente")

    fecha = st.date_input("Fecha del remito", value=date.today(), key="rem_fecha")
    proveedor = st.text_input("Proveedor", value="Capuano", key="rem_prov")

    st.markdown("**Líneas del remito**")
    n_lineas = st.number_input("Cantidad de líneas", min_value=1, max_value=30, value=5, key="rem_n")

    lineas = []
    for i in range(n_lineas):
        cols = st.columns([3, 1, 2])
        sabor = cols[0].text_input("Sabor", key=f"rem_sabor_{i}")
        kilos = cols[1].number_input("Kg", min_value=0.0, step=0.5, key=f"rem_kg_{i}")
        importe = cols[2].number_input("Importe ($)", min_value=0.0, step=1000.0, key=f"rem_imp_{i}")
        if sabor and kilos > 0 and importe > 0:
            lineas.append({"sabor": sabor, "kilos": kilos, "importe": importe})

    if st.button("Guardar remito", type="primary", key="btn_rem_manual"):
        if lineas:
            n = ice_svc.agregar_remito_manual(fecha, proveedor, lineas)
            st.success(f"✅ {n} líneas guardadas.")
            st.rerun()
        else:
            st.warning("Complete al menos una línea válida.")


def _render_carga_pdf(ice_svc):
    st.subheader("Cargar remito desde PDF")

    uploaded = st.file_uploader("Subir remito PDF", type=["pdf"], key="rem_pdf")
    if uploaded:
        file_bytes = uploaded.read()
        parsed = parse_remito_pdf(file_bytes)

        if "error" in parsed:
            st.error(parsed["error"])
            st.markdown("**Alternativa:** Pegue el texto del remito abajo.")
            texto = st.text_area("Texto del remito", height=300, key="rem_texto")
            if texto and st.button("Procesar texto", key="btn_rem_text"):
                parsed = parse_remito_text(texto)
                if parsed.get("lineas"):
                    n = ice_svc.agregar_remito_pdf(parsed, uploaded.name)
                    st.success(f"✅ {n} líneas importadas desde texto.")
                    st.rerun()
                else:
                    st.warning("No se encontraron líneas en el texto.")
        else:
            st.markdown(f"**Fecha:** {parsed.get('fecha')}")
            st.markdown(f"**Proveedor:** {parsed.get('proveedor')}")
            st.markdown(f"**Total:** {fmt_ars(parsed.get('total', 0))}")

            if parsed.get("lineas"):
                df_preview = pd.DataFrame(parsed["lineas"])
                st.dataframe(df_preview, width="stretch", hide_index=True)

                if st.button("Importar remito", type="primary", key="btn_rem_import"):
                    n = ice_svc.agregar_remito_pdf(parsed, uploaded.name)
                    st.success(f"✅ {n} líneas importadas.")
                    st.rerun()
            else:
                st.warning("No se pudieron extraer líneas del PDF.")

    st.divider()
    st.markdown("**¿No se pudo leer el PDF?** Pegue el texto del remito:")
    texto_alt = st.text_area("Texto del remito", height=200, key="rem_texto_alt")
    if texto_alt and st.button("Procesar texto pegado", key="btn_rem_text_alt"):
        parsed = parse_remito_text(texto_alt)
        if parsed.get("lineas"):
            n = ice_svc.agregar_remito_pdf(parsed, "texto_pegado")
            st.success(f"✅ {n} líneas importadas.")
            st.rerun()
        else:
            st.warning("No se encontraron líneas válidas.")


def _render_historial(ice_svc):
    st.subheader("Historial de compras de helado")
    df = ice_svc.historial_compras()
    if df.empty:
        st.info("Sin compras registradas.")
        return

    filtro_fecha = st.checkbox("Filtrar por fecha", key="rem_filtro_f")
    if filtro_fecha:
        fechas = pd.to_datetime(df["fecha"]).dt.date
        rango = st.date_input("Rango", value=(fechas.min(), fechas.max()), key="rem_rango")
        if len(rango) == 2:
            df = df[(df["fecha"] >= rango[0]) & (df["fecha"] <= rango[1])]

    st.dataframe(df, width="stretch", hide_index=True)

    total_kg = df["kilos"].sum()
    total_imp = df["importe_total"].sum()
    costo_pond = total_imp / total_kg if total_kg > 0 else 0
    st.metric("Costo ponderado período", fmt_ars(costo_pond))


def _render_costo_sabor(ice_svc):
    st.subheader("Costo ponderado por sabor (informativo)")
    df = ice_svc.costo_por_sabor()
    if df.empty:
        st.info("Sin datos.")
        return

    st.dataframe(df, width="stretch", hide_index=True)

    fig = px.bar(
        df.head(20), x="sabor", y="costo_kg",
        title="Costo por kg — top 20 sabores",
        labels={"sabor": "Sabor", "costo_kg": "Costo/kg ($)"},
        color="total_kg", color_continuous_scale="Tealgrn",
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, width="stretch")
