# Pre-registro: episodio de incendio 2025 en la Comarca de los Alerces

**Versión 1, 07/11/2026.** Se escribe y se commitea **antes** de bajar cualquier reseña de Google Maps. Lo que se
cambie después de ver reseñas va en la sección "Cambios" con la fecha y el motivo, y el análisis original se
informa igual. Contexto y piloto: `docs/plan_reformulacion_alerces.md`.

## 1. Pregunta e hipótesis

¿Durante el episodio de incendio de febrero de 2025, cayó más el volumen de reseñas de Google en los lugares
expuestos que en lugares del mismo rubro, no expuestos, observados en las mismas semanas?

- H₀: β = 0. El cambio en reseñas semanales durante el episodio es igual en expuestos y en comparación.
- H₁: β < 0. A una cola, α = 5%.
- **Qué mide:** reseñas por fecha de publicación, un proxy de actividad. No mide ocupación ni ingresos.

## 2. Episodio y exposición (solo FIRMS)

Fuente: `src/exposicion_alerces.py`, con VIIRS S-NPP SP de nov-2023 a mar-2026 en el bbox sur y el bbox norte.
- Confianza n/h, sin volcanes ni fuentes fijas (`type` 1 y 2).
- DBSCAN de 2 km ≈ 3 días; foco = evento con ≥ 50 detecciones.

- **Episodio:** del **16/02/2025 al 01/03/2025**. Son los días con detecciones de eventos ≥ 50 a ≤ 25 km de
  Esquel, Trevelin o Villa Futalaufquen: el evento 26 (PN Los Alerces, 20/02–01/03, 212 detecciones) y el 25
  (sur-sudeste de Esquel, 16/02–26/02, 211 detecciones).
- **Semanas del episodio** (lunes a domingo, hora de Argentina): 10/02–16/02 (solo el domingo 16), 17/02–23/02
  y 24/02–02/03. **Principal:** las semanas del 17/02 y del 24/02.
- **Nivel de exposición de cada ficha:** d = distancia haversine mínima desde la coordenada de Google Maps a una
  detección de un evento ≥ 50 durante el episodio.

| Nivel | Regla | Uso |
|---|---|---|
| Alta | d ≤ 5 km | expuesto |
| Media | 5 < d ≤ 25 km | expuesto |
| Zona gris | 25 < d ≤ 40 km | se excluye del test y se describe aparte |
| Comparación | ninguna detección de un evento ≥ 50 a ≤ 40 km entre el 19/01 y el 29/03/2025 (episodio ± 28 días), y la ficha está en una localidad de comparación | control |

- Referencias (centro de la localidad, verificado 07/11):
  - Villa Futalaufquen, a 1,5 km: alta.
  - Trevelin, a 12,0 km: media.
  - Esquel, a 14,3 km: media.
- **Localidades de comparación** (verificadas 07/11, sin focos ≥ 50 a ≤ 40 km en la ventana y en todo
  mar-2024 a dic-2025):
  - **Villa La Angostura** (69 km): principal.
  - **San Martín de los Andes** (59 km del fuego del PN Lanín, 30/01–27/02/2025, 3.336 detecciones): pasa la
    regla, pero se informa también **sin ella**, porque el fuego afectó atractivos del mismo parque.
  - **Corcovado** (52 km): solo si hay al menos 5 fichas elegibles.
- **Excluidas como comparación:**
  - Junín de los Andes: foco a 37 km del 08 al 10/02/2025.
  - Bariloche: 42 km del PN Nahuel Huapi y fuego dic-2024 a feb-2025.
  - El Bolsón y Cholila: fuego en ene–feb 2025.

## 3. Unidad, muestra y outcome

- **Unidad:** ficha de Google Maps (Place ID) × semana.
- **Ventana de análisis:** semanas del 04/03/2024 al 29/12/2025. Queda fuera del fuego de Los Alerces de
  ene–feb 2024 y del de ene–feb 2026.
- **Rubros:** alojamiento, gastronomía, camping, excursiones y turismo activo, y atractivos. Se mapean las
  categorías de Google a rubros con una tabla que se fija con el catálogo, antes de bajar reseñas.
- **Fichas elegibles:**
  1. están en una localidad expuesta (alta o media) o de comparación, y en un rubro de la lista;
  2. tienen reseñas de Google desde jun-2024 o antes;
  3. alcanzan un mínimo de reseñas de Google en el período previo (mar-2024 a ene-2025). El mínimo se fija con el
     piloto **usando solo el período previo** y se anota acá antes de la corrida completa.

  Se incluyen las fichas que después cerraron.
- **Muestra:** todas las elegibles, o una muestra al azar estratificada por localidad × rubro si el presupuesto
  no alcanza (semilla fija). Se baja por Place ID con `reviewsStartDate=2024-03-01`.
- **Outcome principal:** cantidad de reseñas de origen Google publicadas en la semana. Las de otros sitios se
  descartan.
- **Outcome secundario:** nota media semanal, ponderada por cantidad.
- **Exclusiones:** fichas truncadas (llegaron a `maxReviews` o les falta historial); se informa una
  sensibilidad que las incluye.

## 4. Modelo y test

- **Principal:** `fepois(resenas ~ expuesto:episodio | ficha + rubro^semana)`, con errores clusterizados por ficha.
  - `expuesto` = alta o media.
  - `episodio` = semanas del 17/02 y del 24/02/2025.
  - β < 0 con p a una cola < 0,05.
- **Inferencia por permutación**, por si hay pocas zonas expuestas: se repite la estimación corriendo el
  "episodio" a cada par de semanas consecutivas sin fuego en la ventana de análisis, salvo el episodio ± 4 semanas.
  - p = proporción de β placebo ≤ β observado.
  - Se informan los dos valores de p. El test se considera superado solo si los dos son < 0,05.
- **Event study:** `i(semana_rel, expuesto, ref=-1)`, con semanas relativas al 17/02/2025, de −26 a +12.
  Los extremos se agrupan.
- **Condición de validez (tendencias previas):** los coeficientes de −26 a −2 no se rechazan conjuntamente al 10%.
  Si se rechazan, el resultado principal se informa como no creíble, como pasó con el DiD 2×2 del MVP.

## 5. Análisis secundarios y de robustez (declarados de antemano; se informan todos)

1. Alta contra comparación y media contra comparación, por separado.
2. Por rubro, como secundario. El test es el resultado de todos los rubros juntos.
3. Rezago de publicación: episodio corrido +1 y +2 semanas, y episodio de 4 semanas (17/02–16/03).
4. Sin Esquel: está a 14,3 km, en el límite que ya fue problema en el MVP.
5. Sin San Martín de los Andes como comparación.
6. Comparación emparejada dentro del rubro, con datos del período previo solamente: correlación del perfil
   semanal y tercil de volumen.
7. Agregación por quincena y por mes.
8. Con las fichas truncadas.
9. Nota media como outcome.

## 6. Reglas que salen del piloto (se fijan antes de la corrida completa)

- **Formato:** si la fecha de publicación no viene exacta, no hay análisis semanal y la unidad pasa a ser el mes.
  Con meses, el episodio es febrero de 2025 completo y se declara la pérdida de resolución.
- **Cobertura:** si la mediana de reseñas de Google por ficha y semana en ene–mar 2025 es menor a 1, la unidad
  pasa a quincena.
- **Mínimo de reseñas previas** (criterio 3 de elegibilidad): se fija con la distribución del período previo
  en el piloto.
- **Potencia:** con la varianza del piloto (como `src/potencia.py`) se calcula el efecto mínimo detectable para
  el tamaño de muestra que permita el presupuesto, y se anota acá antes de bajar la muestra completa.
- En el piloto **no se calcula** la diferencia entre expuestos y comparación durante el episodio.

## 7. Fuera del modelo (pendiente de consulta)

- **Cronología de cierres y reaperturas** del PN Los Alerces: se documenta en un archivo aparte y no define la
  exposición.
- **Informes de Esquel** (anuario 2025 y semestral 2026): contraste descriptivo, solo si lo aprueba la profesora.
- **Booking:** antecedente del MVP.

## Cambios

_(ninguno)_
