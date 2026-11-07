"""
Humo en la temporada — baseline: diferencias en diferencias 2×2.

    β = (cerca_durante − cerca_antes) − (lejos_durante − lejos_antes)

- Unidad: alojamiento × temporada. Para cada uno se calcula
  Δ_i = media(outcome en meses de fuego) − media(outcome en meses previos de la ventana).
  β = media(Δ | cerca) − media(Δ | lejos).  Es el mismo número que la tabla 2×2 de medias,
  pero hecho por alojamiento para poder hacer bootstrap clusterizado.
- IC 95%: bootstrap por alojamiento (re-muestrea alojamientos, no filas).
- Outcomes: n_reviews (proxy de ocupación; principal) y nota_media (ponderada por reviews).
- Supuesto clave: sin fuego, cerca y lejos habrían seguido la misma tendencia
  (tendencias paralelas). Se chequea después con el event study, no acá.

Uso (desde humo/):
  python src/did_baseline.py --panel data/processed/panel_stacked.csv
"""
import argparse

import numpy as np
import pandas as pd

B = 2000
SEED = 42


def deltas(p: pd.DataFrame, y: str, ponderar: bool) -> pd.DataFrame:
    """Δ por alojamiento × temporada. Antes = rel_t < 0; durante = fuego == 1."""
    p = p[(p["rel_t"] < 0) | (p["fuego"] == 1)].copy()
    p["periodo"] = np.where(p["fuego"] == 1, "durante", "antes")
    if ponderar:  # nota media ponderada por cantidad de reviews
        p = p[p["n_reviews"] > 0]
        p["_w"] = p["n_reviews"]
        p["_yw"] = p[y] * p["_w"]
        g = p.groupby(["aloj_id", "temporada", "cerca", "periodo"])[["_yw", "_w"]].sum()
        m = (g["_yw"] / g["_w"]).unstack("periodo")
    else:
        m = p.groupby(["aloj_id", "temporada", "cerca", "periodo"])[y].mean().unstack("periodo")
    m = m.dropna(subset=["antes", "durante"]).reset_index()
    m["delta"] = m["durante"] - m["antes"]
    return m


def beta(d: pd.DataFrame) -> float:
    return d.loc[d["cerca"] == 1, "delta"].mean() - d.loc[d["cerca"] == 0, "delta"].mean()


def bootstrap(d: pd.DataFrame, rng) -> tuple[float, float]:
    ids = d["aloj_id"].unique()
    grupos = {i: g for i, g in d.groupby("aloj_id")}
    reps = []
    for _ in range(B):
        muestra = rng.choice(ids, size=len(ids), replace=True)
        db = pd.concat([grupos[i] for i in muestra], ignore_index=True)
        if db["cerca"].nunique() == 2:
            reps.append(beta(db))
    return tuple(np.percentile(reps, [2.5, 97.5]))


def tabla_2x2(d: pd.DataFrame) -> pd.DataFrame:
    t = d.groupby("cerca")[["antes", "durante"]].mean()
    t.index = t.index.map({1: "cerca (≤15 km)", 0: "lejos"})
    t["cambio"] = t["durante"] - t["antes"]
    return t


def reportar(nombre, d, rng):
    if d["cerca"].nunique() < 2:
        print(f"  {nombre}: falta grupo cerca o lejos con datos antes y durante. Se omite.")
        return {}
    b = beta(d)
    lo, hi = bootstrap(d, rng)
    # Contrafactual: cómo habrían estado los cercanos sin fuego = su nivel previo + el cambio de los lejanos.
    contraf = d.loc[d["cerca"] == 1, "antes"].mean() + (
        d.loc[d["cerca"] == 0, "durante"].mean() - d.loc[d["cerca"] == 0, "antes"].mean())
    pct = f" ({b / contraf:+.0%} respecto del contrafactual sin fuego)" if contraf else ""
    n1, n0 = (d["cerca"] == 1).sum(), (d["cerca"] == 0).sum()
    print(f"\n  {nombre}  [n cerca={n1}, lejos={n0}]")
    print(tabla_2x2(d).round(3).to_string())
    print(f"  β = {b:+.3f}{pct}   IC95% [{lo:+.3f}, {hi:+.3f}]"
          f"{'   ← significativo' if lo > 0 or hi < 0 else '   (el IC incluye 0)'}")
    return {"beta": b, "ic95_lo": lo, "ic95_hi": hi, "pct_contrafactual": b / contraf if contraf else None,
            "n_cerca": int(n1), "n_lejos": int(n0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="data/processed/panel_stacked.csv")
    ap.add_argument("--salida", default="data/processed/did_baseline.csv")
    a = ap.parse_args()
    rng = np.random.default_rng(SEED)
    panel = pd.read_csv(a.panel, dtype={"temporada": str})

    filas = []
    for y, ponderar, titulo in [("n_reviews", False, "VOLUMEN DE REVIEWS por alojamiento-mes (proxy de ocupación)"),
                                ("nota_media", True, "NOTA MEDIA (ponderada por reviews)")]:
        print(f"\n=== {titulo} ===")
        d_all = deltas(panel, y, ponderar)
        for temp in sorted(d_all["temporada"].unique()):
            d = d_all[d_all["temporada"] == temp]
            filas.append({"outcome": y, "temporada": temp, **reportar(f"Temporada {temp}", d, rng)})
        filas.append({"outcome": y, "temporada": "apilado", **reportar("Apilado (ambas temporadas)", d_all, rng)})

    pd.DataFrame(filas).to_csv(a.salida, index=False)

    # Robustez (buenas prácticas; NO cambia la especificación principal de arriba):
    #  - placebo: el "fuego" se corre al último mes previo (rel_t = -1) usando solo meses previos.
    #    Si β_placebo ≠ 0, cerca y lejos ya divergían antes del fuego (falla de tendencias paralelas).
    #  - sin Bariloche: el control queda solo con la Comarca/Esquel; aísla la estacionalidad propia
    #    de Bariloche (pico de enero mucho más fuerte que el de las cabañas).
    pre = panel[panel["rel_t"] < 0].copy()
    pre["fuego"] = (pre["rel_t"] == -1).astype(int)
    pre["rel_t"] = pre["rel_t"] + 1          # el mes placebo deja de contar como "antes"
    variantes = {"placebo (fuego falso en rel_t = -1)": pre,
                 "sin Bariloche": panel[panel["localidad"] != "Bariloche"]}
    rob = []
    print("\n=== ROBUSTEZ (apilado) ===")
    for nombre, p in variantes.items():
        for y, ponderar in [("n_reviews", False), ("nota_media", True)]:
            d = deltas(p, y, ponderar)
            print(f"\n  [{nombre}] {y}", end="")
            rob.append({"variante": nombre, "outcome": y, **reportar("", d, rng)})
    pd.DataFrame(rob).to_csv(a.salida.replace(".csv", "_robustez.csv"), index=False)
    print(f"\nGuardado: {a.salida}")
    print("Lectura: β < 0 en volumen = los alojamientos cerca del fuego perdieron reviews (y ocupación) "
          "respecto de los lejanos, netos de la estacionalidad común.")


if __name__ == "__main__":
    main()
