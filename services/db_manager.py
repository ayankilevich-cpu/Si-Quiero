"""Gestión de la base de datos SQLite para Si Quiero."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from config import DB_PATH

_DDL = """
CREATE TABLE IF NOT EXISTS ingredientes (
    ingredient_id   INTEGER PRIMARY KEY,
    ingrediente     TEXT NOT NULL,
    ingrediente_norm TEXT DEFAULT '',
    costo_actual    REAL DEFAULT 0,
    alicuota_iva    REAL DEFAULT 21.0,
    unidad_base     TEXT DEFAULT '',
    unidad_compra   TEXT DEFAULT '',
    factor_compra_a_base REAL DEFAULT 1.0,
    rubro           TEXT DEFAULT '',
    subrubro        TEXT DEFAULT '',
    proveedor       TEXT DEFAULT '',
    requiere_revision_costo INTEGER DEFAULT 1,
    notas           TEXT DEFAULT '',
    activo          INTEGER DEFAULT 1,
    ultimo_update   TEXT
);

CREATE TABLE IF NOT EXISTS productos (
    product_id      INTEGER PRIMARY KEY,
    codigo_lista    TEXT DEFAULT '',
    codigo_venta    TEXT DEFAULT '',
    producto        TEXT NOT NULL,
    producto_norm   TEXT DEFAULT '',
    categoria       TEXT DEFAULT '',
    subcategoria    TEXT DEFAULT '',
    area            TEXT DEFAULT '',
    tipo_producto   TEXT DEFAULT 'simple',
    precio_venta_actual    REAL DEFAULT 0,
    precio_promedio_realizado REAL DEFAULT 0,
    unidades_vendidas_mes  REAL DEFAULT 0,
    facturacion_mes        REAL DEFAULT 0,
    tickets         REAL DEFAULT 0,
    vendido_ultimo_mes     TEXT DEFAULT '',
    usar_en_app     TEXT DEFAULT '',
    requiere_receta_o_componentes TEXT DEFAULT '',
    notas           TEXT DEFAULT '',
    activo          INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS componentes (
    rowid_pk        INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id       TEXT NOT NULL,
    parent_type     TEXT NOT NULL,
    component_type  TEXT NOT NULL,
    component_id    TEXT NOT NULL,
    component_name  TEXT DEFAULT '',
    cantidad        REAL DEFAULT 0,
    unidad          TEXT DEFAULT '',
    merma_pct       REAL DEFAULT 0,
    notas           TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_comp_parent ON componentes(parent_id);
CREATE INDEX IF NOT EXISTS idx_comp_component ON componentes(component_id);

CREATE TABLE IF NOT EXISTS recetas (
    recipe_id              TEXT PRIMARY KEY,
    recipe_name            TEXT NOT NULL,
    categoria              TEXT DEFAULT '',
    subcategoria           TEXT DEFAULT '',
    rendimiento_cantidad   INTEGER DEFAULT 1,
    unidad_rendimiento     TEXT DEFAULT 'porcion',
    product_id_vinculado   TEXT DEFAULT '',
    notas                  TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS combos (
    combo_id    TEXT PRIMARY KEY,
    combo_name  TEXT NOT NULL,
    precio_venta REAL DEFAULT 0,
    categoria   TEXT DEFAULT '',
    activo      INTEGER DEFAULT 1,
    notas       TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS combo_items (
    rowid_pk    INTEGER PRIMARY KEY AUTOINCREMENT,
    combo_id    TEXT NOT NULL,
    product_id  TEXT NOT NULL,
    cantidad    REAL DEFAULT 1,
    FOREIGN KEY (combo_id) REFERENCES combos(combo_id)
);

CREATE TABLE IF NOT EXISTS helado_compras (
    purchase_id     INTEGER PRIMARY KEY,
    fecha           TEXT,
    proveedor       TEXT DEFAULT '',
    sabor           TEXT DEFAULT '',
    kilos           REAL DEFAULT 0,
    importe_total   REAL DEFAULT 0,
    costo_kg        REAL DEFAULT 0,
    remito_origen   TEXT DEFAULT '',
    observaciones   TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ventas (
    rowid_pk        INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_hora      TEXT,
    numero_pedido   INTEGER DEFAULT 0,
    codigo_venta    INTEGER DEFAULT 0,
    producto        TEXT DEFAULT '',
    producto_norm   TEXT DEFAULT '',
    cantidad        REAL DEFAULT 0,
    total           REAL DEFAULT 0,
    rubro           TEXT DEFAULT '',
    subrubro        TEXT DEFAULT '',
    area            TEXT DEFAULT '',
    sector          TEXT DEFAULT '',
    costo_unitario  REAL,
    margen_pct      REAL,
    food_cost_pct   REAL
);
CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha_hora);

CREATE TABLE IF NOT EXISTS ventas_resumen (
    rowid_pk                INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_norm           TEXT DEFAULT '',
    producto                TEXT DEFAULT '',
    codigo_venta            TEXT DEFAULT '',
    rubro                   TEXT DEFAULT '',
    subrubro                TEXT DEFAULT '',
    area                    TEXT DEFAULT '',
    tickets                 REAL DEFAULT 0,
    unidades_vendidas_mes   REAL DEFAULT 0,
    facturacion_mes         REAL DEFAULT 0,
    precio_promedio_realizado REAL DEFAULT 0,
    vendido_ultimo_mes      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS historial_precios (
    rowid_pk        INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha           TEXT,
    ingredient_id   INTEGER DEFAULT 0,
    precio_anterior REAL DEFAULT 0,
    precio_nuevo    REAL DEFAULT 0,
    origen          TEXT DEFAULT 'manual'
);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Abre una conexión a la base SQLite."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


_MIGRATIONS = [
    "ALTER TABLE ventas ADD COLUMN costo_unitario REAL",
    "ALTER TABLE ventas ADD COLUMN margen_pct REAL",
    "ALTER TABLE ventas ADD COLUMN food_cost_pct REAL",
]


def init_db(db_path: Path | None = None) -> None:
    """Crea las tablas si no existen y aplica migraciones pendientes."""
    conn = get_connection(db_path)
    try:
        conn.executescript(_DDL)
        for stmt in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()
    finally:
        conn.close()
