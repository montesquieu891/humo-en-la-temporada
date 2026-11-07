# Decisiones abiertas para el grupo (07/11/2026)

Son tres preguntas que no se resolvieron solas porque tocan decisiones de diseño (CLAUDE.md). Cada una tiene
las opciones, la evidencia medida con datos reales y una recomendación. Cuando el grupo decida, completar
**Decisión** y actualizar CLAUDE.md.

---

## 1. ¿Qué meses cuentan como "fuego" en la temporada 2025?

**Contexto (verificado con FIRMS):** hoy el único mes de fuego 2025 es **2025-02** (Mallín Ahogado, desde el
30/01). Pero en esa temporada también hubo fuego en **Epuyén del 15 al 30/01/2025** (evento 5, a 5 km del
pueblo) y en **Esquel y Trevelin en feb-2025** (eventos 25 y 26). Además, el incendio del PN Nahuel Huapi
(dic-2024 a feb-2025) queda a unos 46–50 km de Bariloche.

**Cuánto cambia el resultado** (modelo de efectos fijos alojamiento × mes calendario, `src/fe_preliminar.py`,
29 alojamientos):

| Opción | Volumen de reviews | Nota | Alojamiento-meses tratados |
|---|---|---|---|
| A) Actual: fuego 2025 = feb | −10% [−53%, +71%] | −0,11 [−0,55; +0,32] | 45 |
| B) Fuego 2025 = ene + feb para todos | **+36%** [−22%, +137%] | +0,10 [−0,22; +0,41] | 64 |
| C) Actual, sin alojamientos de Chubut en 2025 | −46% [−87%, +128%] | −0,51 [−1,66; +0,64] | 35 |

**Lectura:**
- La opción B está mal planteada. Marca enero como mes con fuego para todos los alojamientos "cerca" en 2025,
  incluido El Bolsón, cuando Mallín Ahogado recién empezó el 30/01. Enero es temporada alta, así que el signo
  se invierte. El fuego de Epuyén de enero solo debería contar para los alojamientos cercanos a Epuyén, y en
  el panel actual no hay ninguno (El Hoyo tiene 2).
- Que la estimación salte de −46% a +36% según la definición confirma que **con 29 alojamientos no hay
  potencia**: todos los intervalos son anchísimos.

**Opciones para decidir:**
- **A — dejar feb-2025.** Simple y es lo que está implementado. Ignora Epuyén (enero) y deja a Esquel como "cerca".
- **D — meses de fuego por evento (recomendada).** El mes de fuego de cada alojamiento lo definen las fechas
  del evento FIRMS más cercano (inicio y fin en `firms_eventos.csv`), no un calendario común. Es consistente
  con la decisión 6 (stacked DiD, cada evento por separado) y con el event study del Producto 2.
- **C — sacar a Chubut de la temporada 2025** por contaminado. Pierde muestra y no resuelve Esquel.

**Recomendación:** mantener **A** para el MVP y el 12/11 (ya está y es transparente), e implementar **D**
para el Producto 2, junto con la corrida completa de reviews.

**Decisión:** ______________________ (fecha, quién)

---

## 2. ¿Qué presentamos como "Dataset 2" (Booking) en la consigna?

**Consigna:** entre 700 y 2.000 registros, ≈ 10 features comprensibles, pocos nulos y con coordenadas.

| | `alojamientos.csv` | `reviews_dataset.csv` |
|---|---|---|
| Filas | 834 ✔ | 1.789 ✔ |
| Columnas | 16 (se puede bajar a 15 sacando `moneda`) | 13 ✔ |
| Nulos | `precio_ref` y `moneda` 35,5% (vienen de búsquedas sin fechas) | 0% ✔ |
| Coordenadas | sí ✔ | sí (las del alojamiento) ✔ |
| Qué representa | el universo de oferta: todos los alojamientos de la zona | una muestra de 42 alojamientos |
| **Después de la corrida completa** | sigue en ~834–1.000 ✔ | **≈ 11.800 reviews: se pasa del máximo de 2.000** ✘ |

**Lectura:** hoy los dos cumplen y las reviews están más limpias. Pero la corrida completa de reviews prevista
para el Producto 2 deja a `reviews_dataset` muy por encima de 2.000 filas. Los alojamientos son estables y
representan el fenómeno de la consigna ("oferta y reputación turística").

**Recomendación:** presentar **`alojamientos`** como Dataset 2:
- Sacar `moneda`, que es redundante (todo está en USD), y quedar en 15 columnas.
- Documentar que `precio_ref` solo existe para los alojamientos con calendario abierto para ene-2027 y que es
  una tarifa de referencia para el ROI, no un outcome.
- Las reviews quedan como tabla derivada del panel.
- Alternativa para reducir nulos: volver a correr con fechas cercanas (≤ 3 meses) para todo el universo
  cuando haya crédito (≈ USD 4).

**Decisión:** ______________________ (fecha, quién)

---

## 3. ¿Cuánto gastar en la corrida de reviews del Producto 2? (efecto mínimo detectable)

**Pregunta:** con el modelo de la decisión 5 (FE alojamiento × mes calendario + año-mes, `fepois`, errores
por alojamiento), ¿qué caída del volumen de reviews se puede detectar según cuántos alojamientos se bajen?

**Método** (`src/potencia.py`, 400 réplicas, semilla 7, `data/processed/potencia.csv`):
- Bootstrap estratificado de los 29 alojamientos reales del panel, con su historia mes a mes, reescalado
  a cada tamaño de muestra en las proporciones del universo a bajar.
- El universo son 380 alojamientos con ≥ 10 reviews a ≤ 40 km de un foco: 51% Esquel (cerca solo en 2025),
  36% El Bolsón (cerca en las dos temporadas), 10% El Hoyo (cerca solo en 2026) y 3% nunca cerca.
- Se descuentan los truncados: los completos son el 76% de los alojamientos cercanos pedidos y el 56% de los
  de Bariloche (muestra MVP).
- MDE = 80% de potencia, α = 5%.

| Escenario (pedidos cerca + lejos) | Completos | Costo USD* | MDE volumen** | Potencia ante −20% | ante −30% | MDE nota |
|---|---|---|---|---|---|---|
| Actual MVP (33 + 9) | 31 | 5 | −50% a −59% | 15% | 30% | −0,49 |
| 90 + 10 | 73 | 9–11 | −36% a −44% | 28% | 60% | −0,30 |
| 190 + 15 | 153 | 18–21 | −27% a −33% | 53% | 90% | −0,20 |
| 280 + 20 | 224 | 26–30 | −23% a −28% | 69% | 97% | −0,17 |
| **Universo cercano (380 + 30)** | **305** | **36–42** | **−20% a −25%** | **81%** | 100% | −0,14 |
| Universo + 100 de control (380 + 100) | 344 | 56–62 | −20% a −24% | 80% | 99% | −0,14 |

\* El rango va del costo promedio del universo (USD 0,072 por alojamiento cercano) al de la muestra MVP (USD 0,087,
que eligió alojamientos más grandes). Cada alojamiento de Bariloche cuesta ≈ USD 0,29.
\** El primer número sale de la simulación. El segundo escala el error estándar real del panel actual
(0,330 con 29 alojamientos) por √(29/N). Con los datos actuales la simulación subestima el error.

**Lectura (simulado, no medido):**
- Con el crédito de una sola renovación (≈ USD 10) solo se detectan caídas de más de un tercio. Con el
  presupuesto actual, un resultado "sin efecto" no diría nada.
- Para detectar −20% con 80% de potencia hace falta prácticamente **todo el universo cercano** (≈ USD 36–42).
  Aun así es el escenario optimista: el pesimista da −25%.
- **Sumar controles lejanos casi no ayuda** (de 30 a 100 el MDE no se mueve y cuesta USD 20 más). Los controles
  salen sobre todo de los propios alojamientos cercanos en la temporada en que no les tocó el fuego.
- **El Bolsón queda "cerca" en las dos temporadas.** Con el efecto fijo alojamiento × mes calendario, su
  febrero 2025 (con fuego) se compara contra su febrero 2026 (también con fuego), así que para él solo
  identifica enero. Es el 36% del universo y aporta poco.
- **Supuestos:** los alojamientos nuevos se parecen a los del panel en su estrato (El Hoyo tiene solo 2), y la
  tasa de truncados y el costo son los de la muestra MVP. La muestra MVP tiene alojamientos más grandes que el
  universo (mediana de 56 reviews contra 34). Con alojamientos más chicos la potencia sería algo menor.

**Opciones:**
- **A — Universo cercano (380) + 30 de Bariloche, ≈ USD 36–42.** Es la única que llega a detectar −20 a −25%.
  Hace falta crédito de unas 8 cuentas FREE (USD 5 cada una) o un mes de un plan pago. Hay que correrlo entre el
  13/11 (renovación de la cuenta 1) y el 18/11 para llegar al 20/11.
- **B — 190 + 15, ≈ USD 20.** Detecta caídas de 30% o más (potencia del 90% ante −30%). Si el efecto real es
  chico, queda como "no detectable" con un IC más angosto.
- **C — Extender la ventana un año hacia atrás** (estadías desde nov-2023; Booking guarda unos 36 meses).
  Le da a El Bolsón un febrero sin fuego (2024) y agrega una comparación más por mes calendario a todos.
  Cuesta ≈ +60% de reviews por alojamiento. La ganancia de potencia **no está medida**: se puede probar
  bajando la historia larga de 20–30 alojamientos (≈ USD 2–3) antes de decidir. Es combinable con A o B.

**Hallazgo para la opción C (FIRMS, verificado 07/11):** la temporada 2023-24 **no está limpia**. Del 26/01 al
07/02/2024 hubo un incendio grande en el PN Los Alerces (637 detecciones, centro −42,83 / −71,57, a ≈ 22 km de
Esquel; `data/processed/firms_2024/`).
- El Bolsón queda a ≈ 96 km: gana un enero y un febrero sin fuego, que es lo que le falta.
- 10 de los 29 alojamientos del panel (Esquel) quedan a ≤ 15 km: con ventana larga suman una tercera temporada
  tratada (2024-02).
- **Decidido (07/11):** en 2024 cuenta solo febrero, igual que en 2025 (los dos fuegos empezaron a fines de
  enero).

**Prueba de la opción C, lista para correr** (no se corrió: hoy no hay crédito):
```bash
python src/run_booking.py --cuenta 1 ventana-larga --dry-run      # 22 alojamientos completos, ≈ USD 2,95
python src/run_booking.py --cuenta 1 ventana-larga                # después del 13/11
python src/piloto_ventana.py --reviews data/raw/ventana_larga/reviews_desde_2023-11.json
```
- Vuelve a pedir, con cutoff 2023-11-01, los alojamientos cercanos cuya historia corta quedó completa (los
  11 de El Bolsón primero) y guarda el resultado en `data/raw/ventana_larga/`, fuera del panel principal.
- `piloto_ventana.py` estima el modelo con ventana corta y con ventana larga sobre los mismos alojamientos,
  calcula la razón de errores estándar y reescala la tabla de arriba (`data/processed/piloto_ventana.csv`).
- Validado con los datos actuales: reproduce el modelo (β −0,111, EE 0,330) y da razón 1,01, como corresponde
  sin estadías anteriores a nov-2024.
- **Antes de correrla:** el tope acumulado del MVP (USD 10) ya está en USD 9,86, así que la corrida frena.
  Para el Producto 2 hay que acordar un presupuesto nuevo y fijarlo con `TOPE_USD_TOTAL` en `.env`.

**Recomendación:** decidir el presupuesto con esta tabla. Si no se consigue crédito para A:
1. hacer la prueba de C (≈ USD 3);
2. según lo que dé, correr B con ventana larga.

Con cualquier opción, no pedir más de 30 controles lejanos y no gastar en alojamientos con < 10 reviews.

**Decisión:** ______________________ (fecha, quién)
