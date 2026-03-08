"""Esquemas de validación para las entidades del negocio."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class Ingrediente:
    ingredient_id: int
    ingrediente: str
    categoria: str
    unidad_base: str
    costo_actual: float
    alicuota_iva: float = 21.0
    unidad_compra: str = ""
    factor_compra_a_base: float = 1.0
    rubro: str = ""
    subrubro: str = ""
    proveedor: str = ""
    requiere_revision_costo: bool = True
    ultimo_update: Optional[date] = None
    activo: bool = True
    notas: str = ""


@dataclass
class HeladoCompra:
    purchase_id: int = 0
    fecha: Optional[date] = None
    proveedor: str = ""
    sabor: str = ""
    kilos: float = 0.0
    importe_total: float = 0.0
    costo_kg: float = 0.0
    remito_origen: str = ""
    observaciones: str = ""


@dataclass
class Receta:
    recipe_id: str = ""
    recipe_name: str = ""
    categoria: str = ""
    subcategoria: str = ""
    rendimiento_cantidad: int = 1
    unidad_rendimiento: str = "porcion"
    product_id_vinculado: str = ""
    notas: str = ""


@dataclass
class Componente:
    parent_id: str = ""
    parent_type: str = ""  # receta | producto
    component_type: str = ""  # ingrediente | receta | producto | helado_base
    component_id: str = ""
    component_name: str = ""
    cantidad: float = 0.0
    unidad: str = ""
    merma_pct: float = 0.0
    notas: str = ""


@dataclass
class Producto:
    product_id: int = 0
    nombre_producto: str = ""
    categoria: str = ""
    subcategoria: str = ""
    tipo_producto: str = "producto"  # simple | receta | armado | combo
    precio_venta_actual: float = 0.0
    activo: bool = True
    notas: str = ""


@dataclass
class Combo:
    combo_id: str = ""
    combo_name: str = ""
    precio_venta: float = 0.0
    categoria: str = ""
    activo: bool = True
    notas: str = ""


@dataclass
class ComboItem:
    combo_id: str = ""
    product_id: int = 0
    product_name: str = ""
    cantidad: float = 1.0
    notas: str = ""


@dataclass
class Venta:
    fecha_hora: Optional[datetime] = None
    numero_pedido: int = 0
    codigo_venta: int = 0
    producto: str = ""
    producto_norm: str = ""
    cantidad: float = 0.0
    total: float = 0.0
    rubro: str = ""
    subrubro: str = ""
    area: str = ""
    sector: str = ""


@dataclass
class HistorialPrecio:
    fecha: Optional[date] = None
    ingredient_id: int = 0
    precio_anterior: float = 0.0
    precio_nuevo: float = 0.0
    origen: str = "manual"


REQUIRED_COLUMNS = {
    "ingredientes": [
        "ingredient_id", "ingrediente", "unidad_base", "costo_actual",
    ],
    "productos": [
        "product_id", "nombre_producto", "tipo_producto", "precio_venta_actual",
    ],
    "helado_compras": [
        "fecha", "sabor", "kilos", "importe_total",
    ],
    "ventas": [
        "fecha_hora", "numero_pedido", "producto", "cantidad", "total",
    ],
    "componentes": [
        "parent_id", "parent_type", "component_type", "component_id", "cantidad", "unidad",
    ],
    "combos": ["combo_id", "combo_name", "precio_venta"],
    "combo_items": ["combo_id", "product_id", "cantidad"],
}
