# Make — escenario mínimo del MVP

## Estado (07/11/2026): hecho y probado
- Escenario **6938238** ("Integration Apify") en el equipo de Make del grupo, **inactivo**.
  Blueprint exportado: [`mvp_booking.json`](mvp_booking.json), sin mails ni tokens. Para importarlo:
  *Create scenario → … → Import Blueprint*, y después volver a elegir las dos conexiones.
- Conexiones: Apify con el token de la **cuenta 2**, y Google con la cuenta dueña de `humo_mvp`.
  Ojo: el equipo de Make tiene otras conexiones de Google ("Medcare"). Revisar siempre cuál queda elegida.
- *Run once* del 07/11: Run an Actor → Get Dataset Items → 10 × Add a Row en `booking_make`.
  Costo en Apify: USD 0,05 (en `data/processed/apify_gastos.csv`). En Make: ≈ 12 créditos.
  Primera fila: 2026-11-06 · El Bolsón · Hostel Cosmo · guest_house · 160.34 US$ · 9.3 · 230 reviews.
- **No activar el escenario así como está:** quedó con la programación por defecto de Make ("Every 15
  minutes"). Activado, correría el actor cada 15 minutos (≈ USD 0,05 cada vez). Para el escenario semanal:
  cambiar la programación a semanal y las fechas del input (ver la nota de fechas más abajo).
- El módulo 1 tiene *Maximum cost per run* = 0,07: es el tope duro de gasto de Apify dentro de Make.

**Objetivo:** que una corrida disparada desde Make agregue filas nuevas a la Google Sheet `humo_mvp`.
Flujo: **Run an Actor → Get Dataset Items → Google Sheets (Add a Row)**. Al terminar, exportar el
blueprint a `make/mvp_booking.json` (menú `…` del escenario → *Export Blueprint*).

## Antes de empezar

1. **Google Sheet `humo_mvp`.** Está todo en un solo archivo, `data/processed/sheets/humo_mvp.xlsx`, con las
   pestañas `leeme`, `focos`, `alojamientos`, `panel`, `reviews` y `kpi_did`:
   - Subir el `.xlsx` a Google Drive (*Nuevo → Subir archivo*). Después: clic derecho → *Abrir con →
     Hojas de cálculo de Google* → *Archivo → Guardar como Hojas de cálculo de Google*. Renombrarla `humo_mvp`
     y borrar el `.xlsx` subido, para que quede un solo archivo.
   - Atajo: con *Configuración de Drive → Convertir archivos subidos* activado, la conversión es automática.
   - Las fechas (`fecha`, `mes`, `fecha_checkin`) llegan como fechas, que es lo que Looker Studio necesita
     para las series. Los CSV sueltos de la misma carpeta sirven si se prefiere importar pestaña por pestaña.
   - Para regenerar todo: `python src/export_sheets.py`.
   - No se subió desde Claude porque esta sesión no tiene el conector de Google Sheets, y por Drive el
     archivo (≈ 320 KB) tendría que viajar entero dentro de la llamada.
2. **Pestaña nueva `booking_make`** con esta fila de encabezados (es donde escribe Make):
   `fecha_corrida | destino | nombre | tipo | precio | moneda | rating | reviews | lat | lng | url`
3. **Token de Apify:** al 07/11 las dos cuentas FREE quedaron con ≈ USD 0,08 cada una. La cuenta 1 se
   renueva el **13/11** (USD 5) y la 2 el 06/12. Una prueba de 10 alojamientos cuesta ≈ USD 0,05, así que
   alcanza para *Run once*, pero no para más. El token se pega en la conexión de Make, nunca en el repo.

## Módulos

### 1. Apify → *Run an Actor*
- Connection: crear una conexión con el token de la cuenta que tenga crédito (ver arriba).
- Actor: `voyager/booking-scraper`.
- **Run synchronously: Yes**. Así el módulo espera a que termine y devuelve el `defaultDatasetId`.
- Input JSON. Son los mismos nombres de campo que valida `src/run_booking.py` contra el schema real.
  **Ojo con las fechas:** a 14 meses, Booking lista solo los alojamientos que ya abrieron calendario
  (≈ la mitad; verificado 07/11). Para el escenario semanal conviene usar fechas a ≤ 3 meses, o no usar
  fechas, aunque así no viene precio.
  Usar **`maxItems` chico**: cada alojamiento cuesta USD 0,005, así que 10 alojamientos son ≈ USD 0,05 por corrida.
  ```json
  {
    "search": "El Bolsón, Río Negro, Argentina",
    "maxItems": 10,
    "checkIn": "2027-01-15",
    "checkOut": "2027-01-17",
    "currency": "USD",
    "language": "es",
    "adults": 2,
    "rooms": 1,
    "sortBy": "distance_from_search"
  }
  ```

### 2. Apify → *Get Dataset Items*
- Dataset ID: mapear `defaultDatasetId` del módulo 1.
- Format: JSON · Limit: 10 (igual que `maxItems`).
- Devuelve un *bundle* por alojamiento, así que el módulo 3 corre una vez por cada uno.

### 3. Google Sheets → *Add a Row*
- Spreadsheet: `humo_mvp` · Sheet: `booking_make` · *Table contains headers*: Yes.
- Mapeo (campos reales del actor, verificados el 07/11):

| Columna | Valor en Make |
|---|---|
| fecha_corrida | `{{formatDate(now; "YYYY-MM-DD")}}` |
| destino | `El Bolsón` (texto fijo) |
| nombre | `name` |
| tipo | `type` |
| precio | `price` (estadía de 2 noches) |
| moneda | `currency` |
| rating | `rating` |
| reviews | `reviews` |
| lat | `location.lat` (viene como texto: Sheets lo convierte) |
| lng | `location.lng` |
| url | `url` |

## Probar y cerrar
1. *Run once*. **Listo cuando** aparecen ≈ 10 filas nuevas en `booking_make`.
2. Revisar el costo de la corrida en la consola de Apify (*Runs*) y sumarlo a mano a
   `data/processed/apify_gastos.csv`. El cobro aparece unos minutos después de terminar.
3. Exportar el blueprint a `make/mvp_booking.json` y commitearlo. Antes, revisar que no tenga el token:
   Make guarda la conexión aparte, pero conviene confirmarlo.

## Escenario diario de FIRMS NRT (07/11/2026): hecho y probado

- Escenario **6939387** (`humo_firms_nrt_diario`), **inactivo**, programado **Daily a las 09:00**
  (zona horaria del escenario: America/Argentina/Buenos_Aires). Activarlo es una decisión del grupo.
  Make cobra por operación aunque no haya focos: un día sin fuego gasta unos 2 créditos (Tools y HTTP).
- Blueprint: [`mvp_firms_nrt.json`](mvp_firms_nrt.json). **No es el export de Make**: se armó a partir de
  la versión guardada del escenario, porque el export descarga un archivo. La MAP_KEY quedó como
  `PEGAR_MAP_KEY_DE_FIRMS` y falta la conexión de Google. Después de importar: pegar la MAP_KEY en el
  módulo 1 y elegir la conexión de Google en el módulo 4.
- Escribe en la pestaña **`focos_nrt`** de `humo_mvp`. Encabezados:
  `fecha_carga | acq_date | acq_time | lat | lng | bright_ti4 | frp | confidence | daynight | alerta_40km`.

### Módulos
1. **Tools → Set variables.** Las variables son `map_key`, `fuente` (`VIIRS_SNPP_NRT`), `bbox`
   (`-72.3,-43.4,-70.8,-40.8`), `dias` (`1`) y `sufijo_fecha` (`/{{formatDate(addDays(now; -1); "YYYY-MM-DD")}}`,
   o sea ayer). La MAP_KEY vive solo acá, para que el resto del escenario no la repita.
   Para una prueba con fuego real se cambia `sufijo_fecha` por una fecha fija, por ejemplo `/2025-02-02`.
2. **HTTP → Make a request:**
   `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{{1.map_key}}/{{1.fuente}}/{{1.bbox}}/{{1.dias}}{{1.sufijo_fecha}}`.
   Con *Return error if HTTP request fails* activado, una MAP_KEY vacía o inválida da error (400) en vez de
   pasar en silencio (verificado 07/11).
3. **Filtro "hay datos"** entre HTTP y CSV: `{{length(split(trim(2.data); newline))}}` > 1 (operador
   numérico). En un día sin focos FIRMS devuelve solo la línea de encabezado, y *Parse CSV* fallaba con
   "Number of columns on line 1 does not match header". **Verificado 07/11:** con el filtro, la corrida de
   producción sin focos termina sin error y sin escribir filas.
4. **CSV → Parse CSV** con *CSV contains headers* = Yes y los 14 encabezados del NRT
   (`latitude,…,daynight`; el SP trae además `type`). **Ojo:** aunque el panel muestre los nombres, las
   claves internas son `col1…col14`. `{{3.latitude}}` no resuelve; hay que mapear `{{3.col1}}`.
   Las claves que se usan son `col1` latitude, `col2` longitude, `col3` bright_ti4, `col6` acq_date,
   `col7` acq_time, `col10` confidence, `col13` frp y `col14` daynight.
5. **Filtro "confianza n/h (descarta l)"** entre CSV y Sheets: `{{3.col10}}` *Not equal to
   (case insensitive)* `l`.
6. **Google Sheets → Add a Row** en `focos_nrt`, con *Value input option* = USER_ENTERED.
   `fecha_carga = {{formatDate(now; "YYYY-MM-DD HH:mm")}}` queda en hora de Argentina; `acq_date` y
   `acq_time` vienen de FIRMS en UTC.

### Alerta (`alerta_40km`)
`SI` si el foco cae a ≤ 40 km del centro de alguna de las 10 localidades del panel (Bariloche,
Villa La Angostura, Dina Huapi, El Bolsón, Lago Puelo, El Hoyo, Epuyén, Cholila, Esquel y Trevelin).
- Es una **aproximación equirrectangular**: Make no tiene trigonometría. La distancia al cuadrado es
  Δlat² · 12.365 + Δlng² · 6.839 (en km², con 111,2 km por grado de latitud y ≈ 111,2 · cos 42° por grado de longitud),
  y el umbral es 1.600 km². A 40 km la diferencia con haversine es despreciable (supuesto, no medido).
- Se usan 40 km del centro de la localidad en vez de "30 km de algún alojamiento" porque los
  alojamientos se reparten hasta unos 10 km del centro: es una alerta conservadora.
- Fórmula completa en el blueprint (columna J del módulo 4).
- **Prueba (07/11):** con fecha fija 2025-02-02 y bbox de Mallín Ahogado se escribieron 11 de 12 filas
  (la de confianza `l` quedó filtrada), todas con `SI`. Coinciden con el cálculo en Python. Esas filas se
  borraron después. El caso "hay datos" con el filtro nuevo no se volvió a correr: el filtro solo deja
  pasar la respuesta cuando tiene más de una línea, y esa prueba tenía 13.

## Próximos escenarios
- **Semanal, Booking:** el mismo flujo de este README, con los 7 destinos. Necesita crédito de Apify
  (la cuenta 1 se renueva el 13/11).
