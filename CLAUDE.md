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
  **Con fechas a 14 meses Booking lista solo ~la mitad** (los que ya abrieron calendario; verificado 07/11
  con búsquedas sin fechas de 1 ítem: el actor informa "N properties found"). Universo sin fechas:
  El Bolsón 209, Lago Puelo 93, El Hoyo 33, Esquel 212, Trevelin 108, Epuyén 14, Cholila 14,
  Villa La Angostura 280, Bariloche 1.386 (`UNIVERSO_SIN_FECHAS` en `run_booking.py`).
  Sin fechas **no trae precio**: el precio de referencia sale solo de las corridas con fechas.
  Tenemos **834 alojamientos únicos**: zona tratada completa sin fechas (salvo El Bolsón: los 155 más
  cercanos de 209, y Trevelin: solo con fechas), Bariloche 136, Villa La Angostura 64, Dina Huapi 16.
  Para Make y la corrida semanal: usar fechas cercanas (≤ 3 meses) o no usar fechas.
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
  - Muestra MVP (07/11), 4 corridas (`reviews.json`, `reviews_bariloche.json`, `reviews_reintento.json`,
    `reviews_extra.json`): 42 alojamientos pedidos (33 a ≤40 km de un foco + 9 de Bariloche al azar)
    → 2.231 reviews únicas. Completos: 25 de 33 tratados y 5 de 9 de Bariloche
    (`python src/run_booking.py cobertura` regenera el estado desde los logs).
  - Corrida completa de la zona tratada: 352 alojamientos con ≥10 reviews a ≤40 km ≈ 11.800 reviews en la
    ventana ≈ **USD 23,6 en tier FREE** (USD 0,002/review). Recalculado el 07/11 con `alojamientos.csv`: 380 alojamientos, ≈ 13.700
    reviews en la ventana (≈ 70% del total de cada uno) ≈ **USD 27,5**, más ≈ USD 0,29 por cada control de Bariloche. Planificar créditos (una cuenta por integrante).
  - Cuentas de Apify: `APIFY_TOKEN` (cuenta 1) y `APIFY_TOKEN2` (cuenta 2, `--cuenta 2`). Gasto en
    `data/processed/apify_gastos.csv`: **el cobro se asienta minutos después de terminar la corrida**
    (se cobra cada ítem entregado); releer el run antes de dar por cerrado el gasto.
- `price` es el precio de HOY para una fecha futura: sirve como tarifa de referencia para el ROI, **nunca**
  como outcome del fuego.

### Make (07/11, detalle en `make/README.md`)
- Booking: escenario 6938238, inactivo y probado. Blueprint en `make/mvp_booking.json`.
- **FIRMS NRT diario:** escenario 6939387 (`humo_firms_nrt_diario`), **activo desde el 07/11**, *Daily 09:00* en hora de Argentina
  (2 créditos de Make por día sin focos).
  Flujo Tools (variables; la MAP_KEY solo ahí) → HTTP (ayer, 1 día) → filtro "hay datos" → Parse CSV →
  filtro confianza ≠ `l` → Add a Row en `focos_nrt`, con `alerta_40km` (SI/NO, equirrectangular a ≤ 40 km de
  las 10 localidades). Blueprint en `make/mvp_firms_nrt.json`, sin MAP_KEY ni conexión.
- **Parse CSV de Make:** las claves internas son `col1…colN` aunque la UI muestre los encabezados. Mapear
  `{{3.col1}}`, no `{{3.latitude}}`.
- Un día sin focos: FIRMS devuelve solo el encabezado y Parse CSV falla. Por eso está el filtro "hay datos"
  (verificado 07/11: termina sin error y sin filas).

### Reformulación Comarca de los Alerces 2025 (07/11, a partir de la devolución de la profesora; EN CURSO)
- Fuentes nuevas: FIRMS + Google Maps vía Apify (`compass/crawler-google-places` para el catálogo y
  `compass/google-maps-reviews-scraper` para las reseñas por Place ID). Booking queda como antecedente.
  Esto reemplaza la regla "ni Google Maps" de la consigna original. Plan: `docs/plan_reformulacion_alerces.md`;
  reglas del test: **`docs/preregistro_alerces.md`** (commiteado antes de bajar reseñas).
- Episodio FIRMS: 16/02–01/03/2025 (eventos 26 en el PN Los Alerces y 25 al sur-sudeste de Esquel). Esquel queda
  a 14,3 km, Trevelin a 12,0 y Villa Futalaufquen a 1,5. Comparación: Villa La Angostura (principal),
  San Martín de los Andes (secundaria: fuego del Lanín a 59 km) y Corcovado. `src/exposicion_alerces.py`.
- Precios FREE verificados 07/11: catálogo USD 0,004 por ficha y reseñas USD 0,0006 cada una. Todavía no se
  corrió ningún actor de Maps.
- Piloto de Maps: `src/run_maps.py` (catalogo → seleccion → resenas → diagnostico), con el control de gasto de
  `run_booking.py`. Cuenta 3 (`APIFY_TOKEN3`, FREE, USD 5 desde el 07/11). Catálogo ≈ USD 1,44 y reseñas ≤ USD 3.
- **Piloto de Maps hecho (07/11):** 314 fichas en el catálogo (USD 1,29) y 14 fichas con 3.136 reseñas (USD 1,88).
  `publishedAtDate` exacta; `reviewOrigin` = Google; `visitedIn` vacío. Mediana de 1 reseña por ficha y semana.
  ≈ 18% de las reseñas totales son de mar-2024 en adelante. Efecto mínimo detectable a una cola ≈ −28% con
  120 + 60 fichas (optimista). Reglas fijadas en el pre-registro §6.
- **Muestra completa (preparada, sin correr):** `run_maps.py --cuentas … catalogo --completo` (≈ USD 6,40) → `muestra`
  (≥ 50 reseñas totales) → `resenas --completa` (desde 2023-07-31, máximo 1.000; ≈ USD 18–25).
  Hacen falta ≈ USD 22–27 (5–6 cuentas FREE) y subir `TOPE_USD_TOTAL`. Elegibilidad final: ≥ 6 reseñas previas.
- **Apilar episodios (verificado 07/11):** 2024 (26/01–07/02), 2025 (16/02–01/03) y 2026 (07/01–02/02), con la misma
  regla. Villa La Angostura, San Martín y Corcovado están limpias en los tres; Bariloche en 2024 y 2026. Esquel
  está a 24,8 km en 2026 (otra vez en el límite). Costo extra ≈ USD 5–6 (solo 2024 necesita reseñas desde 2023-07-28).
  Plan §9. **Adoptado en el pre-registro v2 (§8) como análisis secundario**; el principal sigue siendo 2025.
  La muestra completa baja desde 2023-07-31.
- FIRMS: se descartan `type` 1/2 (volcán Villarrica en el bbox norte). Crudos nuevos: `firms_crudo_sp_huecos.csv`
  y `firms_crudo_sp_norte.csv`.

## Decisiones de diseño (no cambiar sin discutirlo con el grupo)

1. **Fecha de estadía, no fecha de publicación** de la review, para fechar el efecto.
2. **Outcome principal: volumen de reviews por alojamiento × mes de estadía** (proxy de ocupación:
   quien cancela no deja review). Outcome secundario: nota media y % de menciones a
   `humo|incendio|fuego|ceniza`.
3. **Tratamiento por distancia calculada** (haversine al foco más cercano de cada temporada), no por
   nombre de localidad. Bandas: 0–15, 15–40, 40–80, más de 80 km. Tratado = 15 km o menos.
4. **Meses de fuego:** 2025-02 (Mallín Ahogado) y 2026-01, 2026-02 (Chubut). Si se usa la ventana larga
   (desde nov-2023): también 2024-02 (PN Los Alerces, desde el 26/01/2024; solo febrero, igual que Mallín Ahogado,
   porque los dos empezaron a fines de enero). Decidido el 07/11.
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
- **Dataset 2 (Booking):** `alojamientos.csv` = 834 filas × 16 col (cumple 700–2.000; `precio_ref` nulo en
  los que vienen de búsquedas sin fechas). Alternativa/complemento: `reviews_dataset.csv` = 1 fila por review
  en la ventana nov-2024 a abr-2026, con coordenadas y distancia → 1.789 filas × 13 col, sin nulos.

### Primer número y chequeos (MVP 07/11, sin truncados; `sheets/kpi_did.csv` los reúne)
- DiD 2×2 apilado (IC95% bootstrap por alojamiento): volumen β = −2,25 (−35%), IC [−4,28; −0,42];
  nota β = −0,53, IC [−1,09; −0,01].
- **Placebo (fuego falso en el mes previo): volumen β = +2,43, IC [+0,67; +4,52] → el 2×2 NO es creíble:**
  cerca y lejos tienen estacionalidad distinta (pico de enero más fuerte cerca). Sin Bariloche: −1,54, IC toca 0.
- **FE alojamiento × mes calendario + año-mes (decisión 5, `src/fe_preliminar.py`, preliminar):**
  volumen −10% (IC −53% a +71%), nota −0,11 (IC −0,55 a +0,33). **Con 29 alojamientos no se detecta efecto.**
  Es el número a mostrar con su IC, no el del 2×2. Hace falta la corrida completa de reviews.

### Análisis secundarios (07/11, `src/analisis_secundario.py`; mismos FE, PRELIMINAR)
- Panel con outcomes nuevos: `noches_total` (noches asociadas a reviews, NO pernoctaciones), `noches_media`,
  `pct_familia`, `pct_pareja`, `pct_grupo`, `pct_solo`.
- Duración: noches −14% [−61%, +87%]; noches por review +0,17 [−0,38; +0,71] → sin señal de viajes más cortos.
- Tipo de viajero: sin cambios detectables (familias −3,4 pp, parejas +3,9 pp; IC incluyen 0).
- **Desplazamiento:** contra la banda 15–40 km, los lejanos (> 40 km, Bariloche) dan +253% [−11%, +1.293%] en
  meses de fuego y el efecto "cerca" pasa a +25%. Compatible con control lejano inflado por turistas desplazados;
  con solo 4 alojamientos lejanos. Producto 2: muestra de control más grande y banda 15–40 como control alternativo.
- Texto: con el patrón corregido (sin chimenea/leña/fireplace) hay 1 mención al incendio en 1.481 reviews →
  `pct_humo` es descriptivo, no outcome (quien cancela no deja review).

### Efecto mínimo detectable (07/11, `src/potencia.py`, simulado; detalle en `docs/decisiones_abiertas.md` §3)
- Bootstrap estratificado de los 29 alojamientos del panel, reescalado al universo de 380 cercanos
  (≥ 10 reviews, ≤ 40 km), descontando truncados. MDE volumen al 80% de potencia:
  ≈ USD 10 → −36/−44%, ≈ USD 20 → −27/−33%, universo cercano + 30 de control (≈ USD 36–42) → −20/−25%.
- Los controles lejanos casi no suman (30 alcanzan). **El Bolsón es "cerca" en las dos temporadas:** con FE
  alojamiento × mes calendario solo identifica enero. Extender la ventana a nov-2023 lo resolvería (no medido).
- **FIRMS 2023-24 (verificado 07/11, `firms_backfill.py --periodos 2023-11-01:2024-04-30`):** incendio en el PN Los
  Alerces del 26/01 al 07/02/2024 (637 detecciones, ≈ 22 km de Esquel). La ventana larga no es control limpio
  para Esquel; para El Bolsón sí (≈ 96 km). Salidas en `data/processed/firms_2024/`.
- Piloto listo y no corrido: `run_booking.py ventana-larga` (22 alojamientos, ≈ USD 2,95) → `src/piloto_ventana.py`.
  El tope acumulado de gasto ahora se lee de `TOPE_USD_TOTAL` en `.env`; sin esa variable sigue en USD 10, y ya
  hay USD 9,86 gastados.

### Sensibilidad de Esquel y del umbral (07/11, `src/sensibilidad_esquel.py`, PRELIMINAR; memo §4)
- En 2025 Esquel está a 14,2 ± 0,9 km del foco: su estado de tratado depende del umbral de 15 km. En 2026 es
  control (15–40 km), pero el PN Los Alerces estuvo cerrado parte de la temporada. Con 15 km, El Bolsón queda
  tratado en las dos temporadas.
- Volumen: base −10% [−53, +71]; sin Esquel −55% [−86, +43]; umbral 10 km −49% [−63, −31]; umbral 12 km −40%
  [−61, −9]. Los placebos de volumen incluyen 0. Son 12 tratados y 7 variantes probadas: no es un resultado.
- **Se mantiene 15 km como referencia** (decisión 3). 10 y 12 km se presentan como exposición más localizada,
  no como resultado principal: a 10 km, 11 de 12 tratados son de El Bolsón, y el radio se eligió después de ver
  las variantes (la corrida completa lo vuelve a estimar, no lo valida). Si el grupo quiere 10 km como principal,
  tiene que formular esa pregunta más acotada y justificar el radio por el tipo de exposición.
  Borradores de mails a Parques y a la profesora en `docs/borradores_mails.md` (no enviados).

### Preguntas abiertas para el grupo (no se cambió nada; memo con evidencia: `docs/decisiones_abiertas.md`)
- Temporada 2025: hubo fuego en Epuyén del 15 al 30/01/2025 (evento 5) y en Esquel/Trevelin en feb-2025, pero
  los meses de fuego 2025 son solo 2025-02. ¿Agregar 2025-01 para Epuyén, o tratar a Chubut 2025 como contaminado?
- ¿Qué dataset de Booking presentamos como "Dataset 2": alojamientos (834) o reviews (1.789)? Ambos cumplen.

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
python src/run_booking.py --cuenta 2 listings --solo esquel --sin-fechas --dry-run   # universo completo, sin precio
python src/run_booking.py --cuenta 2 reviews --grupos control_bariloche --n-bariloche 50 --presupuesto 2 --salida reviews_x.json --dry-run
# Veredicto, panel, DiD, CSV para Sheets
python booking_pilot_check.py --listings "data/raw/listings_*.json" --reviews "data/raw/reviews*.json" --firms data/processed/firms_detecciones_eventos50.csv
python src/build_panel.py --listings "data/raw/listings_*.json" --reviews "data/raw/reviews*.json" --firms data/processed/firms_detecciones_eventos50.csv
python src/run_booking.py cobertura          # estado por alojamiento desde los logs (antes de build_panel)
python src/did_baseline.py                   # baseline 2x2 + placebo + sin Bariloche
python src/fe_preliminar.py                  # FE alojamiento x mes calendario (preliminar)
python src/analisis_secundario.py            # duración, tipo de viajero y desplazamiento (preliminar)
python src/potencia.py                       # efecto mínimo detectable según N y costo (≈ 10 min)
python src/sensibilidad_esquel.py             # Esquel y umbral de distancia, con placebos (preliminar)
python src/exposicion_alerces.py              # episodio 2025, ventanas por localidad, comparación y figuras
python src/run_maps.py --cuenta 3 catalogo --dry-run   # piloto Maps: catalogo → seleccion → resenas → diagnostico
python src/potencia_maps.py                   # efecto mínimo detectable con la varianza del piloto (solo período previo)
python src/run_booking.py --cuenta 1 ventana-larga --dry-run   # piloto de ventana larga (nov-2023)
python src/piloto_ventana.py --reviews data/raw/ventana_larga/reviews_desde_2023-11.json
python src/export_sheets.py
```

Nota: la consola de Windows usa cp1252; si un script falla al imprimir "→" o "≥", usar
`PYTHONIOENCODING=utf-8`.
