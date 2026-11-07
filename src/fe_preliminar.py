"""
Humo en la temporada — versión PRELIMINAR del modelo principal (Producto 2), para chequear el baseline.

Por qué: el placebo del DiD 2×2 (did_baseline.py) da β ≠ 0 antes del fuego, es decir que cerca y lejos
tienen estacionalidad distinta. La especificación de CLAUDE.md (decisión 5) la controla con un efecto fijo
alojamiento × mes calendario (cada mes de fuego se compara con el mismo mes del año sin fuego) más un
efecto fijo año-mes.

  n_reviews ~ fuego_cerca | aloj_id^mes_cal + mes_estadia        (fepois, volumen)
  nota_media ~ fuego_cerca | aloj_id^mes_cal + mes_estadia       (feols, ponderado por n_reviews)

fuego_cerca = 1 en los meses de fuego de cada temporada para los alojamientos a ≤15 km de ESA temporada
(2025-02 por Mallín Ahogado; 2026-01 y 2026-02 por Chubut). Errores clusterizados por alojamiento.
Es preliminar: falta el event study, las bandas y el stacked DiD por evento (decisión 6).

Uso (desde humo/): python src/fe_preliminar.py
"""
import numpy as np
import pandas as pd
import pyfixest as pf

FUEGO = {"2025": ["2025-02"], "2026": ["2026-01", "2026-02"]}


def main():
    p = pd.read_csv("data/processed/panel.csv")
    p["fuego_cerca"] = (
        (p["mes_estadia"].isin(FUEGO["2025"]) & (p["cerca_2025"] == 1))
        | (p["mes_estadia"].isin(FUEGO["2026"]) & (p["cerca_2026"] == 1))
    ).astype(int)
    print(f"Panel: {len(p)} filas, {p['aloj_id'].nunique()} alojamientos, "
          f"{p['fuego_cerca'].sum()} alojamiento-meses tratados")

    filas = []
    m = pf.fepois("n_reviews ~ fuego_cerca | aloj_id^mes_cal + mes_estadia", data=p, vcov={"CRV1": "aloj_id"})
    t = m.tidy().loc["fuego_cerca"]
    efecto = np.exp(t["Estimate"]) - 1
    print("\n=== Volumen (fepois) ===")
    print(m.tidy().round(3).to_string())
    print(f"  Efecto: {efecto:+.0%} de reviews en meses de fuego cerca del foco "
          f"(IC95% {np.exp(t['2.5%']) - 1:+.0%} a {np.exp(t['97.5%']) - 1:+.0%}) | n usado: {m._N}")
    filas.append({"outcome": "n_reviews", "modelo": "fepois", "coef": t["Estimate"], "ic95_lo": t["2.5%"],
                  "ic95_hi": t["97.5%"], "efecto_pct": efecto, "n": m._N})

    q = p[p["n_reviews"] > 0].copy()
    m2 = pf.feols("nota_media ~ fuego_cerca | aloj_id^mes_cal + mes_estadia", data=q, weights="n_reviews",
                  vcov={"CRV1": "aloj_id"})
    t2 = m2.tidy().loc["fuego_cerca"]
    print("\n=== Nota media (feols, ponderada) ===")
    print(m2.tidy().round(3).to_string())
    filas.append({"outcome": "nota_media", "modelo": "feols", "coef": t2["Estimate"], "ic95_lo": t2["2.5%"],
                  "ic95_hi": t2["97.5%"], "efecto_pct": np.nan, "n": m2._N})
    pd.DataFrame(filas).to_csv("data/processed/fe_preliminar.csv", index=False)
    print("\nGuardado: data/processed/fe_preliminar.csv (PRELIMINAR, muestra chica)")


if __name__ == "__main__":
    main()
