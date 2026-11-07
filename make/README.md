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

## Próximos escenarios (Producto 1, 12/11)
- **Diario, FIRMS NRT:** *HTTP → Make a request* a
  `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/VIIRS_SNPP_NRT/-72.3,-43.4,-70.8,-40.8/1`
  → *Parse CSV* → filtro `confidence` en `n`/`h` → *Add rows* en `focos` → alerta si hay un foco a menos
  de 30 km de algún alojamiento. La API acepta **como máximo 5 días por llamada**. La MAP_KEY va en
  una variable del escenario, no en el blueprint commiteado.
- **Semanal, Booking:** el mismo flujo de este README, con los 7 destinos.
