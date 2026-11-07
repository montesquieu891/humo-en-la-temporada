"""
Humo en la temporada — efecto mínimo detectable (MDE) del modelo FE según el tamaño de la muestra de reviews.

Pregunta: ¿cuántos alojamientos hay que bajar (y cuánto cuesta en Apify) para detectar una caída de X% en
el volumen de reviews con el modelo de la decisión 5 (src/fe_preliminar.py)?

  n_reviews ~ fuego_cerca | aloj_id^mes_cal + mes_estadia     (fepois, errores clusterizados por alojamiento)

Método: bootstrap estratificado de alojamientos REALES del panel actual (con su historia mes a mes completa),
reescalado al tamaño de cada escenario. Así se conserva la estacionalidad, la sobredispersión y la estructura
de tratamiento de los datos (por ejemplo, El Bolsón queda "cerca" en las dos temporadas). Para cada escenario:
  1. se arma una muestra con reemplazo, estrato por estrato, en las proporciones del universo a bajar;
  2. se estima el modelo y se guarda el coeficiente;
  3. el desvío del coeficiente entre réplicas es el error estándar con ese N;
  4. MDE (80% de potencia, α = 5%, dos colas) = (1,96 + 0,84) × EE, y en % = 1 − exp(−MDE).
     Se usa el MAYOR entre el EE de bootstrap y la mediana del EE clusterizado (CRV1) de las réplicas:
     con pocos alojamientos únicos por estrato, ninguno de los dos es confiable solo.

Estratos (a nivel alojamiento): s1 = cerca solo en 2025 (Esquel), s2 = cerca solo en 2026 (El Hoyo),
s3 = cerca en las dos (El Bolsón), nunca = nunca a ≤15 km (Bariloche y el resto).

Supuestos (marcados también en la salida):
- Los alojamientos nuevos se parecen a los del panel actual de su estrato. El estrato s2 tiene solo
  2 alojamientos en el panel: su heterogeneidad está subestimada.
- Tasa de alojamientos con historia completa = la de la muestra MVP (reviews_cobertura.csv): los
  truncados se excluyen del panel (decisión 9).
- Costo por alojamiento pedido = reviews estimadas en la ventana × USD 0,002 (tier FREE).
- El MDE es sobre el efecto total; el panel actual ya trae su propio efecto (−10%, no significativo),
  que no afecta al error estándar.

Uso (desde humo/): python src/potencia.py [--reps 200] [--seed 7]
"""
import argparse
import time
import warnings

import numpy as np
import pandas as pd
import pyfixest as pf

FUEGO = {"2025": ["2025-02"], "2026": ["2026-01", "2026-02"]}
Z = 1.96 + 0.84  # α = 5% dos colas, potencia 80%
USD_REVIEW = 0.002

# Escenarios: alojamientos PEDIDOS a Apify (cerca = ≤40 km de un foco con ≥10 reviews; lejos = control > 40 km)
ESCENARIOS = [
    ("actual (MVP)", 33, 9),
    ("≈ USD 10", 90, 10),
    ("≈ USD 20", 190, 15),
    ("≈ USD 30", 280, 20),
    ("universo cerca", 380, 30),
    ("universo + control", 380, 100),
]


def cargar_panel() -> pd.DataFrame:
    p = pd.read_csv("data/processed/panel.csv")
    p["fuego_cerca"] = (
        (p["mes_estadia"].isin(FUEGO["2025"]) & (p["cerca_2025"] == 1))
        | (p["mes_estadia"].isin(FUEGO["2026"]) & (p["cerca_2026"] == 1))
    ).astype(int)
    u = p.groupby("aloj_id")[["cerca_2025", "cerca_2026"]].max()
    s = (u["cerca_2025"] + 2 * u["cerca_2026"]).map({0: "nunca", 1: "s1", 2: "s2", 3: "s3"})
    p["estrato"] = p["aloj_id"].map(s)
    return p


def universo() -> dict:
    """Proporciones por estrato de los alojamientos 'cerca' a bajar (≥10 reviews, ≤40 km de un foco)."""
    a = pd.read_csv("data/processed/alojamientos.csv")
    dmin = a[["dist_2025_km", "dist_2026_km"]].min(axis=1)
    u = a[(a["n_reviews_total"] >= 10) & (dmin <= 40)]
    s = (u["cerca_2025"] + 2 * u["cerca_2026"]).map({0: "nunca", 1: "s1", 2: "s2", 3: "s3"})
    lejos = a[(a["n_reviews_total"] >= 10) & (dmin > 40)]
    return {"prop_cerca": s.value_counts(normalize=True).to_dict(), "n_cerca": len(u), "n_lejos": len(lejos)}


def parametros_cobertura() -> dict:
    c = pd.read_csv("data/processed/reviews_cobertura.csv")
    g = c.groupby("grupo")
    completo = g["estado"].apply(lambda x: (x == "completo").mean())
    rev = g["rev_est"].mean()
    return {"tasa_cerca": completo["cerca_40km"], "tasa_lejos": completo["control_bariloche"],
            "usd_cerca": rev["cerca_40km"] * USD_REVIEW, "usd_lejos": rev["control_bariloche"] * USD_REVIEW}


def asignar(n_cerca_ef: float, n_lejos_ef: float, prop: dict) -> dict:
    n = {k: n_cerca_ef * prop.get(k, 0) for k in ["s1", "s2", "s3", "nunca"]}
    n["nunca"] += n_lejos_ef
    n = {k: max(1, int(round(v))) for k, v in n.items()}
    return n


def remuestrear(p: pd.DataFrame, n_por_estrato: dict, rng) -> pd.DataFrame:
    partes = []
    for est, n in n_por_estrato.items():
        ids = p.loc[p["estrato"] == est, "aloj_id"].unique()
        elegidos = rng.choice(ids, size=n, replace=True)
        for j, i in enumerate(elegidos):
            d = p[p["aloj_id"] == i].copy()
            d["aloj_id"] = f"{est}_{j}"
            partes.append(d)
    return pd.concat(partes, ignore_index=True)


def estimar(d: pd.DataFrame):
    out = {"vol": np.nan, "vol_se": np.nan, "nota": np.nan, "nota_se": np.nan}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            m = pf.fepois("n_reviews ~ fuego_cerca | aloj_id^mes_cal + mes_estadia", data=d,
                          vcov={"CRV1": "aloj_id"})
            t = m.tidy().loc["fuego_cerca"]
            out["vol"], out["vol_se"] = t["Estimate"], t["Std. Error"]
        except Exception:
            pass
        try:
            q = d[d["n_reviews"] > 0]
            m2 = pf.feols("nota_media ~ fuego_cerca | aloj_id^mes_cal + mes_estadia", data=q,
                          weights="n_reviews", vcov={"CRV1": "aloj_id"})
            t2 = m2.tidy().loc["fuego_cerca"]
            out["nota"], out["nota_se"] = t2["Estimate"], t2["Std. Error"]
        except Exception:
            pass
    return out


def potencia(efecto_pct: float, ee: float) -> float:
    from scipy.stats import norm
    b = abs(np.log(1 + efecto_pct))
    return norm.cdf(b / ee - 1.96) + norm.cdf(-b / ee - 1.96)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    p = cargar_panel()
    uni, cob = universo(), parametros_cobertura()
    print(f"Panel actual: {p['aloj_id'].nunique()} alojamientos | por estrato: "
          f"{p.groupby('estrato')['aloj_id'].nunique().to_dict()}")
    print(f"Universo a bajar: {uni['n_cerca']} cerca (≥10 reviews, ≤40 km) + {uni['n_lejos']} lejos disponibles | "
          f"proporciones cerca: { {k: round(v, 2) for k, v in uni['prop_cerca'].items()} }")
    print(f"Cobertura MVP: completos {cob['tasa_cerca']:.0%} cerca, {cob['tasa_lejos']:.0%} lejos | "
          f"costo por alojamiento pedido: USD {cob['usd_cerca']:.3f} cerca, USD {cob['usd_lejos']:.3f} lejos\n")

    real = estimar(p)
    print(f"Modelo con el panel real: volumen β = {real['vol']:+.3f} (EE CRV1 {real['vol_se']:.3f}) | "
          f"nota β = {real['nota']:+.3f} (EE {real['nota_se']:.3f})\n")

    filas = []
    for nombre, n_c, n_l in ESCENARIOS:
        n_l = min(n_l, uni["n_lejos"])
        n_c = min(n_c, uni["n_cerca"])
        ef_c, ef_l = n_c * cob["tasa_cerca"], n_l * cob["tasa_lejos"]
        alloc = asignar(ef_c, ef_l, uni["prop_cerca"])
        t0 = time.time()
        res = pd.DataFrame([estimar(remuestrear(p, alloc, rng)) for _ in range(args.reps)])
        ee_vol, ee_nota = res["vol"].std(), res["nota"].std()
        ee_crv1 = res["vol_se"].median()
        ee_cons = max(ee_vol, ee_crv1)  # conservador: el mayor de los dos errores estándar
        mde_vol = 1 - np.exp(-Z * ee_cons)
        fila = {"escenario": nombre, "pedidos_cerca": n_c, "pedidos_lejos": n_l,
                "completos_estimados": sum(alloc.values()), "por_estrato": str(alloc),
                "costo_usd": n_c * cob["usd_cerca"] + n_l * cob["usd_lejos"],
                "ee_vol_bootstrap": ee_vol, "ee_vol_crv1_mediana": ee_crv1,
                "mde_vol_pct": -mde_vol, "mde_vol_pct_bootstrap": -(1 - np.exp(-Z * ee_vol)),
                "mde_vol_pct_crv1": -(1 - np.exp(-Z * ee_crv1)), "mde_nota_puntos": -Z * ee_nota,
                "ee_nota_bootstrap": ee_nota, "reps_ok": int(res["vol"].notna().sum())}
        for e in [-0.10, -0.20, -0.30]:
            fila[f"potencia_{int(-e * 100)}pct"] = potencia(e, ee_cons)
        filas.append(fila)
        print(f"{nombre:13s} pedidos {n_c:3d}+{n_l:3d} → ~{fila['completos_estimados']:3d} completos | "
              f"USD {fila['costo_usd']:5.1f} | EE {ee_vol:.3f} (CRV1 {fila['ee_vol_crv1_mediana']:.3f}) | "
              f"MDE volumen {-mde_vol:+.0%} | MDE nota {-Z * ee_nota:+.2f} | "
              f"potencia −20%: {fila['potencia_20pct']:.0%} | {time.time() - t0:.0f}s")

    r = pd.DataFrame(filas)
    r.to_csv("data/processed/potencia.csv", index=False)
    print("\nGuardado: data/processed/potencia.csv")
    print("SUPUESTOS: los alojamientos nuevos se parecen a los del panel actual de su estrato; s2 (El Hoyo) "
          "tiene 2 alojamientos; cobertura y costo según la muestra MVP.")


if __name__ == "__main__":
    main()
