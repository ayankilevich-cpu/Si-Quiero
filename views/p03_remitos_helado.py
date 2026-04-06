"""Gestión de remitos de helado: carga manual, carga PDF, historial y costo vigente."""

from __future__ import annotations

import re
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.helpers import fmt_ars
from utils.pdf_parser import parse_remito_pdf, parse_remito_text


def _suma_subtotales_lineas(lineas: list[dict], precio_es_unitario: bool) -> float:
    """Igual que al guardar: subtotal = importe o importe × kg si es precio unitario."""
    total = 0.0
    for l in lineas:
        imp = float(l.get("importe", 0) or 0)
        kg = float(l.get("kilos", 0) or 0)
        if precio_es_unitario and kg > 0:
            total += imp * kg
        else:
            total += imp
    return total


def _tolerancia_total(suma: float, total_remito: float) -> tuple[float, float]:
    """(tolerancia_absoluta, tolerancia_pct) para considerar alineado."""
    if total_remito <= 0:
        return (0.0, 0.0)
    tol_abs = max(500.0, abs(total_remito) * 0.005)
    tol_pct = 1.5
    return (tol_abs, tol_pct)


def _remito_alineado(suma: float, total_remito: float) -> bool:
    if total_remito <= 0:
        return True
    diff = abs(suma - total_remito)
    tol_abs, tol_pct = _tolerancia_total(suma, total_remito)
    if diff <= tol_abs:
        return True
    if abs(total_remito) > 1e-6 and (diff / abs(total_remito) * 100) <= tol_pct:
        return True
    return False


def _key_prefix_seguro(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", s)[:48] or "rem"


def render_validacion_suma_vs_total(
    lineas: list[dict],
    total_remito: float,
    precio_es_unitario: bool,
    *,
    key_prefix: str,
) -> bool:
    """Muestra suma de líneas vs total del remito. Devuelve True si se puede importar/guardar."""
    if not lineas:
        return False

    suma = _suma_subtotales_lineas(lineas, precio_es_unitario)
    st.markdown("**Control: suma de líneas vs total del remito**")

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Suma de líneas (subtotales)",
        fmt_ars(suma),
        help="Con «precio $/kg» activo, cada fila suma importe × kg.",
    )
    if total_remito > 0:
        c2.metric("Total detectado en remito", fmt_ars(total_remito))
        diff = suma - total_remito
        tol_abs, tol_pct = _tolerancia_total(suma, total_remito)
        pct = abs(diff / total_remito * 100) if abs(total_remito) > 1e-9 else 0.0
        c3.metric("Diferencia", fmt_ars(diff), delta=f"{pct:.2f} % vs total")
    else:
        c2.metric("Total detectado en remito", "—")
        c3.metric("Diferencia", "—")

    alineado = _remito_alineado(suma, total_remito)

    if total_remito <= 0:
        st.info(
            "No se encontró una línea **TOTAL:** en el texto parseado. "
            "Comprobá la suma contra el remito impreso antes de guardar."
        )
        return True

    if alineado:
        tol_abs, _ = _tolerancia_total(suma, total_remito)
        st.success(
            f"Suma y total coinciden dentro de tolerancia (hasta {fmt_ars(tol_abs)} o 1,5 %)."
        )
        return True

    st.warning(
        "La suma de líneas **no coincide** con el total del remito. Suele deberse a: miles mal leídos, "
        "columna precio/kg sin marcar, o líneas que el parser no capturó. Corregí el origen o confirmá abajo."
    )
    force = st.checkbox(
        "Entiendo el riesgo: guardar / importar de todos modos",
        value=False,
        key=f"rem_val_force_{key_prefix}",
    )
    return force


def render(loader, engine, **kwargs):
    st.header("Gestión de remitos de helado")

    ice_svc = kwargs.get("ice_svc") or engine.ice_svc
    info = ice_svc.costo_ponderado_general()

    st.caption(
        "El costo ponderado es **Σ importe línea ÷ Σ kilos**. Si el remito trae **precio por kg** "
        "en la última columna (y no el subtotal), activá la opción correspondiente al importar o cargar."
    )

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
    precio_unit = st.checkbox(
        "La columna importe es **precio $/kg** (se multiplica por kg de cada línea)",
        value=False,
        key="rem_manual_pu",
    )

    total_remito_manual = st.number_input(
        "Total impreso en el remito (opcional, para validar la suma)",
        min_value=0.0,
        step=1000.0,
        value=0.0,
        key="rem_total_manual",
    )

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

    puede_guardar = True
    if lineas and total_remito_manual > 0:
        puede_guardar = render_validacion_suma_vs_total(
            lineas,
            float(total_remito_manual),
            precio_unit,
            key_prefix="manual_save",
        )
    elif lineas:
        st.caption("Tip: ingresá el total del remito arriba para comparar automáticamente con la suma de líneas.")

    if st.button("Guardar remito", type="primary", key="btn_rem_manual", disabled=not lineas or not puede_guardar):
        if lineas:
            n = ice_svc.agregar_remito_manual(
                fecha, proveedor, lineas, precio_es_unitario=precio_unit,
            )
            st.success(f"✅ {n} líneas guardadas.")
            st.rerun()
        else:
            st.warning("Complete al menos una línea válida.")


def _render_carga_pdf(ice_svc):
    st.subheader("Cargar remito desde PDF")

    uploaded = st.file_uploader("Subir remito PDF", type=["pdf"], key="rem_pdf")
    precio_unit_pdf = st.checkbox(
        "Importación PDF / texto: la última columna es **precio $/kg** (no subtotal de línea)",
        value=False,
        key="rem_pdf_pu",
    )
    if uploaded:
        file_bytes = uploaded.read()
        parsed = parse_remito_pdf(file_bytes)

        if "error" in parsed:
            st.error(parsed["error"])
            st.markdown("**Alternativa:** Pegue el texto del remito abajo.")
            texto = st.text_area("Texto del remito", height=300, key="rem_texto")
            sess_key = f"rem_pdf_txt_{_key_prefix_seguro(uploaded.name)}"
            if texto and st.button("Vista previa del texto", key="btn_rem_text_preview"):
                st.session_state[sess_key] = parse_remito_text(texto)
            parsed_txt = st.session_state.get(sess_key)
            if parsed_txt and parsed_txt.get("lineas"):
                st.markdown(f"**Fecha:** {parsed_txt.get('fecha')}")
                st.markdown(f"**Proveedor:** {parsed_txt.get('proveedor')}")
                st.markdown(f"**Total:** {fmt_ars(parsed_txt.get('total', 0))}")
                st.dataframe(pd.DataFrame(parsed_txt["lineas"]), width="stretch", hide_index=True)
                puede_txt = render_validacion_suma_vs_total(
                    parsed_txt["lineas"],
                    float(parsed_txt.get("total") or 0),
                    precio_unit_pdf,
                    key_prefix=f"pdf_txt_{_key_prefix_seguro(uploaded.name)}",
                )
                c_imp, c_clr = st.columns(2)
                if c_imp.button(
                    "Importar desde texto",
                    type="primary",
                    key="btn_rem_text_import",
                    disabled=not puede_txt,
                ):
                    n = ice_svc.agregar_remito_pdf(
                        parsed_txt, uploaded.name, precio_es_unitario=precio_unit_pdf,
                    )
                    st.session_state.pop(sess_key, None)
                    st.success(f"✅ {n} líneas importadas desde texto.")
                    st.rerun()
                if c_clr.button("Limpiar vista previa", key="btn_rem_text_clear"):
                    st.session_state.pop(sess_key, None)
                    st.rerun()
            elif texto and st.session_state.get(sess_key) is not None:
                st.warning("No se encontraron líneas en el texto analizado.")
        else:
            st.markdown(f"**Fecha:** {parsed.get('fecha')}")
            st.markdown(f"**Proveedor:** {parsed.get('proveedor')}")
            st.markdown(f"**Total:** {fmt_ars(parsed.get('total', 0))}")

            if parsed.get("lineas"):
                df_preview = pd.DataFrame(parsed["lineas"])
                st.dataframe(df_preview, width="stretch", hide_index=True)
                kp = _key_prefix_seguro(uploaded.name or "pdf")
                puede_pdf = render_validacion_suma_vs_total(
                    parsed["lineas"],
                    float(parsed.get("total") or 0),
                    precio_unit_pdf,
                    key_prefix=f"pdf_ok_{kp}",
                )
                if st.button(
                    "Importar remito",
                    type="primary",
                    key="btn_rem_import",
                    disabled=not puede_pdf,
                ):
                    n = ice_svc.agregar_remito_pdf(
                        parsed, uploaded.name, precio_es_unitario=precio_unit_pdf,
                    )
                    st.success(f"✅ {n} líneas importadas.")
                    st.rerun()
            else:
                st.warning("No se pudieron extraer líneas del PDF.")

    st.divider()
    st.markdown("**¿No se pudo leer el PDF?** Pegue el texto del remito:")
    texto_alt = st.text_area("Texto del remito", height=200, key="rem_texto_alt")
    st.caption("Si cambiás el texto, volvé a pulsar **Vista previa** para recalcular el control.")
    sess_pego = "rem_texto_pego_parsed"
    if texto_alt and st.button("Vista previa (texto pegado)", key="btn_rem_text_alt_prev"):
        st.session_state[sess_pego] = parse_remito_text(texto_alt)
    parsed_pego = st.session_state.get(sess_pego)
    if parsed_pego and parsed_pego.get("lineas"):
        st.markdown(f"**Fecha:** {parsed_pego.get('fecha')}")
        st.markdown(f"**Proveedor:** {parsed_pego.get('proveedor')}")
        st.markdown(f"**Total:** {fmt_ars(parsed_pego.get('total', 0))}")
        st.dataframe(pd.DataFrame(parsed_pego["lineas"]), width="stretch", hide_index=True)
        puede_pego = render_validacion_suma_vs_total(
            parsed_pego["lineas"],
            float(parsed_pego.get("total") or 0),
            precio_unit_pdf,
            key_prefix="texto_pego",
        )
        c1, c2 = st.columns(2)
        if c1.button(
            "Importar remito",
            type="primary",
            key="btn_rem_text_alt_imp",
            disabled=not puede_pego,
        ):
            n = ice_svc.agregar_remito_pdf(
                parsed_pego, "texto_pegado", precio_es_unitario=precio_unit_pdf,
            )
            st.session_state.pop(sess_pego, None)
            st.success(f"✅ {n} líneas importadas.")
            st.rerun()
        if c2.button("Limpiar vista previa", key="btn_rem_text_alt_clear"):
            st.session_state.pop(sess_pego, None)
            st.rerun()
    elif texto_alt and st.session_state.get(sess_pego) is not None:
        st.warning("No se encontraron líneas válidas en el último análisis.")


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
