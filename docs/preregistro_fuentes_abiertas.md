# Pre-registro: fuentes abiertas de validación (07/11/2026)

Se escribe y se commitea **antes de abrir** los datos de visitas a Parques Nacionales y de empleo por rama de CEP XXI.
El empleo de OEDE **ya se miró** (exploración del 07/11) y queda marcado como exploratorio. Estas fuentes son
**validación externa**: no reemplazan al test de Google Maps y su uso en la entrega depende de la profesora.

## Pregunta

¿En los meses de los episodios de incendio de Los Alerces cayeron más las visitas al parque, y el empleo en
alojamiento y gastronomía de Futaleufú (Esquel y Trevelin), que en lugares comparables, respecto de su propio
patrón mensual?

- H₀: β = 0. H₁: β < 0, a una cola, α = 5%.

## Episodios (los mismos de FIRMS, `episodios_apilados.csv`)

Un mes cuenta como tratado si tiene ≥ 7 días de episodio:

| Episodio | Días | Meses tratados |
|---|---|---|
| 2024 | 26/01 – 07/02/2024 | ene-2024 (6 días) no cuenta; feb-2024 (7 días) sí → **feb-2024** |
| 2025 | 16/02 – 01/03/2025 | **feb-2025** (13 días) |
| 2026 | 07/01 – 02/02/2026 | **ene-2026** (25 días), solo si los datos llegan a esa fecha |

## A. Visitas mensuales a Parques Nacionales (registro de recaudación de Parques Nacionales)

- **Tratado:** PN Los Alerces.
- **Comparación:** parques de Patagonia con temporada de verano parecida y **sin focos ≥ 50 a ≤ 40 km** en el mes
  tratado ± 28 días:
  - PN Nahuel Huapi (en feb-2025 tuvo fuego en el parque: se excluye ese episodio);
  - PN Los Arrayanes;
  - PN Los Glaciares, PN Tierra del Fuego y PN Perito Moreno, si están en el archivo;
  - PN Lanín: se excluye en 2025 (fuego del 30/01 al 27/02/2025);
  - PN Lago Puelo: se excluye en 2025 (Mallín Ahogado y Epuyén).

  La lista final de controles por episodio se fija con FIRMS antes de estimar.
- **Ventana:** 2008 a la última fecha disponible. **Se excluyen 2020 y 2021** (pandemia).
- **Modelo:** `feols(log(visitas) ~ trat | parque^mes_calendario + periodo)`. trat = PN Los Alerces × mes tratado.
  El efecto fijo parque × mes calendario compara cada mes contra el mismo mes de los demás años.
  - Principal: **feb-2025**. Secundarios: feb-2024, ene-2026 si hay datos, y el apilado.
- **Inferencia:** con pocos parques, el error clusterizado no sirve. Se usa **permutación**: se repite la estimación
  marcando como "tratado" cada mes de Los Alerces sin fuego (excluidos los meses ± 2 alrededor de los episodios,
  2020–2021 y los meses con fuego conocidos), y p = proporción de β placebo ≤ β observado.
- **Validez:** el promedio de los β placebo de los 6 meses previos al episodio tiene que estar dentro del rango
  central del 90% de la distribución de permutación.
- Si el archivo trae visitantes residentes y no residentes, el principal es el **total**; las dos series van como
  secundarias.

## B. Empleo asalariado registrado por departamento y rama (CEP XXI, CLAE 2 dígitos)

- **Tratado:** departamento Futaleufú (Chubut).
- **Comparación:** Los Lagos (Villa La Angostura) y Lácar (San Martín de los Andes). Bariloche se excluye en
  feb-2025 (fuego del PN Nahuel Huapi).
- **Ramas:** **55 (alojamiento)** y **56 (gastronomía)**, por separado y sumadas. La suma es la principal.
- **Ventana:** desde 2019 (o desde donde empiece el archivo) hasta la última fecha. Se excluyen 2020 y 2021.
- **Modelo e inferencia:** igual que en A, con departamento en lugar de parque. Permutación sobre los meses sin
  fuego de Futaleufú.
- **Secundario:** Cushamen (Cholila y Epuyén) contra los mismos controles en ene–feb 2025 (fuego de Epuyén,
  15–30/01/2025). Está motivado por la exploración de OEDE, así que se informa como **hipótesis surgida de los
  datos**, no como confirmación.

## C. OEDE (ya explorado el 07/11; no es confirmatorio)

- Empleo mensual por departamento y sector amplio ("Servicios", "Comercio"), 2019 – dic-2025.
- Lo que se vio:
  - Futaleufú, servicios, feb–mar 2025: −0,4% [−3,5%, +2,8%];
  - Futaleufú, comercio, ene–feb 2024: −4,7% [−7,8%, −1,5%];
  - Cushamen, servicios, feb-2025: −10% contra su patrón.
- Se informa como exploración, con estas salvedades:
  - sectores amplios;
  - pocos departamentos;
  - errores heterocedásticos, no clusterizados.

### C, con la inferencia de este pre-registro (permutación; `src/fuentes_abiertas.py`, 07/11)

| Análisis (exploratorio) | Efecto | p de permutación |
|---|---|---|
| Servicios, Futaleufú, feb-2024 / feb-2025 | +0,0% / +0,4% | 0,46 / 0,52 |
| Comercio, Futaleufú, feb-2024 / feb-2025 | −5,4% / +2,2% | 0,25 / 0,60 |
| Servicios, Cushamen, ene–feb 2025 | −9,7% | 0,125 |
| Comercio, Cushamen, ene–feb 2025 | +0,5% | 0,44 |

Con errores heterocedásticos, el comercio de Futaleufú en 2024 parecía significativo ([−7,8%, −1,5%]). Con
permutación no lo es. **Ninguna señal de OEDE es significativa.**

## Qué se va a concluir

- **Convergencia:** que Parques (A) y alojamiento y gastronomía (B) den β < 0 con p de permutación < 0,05 en
  feb-2025, junto con los indicios de Maps (signos negativos, gradiente), es evidencia convergente de un efecto.
- **Si dan nulos:** se informa que tres mediciones independientes no detectan efecto en el episodio 2025.
- Ninguna de estas fuentes cambia el veredicto del test pre-registrado de Maps, que ya está informado.

## Cambios

_(ninguno)_
