# Resultado del test pre-registrado: Comarca de los Alerces, episodio 2025 (07/11/2026)

Script: `src/test_alerces.py`. Salidas: `data/processed/test_alerces/` (`resultados.csv`, `principal.json`,
`event_study_2025.csv`, `permutacion_principal.csv`). Figura: `docs/figs/alerces_test_2025.png`.
Reglas: `docs/preregistro_alerces.md` (v3). **Nada se eligió después de ver el episodio.**

## Veredicto (criterio pre-registrado)

**TEST PRINCIPAL NO SUPERADO.** No se puede afirmar, con estos datos, que el volumen de reseñas haya caído más en
los lugares expuestos durante el episodio de febrero de 2025.

| Criterio | Resultado | ¿Cumple? |
|---|---|---|
| β < 0 con p a una cola (CRV1) < 0,05 | β = −0,172, o sea **−16%** [IC95% −45%, +30%]; p = 0,22 | no |
| p de permutación < 0,05 | p = 0,57 (60 pares de semanas sin fuego) | no |
| Tendencias previas no rechazadas al 10% | Wald = 216 con 25 gl, p < 0,001 | **no: el diseño no es creíble** |

- Muestra: 75 fichas (51 de exposición media, 6 de alta y 18 de comparación en Villa La Angostura) y 4.229 reseñas
  de Google, del 19/08/2024 al 29/12/2025.
- El efecto mínimo detectable declarado de antemano era ≈ −43%. La estimación puntual (−16%) está muy por debajo
  y el intervalo es compatible tanto con una caída del 45% como con una suba del 30%.

## Por qué fallan las tendencias previas

- Las fichas expuestas (Esquel y Trevelin) tienen un **pico propio en octubre–noviembre**, que coincide con el
  anuario de Esquel (octubre es el mes con más turistas del año). Villa La Angostura tiene su pico en enero.
- En el event study eso aparece como coeficientes negativos en las semanas −24 a −20 y positivos en las −18 a −15
  (fines de octubre a noviembre de 2024).
- El efecto fijo rubro × semana absorbe lo común a todos, pero no esta diferencia de calendario entre destinos.
- Es el mismo tipo de problema que invalidó el DiD 2×2 del MVP: cerca y lejos tienen estacionalidades distintas.
- **No hay un año limpio** para comparar cada ficha con su mismo mes de otro año: hubo fuego en Los Alerces en
  2024, 2025 y 2026.
- **Salvedad técnica:** con 25 coeficientes y 75 clusters, el test de Wald puede rechazar de más. Pero el patrón
  del gráfico es claro y tiene una explicación concreta.

## Robustez declarada (§5) y extensión apilada (§8)

| Análisis | Efecto | IC 95% | p (una cola) |
|---|---|---|---|
| Alta vs comparación (6 fichas) | −19% | −60% a +65% | 0,28 |
| Media vs comparación | −15% | −45% a +32% | 0,23 |
| Por rubro: alojamiento | −33% | −73% a +67% | 0,20 |
| Por rubro: atractivo / excursiones | −6% / 0% | muy anchos | 0,46 / 0,50 |
| Por rubro: camping / gastronomía | no estimable (menos de 2 fichas por grupo) | | |
| Episodio corrido +1 semana | −16% | −42% a +23% | 0,19 |
| Episodio corrido +2 semanas | −29% | −49% a 0% | 0,025 |
| Episodio de 4 semanas (17/02–16/03) | −23% | −44% a +5% | 0,048 |
| Sin Esquel | −10% | −45% a +47% | 0,34 |
| Agregado por quincena / por mes | −16% / −2% | | 0,22 / 0,45 |
| Con fichas "sin señal" en el log | −17% | −46% a +27% | 0,20 |
| Nota media | +0,00 puntos | −0,25 a +0,26 | 0,50 |
| Apilado 2025 + 2026 | −9% | −35% a +25% | 0,27 (permutación 0,42) |
| Solo 2026 | −7% | −39% a +42% | 0,37 |
| Apilado sin Esquel | −2% | −29% a +36% | 0,46 |
| Apilado, gradiente: alta / media | −19% / −7% | | 0,17 / 0,33 |

No ejecutados, como estaba declarado: sin San Martín de los Andes (no está en el catálogo) y comparación
emparejada (con 18 fichas de comparación no hay emparejamiento útil).

**Lectura:**
- **Casi todos los puntos son negativos y el gradiente va en la dirección esperada** (alta −19% > media −7% en el
  apilado). Pero ninguno es distinguible de 0, y todos heredan el problema de estacionalidad.
- **Las variantes con el episodio corrido 2 semanas o de 4 semanas dan p < 0,05.** Una caída que aparece después
  del fuego es coherente con el rezago de publicación. Pero no pueden presentarse como resultado:
  - son 2 de 16 pruebas secundarias (con tantas pruebas, alguna sale significativa por azar);
  - la condición de tendencias previas no se cumple;
  - el test principal no las acompaña.

## Qué se puede decir y qué no

**Se puede decir:**
- Con un diseño fijado de antemano y datos de Google Maps, **no se detecta** una caída de reseñas en los lugares
  expuestos durante el episodio de febrero de 2025.
- **El diseño no permite descartar un efecto**: el intervalo llega a −45%, y la comparación con Villa La Angostura
  no es válida porque Esquel tiene otro calendario turístico.
- Los signos van en la dirección esperada. Hay indicios débiles de una caída rezagada y de un gradiente por
  cercanía, para investigar con mejores datos.

**No se puede decir:**
- Que "no hubo efecto".
- Que el fuego redujo la actividad turística en X%.

**Qué haría falta para un test creíble:**
1. Un grupo de comparación con el **mismo calendario** que Esquel, por ejemplo destinos con pico en octubre.
   O un año sin fuego en Los Alerces, que no existe en 2024–2026.
2. Una medición independiente de las reseñas: ingresos semanales al parque por portada (pedido a Parques
   redactado) u ocupación por establecimiento (cámara hotelera).
3. Más fichas de exposición alta: hoy son 6.

**Costo total de Apify** para el piloto y la muestra de Maps: USD 4,87, dentro del tope acordado. El gasto total
del proyecto es de USD 14,73.
