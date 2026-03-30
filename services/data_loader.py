"""Capa de abstracción de datos — backend SQLite."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from config import DB_PATH
from services.db_manager import get_connection, init_db


class DataLoader:

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or DB_PATH
        init_db(self._db_path)

    def _conn(self):
        return get_connection(self._db_path)

    # ── helpers ──

    @staticmethod
    def _parse_dates(df: pd.DataFrame, col: str, to_date: bool = True) -> pd.DataFrame:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            if to_date:
                df[col] = df[col].dt.date
        return df

    @staticmethod
    def _bool_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        for c in cols:
            if c in df.columns:
                df[c] = df[c].astype(bool)
        return df

    def _save_replace(self, table: str, df: pd.DataFrame, drop_pk: str | None = None) -> None:
        """Reemplaza toda la tabla con el contenido del DataFrame."""
        clean = df.copy()
        if drop_pk and drop_pk in clean.columns:
            clean = clean.drop(columns=[drop_pk])
        conn = self._conn()
        try:
            conn.execute(f"DELETE FROM {table}")
            clean.to_sql(table, conn, if_exists="append", index=False)
            conn.commit()
        finally:
            conn.close()

    # ── Ingredientes ──

    def load_ingredientes(self) -> pd.DataFrame:
        conn = self._conn()
        try:
            df = pd.read_sql("SELECT * FROM ingredientes", conn)
        finally:
            conn.close()
        self._parse_dates(df, "ultimo_update", to_date=True)
        self._bool_cols(df, ["requiere_revision_costo", "activo"])
        return df

    def save_ingredientes(self, df: pd.DataFrame) -> None:
        self._save_replace("ingredientes", df)

    # ── Productos ──

    def load_productos(self) -> pd.DataFrame:
        conn = self._conn()
        try:
            df = pd.read_sql("SELECT * FROM productos", conn)
        finally:
            conn.close()
        self._bool_cols(df, ["activo"])
        return df

    def save_productos(self, df: pd.DataFrame) -> None:
        self._save_replace("productos", df)

    # ── Componentes ──

    def load_componentes(self) -> pd.DataFrame:
        conn = self._conn()
        try:
            df = pd.read_sql(
                "SELECT parent_id, parent_type, component_type, component_id, "
                "component_name, cantidad, unidad, merma_pct, notas "
                "FROM componentes", conn,
            )
        finally:
            conn.close()
        if df.empty:
            df = pd.DataFrame(columns=[
                "parent_id", "parent_type", "component_type",
                "component_id", "component_name", "cantidad",
                "unidad", "merma_pct", "notas",
            ])
        return df

    def save_componentes(self, df: pd.DataFrame) -> None:
        self._save_replace("componentes", df, drop_pk="rowid_pk")

    # ── Recetas ──

    def load_recetas(self) -> pd.DataFrame:
        conn = self._conn()
        try:
            df = pd.read_sql("SELECT * FROM recetas", conn)
        finally:
            conn.close()
        if df.empty:
            df = pd.DataFrame(columns=[
                "recipe_id", "recipe_name", "categoria", "subcategoria",
                "rendimiento_cantidad", "unidad_rendimiento",
                "product_id_vinculado", "notas",
            ])
        return df

    def save_recetas(self, df: pd.DataFrame) -> None:
        self._save_replace("recetas", df)

    # ── Combos ──

    def load_combos(self) -> pd.DataFrame:
        conn = self._conn()
        try:
            df = pd.read_sql("SELECT * FROM combos", conn)
        finally:
            conn.close()
        if df.empty:
            df = pd.DataFrame(columns=["combo_id", "combo_name", "precio_venta"])
        return df

    def load_combo_items(self) -> pd.DataFrame:
        conn = self._conn()
        try:
            df = pd.read_sql(
                "SELECT combo_id, product_id, cantidad FROM combo_items", conn,
            )
        finally:
            conn.close()
        if df.empty:
            df = pd.DataFrame(columns=["combo_id", "product_id", "cantidad"])
        return df

    def save_combos(self, df_combos: pd.DataFrame, df_ci: pd.DataFrame) -> None:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM combo_items")
            conn.execute("DELETE FROM combos")
            df_combos.to_sql("combos", conn, if_exists="append", index=False)
            ci = df_ci.copy()
            if "rowid_pk" in ci.columns:
                ci = ci.drop(columns=["rowid_pk"])
            ci.to_sql("combo_items", conn, if_exists="append", index=False)
            conn.commit()
        finally:
            conn.close()

    # ── Helado compras ──

    def load_helado_compras(self) -> pd.DataFrame:
        conn = self._conn()
        try:
            df = pd.read_sql("SELECT * FROM helado_compras", conn)
        finally:
            conn.close()
        self._parse_dates(df, "fecha", to_date=True)
        if df.empty:
            df = pd.DataFrame(columns=[
                "purchase_id", "fecha", "proveedor", "sabor",
                "kilos", "importe_total", "costo_kg",
                "remito_origen", "observaciones",
            ])
        return df

    def save_helado_compras(self, df: pd.DataFrame) -> None:
        self._save_replace("helado_compras", df)

    # ── Ventas ──

    def load_ventas(self) -> pd.DataFrame:
        conn = self._conn()
        try:
            df = pd.read_sql(
                "SELECT fecha_hora, numero_pedido, codigo_venta, producto, "
                "producto_norm, cantidad, total, rubro, subrubro, area, sector "
                "FROM ventas", conn,
            )
        finally:
            conn.close()
        return df

    def load_ventas_resumen(self) -> pd.DataFrame:
        conn = self._conn()
        try:
            df = pd.read_sql(
                "SELECT producto_norm, producto, codigo_venta, rubro, subrubro, "
                "area, tickets, unidades_vendidas_mes, facturacion_mes, "
                "precio_promedio_realizado, vendido_ultimo_mes "
                "FROM ventas_resumen", conn,
            )
        finally:
            conn.close()
        return df

    # ── Ventas: escritura ──

    def save_ventas(self, df: pd.DataFrame) -> None:
        self._save_replace("ventas", df, drop_pk="rowid_pk")

    def save_ventas_resumen(self, df: pd.DataFrame) -> None:
        self._save_replace("ventas_resumen", df, drop_pk="rowid_pk")

    def append_ventas(self, df: pd.DataFrame) -> int:
        """Agrega filas nuevas a ventas sin borrar las existentes.
        Devuelve la cantidad de filas insertadas."""
        clean = df.copy()
        if "rowid_pk" in clean.columns:
            clean = clean.drop(columns=["rowid_pk"])
        conn = self._conn()
        try:
            clean.to_sql("ventas", conn, if_exists="append", index=False)
            conn.commit()
        finally:
            conn.close()
        return len(clean)

    # ── Historial de precios ──

    def load_historial_precios(self) -> pd.DataFrame:
        conn = self._conn()
        try:
            df = pd.read_sql(
                "SELECT fecha, ingredient_id, precio_anterior, precio_nuevo, origen "
                "FROM historial_precios", conn,
            )
        finally:
            conn.close()
        self._parse_dates(df, "fecha", to_date=True)
        if df.empty:
            df = pd.DataFrame(columns=[
                "fecha", "ingredient_id", "precio_anterior", "precio_nuevo", "origen",
            ])
        return df

    def save_historial_precios(self, df: pd.DataFrame) -> None:
        self._save_replace("historial_precios", df, drop_pk="rowid_pk")

    def append_historial(self, registros: list[dict]) -> None:
        if not registros:
            return
        new = pd.DataFrame(registros)
        conn = self._conn()
        try:
            new.to_sql("historial_precios", conn, if_exists="append", index=False)
            conn.commit()
        finally:
            conn.close()
