# Decisiones abiertas para el grupo (07/11/2026)

Son dos preguntas que no se resolvieron solas porque tocan decisiones de diseño (CLAUDE.md). Cada una tiene
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
