"""
Humo en la temporada — piloto de ventana larga (docs/decisiones_abiertas.md §3, opción C).

¿Cuánto baja el error estándar del modelo FE si el panel arranca en nov-2023 en vez de nov-2024?
Se mide sobre los MISMOS alojamientos (los re-pedidos con `run_booking.py ventana-larga`):

  corta: meses 2024-11 … 2026-04   (análisis actual)
  larga: meses 2023-11 … 2026-04   (un año más de comparación por mes calendario)

  n_reviews ~ fuego_cerca | aloj_id^mes_cal + mes_estadia   (fepois, errores por alojamiento)

fuego_cerca:
  2024-02 si el alojamiento está a ≤15 km de un foco de la temporada 2024 (eventos FIRMS ≥50 detecciones;
          PN Los Alerces, 26/01–07/02/2024). SUPUESTO a confirmar por el grupo: como Mallín Ahogado empezó
          el 30/01 y en 2025 cuenta solo febrero, en 2024 también cuenta solo febrero.
  2025-02 cerca de un foco 2025 · 2026-01 y 2026-02 cerca de un foco 2026 (decisión 4).

Salida:
  - EE de la ventana corta y la larga (CRV1 y bootstrap por alojamiento) → razón larga/corta;
  - el costo extra observado (reviews totales de la larga / reviews de la corta);
  - data/processed/piloto_ventana.csv: la tabla de potencia.csv reescalada por esa razón (MDE con ventana larga).

Uso (desde humo/, después de la corrida paga):
  python src/piloto_ventana.py --reviews data/raw/ventana_larga/reviews_desde_2023-11.json
Prueba sin datos nuevos (debe dar razón ≈ 1, porque no hay estadías anteriores a nov-2024):
  python src/piloto_ventana.py --reviews "data/raw/reviews*.json" --solo-completos
"""
import argparse
import glob
import os
import sys
import warnings

import numpy as np
import pandas as pd
import pyfixest as pf

sys.path.insert(0, os.path.dirname(__file__))
from build_panel import (armar_panel, excluir_truncados, focos_por_temporada,  # noqa: E402
                         haversine_min, preparar_alojamientos, preparar_reviews, RADIO_CERCA_KM)

FUEGO = {"2024": ["2024-02"], "2025": ["2025-02"], "2026": ["2026-01", "2026-02"]}
Z = 1.96 + 0.84


def expandir(patrones):
    return [p for pat in patrones for p in glob.glob(pat)] or patrones


def marcar_tratamiento(p: pd.DataFrame) -> pd.DataFrame:
    p = p.copy()
    t = np.zeros(len(p), dtype=bool)
    for temp, ms in FUEGO.items():
        col = f"cerca_{temp}"
        if col in p:
            t |= p["mes_estadia"].isin(ms).to_numpy() & (p[col] == 1).to_numpy()
    p["fuego_cerca"] = t.astype(int)
    return p


def ajustar(p: pd.DataFrame):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = pf.fepois("n_reviews ~ fuego_cerca | aloj_id^mes_cal + mes_estadia", data=p, vcov={"CRV1": "aloj_id"})
    t = m.tidy().loc["fuego_cerca"]
    return t["Estimate"], t["Std. Error"]


def bootstrap(p: pd.DataFrame, reps: int, rng) -> float:
    ids = p["aloj_id"].unique()
    grupos = {i: d for i, d in p.groupby("aloj_id")}
    coefs = []
    for _ in range(reps):
        elegidos = rng.choice(ids, size=len(ids), replace=True)
        d = pd.concat([grupos[i].assign(aloj_id=f"b{j}") for j, i in enumerate(elegidos)], ignore_index=True)
        try:
            coefs.append(ajustar(d)[0])
        except Exception:
            pass
    return float(np.std(coefs, ddof=1)), len(coefs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviews", nargs="+", required=True, help="reviews con ventana larga (JSON del piloto)")
    ap.add_argument("--listings", nargs="+", default=["data/raw/listings_*.json"])
    ap.add_argument("--firms", default="data/processed/firms_detecciones_eventos50.csv")
    ap.add_argument("--firms-2024", default="data/processed/firms_2024/firms_detecciones_eventos50.csv")
    ap.add_argument("--cobertura", default="data/processed/reviews_cobertura.csv",
                    help="para la prueba con datos viejos: excluir truncados")
    ap.add_argument("--solo-completos", action="store_true", help="excluir truncados según --cobertura")
    ap.add_argument("--reps", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    aloj = preparar_alojamientos(expandir(a.listings), focos_por_temporada(a.firms))
    f24 = pd.read_csv(a.firms_2024)
    pts24 = f24[["latitude", "longitude"]].to_numpy()
    aloj["dist_2024_km"] = [haversine_min(x, y, pts24) for x, y in zip(aloj["lat"], aloj["lng"])]
    aloj["cerca_2024"] = (aloj["dist_2024_km"] <= RADIO_CERCA_KM).astype(int)

    rev = preparar_reviews(expandir(a.reviews))
    if a.solo_completos:
        rev = excluir_truncados(rev, a.cobertura)
    # Completitud de la historia larga: si la paginación se cortó (falla del actor), la review publicada más
    # vieja queda lejos del cutoff. Criterio: alguna estadía en nov-2023…ene-2024, o el alojamiento abrió después.
    primera = rev.groupby("aloj_id")["mes_estadia"].min()
    print(f"Alojamientos en el archivo: {rev['aloj_id'].nunique()} | con estadías anteriores a nov-2024: "
          f"{(primera < '2024-11').sum()} | con alguna en nov-2023…ene-2024: {(primera <= '2024-01').sum()}")

    corta = marcar_tratamiento(armar_panel(aloj, rev[rev["mes_estadia"] >= "2024-11"], "2024-11", "2026-04"))
    larga = marcar_tratamiento(armar_panel(aloj, rev, "2023-11", "2026-04"))
    for nombre, p in [("corta", corta), ("larga", larga)]:
        tr = p.groupby("aloj_id")[["cerca_2024", "cerca_2025", "cerca_2026"]].max().sum().to_dict()
        print(f"  {nombre}: {len(p)} filas, {p['aloj_id'].nunique()} alojamientos, {p['n_reviews'].sum()} reviews, "
              f"{p['fuego_cerca'].sum()} alojamiento-meses tratados | cerca por temporada: {tr}")

    filas = {}
    for nombre, p in [("corta", corta), ("larga", larga)]:
        b, se = ajustar(p)
        sd, ok = bootstrap(p, a.reps, rng)
        filas[nombre] = {"beta": b, "ee_crv1": se, "ee_bootstrap": sd, "reps_ok": ok, "reviews": int(p["n_reviews"].sum()),
                         "alojamientos": p["aloj_id"].nunique()}
        print(f"  {nombre}: β = {b:+.3f} | EE CRV1 {se:.3f} | EE bootstrap {sd:.3f} ({ok} réplicas)")
    r = pd.DataFrame(filas).T
    razon_crv1 = r.loc["larga", "ee_crv1"] / r.loc["corta", "ee_crv1"]
    razon_boot = r.loc["larga", "ee_bootstrap"] / r.loc["corta", "ee_bootstrap"]
    razon = max(razon_crv1, razon_boot)  # conservador
    costo = r.loc["larga", "reviews"] / r.loc["corta", "reviews"]
    print(f"\nRazón EE larga/corta: CRV1 {razon_crv1:.2f} | bootstrap {razon_boot:.2f} → se usa {razon:.2f} (la mayor)")
    print(f"Costo relativo (reviews en ventana larga / corta): {costo:.2f}")

    pot = pd.read_csv("data/processed/potencia.csv")
    ee = np.maximum(pot["ee_vol_bootstrap"], pot["ee_vol_crv1_mediana"])
    out = pot[["escenario", "pedidos_cerca", "pedidos_lejos", "completos_estimados", "costo_usd", "mde_vol_pct"]].copy()
    out["razon_ee"] = razon
    out["mde_vol_pct_ventana_larga"] = -(1 - np.exp(-Z * ee * razon))
    out["costo_usd_ventana_larga"] = out["costo_usd"] * costo
    out.to_csv("data/processed/piloto_ventana.csv", index=False)
    r.to_csv("data/processed/piloto_ventana_ee.csv")
    print("\n" + out.round(3).to_string(index=False))
    print("\nGuardado: data/processed/piloto_ventana.csv y piloto_ventana_ee.csv")
    print("Ojo: con ~20 alojamientos la razón es ruidosa; mirarla junto con los IC, no como número exacto.")


if __name__ == "__main__":
    main()
