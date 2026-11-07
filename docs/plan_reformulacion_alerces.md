# Plan de reformulación: Comarca de los Alerces, 2025 (borrador, 07/11/2026)

Surge de la devolución de la profesora. **No se corrió ningún actor ni se modificó el pipeline.** Todo lo que
dice "verificado" se comprobó hoy con los datos del repo, con la API pública de Apify o con los informes locales.
Lo que dice "supuesto" o "a verificar" depende del piloto.

## 1. Pregunta y test

> ¿Durante los episodios de incendio de 2025, cayó más el volumen de reseñas de Google en los lugares
> expuestos que en lugares comparables, del mismo rubro, observados en las mismas fechas?

- H₀: el cambio en el volumen de reseñas durante el episodio es igual en los grupos expuesto y de comparación.
- H₁: el volumen cae más en el grupo expuesto. Es una hipótesis a una cola, que hay que dejar escrita antes
  de ver los datos.
- **Qué mide:** reseñas por **fecha de publicación**, no visitas. Para noches vendidas o ingresos harían falta
  registros de los alojamientos.

**Fuentes del modelo:** NASA FIRMS y Google Maps vía Apify. Booking queda como antecedente del MVP. Los informes
de Esquel y la cronología de cierres se documentan aparte y se consulta a la profesora cómo encuadrarlos (§7).

## 2. Lo que ya muestran los datos (verificado hoy)

### FIRMS: el episodio de 2025 es corto y la región entera tuvo fuego
- **Cobertura SP (completada el 07/11):**
  - nov-2023 a mar-2026 en el bbox sur;
  - 2024–2025 en un bbox norte (−72,3, −40,8, −70,5, −39,4).

  En abr–nov 2025 **no hubo ningún evento ≥ 50** en el sur. Salidas en `data/processed/firms_alerces/`
  (`src/exposicion_alerces.py`).
- **Volcán Villarrica:** el bbox norte trae 229 detecciones de tipo 1 (volcán activo). DBSCAN las agrupaba como
  un "evento" de ene–mar 2024 y ahora se descartan.
- **Verificación de comparación** (eventos ≥ 50 a ≤ 40 km entre el 19/01 y el 29/03/2025):
  - **limpias:** Villa La Angostura (69 km), San Martín de los Andes (59 km) y Corcovado (52 km);
  - **descartada:** Junín de los Andes (37 km, 08–10/02).
  - **Hubo un incendio grande en el PN Lanín** (30/01–27/02/2025, 3.336 detecciones): San Martín de los Andes
    pasa la regla, pero queda como comparación secundaria.
- Figuras del EDA: `docs/figs/alerces_mapa_focos_2025.png` y `docs/figs/alerces_linea_tiempo.png`.
- Las reglas del test quedaron en `docs/preregistro_alerces.md`.
- En la Comarca de los Alerces, 2025 tuvo dos eventos con ≥ 50 detecciones:

| Evento | Fechas | Detecciones | Centro | Dónde |
|---|---|---|---|---|
| 26 | 20/02 – 01/03/2025 | 212 | −42,92 / −71,63 | PN Los Alerces, a 1,5 km de Villa Futalaufquen |
| 25 | 16/02 – 26/02/2025 | 211 | −43,05 / −71,24 | ≈ 16 km al sur-sudeste de Esquel |

  Hubo además eventos chicos (20 y 40 detecciones) el 23–26/02.
- **Distancia mínima a esos focos y días de exposición:**
  - Villa Futalaufquen: 1,5 km, 10 días a ≤ 15 km.
  - Trevelin: 12,0 km, 2 días a ≤ 15 km y 13 días a ≤ 25 km.
  - Esquel: 14,3 km, 4 días a ≤ 15 km y 11 días a ≤ 25 km.

  **Esquel vuelve a quedar justo en el límite de 15 km**, igual que en el MVP.
- **El episodio dura unas 2 semanas** (16/02 – 01/03): en una serie mensual solo afecta la mitad de febrero. El
  test necesita semanas, o al menos quincenas, y eso depende de la cobertura (§5).
- **No hay un año limpio para comparar en el mismo lugar.** Hubo fuego en Los Alerces el 26/01–07/02/2024 y en
  ene–feb 2026, que fue el evento grande (3.876 detecciones). Comparar febrero 2025 contra febrero de otro año
  es comparar fuego contra fuego. La comparación tiene que ser **entre lugares, en las mismas semanas de 2025**.
- **En febrero de 2025 casi toda la cordillera tuvo fuego cerca:** El Bolsón a 4,6 km (Mallín Ahogado), Epuyén
  a 2 km (enero), Bariloche a 42 km (PN Nahuel Huapi) y Cholila a 45 km. Sin foco en un radio amplio solo quedan
  Villa La Angostura (69 km), Corcovado (52 km, con poca oferta) y San Martín de los Andes (59 km; verificado
  después, ver arriba).
- **Consigna:** las detecciones de 2025 en la Comarca son ≈ 500, menos que el mínimo de 700. El Dataset 1 puede
  seguir siendo el FIRMS regional (celda × día, 1.669 filas), aunque el test use solo la Comarca.

### Apify: precios y campos (API pública, tier FREE)

| Actor | Evento | USD |
|---|---|---|
| `compass/crawler-google-places` | por ficha | 0,004 |
| | por cada filtro aplicado | +0,001 |
| | por pedir detalles de la ficha | +0,002 |
| `compass/google-maps-reviews-scraper` | por reseña | 0,0006 |

- Inputs útiles del scraper de reseñas: `placeIds`, `reviewsStartDate` (fecha absoluta, corta el historial),
  `reviewsSort=newest`, `reviewsOrigin` (`all` o `google`), `maxReviews` y `personalData=false`.
- **A verificar en el piloto:**
  - el nombre del campo que identifica el origen de cada reseña;
  - que la fecha de publicación venga exacta (ISO) y no relativa ("hace un año"), porque sin fecha exacta no se
    puede trabajar por semana;
  - si alguna ficha trae fecha de visita.

### Informes de Esquel
- **Anuario 2025:**
  - turistas por mes (por ejemplo, ene 13.883, feb 7.637, mar 7.934), ocupación y pernocte;
  - ingresos mensuales al PN Los Alerces (ene 42.690, feb 22.210, mar 9.709).
- **Informe semestral 2026:** turistas por mes (ene 10.653, feb 8.019) y ocupación por unidades funcionales
  (ene 45%, feb 38%).
- **No encontré** en la carpeta las pernoctaciones de enero y febrero de otras localidades de Chubut: ¿dónde están?

## 3. Qué se reutiliza

| Pieza | Para qué sirve ahora |
|---|---|
| `firms_backfill.py` (con `--periodos`) | bajar lo que falta de 2025 y las zonas de comparación, sin tocar el código |
| DBSCAN de eventos y regla de ≥ 50 detecciones (decisión 8) | definir episodios y ventanas por zona |
| Escenario diario de FIRMS NRT en Make | monitoreo y demostración; no aporta historia de 2025 |
| Escenario de Booking en Make (Run Actor → Dataset → Sheets) | plantilla para los dos actores de Maps |
| `run_booking.py`: validación contra el schema, estimación, `max_total_charge_usd`, `apify_gastos.csv`, varias cuentas | base de un `run_maps.py` con el mismo control de gasto |
| Haversine, armado de panel, placebos (`sensibilidad_esquel.py`), bootstrap de potencia (`potencia.py`) | se adaptan a lugar × semana |
| Google Sheet `humo_mvp` y dashboard de Data Studio | páginas nuevas: mapa, línea de tiempo, series |
| Booking: datos y resultados del MVP | antecedente, con sus lecciones: falla del actor por truncado, placebo que invalidó el 2×2, Esquel en el límite |

## 4. Qué falta conseguir

1. **FIRMS (gratis):** abr–nov 2025 en el bbox actual. Hay que ampliar el bbox al norte (hasta ≈ −39,5) para
   verificar Villa La Angostura, San Martín de los Andes y el PN Lanín entre dic-2024 y mar-2025.
2. **Catálogo de Google Maps** de la Comarca y de la zona de comparación (§6). Es el candidato a **Dataset 2**:
   700–2.000 fichas con coordenadas, rubro, rating y cantidad de reseñas.
3. **Reseñas** de una muestra fija por Place ID: primero el piloto (§5), después la muestra completa.
4. **Cronología de cierres y reaperturas** del PN Los Alerces en feb-2025, con fuente oficial, en una tabla aparte.
5. **Crédito y tope.** Las dos cuentas de Apify tienen ≈ USD 0,08. La cuenta 1 se renueva el 13/11, **un día
   después de la entrega del Producto 1**. El tope acumulado está en USD 9,86 de 10. Hace falta acordar un
   `TOPE_USD_TOTAL` o abrir una cuenta nueva si se quiere correr el piloto antes del 12/11.
6. **Aprobación de la profesora** de lo que se lista en §7.

## 5. Piloto de unas 15 fichas

**Objetivo:** verificar cobertura y formato, **no** estimar el efecto. No se mira la diferencia entre
expuestos y controles en feb-2025 hasta fijar el diseño.

**Paso A, catálogo mínimo** (≈ USD 1–1,5, tope duro 1,5):
- Búsquedas: hotel, cabañas, restaurante, camping, excursión lacustre y atractivo turístico.
- Lugares: Esquel, Trevelin, PN Los Alerces y Villa La Angostura.
- `maxCrawledPlacesPerSearch` = 15, sin detalles ni filtros (los filtros cobran extra) y sin saltear los
  cerrados (para no sesgar hacia los que sobrevivieron).

**Paso B, selección de las 15 fichas** (estratificada, con reglas fijadas antes de ver reseñas):

| Estrato | Fichas | Rubros |
|---|---|---|
| PN Los Alerces (exposición alta) | 5 | 2 campings, 1 excursión lacustre o puerto, 1 centro de informes o portada, 1 alojamiento dentro del parque |
| Esquel (exposición media, en el límite) | 4 | 2 alojamientos (hotel y cabañas), 2 gastronomía |
| Trevelin (exposición media) | 3 | 1 alojamiento, 1 gastronomía o casa de té, 1 atractivo |
| Villa La Angostura (comparación) | 3 | 1 alojamiento, 1 gastronomía, 1 camping o atractivo |

- En cada estrato, mezclar tamaños: entre 50 y 3.000 reseñas totales, con al menos una ficha grande y una
  mediana. Si hay más candidatas que cupos, elegir al azar con semilla fija.
- Excluir las fichas abiertas después de jun-2024 (no tienen período previo).

**Paso C, reseñas** (≈ USD 2–3, tope duro 3):
- `placeIds` = las 15, `reviewsOrigin=all` (para medir qué parte no es de Google), `reviewsStartDate=2024-01-01`,
  `reviewsSort=newest`, `personalData=false` y `maxReviews` = 800 como seguro.
- Una ficha que llega a 800 queda marcada como truncada, igual que en Booking.

**Costo total del piloto: tope de USD 4,5.**

**Qué responde el piloto (criterios para seguir):**
1. **Formato:** fecha de publicación exacta y un campo de origen que distinga Google de otros sitios. Si la fecha
   viene solo relativa, no hay análisis semanal.
2. **Profundidad:** que el historial llegue a ene-2024 sin cortarse, comparando lo devuelto con la cantidad de
   reseñas de la ficha.
3. **Cobertura:** reseñas de Google por ficha y por semana en ene–mar 2025.
   - Para trabajar por semana hace falta una mediana de ≥ 2 por semana por ficha en temporada alta, o agregar
     por grupo.
   - Si no alcanza, se trabaja por quincena o se suma por grupo y rubro.
4. **Origen:** qué parte de las reseñas no es de Google, por rubro. Las de otros sitios se descartan.
5. **Costo real por ficha**, para dimensionar la muestra completa.

## 6. Diseño del test

**Exposición** (solo con FIRMS, escrita y commiteada **antes** de bajar reseñas):
- Ventana del episodio: del primer al último día con detecciones de eventos ≥ 50 a ≤ R km de la ficha, más un
  margen de 7 días después (para el rezago de publicación).
- Niveles, a definir con distancias y no con resultados:
  - alta: ≤ 5 km de una detección del episodio, o dentro del sector del parque afectado;
  - media: 5–25 km (Esquel y Trevelin);
  - comparación: ningún foco ≥ 50 a menos de 40 km en la ventana ± 4 semanas.
- **Que Esquel quede en 14,3 km no se resuelve eligiendo el radio que mejor dé.** Se informan el nivel medio
  completo y la sensibilidad a 15 km, como en el MVP.
- Esta vez el pre-registro es real: los datos de Google de 2025 todavía no se vieron.

**Grupo de comparación** (mismo rubro, mismas semanas):
- Destinos de montaña y lagos sin fuego en la ventana: Villa La Angostura y, si FIRMS lo confirma, San Martín de
  los Andes y el PN Lanín. Ambos tienen campings, excursiones lacustres, gastronomía y cabañas comparables.
- Bariloche (fuego a 42 km) y la Comarca Andina (Mallín Ahogado) **no sirven como control** en esas semanas.
- Emparejamiento dentro del rubro, usando **solo** el período previo (mar-2024 a ene-2025):
  - perfil estacional de reseñas semanales, por correlación;
  - nivel de volumen, por tercil.

  Se excluyen las semanas del fuego de 2024 en Los Alerces (26/01–07/02/2024).
- Campings del parque contra restaurantes urbanos: solo para describir diferencias, no para el test.

**Modelo:**
- Reseñas por lugar × semana ~ expuesto × episodio, con efecto fijo de lugar y de rubro × semana (Poisson).
- Event study con semanas relativas al 16/02/2025, de −26 a +12.
- Ventana de análisis: mar-2024 a dic-2025. Se corta antes del fuego de ene-2026.
- Inferencia: errores por lugar. Con pocas zonas expuestas, sumar inferencia por permutación: se corre la fecha
  del episodio a semanas sin fuego y se ubica el efecto real en esa distribución.
- **Resultado principal:** todos los rubros juntos, con efecto fijo rubro × semana. Por rubro, como secundario.

**Condiciones para que el test sea defendible:**
1. El piloto aprueba formato, profundidad y cobertura (§5).
2. Exposición, radios, ventanas, rubros, regla de emparejamiento y especificación principal quedan commiteados
   antes de bajar la muestra completa.
3. El grupo de comparación está verificado sin focos ≥ 50 en el radio y la ventana definidos (FIRMS ampliado).
4. Tendencias previas: los coeficientes previos del event study son conjuntamente ≈ 0. Además, el placebo con
   fechas falsas en semanas sin fuego (nov–dic 2024 y abr–may 2025) da ≈ 0. No se usan las mismas semanas de
   2024, porque hubo fuego.
5. Potencia calculada con la varianza del piloto antes de la corrida completa (como `potencia.py`). Si el efecto
   mínimo detectable es más grande que lo plausible, se dice antes de correr.
6. Muestra fija por Place ID, que incluye fichas que después cerraron. Las truncadas se excluyen, con una
   sensibilidad que las incluye.
7. Rezago de publicación: el resultado se informa también con la ventana corrida 1 y 2 semanas.
8. Se informan todos los análisis declarados, dé lo que dé.

## 7. Qué hay que consultar con la profesora
1. **Booking como antecedente:** ¿cuenta como fuente si no entra al modelo nuevo?
2. **Informes de Esquel** (anuario y semestral) como contraste descriptivo. Propuesta:
   - una lámina que compare turistas y ocupación mensuales de 2025 (y ene–jun 2026) con el total mensual de
     reseñas de Google de alojamientos de Esquel;
   - sirve para ver si las reseñas siguen a los turistas y valida el proxy, sin efecto causal.
   - Por ejemplo, feb-2025 tuvo menos turistas que marzo (7.637 contra 7.934), algo poco habitual.
3. **Cierres y reaperturas del parque:** ¿tabla de referencia de fechas, como los límites geográficos, o fuente
   aparte? Mientras tanto se documentan en un archivo separado y no entran a la definición de exposición, que
   usa solo FIRMS.

## 8. Orden propuesto y fechas

| Cuándo | Qué | Costo |
|---|---|---|
| Ya | FIRMS abr–nov 2025 y bbox ampliado al norte, ventanas por zona, línea de tiempo y mapa de focos para el EDA | 0 |
| Ya | Documento de pre-registro (exposición, comparación y modelo) y consulta a la profesora | 0 |
| Cuando haya crédito (13/11 o cuenta nueva) | Piloto: catálogo mínimo y 15 fichas | ≤ USD 4,5 |
| Después del piloto | Potencia con la varianza del piloto; tamaño y costo de la muestra completa | 0 |
| Antes del 20/11 | Catálogo completo (Dataset 2) y reseñas de la muestra fija; escenario de Make con los actores de Maps | a dimensionar |
| 20–24/11 | Test, event study, placebos, contraste descriptivo (si se aprueba), Actor y presentación | — |

**Riesgo de calendario:** el Producto 1 es el 12/11 y sin crédito el piloto no puede correr antes. Para el
12/11 se puede presentar:
- el ETL y el EDA de FIRMS con la línea de tiempo de 2025;
- el dashboard;
- el escenario diario de FIRMS en Make;
- el diseño del test;
- el MVP de Booking como antecedente.

## 9. Apilar los tres episodios de Los Alerces: verificación con FIRMS (07/11)

Fuente: `src/exposicion_alerces.py` → `data/processed/firms_alerces/episodios_apilados.csv`. Misma regla que en
2025: días con foco de un evento ≥ 50 a ≤ 25 km de Esquel, Trevelin o Villa Futalaufquen. Se completó el bbox
norte para nov–dic 2023 y dic-2025 a mar-2026 (sin incendios; solo el volcán Villarrica, que se descarta).

| Episodio | Fechas | Detecciones a ≤ 25 km | Villa Futalaufquen | Esquel | Trevelin |
|---|---|---|---|---|---|
| 2024 | 26/01 – 07/02/2024 (13 días) | 637 | 4,0 km (alta) | 8,7 km (media) | 17,4 km (media) |
| 2025 | 16/02 – 01/03/2025 (14 días) | 423 | 1,5 km (alta) | 14,3 km (media) | 12,0 km (media) |
| 2026 | 07/01 – 02/02/2026 (27 días) | 1.668 | 10,5 km (media) | **24,8 km (media, en el límite de 25)** | 34,1 km (gris) |

**Controles (sin focos ≥ 50 a ≤ 40 km en el episodio ± 28 días):**
- Villa La Angostura, San Martín de los Andes y Corcovado están **limpias en los tres episodios**.
- Bariloche está limpia en 2024 (184 km) y en 2026 (107 km). Solo en 2025 quedó excluida.
- Ninguna localidad expuesta o de comparación tiene otro episodio dentro de su ventana de análisis (−26/+12
  semanas), y las ventanas de los tres episodios no se superponen.

**Lectura:**
- **Apilar es viable:** tres episodios con controles limpios. En 2024 y 2026 se puede sumar Bariloche como control.
- La exposición cambia entre episodios: en 2024 Esquel quedó más cerca (8,7 km) y en 2026 el fuego estuvo
  más al norte, dentro del parque.
- **Esquel queda otra vez en el límite en 2026 (24,8 km contra 25).** Se resuelve igual que en 2025: se informa
  la sensibilidad, no se mueve el radio.
- El incendio de 2026 tuvo cierres y evacuaciones grandes del parque: FIRMS mide distancia, no acceso (§7).

**Costo extra (estimado con el ritmo del piloto, ≈ 0,56% del total de cada ficha por mes):**
- 2026: **0**, porque la bajada desde 2024-03-01 ya llega a hoy.
- 2024: hace falta el período previo desde el 28/07/2023, ≈ 7 meses más. Son ≈ +22% de reseñas: ≈ USD 3–4,
  más ≈ USD 2 para volver a bajar las 14 fichas del piloto desde esa fecha.

**Para adoptarlo:** ampliar el pre-registro (episodios, ventanas, controles por episodio, modelo apilado con
efecto fijo de ficha × episodio y de semana × episodio) **antes** de bajar la muestra completa, y cambiar
`reviewsStartDate` a 2023-07-28.
