"""
Humo en la temporada — análisis secundarios (decididos 07/11, sin reemplazar el análisis principal).

Misma especificación que src/fe_preliminar.py (efectos fijos alojamiento × mes calendario + año-mes,
errores clusterizados por alojamiento) aplicada a otros outcomes y a un chequeo de desplazamiento:

  1. Duración de la estadía
     - noches_total: noches asociadas a reviews (fepois). NO son pernoctaciones ni habitaciones vendidas.
     - noches_media: noches por review (feols ponderado por n_reviews). Hipótesis: el fuego acorta los
       viajes aunque la cantidad de estadías no caiga tanto.
  2. Composición del viajero: pct_familia, pct_pareja (feols ponderado por n_reviews).
  3. Desplazamiento: ¿los destinos lejanos (> 40 km) ganan reviews en los meses de fuego?
     n_reviews ~ fuego_cerca + fuego_lejos, con la banda 15–40 km como referencia. Si fuego_lejos > 0,
     el control lejano estaría "inflado" y el efecto principal exagerado. Es evidencia compatible con
     desplazamiento, no prueba: sin reservas ni itinerarios no se sabe si son los mismos viajeros.

Todo es PRELIMINAR (29 alojamientos en el panel): leer los intervalos, no los puntos.
Uso (desde humo/): python src/analisis_secundario.py
"""
import numpy as np
import pandas as pd
import pyfixest as pf

FUEGO = {"2025": ["2025-02"], "2026": ["2026-01", "2026-02"]}
FE = "aloj_id^mes_cal + mes_estadia"
VCOV = {"CRV1": "aloj_id"}


def preparar() -> pd.DataFrame:
    p = pd.read_csv("data/processed/panel.csv")
    temporada = np.where(p["mes_estadia"] <= "2025-05", "2025", "2026")
    p["dist_temp"] = np.where(temporada == "2025", p["dist_2025_km"], p["dist_2026_km"])
    fuego = p["mes_estadia"].isin(FUEGO["2025"] + FUEGO["2026"])
    p["fuego_cerca"] = (fuego & (p["dist_temp"] <= 15)).astype(int)
    p["fuego_lejos"] = (fuego & (p["dist_temp"] > 40)).astype(int)
    return p


def fila(m, var, outcome, espec, poisson):
    t = m.tidy().loc[var]
    efecto = (np.exp(t["Estimate"]) - 1) if poisson else np.nan
    return {"outcome": outcome, "especificacion": espec, "variable": var, "coef": t["Estimate"],
            "ic95_lo": t["2.5%"], "ic95_hi": t["97.5%"],
            "efecto_pct": efecto, "efecto_pct_lo": (np.exp(t["2.5%"]) - 1) if poisson else np.nan,
            "efecto_pct_hi": (np.exp(t["97.5%"]) - 1) if poisson else np.nan, "n": m._N}


def main():
    p = preparar()
    q = p[p["n_reviews"] > 0]
    filas = []

    m = pf.fepois(f"noches_total ~ fuego_cerca | {FE}", data=p, vcov=VCOV)
    filas.append(fila(m, "fuego_cerca", "noches_total", "FE (fepois)", True))
    for y in ["noches_media", "pct_familia", "pct_pareja"]:
        m = pf.feols(f"{y} ~ fuego_cerca | {FE}", data=q, weights="n_reviews", vcov=VCOV)
        filas.append(fila(m, "fuego_cerca", y, "FE (feols, ponderado)", False))

    # Desplazamiento: referencia = banda 15–40 km
    for y in ["n_reviews", "noches_total"]:
        m = pf.fepois(f"{y} ~ fuego_cerca + fuego_lejos | {FE}", data=p, vcov=VCOV)
        for v in ["fuego_cerca", "fuego_lejos"]:
            filas.append(fila(m, v, y, "desplazamiento (ref. 15–40 km)", True))

    r = pd.DataFrame(filas)
    r.to_csv("data/processed/analisis_secundario.csv", index=False)

    n = p.groupby("aloj_id").agg(cerca=("fuego_cerca", "max"), lejos=("fuego_lejos", "max"))
    print(f"Panel: {len(p)} filas, {p['aloj_id'].nunique()} alojamientos | con algún mes de fuego cerca: "
          f"{int(n['cerca'].sum())} | lejos (> 40 km): {int(n['lejos'].sum())}\n")
    for _, x in r.iterrows():
        if pd.notna(x["efecto_pct"]):
            txt = f"{x['efecto_pct']:+.0%} [{x['efecto_pct_lo']:+.0%}, {x['efecto_pct_hi']:+.0%}]"
        else:
            txt = f"{x['coef']:+.3f} [{x['ic95_lo']:+.3f}, {x['ic95_hi']:+.3f}]"
        sig = "  <- el IC excluye 0" if (x["ic95_lo"] > 0 or x["ic95_hi"] < 0) else ""
        print(f"{x['outcome']:13s} {x['especificacion']:31s} {x['variable']:12s} {txt}{sig}")
    print("\nGuardado: data/processed/analisis_secundario.csv (PRELIMINAR, muestra chica)")


if __name__ == "__main__":
    main()
