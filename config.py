"""Configuración global de la aplicación Si Quiero."""

from pathlib import Path

# ── Rutas ──
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
DB_PATH = DATA_DIR / "si_quiero.db"

# ── Moneda ──
MONEDA_SIMBOLO = "$"
MONEDA_CODIGO = "ARS"

# ── Márgenes objetivo ──
MARGEN_OBJETIVO_PCT = 65.0
FOOD_COST_OBJETIVO_PCT = 35.0
MARGEN_ALERTA_COMBO_PCT = 20.0

# ── Umbrales de alerta ──
DIAS_SIN_ACTUALIZAR_ALERTA = 30

# ── Rubros de ingredientes ──
RUBROS_INGREDIENTES = ["CAFET", "HELAD", "HAVANNAA", "OTROS"]

# ── Categorías de productos ──
CATEGORIAS_PRODUCTOS = [
    "HELADERIA",
    "CAFETERIA",
    "BEBIDAS",
    "TORTAS",
    "HAVANNA",
    "OTROS",
]

# ── Tipos de producto ──
TIPOS_PRODUCTO = ["simple", "receta", "armado", "combo"]

# ── Tipos de componente ──
TIPOS_COMPONENTE = ["ingrediente", "receta", "producto", "helado_base"]

# ── Unidades ──
UNIDADES_BASE = ["GRAMOS", "MILILITROS", "UNIDAD"]

UNIDADES_COMPRA = {
    "KG": {"factor_a_base": 1000, "unidad_base": "GRAMOS"},
    "GRAMOS": {"factor_a_base": 1, "unidad_base": "GRAMOS"},
    "LT": {"factor_a_base": 1000, "unidad_base": "MILILITROS"},
    "MILILITROS": {"factor_a_base": 1, "unidad_base": "MILILITROS"},
    "UNIDAD": {"factor_a_base": 1, "unidad_base": "UNIDAD"},
    "DOCENA": {"factor_a_base": 12, "unidad_base": "UNIDAD"},
}

# ── Helado: gramos por formato ──
HELADO_GRAMOS = {
    "1_bocha": 90,
    "2_bochas": 180,
    "cuarto_kg": 250,
    "medio_kg": 500,
    "un_kg": 1000,
}

# ── Colores del tema ──
COLORS = {
    "primary": "#E85D75",
    "secondary": "#6C5B7B",
    "accent": "#F8B500",
    "success": "#2ECC71",
    "warning": "#F39C12",
    "danger": "#E74C3C",
    "info": "#3498DB",
    "muted": "#95A5A6",
}

ESTADO_COLORS = {
    "Saludable": COLORS["success"],
    "Atención": COLORS["warning"],
    "Crítico": COLORS["danger"],
}
