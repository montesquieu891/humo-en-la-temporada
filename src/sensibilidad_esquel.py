"""
Humo en la temporada — sensibilidad del modelo FE a cómo se clasifica Esquel (07/11, PRELIMINAR).

Por qué (docs/decisiones_abiertas.md §4):
  1. En 2026 Esquel queda a 15–40 km del foco (control), pero el PN Los Alerces —su atractivo principal—
     estuvo evacuado/cerrado parte de la temporada: el control recibe el shock por la vía del acceso.
     Como Esquel es "cerca" en 2025, su febrero 2025 se compara contra su febrero 2026: si 2026 también
     estuvo afectado, el efecto se achica hacia 0.
  2. En 2025 los alojamientos de Esquel están a 14,2 ± 0,9 km del foco más cercano: su estado de
     "tratado" depende de que el umbral sea 15 km y no 14.

No cambia el modelo principal (src/fe_preliminar.py); son variantes:
  base              decisión 3 y 5 tal cual (umbral 15 km)
  sin_esquel        sin alojamientos de Esquel ni Trevelin
  acceso_parque     Esquel/Trevelin tratados también en 2026-01 y 2026-02 (exposición por el cierre del parque).
                    SUPUESTO: meses completos; la cronología (evacuación 07/01, reapertura de la RN 71 el
                    14/02/2026) viene de la propuesta del grupo y no está verificada en este repo.
  umbral_10/12/18/20  "cerca" = a ≤ N km del foco de cada temporada
  PLACEBO …         cada variante principal con el fuego corrido al mes anterior (2025-01 y 2025-12) y sin
                    los meses de fuego reales: tiene que dar ≈ 0

  n_reviews ~ fuego_cerca | aloj_id^mes_cal + mes_estadia   (fepois)
  nota_media ~ fuego_cerca | aloj_id^mes_cal + mes_estadia  (feols ponderado)

Uso (desde humo/): python src/sensibilidad_esquel.py
"""
import warnings

import numpy as np
import pandas as pd
import pyfixest as pf

FUEGO = {"2025": ["2025-02"], "2026": ["2026-01", "2026-02"]}
# Placebo (como did_baseline.py): el "fuego" se corre al mes anterior al inicio de cada evento.
# Si la variante es creíble, el placebo tiene que dar ≈ 0.
PLACEBO = {"2025": ["2025-01"], "2026": ["2025-12"]}
ESQUEL = ["Esquel", "Trevelin"]
FE = "aloj_id^mes_cal + mes_estadia"


def tratamiento(p: pd.DataFrame, umbral: float = 15, acceso: bool = False, meses: dict = FUEGO) -> pd.Series:
    t = (p["mes_estadia"].isin(meses["2025"]) & (p["dist_2025_km"] <= umbral)) | \
        (p["mes_estadia"].isin(meses["2026"]) & (p["dist_2026_km"] <= umbral))
    if acceso:
        t |= p["mes_estadia"].isin(meses["2026"]) & p["localidad"].isin(ESQUEL)
    return t.astype(int)


def estimar(p: pd.DataFrame, nombre: str) -> list[dict]:
    filas = []
    n_trat = p.loc[p["fuego_cerca"] == 1, "aloj_id"].nunique()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = pf.fepois(f"n_reviews ~ fuego_cerca | {FE}", data=p, vcov={"CRV1": "aloj_id"})
        t = m.tidy().loc["fuego_cerca"]
        filas.append({"variante": nombre, "outcome": "n_reviews", "coef": t["Estimate"], "ic95_lo": t["2.5%"],
                      "ic95_hi": t["97.5%"], "efecto_pct": np.exp(t["Estimate"]) - 1,
                      "efecto_pct_lo": np.exp(t["2.5%"]) - 1, "efecto_pct_hi": np.exp(t["97.5%"]) - 1,
                      "alojamientos": p["aloj_id"].nunique(), "alojamientos_tratados": n_trat,
                      "aloj_meses_tratados": int(p["fuego_cerca"].sum())})
        q = p[p["n_reviews"] > 0]
        m2 = pf.feols(f"nota_media ~ fuego_cerca | {FE}", data=q, weights="n_reviews", vcov={"CRV1": "aloj_id"})
        t2 = m2.tidy().loc["fuego_cerca"]
        filas.append({"variante": nombre, "outcome": "nota_media", "coef": t2["Estimate"], "ic95_lo": t2["2.5%"],
                      "ic95_hi": t2["97.5%"], "alojamientos": q["aloj_id"].nunique(),
                      "alojamientos_tratados": n_trat, "aloj_meses_tratados": int(q["fuego_cerca"].sum())})
    return filas


def main():
    p = pd.read_csv("data/processed/panel.csv")
    e = p.drop_duplicates("aloj_id")
    e = e[e["localidad"].isin(ESQUEL)]
    print(f"Panel: {p['aloj_id'].nunique()} alojamientos, {len(e)} de Esquel/Trevelin | distancia 2025: "
          f"{e['dist_2025_km'].mean():.1f} ± {e['dist_2025_km'].std():.1f} km | 2026: {e['dist_2026_km'].mean():.1f} km\n")

    variantes = [("base (15 km)", p.assign(fuego_cerca=tratamiento(p)))]
    s = p[~p["localidad"].isin(ESQUEL)]
    variantes.append(("sin Esquel/Trevelin", s.assign(fuego_cerca=tratamiento(s))))
    variantes.append(("acceso al parque 2026", p.assign(fuego_cerca=tratamiento(p, acceso=True))))
    for u in [10, 12, 18, 20]:
        variantes.append((f"umbral {u} km", p.assign(fuego_cerca=tratamiento(p, umbral=u))))
    # Placebos de las variantes principales: mismo tratamiento, meses falsos (sin los meses de fuego reales).
    sin_fuego = ~p["mes_estadia"].isin(FUEGO["2025"] + FUEGO["2026"])
    pp, sp = p[sin_fuego], s[~s["mes_estadia"].isin(FUEGO["2025"] + FUEGO["2026"])]
    variantes += [
        ("PLACEBO base", pp.assign(fuego_cerca=tratamiento(pp, meses=PLACEBO))),
        ("PLACEBO sin Esquel", sp.assign(fuego_cerca=tratamiento(sp, meses=PLACEBO))),
        ("PLACEBO acceso parque", pp.assign(fuego_cerca=tratamiento(pp, acceso=True, meses=PLACEBO))),
        ("PLACEBO umbral 10 km", pp.assign(fuego_cerca=tratamiento(pp, umbral=10, meses=PLACEBO))),
        ("PLACEBO umbral 12 km", pp.assign(fuego_cerca=tratamiento(pp, umbral=12, meses=PLACEBO))),
    ]

    filas = []
    for nombre, d in variantes:
        try:
            filas += estimar(d, nombre)
        except Exception as ex:  # p. ej. sin variación de tratamiento
            print(f"{nombre}: no se pudo estimar ({type(ex).__name__}: {ex})")
    r = pd.DataFrame(filas)
    r.to_csv("data/processed/sensibilidad_esquel.csv", index=False)
    for _, x in r.iterrows():
        if x["outcome"] == "n_reviews":
            txt = f"{x['efecto_pct']:+.0%} [{x['efecto_pct_lo']:+.0%}, {x['efecto_pct_hi']:+.0%}]"
        else:
            txt = f"{x['coef']:+.2f} [{x['ic95_lo']:+.2f}, {x['ic95_hi']:+.2f}]"
        print(f"{x['variante']:24s} {x['outcome']:10s} {txt:24s} | {x['alojamientos']:.0f} aloj, "
              f"{x['alojamientos_tratados']:.0f} tratados, {x['aloj_meses_tratados']:.0f} aloj-meses tratados")
    print("\nGuardado: data/processed/sensibilidad_esquel.csv (PRELIMINAR: 29 alojamientos, leer los IC)")


if __name__ == "__main__":
    main()
