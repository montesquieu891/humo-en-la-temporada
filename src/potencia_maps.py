"""
Humo en la temporada — potencia del test de Maps con la varianza del piloto (pre-registro §6).

Usa SOLO el período previo (semanas del 04/03/2024 al 27/01/2025): el episodio real no se toca. En cada réplica:
  1. se arma una muestra con reemplazo de las fichas del piloto y se les asigna al azar el rótulo de "expuesta"
     o "comparación" según el escenario. En el período previo nadie está tratado, así que el ruido no depende del
     grupo. Con solo 3 fichas de comparación en el piloto, remuestrear por grupo hacía explotar el coeficiente en
     las semanas en que las 3 tienen 0 (separación; verificado 07/11);
  2. se elige al azar un "episodio" falso de 2 semanas consecutivas dentro del período previo;
  3. se estima fepois(resenas ~ trat | ficha + semana), con trat = expuesta × episodio falso.
El error estándar es el mayor entre el desvío robusto del coeficiente (1,4826 × MAD) y la mediana del EE
clusterizado. Las réplicas degeneradas (|β| > 5, por separación) se cuentan y se informan. Efecto mínimo detectable a una cola: α = 5%, potencia 80% → (1,645 + 0,84) × EE.

SUPUESTOS: las fichas nuevas se parecen a las del piloto (que están sesgadas hacia fichas grandes y visibles:
50–3.000 reseñas, primeras 15 de cada búsqueda). La muestra completa va a tener fichas más chicas, así que este
efecto mínimo es optimista.

Uso (desde humo/): python src/potencia_maps.py
"""
import glob
import json
import os
import warnings

import numpy as np
import pandas as pd
import pyfixest as pf

Z = 1.645 + 0.84
PREVIO = ("2024-03-04", "2025-01-27")  # lunes de la primera y la última semana del período previo
ESCENARIOS = [(10, 3), (20, 10), (40, 20), (80, 40), (120, 60), (200, 80)]  # (expuestas, comparación) elegibles
REPS = 300


def cargar() -> pd.DataFrame:
    sel = pd.read_csv("data/processed/maps_piloto_seleccion.csv")
    items = [x for p in glob.glob("data/raw/maps/resenas_piloto/*.json") for x in json.load(open(p, encoding="utf-8"))]
    r = pd.DataFrame(items)
    r = r[r["reviewOrigin"] == "Google"]
    r["fecha"] = pd.to_datetime(r["publishedAtDate"], utc=True).dt.tz_convert("America/Argentina/Buenos_Aires")
    r["semana"] = r["fecha"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time
    semanas = pd.date_range(*PREVIO, freq="W-MON")
    w = r[r["semana"].isin(semanas)].groupby(["placeId", "semana"]).size()
    base = pd.MultiIndex.from_product([sel["place_id"], semanas], names=["placeId", "semana"])
    p = w.reindex(base, fill_value=0).rename("resenas").reset_index()
    p = p.merge(sel[["place_id", "estrato", "rubro"]].rename(columns={"place_id": "placeId"}), on="placeId")
    # Elegibilidad del pre-registro: con reseñas desde jun-2024 o antes (sale Camping Las Rocas, primera en feb-2025).
    primera = r.groupby("placeId")["fecha"].min()
    viejas = primera[primera.dt.strftime("%Y-%m") <= "2024-06"].index
    p = p[p["placeId"].isin(viejas)]
    p["expuesta"] = (p["estrato"] != "comparacion").astype(int)
    return p


def estimar(d: pd.DataFrame, semanas, rng):
    k = rng.integers(4, len(semanas) - 2)  # deja 4 semanas previas al episodio falso
    epi = set(semanas[k:k + 2])
    d = d.assign(trat=(d["expuesta"] == 1) & d["semana"].isin(epi))
    d["trat"] = d["trat"].astype(int)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = pf.fepois("resenas ~ trat | placeId + semana", data=d, vcov={"CRV1": "placeId"})
    t = m.tidy().loc["trat"]
    return t["Estimate"], t["Std. Error"]


def main():
    p = cargar()
    semanas = np.array(sorted(p["semana"].unique()))
    g = p.groupby("placeId").agg(expuesta=("expuesta", "first"), media=("resenas", "mean"), rubro=("rubro", "first"))
    print(f"Fichas del piloto con período previo: {len(g)} ({int(g['expuesta'].sum())} expuestas, "
          f"{int((1 - g['expuesta']).sum())} de comparación) | semanas: {len(semanas)}")
    print(f"Reseñas por ficha y semana en el período previo: media {p['resenas'].mean():.2f}, "
          f"mediana {p['resenas'].median():.1f}, % ceros {(p['resenas'] == 0).mean():.0%}")
    todos = p["placeId"].unique()
    por_id = {i: d for i, d in p.groupby("placeId")}
    rng = np.random.default_rng(7)
    filas = []
    for n_e, n_c in ESCENARIOS:
        coefs, ses = [], []
        for _ in range(REPS):
            partes = []
            for j, i in enumerate(rng.choice(todos, size=n_e + n_c, replace=True)):
                partes.append(por_id[i].assign(placeId=f"b{j}", expuesta=int(j < n_e)))
            try:
                b, se = estimar(pd.concat(partes, ignore_index=True), semanas, rng)
                coefs.append(b)
                ses.append(se)
            except Exception:
                pass
        c, sv = np.array(coefs), np.array(ses)
        ok = np.abs(c) <= 5
        sd_rob = 1.4826 * np.median(np.abs(c[ok] - np.median(c[ok])))
        ee = max(sd_rob, np.median(sv[ok]))
        mde = 1 - np.exp(-Z * ee)
        filas.append({"expuestas": n_e, "comparacion": n_c, "ee_bootstrap_robusto": sd_rob,
                      "ee_crv1_mediana": np.median(sv[ok]), "mde_pct": -mde, "reps_ok": int(ok.sum()),
                      "reps_degeneradas": int((~ok).sum())})
        print(f"  {n_e:4d} expuestas + {n_c:3d} comparación → EE {ee:.3f} (robusto {sd_rob:.3f}, CRV1 "
              f"{np.median(sv[ok]):.3f}) | efecto mínimo detectable (una cola, 80%): {-mde:+.0%} | "
              f"degeneradas {int((~ok).sum())}/{len(c)}")
    out = pd.DataFrame(filas)
    out.to_csv("data/processed/potencia_maps.csv", index=False)
    print("\nGuardado: data/processed/potencia_maps.csv (optimista: el piloto tiene fichas grandes)")


if __name__ == "__main__":
    main()
