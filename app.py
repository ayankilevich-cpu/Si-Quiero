"""Si Quiero — Sistema de control de costos y rentabilidad."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.db_manager import init_db
from services.data_loader import DataLoader
from services.cost_engine import CostEngine
from services.icecream_cost_service import IceCreamCostService
from services.price_update_service import PriceUpdateService
from services.alert_service import AlertService

init_db()

st.set_page_config(
    page_title="Si Quiero — Control de costos",
    page_icon="🍦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    [data-testid="stSidebar"] { min-width: 240px; }
    .stMetric { background: #f8f9fa; border-radius: 8px; padding: 12px; }
</style>
""", unsafe_allow_html=True)


def get_services():
    loader = DataLoader()
    engine = CostEngine(loader)
    ice_svc = IceCreamCostService(loader)
    price_svc = PriceUpdateService(loader)
    alert_svc = AlertService(loader, engine)
    return loader, engine, ice_svc, price_svc, alert_svc


loader, engine, ice_svc, price_svc, alert_svc = get_services()

PAGES = {
    "Dashboard": "p01_dashboard",
    "Ingredientes": "p02_ingredientes",
    "Remitos helado": "p03_remitos_helado",
    "Recetas": "p04_recetas",
    "Productos": "p05_productos",
    "Rentabilidad productos": "p06_rentabilidad_productos",
    "Rentabilidad combos": "p07_rentabilidad_combos",
    "Simulador": "p08_simulador",
    "Ingeniería de menú": "p09_ingenieria_menu",
}

with st.sidebar:
    st.image("https://img.icons8.com/dusk/64/ice-cream-cone.png", width=50)
    st.title("Si Quiero")
    st.caption("Control de costos y rentabilidad")
    st.divider()

    page = st.radio("Navegación", list(PAGES.keys()), label_visibility="collapsed")

    st.divider()
    if st.button("Refrescar datos", use_container_width=True):
        st.rerun()

    with st.expander("Alertas"):
        alertas = alert_svc.todas_las_alertas()
        if alertas:
            for a in alertas[:10]:
                icon = {"alta": "🔴", "media": "🟡", "baja": "🟢"}.get(a["severidad"], "⚪")
                st.caption(f"{icon} {a['mensaje']}")
            if len(alertas) > 10:
                st.caption(f"… y {len(alertas) - 10} alertas más")
        else:
            st.caption("Sin alertas activas")

module_name = PAGES[page]

if module_name == "p01_dashboard":
    from views.p01_dashboard import render as page_render
elif module_name == "p02_ingredientes":
    from views.p02_ingredientes import render as page_render
elif module_name == "p03_remitos_helado":
    from views.p03_remitos_helado import render as page_render
elif module_name == "p04_recetas":
    from views.p04_recetas import render as page_render
elif module_name == "p05_productos":
    from views.p05_productos import render as page_render
elif module_name == "p06_rentabilidad_productos":
    from views.p06_rentabilidad_productos import render as page_render
elif module_name == "p07_rentabilidad_combos":
    from views.p07_rentabilidad_combos import render as page_render
elif module_name == "p08_simulador":
    from views.p08_simulador import render as page_render
elif module_name == "p09_ingenieria_menu":
    from views.p09_ingenieria_menu import render as page_render

page_render(
    loader, engine,
    ice_svc=ice_svc,
    price_svc=price_svc,
    alert_svc=alert_svc,
)
