# CLAUDE.md — Humo en la temporada

Capstone grupal (3 personas) del Samsung Innovation Campus 2026. Este archivo da contexto a cualquier
sesión de Claude que trabaje en este repo. Leerlo entero antes de tocar código.

## Qué es el proyecto

Medir cuánto pierde un alojamiento turístico de la Comarca Andina / Bariloche / Esquel por estar cerca
de un incendio forestal, para que una cámara hotelera pueda reclamar, comunicar y fijar precios.

- **Cliente:** cámara hotelera o Secretaría de Turismo (El Bolsón, Lago Puelo, Esquel, Bariloche).
- **Pregunta integrada:** ¿cuánto caen la demanda (volumen de reviews) y la nota de un alojamiento
  según su distancia al fuego, durante los meses de fuego?
- **Dos shocks:** Mallín Ahogado (desde el 30/01/2025, cerca de El Bolsón, 3.825 ha) y Chubut cordillerano
  (desde el 05/01/2026: Puerto Patriada/El Hoyo → Epuyén → Cholila → PN Los Alerces, más de 50.000 ha).
  Cada zona es tratada en un año y control en el otro. Bariloche es el control limpio en ambos.

## Consigna (no negociable)

- **Dos datasets, dos fenómenos distintos**, máximo 2 fuentes en total:
  1. NASA FIRMS (focos de calor) → fenómeno: incendios forestales.
  2. Booking vía Apify (alojamientos + reviews) → fenómeno: oferta y reputación turística.
- Cada dataset entre **700 y 2.000 registros**, **≈10 features** comprensibles, pocos nulos, con coordenadas.
- Flujo: extracción → **Make** (ETL, EDA, dashboard) → modelo con baseline, métrica técnica y de negocio
  → **Actor publicado en Apify Store** + repo GitHub + presentación con costos y ROI.
- **No agregar una tercera fuente** (ni SMN, ni Google Maps, ni Airbnb). Polígonos o tablas de referencia
  geográfica no cuentan como fuente, pero hay que justificarlo.

## Fechas

| Fecha | Entrega |
|---|---|
| 07/11 | MVP interno (ver IMPLEMENTATION.md) |
| 12/11 | Producto 1: ETL + EDA + dashboard automatizado con Make |
| 20/11 | Producto 2: modelo integrado al flujo |
| 24/11 | Final: Actor en Apify Store, repo, presentación con ROI |

## Datos

### FIRMS (`firms_backfill.py`)
- API: `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{bbox}/{días}/{fecha}`.
- **Máximo 5 días por llamada** (verificado 06/11/2026: la API responde "Invalid day range. Expects [1..5]";
  `firms_backfill.py --dias 5`). Fuente `VIIRS_SNPP_SP` para histórico: **ya cubre ene–feb 2026** (verificado).
- Bbox (oeste, sur, este, norte): `-72.3,-43.4,-70.8,-40.8`.
- Columnas: `latitude, longitude, bright_ti4, frp, acq_date, acq_time, confidence, daynight, scan, track`.
- `confidence` de VIIRS es `l/n/h`: quedarse con `n` y `h`.
- Eventos: DBSCAN en (x km, y km, t) con eps 2 km ≈ 3 días, `min_samples=3`. `evento = -1` es ruido.
- Si quedan más de 2.000 detecciones, la unidad pasa a celda × día (`firms_celda_dia.csv`).
- **Corrida real (06/11/2026, SP, `--dias 5`):** 12.843 detecciones crudas → 12.089 con confianza n/h →
  12.010 en 61 eventos (3.338 en temporada 2025, 8.672 en 2026), 79 de ruido. Hizo falta `firms_celda_dia.csv`:
  **2.189 filas** (pasa el tope de 2.000 → recortar en el panel). Salidas en `data/processed/firms_*`.
  - Mallín Ahogado = evento 15 (desde 31/01/2025 05:53 UTC, centro -41,88 / -71,58, 308 detecciones).
  - Chubut 2026 = eventos 31 (Cholila / Los Alerces, desde 04/01, 3.876 det.), 33 (Pto. Patriada / Epuyén,
    desde 05/01, 1.959 det.) y 35 (Epuyén, desde 15/01, 1.241 det.).
  - **Ojo (verificado):** en 2025 también hubo fuego en Epuyén (15–30/01/2025, evento 5), Esquel/Trevelin
    (feb-2025, eventos 25–26) y PN Nahuel Huapi (dic-2024 a feb-2025, ~46–50 km de Bariloche). Hay
    eventos de 3–5 detecciones a ~5 km del centro de Bariloche (dic-2024): `firms_detecciones_eventos50.csv`
    deja solo los 20 eventos con ≥50 detecciones (se usó para elegir la muestra de reviews).

### Booking (Apify)
- **Precios reales (verificados vía API el 06/11/2026), pay-per-event:** en el plan FREE se pagan
  USD 0,005 por alojamiento y USD 0,002 por review (los "USD 2/1.000" son del tier GOLD). **La cuenta del
  grupo es FREE: USD 5/mes, el ciclo se renueva el 13/11.** Correr todo con `src/run_booking.py`
  (valida el input contra el schema, estima, aplica `max_total_charge_usd` y anota en `data/processed/apify_gastos.csv`).
- `voyager/booking-scraper`: campos `name, type, stars, price, currency, rating, reviews, address.full,
  address.city, location.lat, location.lng, url, hotelId`. **`location.lat/lng` vienen como texto.**
  `stars` es casi todo nulo (98%). `price` es por la estadía completa (2 noches). Necesita `checkIn/checkOut`.
  **La búsqueda se limita a la ciudad** ("Lago Puelo" no trae El Hoyo): una corrida por localidad.
  Universo real en Booking (07/11): El Bolsón 103, Lago Puelo 41, El Hoyo 23, Esquel 98, Epuyén 6,
  Cholila 9, Trevelin 59; Bariloche truncado en 120 → **459 alojamientos únicos** (consigna: ≥700).
- `voyager/booking-reviews-scraper`: texto, rating, partes "gustó/no gustó", habitación, duración y
  **fecha de estadía (por mes)**. Los nombres exactos de campo se confirman en el piloto: anotarlos acá.
  - Campo fecha de estadía: **`checkInDate`** (verificado 07/11: fecha exacta `YYYY-MM-DD`, no solo el mes;
    100% presente). También vienen `checkOutDate`, `numberOfNights` y `reviewDate` (publicación, ISO UTC;
    rezago mediano 2 días tras el checkout, p95 31 días).
  - Campo URL/ID del alojamiento en la review: **`startUrl`** (= la URL de input, con query; se normaliza
    quitando `?…`). También `hotelId` (numérico, coincide con `hotelId` de listings) y `customData.aloj_url`
    (lo agrega `run_booking.py` vía `userData`).
  - Otros campos: `rating` (1–10), `likedText`, `dislikedText`, `reviewTitle`, `travelerType`, `roomInfo`,
    `reviewLanguage` (`xa/xu/xb` = sin texto), `hotelReviews`, `hotelRating`. Páginas de 25 reviews.
  - Input usado: `sortReviewsBy=f_recent_desc` + `cutoffDate=2024-11-01` (el orden es monótono: verificado).
  - `checkInDate = 1999-12-26` es un **centinela de fecha faltante** (~1%): `a_mes` lo trata como nulo.
  - **Falla del actor (verificado en los logs, 07/11):** para algunos alojamientos Booking devuelve
    "No reviews found for the provided property" en la 1ª página (queda sin reviews) o a mitad de la
    paginación (queda truncado), con bloqueos 202 en el log. Reintentar solo los que no devolvieron nada
    recupera parte; los truncados repiten la falla tras la página 1. Estado por alojamiento en
    `data/processed/reviews_cobertura.csv` (completo / truncado_falla_actor / truncado_tope / sin_reviews).
  - Muestra MVP (07/11), 3 corridas (`reviews.json`, `reviews_bariloche.json`, `reviews_reintento.json`):
    37 alojamientos pedidos (28 a ≤40 km de un foco + 9 de Bariloche al azar) → 2.062 reviews únicas.
    Completos: 21 de 28 tratados y 5 de 9 de Bariloche.
  - Cuentas de Apify: `APIFY_TOKEN` (cuenta 1) y `APIFY_TOKEN2` (cuenta 2, `--cuenta 2`). Gasto en
    `data/processed/apify_gastos.csv`: **el cobro se asienta minutos después de terminar la corrida**
    (se cobra cada ítem entregado); releer el run antes de dar por cerrado el gasto.
- `price` es el precio de HOY para una fecha futura: sirve como tarifa de referencia para el ROI, **nunca**
  como outcome del fuego.

## Decisiones de diseño (no cambiar sin discutirlo con el grupo)

1. **Fecha de estadía, no fecha de publicación** de la review, para fechar el efecto.
2. **Outcome principal: volumen de reviews por alojamiento × mes de estadía** (proxy de ocupación:
   quien cancela no deja review). Outcome secundario: nota media y % de menciones a
   `humo|incendio|fuego|ceniza`.
3. **Tratamiento por distancia calculada** (haversine al foco más cercano de cada temporada), no por
   nombre de localidad. Bandas: 0–15, 15–40, 40–80, más de 80 km. Tratado = 15 km o menos.
4. **Meses de fuego:** 2025-02 (Mallín Ahogado) y 2026-01, 2026-02 (Chubut).
5. **Estacionalidad:** efecto fijo alojamiento × mes calendario (compara contra el mismo mes del año sin fuego)
   + efecto fijo año-mes.
6. **Dos eventos → stacked DiD** (estimar cada evento por separado), no un TWFE único.
7. Errores clusterizados por alojamiento; wild bootstrap por localidad como robustez.
8. **Foco = detección de un evento FIRMS con ≥50 detecciones** (decidido el 07/11). Los clusters
   de 3–5 detecciones, como los del basural o quemas cerca de Bariloche, no cuentan. Archivo:
   `data/processed/firms_detecciones_eventos50.csv`.
9. **Se excluyen del panel los alojamientos con historia de reviews truncada** (falla del actor o tope
   por hotel, según `reviews_cobertura.csv`). Con ellos el β apilado de volumen pasa de −2,3 a −7,5,
   un salto falso. `build_panel.py --incluir-truncados` es la sensibilidad.

### Datasets de la consigna (07/11)
- **Dataset 1 (FIRMS):** `firms_celda_dia.csv` = celda de 0,025° × día, solo eventos ≥50 → 1.669 filas × 9 col.
- **Dataset 2 (Booking):** `reviews_dataset.csv` = 1 fila por review en la ventana nov-2024 a abr-2026,
  con coordenadas y distancia → 1.654 filas × 13 col, sin nulos. `alojamientos.csv` (459) es tabla auxiliar.
  Llegar a ≥700 alojamientos queda pendiente (Villa La Angostura + más Bariloche, ≈ USD 1,5–2).

### Primer número (MVP 07/11, DiD 2×2, sin truncados, IC95% bootstrap por alojamiento)
- Volumen apilado: β = −2,28 reviews por alojamiento-mes (−35% contra el contrafactual), IC [−4,72; −0,12].
- Nota apilada: β = −0,58, IC [−1,24; +0,01]. Por temporada, ningún β de volumen excluye el 0.
- Muestra chica (47 alojamientos en el apilado, 5–6 "lejos" en 2025): es un primer número, no un resultado.

## Modelo

- Baseline: DiD 2×2 (cerca vs. lejos, antes vs. durante).
- Principal: `pyfixest` — `feols` para la nota con bandas, `fepois` para el volumen, event study con `i(rel_t, cerca, ref=-1)`.
- Predictivo (para el Actor): gradient boosting que predice la caída % de reviews según distancia, FRP
  acumulado, duración, tipo, estrellas, precio y rating previo. Baseline = caída media de la banda.
  Métrica: MAE con validación dejando fuera una localidad. SHAP para explicar.

## Estructura del repo

```
humo/
  CLAUDE.md               este archivo
  IMPLEMENTATION.md       lista de tareas hacia el MVP y las entregas
  README.md               pasos de la prueba de factibilidad
  firms_backfill.py       descarga + limpieza + eventos FIRMS
  booking_pilot_check.py  veredicto de la prueba de factibilidad
  data/raw/               exports crudos (FIRMS CSV, JSON de Apify) — no se versionan
  data/processed/         CSV limpios y panel
  src/                    build_panel.py, did_baseline.py, etc.
  notebooks/              EDA
  make/                   blueprints exportados de Make (JSON)
```

## Convenciones

- Python 3.11+, pandas 3 (**las columnas de texto ya no son `object`**: usar
  `pd.api.types.is_numeric_dtype` en vez de comparar dtypes).
- Distancias siempre en km con haversine (radio 6.371 km). Coordenadas en grados decimales, WGS84.
- Fechas en ISO (`YYYY-MM-DD`); meses de estadía como `YYYY-MM`.
- Nombres de columnas en snake_case y en castellano para lo derivado (`dist_2026_km`, `mes_estadia`).
- Secretos (MAP_KEY, token de Apify) en `.env`, nunca en el código ni en el repo.
- Marcar en comentarios y en la presentación qué es verificado y qué es supuesto.

## Comandos

```bash
pip install -r requirements.txt
# FIRMS (FIRMS_KEY en .env). Si ya está el crudo: --desde-csv data/raw/firms_crudo_sp.csv
python firms_backfill.py --dias 5 --raw data/raw/firms_crudo_sp.csv --salida data/processed/firms
# Booking (APIFY_TOKEN / APIFY_TOKEN2 en .env). Siempre primero --dry-run para ver el costo
python src/run_booking.py --cuenta 2 cuenta
python src/run_booking.py --cuenta 2 listings --solo esquel --dry-run
python src/run_booking.py --cuenta 2 reviews --grupos control_bariloche --n-bariloche 50 --presupuesto 2 --salida reviews_x.json --dry-run
# Veredicto, panel, DiD, CSV para Sheets
python booking_pilot_check.py --listings "data/raw/listings_*.json" --reviews "data/raw/reviews*.json" --firms data/processed/firms_detecciones_eventos50.csv
python src/build_panel.py --listings "data/raw/listings_*.json" --reviews "data/raw/reviews*.json" --firms data/processed/firms_detecciones_eventos50.csv
python src/did_baseline.py
python src/export_sheets.py
```

Nota: la consola de Windows usa cp1252; si un script falla al imprimir "→" o "≥", usar
`PYTHONIOENCODING=utf-8`.
