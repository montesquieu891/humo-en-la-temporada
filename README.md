# Humo en la temporada — prueba de factibilidad

Objetivo: decidir antes del **9/11** si seguimos con el proyecto. Costo total: menos de USD 5.
Plan completo: documento "Humo en la temporada — plan de implementación".

## 0. Requisitos (una sola vez)

```bash
pip install pandas numpy scikit-learn requests
```

- **MAP_KEY de FIRMS** (gratis, llega por mail): https://firms.modaps.eosdis.nasa.gov/api/map_key/
- **Cuenta de Apify** (el plan Free trae USD 5 de crédito por mes, alcanza para el piloto).

## 1. Focos de calor (FIRMS) — 5 minutos

```bash
python firms_backfill.py --key TU_MAP_KEY
```

- Baja VIIRS (S-NPP, procesamiento estándar) de dic. 2024–mar. 2025 y dic. 2025–mar. 2026 en el bbox de la Comarca.
- Si devuelve 0 detecciones para 2026, el procesamiento estándar todavía no llegó: repetir con `--source VIIRS_SNPP_NRT`.
- Genera `firms_detecciones.csv` (con columna `evento`), `firms_eventos.csv` y, si hay más de 2.000 filas, `firms_celda_dia.csv`.
- **Qué mirar:** que aparezcan dos eventos grandes, uno desde el 30/01/2025 cerca de El Bolsón (Mallín Ahogado) y otro desde el 05/01/2026 en Chubut (Puerto Patriada, Epuyén, Cholila).

## 2. Alojamientos (Apify `voyager/booking-scraper`) — 10 minutos

En la consola de Apify, una corrida por destino:

| Destino | Check-in / check-out |
|---|---|
| El Bolsón, Río Negro | 15/01/2027 – 17/01/2027 |
| Lago Puelo, Chubut (incluye El Hoyo) | idem |

- Para el piloto alcanza con estos dos (zona tratada). Bariloche y Esquel se suman en la corrida completa.
- Exportar el dataset como **JSON** y unir los dos archivos en `listings.json` (o pasar uno por vez).

## 3. Reviews (Apify `voyager/booking-reviews-scraper`) — 10 minutos

- Elegir **30 alojamientos al azar** entre los que tienen 10 o más reviews (al azar, no los 30 más reseñados: así la extrapolación es honesta; el script igual pondera por reviews).
- Pegar sus URLs como input, sin límite de fecha, ordenadas por más recientes.
- Exportar como **JSON** → `reviews.json`.

## 4. Veredicto

```bash
python booking_pilot_check.py --listings listings.json --reviews reviews.json --firms firms_detecciones.csv
```

El script:

1. calcula la distancia de cada alojamiento al foco más cercano de cada temporada (tratado = 15 km o menos),
2. cuenta reviews con mes de estadía en los meses de fuego (feb. 2025; ene.–feb. 2026),
3. extrapola al universo y aplica los criterios de descarte del plan:
   - 300 o más reviews en zona tratada durante los meses de fuego, y
   - 70% o más de reviews con fecha de estadía.

Si el actor nombra distinto los campos, el script lista las columnas y pide el nombre correcto:

```bash
python booking_pilot_check.py ... --stay-field NOMBRE --hotel-field NOMBRE --listing-id-field NOMBRE
```

## Qué traer a la próxima reunión

- La salida de los dos scripts (copiar y pegar).
- `firms_eventos.csv`.
- Los nombres reales de los campos de fecha de estadía y de URL en el JSON de reviews.
