"""Servicio de alertas del negocio."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd

from config import (
    DIAS_SIN_ACTUALIZAR_ALERTA,
    FOOD_COST_OBJETIVO_PCT,
    MARGEN_ALERTA_COMBO_PCT,
)
from services.data_loader import DataLoader
from services.cost_engine import CostEngine


class AlertService:

    def __init__(
        self,
        loader: Optional[DataLoader] = None,
        engine: Optional[CostEngine] = None,
    ):
        self.loader = loader or DataLoader()
        self.engine = engine or CostEngine(self.loader)

    def todas_las_alertas(self) -> list[dict]:
        alertas: list[dict] = []

        self._alertas_food_cost(alertas)
        self._alertas_combos(alertas)
        self._alertas_ingredientes_desactualizados(alertas)
        self._alertas_helado(alertas)

        return alertas

    def _alertas_food_cost(self, alertas: list[dict]):
        tabla = self.engine.tabla_rentabilidad_productos()
        if tabla.empty:
            return
        criticos = tabla[tabla["Food Cost %"] > FOOD_COST_OBJETIVO_PCT]
        for _, r in criticos.iterrows():
            alertas.append({
                "tipo": "margen",
                "severidad": "alta",
                "mensaje": f"{r['Producto']}: food cost {r['Food Cost %']:.1f}% > objetivo {FOOD_COST_OBJETIVO_PCT}%",
            })

    def _alertas_combos(self, alertas: list[dict]):
        combos = self.loader.load_combos()
        for _, c in combos.iterrows():
            r = self.engine.costo_combo(str(c["combo_id"]))
            if r.get("margen_pct", 100) < MARGEN_ALERTA_COMBO_PCT:
                alertas.append({
                    "tipo": "combo",
                    "severidad": "alta",
                    "mensaje": f"Combo '{r.get('nombre', '')}': margen {r['margen_pct']:.1f}% < {MARGEN_ALERTA_COMBO_PCT}%",
                })

    def _alertas_ingredientes_desactualizados(self, alertas: list[dict]):
        df = self.loader.load_ingredientes()
        if df.empty or "ultimo_update" not in df.columns:
            return
        umbral = date.today() - timedelta(days=DIAS_SIN_ACTUALIZAR_ALERTA)
        for _, r in df.iterrows():
            upd = r.get("ultimo_update")
            if upd and upd < umbral:
                alertas.append({
                    "tipo": "ingrediente",
                    "severidad": "media",
                    "mensaje": f"{r['ingrediente']}: sin actualizar desde {upd}",
                })

    def _alertas_helado(self, alertas: list[dict]):
        df = self.loader.load_helado_compras()
        if df.empty:
            alertas.append({
                "tipo": "helado",
                "severidad": "alta",
                "mensaje": "Sin remitos de helado cargados — costo ponderado no disponible",
            })
