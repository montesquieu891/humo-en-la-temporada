# Dashboard del MVP (Data Studio, ex Looker Studio)

**Informe:** [humo_mvp – dashboard](https://datastudio.google.com/reporting/61d5af90-8504-4775-a59d-e0ce64bfe20a).
Es privado de la cuenta dueña de `humo_mvp` hasta que se comparta (*Compartir*). Se armó el 07/11/2026.

## Fuentes de datos
Las cuatro salen de la Google Sheet `humo_mvp`, que se carga con `data/processed/sheets/humo_mvp.xlsx` y se
regenera con `python src/export_sheets.py`: `panel`, `focos`, `alojamientos` y `kpi_did`.

Campos agregados en Data Studio (no están en la Sheet):
- `ubicacion = CONCAT(lat, ",", lng)`, de tipo **Geo → Latitud, longitud**, en `alojamientos` y en `focos`.
  Sin ese campo, el mapa geocodifica `aloj_id` (la URL) y pone puntos en cualquier parte del mundo.

## Página 1: impacto
| Bloque | Fuente | Configuración |
|---|---|---|
| Nota | — | Meses de fuego (feb-2025; ene–feb 2026) y lectura del KPI |
| Serie temporal | `panel` | Dimensión `mes` como **Año y mes**; métrica `n_reviews` como **Media** ("Reviews por alojamiento-mes"); desglose `banda` |
| Tabla precio/rating | `alojamientos` | Dimensión `localidad`; `precio_ref` como **Mediana** (USD por 2 noches) y `rating` como **Media**; filtro "Con reviews" (`n_reviews_total > 0`) para que los rating 0 no bajen la media |
| KPI | `kpi_did` | Dimensiones `temporada`, `outcome`, `especificacion`; métricas `ic95_hi`, `beta`, `ic95_lo`. Muestra las cuatro especificaciones, no solo el 2×2 |

## Página 2: mapas
| Bloque | Fuente | Configuración |
|---|---|---|
| Alojamientos | `alojamientos` | Mapa de burbujas de Google Maps; ubicación `ubicacion`; color `banda_2026`; texto emergente `nombre` |
| Focos FIRMS | `focos` | Ubicación `ubicacion`; color `temporada` (2025 / 2026); tamaño `frp_total_mw` |

## Verificado contra el notebook (07/11)
- Serie: el pico de la banda >80 km en ene-2026 (≈ 17,8 reviews por alojamiento-mes) coincide con `notebooks/01_eda_mvp.ipynb`.
- Precio mediano de Bariloche: 237,56 USD por 2 noches (≈ 119 por noche), igual que en el notebook.

## Pendiente
- Renombrar las páginas ("Página sin título") y unificar los colores de banda con la rampa del notebook.
- El orden de las columnas del KPI quedó ic95_hi · beta · ic95_lo: Data Studio inserta las métricas arriba.
- Compartir el informe con el grupo y los tutores (*Compartir → Agregar personas*).
