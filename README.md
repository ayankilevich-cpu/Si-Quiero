# Si Quiero — Sistema de Gestion de Costos

Aplicacion Streamlit para gestionar la estructura de costos, rentabilidad y simulacion de margenes de la cafeteria/heladeria **Si Quiero**.

## Requisitos

- Python 3.10+
- Las dependencias listadas en `requirements.txt`

## Instalacion local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy en Streamlit Cloud

1. Subir el repositorio a GitHub (publico o privado).
2. Ir a [share.streamlit.io](https://share.streamlit.io) e iniciar sesion con GitHub.
3. Hacer clic en **New app** y seleccionar el repositorio.
4. Configurar:
   - **Branch**: `main`
   - **Main file path**: `app.py`
5. Hacer clic en **Deploy**.

La app detecta automaticamente `requirements.txt` e instala las dependencias.

> **Nota sobre persistencia**: Streamlit Cloud usa un filesystem efimero.
> Los cambios realizados desde la app (actualizar precios, agregar recetas, etc.)
> se mantienen mientras la app este activa, pero se pierden si el servidor se
> reinicia o se redespliega. Para uso productivo con persistencia, considerar
> migrar a una base de datos en la nube (Supabase, PlanetScale, etc.).

## Estructura del proyecto

```
Si_Quiero/
├── app.py                        # Punto de entrada
├── config.py                     # Configuracion global
├── requirements.txt
├── .streamlit/
│   └── config.toml               # Tema y config de Streamlit
├── data/
│   └── si_quiero.db              # Base de datos SQLite
├── views/                        # Paginas de la app
│   ├── p01_dashboard.py
│   ├── p02_ingredientes.py
│   ├── p03_remitos_helado.py
│   ├── p04_recetas.py
│   ├── p05_productos.py
│   ├── p06_rentabilidad_productos.py
│   ├── p07_rentabilidad_combos.py
│   ├── p08_simulador.py
│   └── p09_ingenieria_menu.py
├── services/                     # Logica de negocio
│   ├── cost_engine.py
│   ├── data_loader.py
│   ├── db_manager.py
│   ├── icecream_cost_service.py
│   ├── price_update_service.py
│   └── alert_service.py
├── models/
│   └── schemas.py
├── utils/
│   ├── helpers.py
│   ├── validators.py
│   ├── pdf_parser.py
│   └── excel_templates.py
└── templates/                    # Plantillas Excel para importacion
```

## Modulos

| Modulo | Descripcion |
|--------|-------------|
| Dashboard | KPIs, facturacion por categoria, rankings de ventas y margen |
| Ingredientes | Gestion de ingredientes, edicion de costos, historial |
| Remitos helado | Carga de remitos, costo ponderado del helado |
| Recetas | Gestion de recetas propias (tortas, cafeteria), import Excel |
| Productos | Fichas de costeo detalladas de productos elaborados |
| Rentabilidad productos | Tabla con margenes, food cost, filtros y semaforo |
| Rentabilidad combos | Desglose por combo, descuento implicito |
| Simulador | Simulacion de cambios de costos y su impacto |
| Ingenieria de menu | Clasificacion BCG: Estrella, Caballo, Rompecabezas, Perro |

## Base de datos

La app usa SQLite como backend (`data/si_quiero.db`). La capa de datos
(`DataLoader`) abstrae el acceso: todos los servicios y vistas trabajan
con DataFrames de Pandas, lo que facilita una futura migracion a
PostgreSQL u otra base.
