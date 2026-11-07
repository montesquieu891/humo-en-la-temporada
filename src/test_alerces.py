"""
Humo en la temporada — test pre-registrado del episodio de incendio 2025 en la Comarca de los Alerces.

Sigue docs/preregistro_alerces.md (v3). Nada de lo que hay acá se eligió mirando el episodio: los parámetros
(semanas, ventanas, niveles de exposición, elegibilidad, modelo, robustez) están fijados en el pre-registro.

Principal (§1–§4, v3):
  panel ficha × semana (lunes a domingo, hora de Argentina), 19/08/2024 – 29/12/2025, reseñas de origen Google
  fepois(resenas ~ trat | ficha + rubro^semana), errores por ficha; trat = expuesta (alta|media) × semanas del
  17/02 y 24/02/2025. H1: β < 0 a una cola. Se considera superado solo si p (CRV1) < 0,05 Y p (permutación) < 0,05
  y las tendencias previas del event study no se rechazan al 10%.
Robustez (§5) y extensión apilada 2025 + 2026 (§8, reducida en v3).

Uso (desde humo/): python src/test_alerces.py
"""
import glob
import json
import os
import warnings

import numpy as np
import pandas as pd
import pyfixest as pf
from scipy.stats import chi2, norm

TZ = "America/Argentina/Buenos_Aires"
PROC = "data/processed"
OUT = f"{PROC}/test_alerces"
FIGS = "docs/figs"
VENTANA = ("2024-08-19", "2025-12-29")
EPISODIO = [pd.Timestamp("2025-02-17"), pd.Timestamp("2025-02-24")]
INICIO = EPISODIO[0]
EXCL_PERM = (pd.Timestamp("2025-01-20"), pd.Timestamp("2025-03-24"))  # episodio ± 4 semanas
FE = "place_id + rubro^semana"
VCOV = {"CRV1": "place_id"}
# Extensión 2026 (pre-registro §8): días y semanas del episodio, ventana −26/+12
EPI26 = ("2026-01-07", "2026-02-02")
SEM26 = [pd.Timestamp(x) for x in ("2026-01-05", "2026-01-12", "2026-01-19", "2026-01-26")]
VENT26 = ("2025-07-07", "2026-03-30")
VENT25 = ("2024-08-19", "2025-05-12")
COMP26 = ("2025-12-10", "2026-03-02")  # episodio 2026 ± 28 días (07/01 − 28 d, 02/02 + 28 d)


def haversine(lat, lon, lats, lons):
    la1, lo1, la2, lo2 = map(np.radians, (lat, lon, lats, lons))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def cargar():
    comp = pd.read_csv(f"{PROC}/maps_completitud.csv")
    m = pd.read_csv(f"{PROC}/maps_muestra.csv").set_index("place_id")
    fichas = comp[comp["estado"].isin(["completa", "sin_senal"])].copy()
    for c in ["lat", "lng", "zona_busqueda", "ciudad"]:
        fichas[c] = fichas["place_id"].map(m[c])
    filas = []
    for pid in fichas["place_id"]:
        for x in json.load(open(f"data/raw/maps/resenas_full/{pid}.json", encoding="utf-8")):
            if x.get("reviewOrigin") == "Google":
                filas.append({"place_id": pid, "fecha": x["publishedAtDate"], "nota": x.get("stars")})
    r = pd.DataFrame(filas)
    r["fecha"] = pd.to_datetime(r["fecha"], utc=True).dt.tz_convert(TZ).dt.tz_localize(None)
    r["semana"] = r["fecha"].dt.to_period("W-SUN").dt.start_time
    return fichas, r


def panel(fichas, r, desde, hasta, freq="W"):
    semanas = pd.date_range(desde, hasta, freq="W-MON")
    base = pd.MultiIndex.from_product([fichas["place_id"], semanas], names=["place_id", "semana"]).to_frame(index=False)
    agg = r.groupby(["place_id", "semana"]).agg(resenas=("fecha", "size"), nota_media=("nota", "mean")).reset_index()
    p = base.merge(agg, on=["place_id", "semana"], how="left")
    p["resenas"] = p["resenas"].fillna(0).astype(int)
    p = p.merge(fichas, on="place_id", how="left")
    return p


def fit(p, formula, var="trat", poisson=True, weights=None):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if poisson:
            m = pf.fepois(formula, data=p, vcov=VCOV)
        else:
            m = pf.feols(formula, data=p, vcov=VCOV, weights=weights)
    t = m.tidy().loc[var]
    return m, t["Estimate"], t["Std. Error"]


def fila(nombre, b, se, n_fichas, extra=None, poisson=True):
    d = {"analisis": nombre, "beta": b, "ee": se, "p_una_cola": norm.cdf(b / se),
         "efecto_pct": np.exp(b) - 1 if poisson else np.nan,
         "ic95_lo_pct": np.exp(b - 1.96 * se) - 1 if poisson else b - 1.96 * se,
         "ic95_hi_pct": np.exp(b + 1.96 * se) - 1 if poisson else b + 1.96 * se, "fichas": n_fichas}
    d.update(extra or {})
    return d


def main():
    os.makedirs(OUT, exist_ok=True)
    fichas, r = cargar()
    # Elegibilidad del test principal (v3): completa y ≥ 3 reseñas de Google entre el 19/08/2024 y el 09/02/2025.
    previas = r[(r["fecha"] >= "2024-08-19") & (r["fecha"] < "2025-02-10")].groupby("place_id").size()
    fichas["previas25"] = fichas["place_id"].map(previas).fillna(0).astype(int)
    fichas["expuesta"] = fichas["exposicion"].isin(["alta", "media"]).astype(int)
    elig = fichas[(fichas["estado"] == "completa") & (fichas["previas25"] >= 3)
                  & fichas["exposicion"].isin(["alta", "media", "comparacion"])].copy()
    print(f"Fichas elegibles: {len(elig)} | {elig['exposicion'].value_counts().to_dict()} | "
          f"reseñas de Google en la ventana: {r[r['place_id'].isin(elig['place_id'])].shape[0]}")

    p = panel(elig, r, *VENTANA)
    p["epi"] = p["semana"].isin(EPISODIO).astype(int)
    p["trat"] = p["expuesta"] * p["epi"]
    res = []

    # ---------------- 1) Test principal
    m0, b0, se0 = fit(p, f"resenas ~ trat | {FE}")
    # Permutación: cada par de semanas consecutivas fuera del episodio ± 4 semanas
    semanas = sorted(p["semana"].unique())
    placebos = []
    for i in range(len(semanas) - 1):
        a, b = semanas[i], semanas[i + 1]
        if EXCL_PERM[0] <= b and a <= EXCL_PERM[1]:
            continue
        q = p[~p["semana"].isin(EPISODIO)].copy()
        q["trat"] = q["expuesta"] * q["semana"].isin([a, b]).astype(int)
        try:
            placebos.append(fit(q, f"resenas ~ trat | {FE}")[1])
        except Exception:
            pass
    placebos = np.array(placebos)
    p_perm = float((placebos <= b0).mean())
    res.append(fila("PRINCIPAL 2025: expuestas vs comparación", b0, se0, p["place_id"].nunique(),
                    {"p_permutacion": p_perm, "n_placebos": len(placebos)}))
    pd.DataFrame({"beta_placebo": placebos}).to_csv(f"{OUT}/permutacion_principal.csv", index=False)

    # ---------------- 2) Event study y tendencias previas
    rel = ((p["semana"] - INICIO).dt.days // 7).clip(-26, 12)
    p["rel"] = rel.astype(int)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        es = pf.fepois(f"resenas ~ i(rel, expuesta, ref=-1) | {FE}", data=p, vcov=VCOV)
    tid = es.tidy()
    tid["rel"] = tid.index.str.extract(r"rel::(-?\d+)")[0].astype(float).values  # nombres: "rel::-26:expuesta"
    tid = tid.sort_values("rel")
    tid.to_csv(f"{OUT}/event_study_2025.csv")
    pre = tid[tid["rel"] <= -2]
    names = list(pre.index)
    allnames = list(es.coef().index)
    idx = [allnames.index(n) for n in names]
    bvec = es.coef().values[idx]
    V = np.asarray(es._vcov)[np.ix_(idx, idx)]
    W = float(bvec @ np.linalg.pinv(V) @ bvec)
    p_pre = float(chi2.sf(W, len(idx)))
    print(f"\nEvent study: tendencias previas (−26…−2), Wald = {W:.1f}, gl = {len(idx)}, p = {p_pre:.3f}")

    # ---------------- 3) Robustez (§5, ajustada en v3)
    p2 = p.copy()
    p2["trat_alta"] = (p2["exposicion"] == "alta").astype(int) * p2["epi"]
    p2["trat_media"] = (p2["exposicion"] == "media").astype(int) * p2["epi"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mg = pf.fepois(f"resenas ~ trat_alta + trat_media | {FE}", data=p2, vcov=VCOV)
    for v, nom in (("trat_alta", "alta vs comparación"), ("trat_media", "media vs comparación")):
        t = mg.tidy().loc[v]
        res.append(fila(f"R1 {nom}", t["Estimate"], t["Std. Error"], p2["place_id"].nunique()))
    for rub in sorted(p["rubro"].unique()):
        q = p[p["rubro"] == rub]
        if q.loc[q["expuesta"] == 0, "place_id"].nunique() < 2 or q.loc[q["expuesta"] == 1, "place_id"].nunique() < 2:
            res.append({"analisis": f"R2 rubro {rub}", "nota": "no estimable: menos de 2 fichas por grupo"})
            continue
        try:
            _, b, se = fit(q, "resenas ~ trat | place_id + semana")
            res.append(fila(f"R2 rubro {rub}", b, se, q["place_id"].nunique()))
        except Exception as e:
            res.append({"analisis": f"R2 rubro {rub}", "nota": f"no estimable: {type(e).__name__}"})
    for k, nom in ((1, "+1 semana"), (2, "+2 semanas")):
        q = p.copy()
        q["trat"] = q["expuesta"] * q["semana"].isin([s + pd.Timedelta(weeks=k) for s in EPISODIO]).astype(int)
        _, b, se = fit(q, f"resenas ~ trat | {FE}")
        res.append(fila(f"R3 episodio corrido {nom}", b, se, q["place_id"].nunique()))
    q = p.copy()
    q["trat"] = q["expuesta"] * q["semana"].between(pd.Timestamp("2025-02-17"), pd.Timestamp("2025-03-10")).astype(int)
    _, b, se = fit(q, f"resenas ~ trat | {FE}")
    res.append(fila("R3 episodio de 4 semanas (17/02–16/03)", b, se, q["place_id"].nunique()))
    q = p[p["zona_busqueda"] != "esquel"]
    _, b, se = fit(q, f"resenas ~ trat | {FE}")
    res.append(fila("R4 sin Esquel", b, se, q["place_id"].nunique()))
    res.append({"analisis": "R5 sin San Martín de los Andes", "nota": "no aplica: sin San Martín en el catálogo (v3)"})
    res.append({"analisis": "R6 comparación emparejada", "nota": "no ejecutado: con 18 fichas de comparación no hay "
                                                                  "emparejamiento útil por rubro (se declara)"})
    for freq, nom in (("2W-MON", "quincena"), ("MS", "mes")):
        q = p.copy()
        if freq == "MS":
            q["per"] = q["semana"].dt.to_period("M").dt.start_time
            epi_per = [pd.Timestamp("2025-02-01")]
        else:
            q["per"] = INICIO + pd.to_timedelta(((q["semana"] - INICIO).dt.days // 14) * 14, unit="D")
            epi_per = [INICIO]
        g = q.groupby(["place_id", "per", "rubro", "expuesta"], as_index=False)["resenas"].sum()
        g["trat"] = g["expuesta"] * g["per"].isin(epi_per).astype(int)
        _, b, se = fit(g, "resenas ~ trat | place_id + rubro^per")
        res.append(fila(f"R7 agregado por {nom}", b, se, g["place_id"].nunique()))
    # R8: con las fichas "sin señal" en el log
    elig8 = fichas[fichas["estado"].isin(["completa", "sin_senal"]) & (fichas["previas25"] >= 3)
                   & fichas["exposicion"].isin(["alta", "media", "comparacion"])]
    q = panel(elig8, r, *VENTANA)
    q["trat"] = q["expuesta"] * q["semana"].isin(EPISODIO).astype(int)
    _, b, se = fit(q, f"resenas ~ trat | {FE}")
    res.append(fila("R8 con fichas sin señal en el log", b, se, q["place_id"].nunique()))
    # R9: nota media semanal (feols ponderado por cantidad)
    qn = p[p["resenas"] > 0]
    _, b, se = fit(qn, f"nota_media ~ trat | {FE}", poisson=False, weights="resenas")
    res.append(fila("R9 nota media (puntos de 1 a 5)", b, se, qn["place_id"].nunique(), poisson=False))

    # ---------------- 4) Extensión apilada 2025 + 2026 (§8 reducida en v3)
    f50 = pd.read_csv(f"{PROC}/firms_alerces/detecciones_eventos50.csv", parse_dates=["acq_date"])
    d26 = f50[f50["acq_date"].between(*EPI26)]
    v26 = f50[f50["acq_date"].between(*COMP26)]
    fichas["dist26"] = [haversine(a, b, d26["latitude"].values, d26["longitude"].values).min()
                        for a, b in zip(fichas["lat"], fichas["lng"])]
    fichas["dist26_v"] = [haversine(a, b, v26["latitude"].values, v26["longitude"].values).min()
                          for a, b in zip(fichas["lat"], fichas["lng"])]
    niv26 = np.select([fichas["dist26"] <= 5, fichas["dist26"] <= 25, fichas["dist26"] <= 40],
                      ["alta", "media", "gris"], "lejos")
    comp26 = (fichas["zona_busqueda"] == "villa_la_angostura") & (fichas["dist26_v"] > 40)
    fichas["expo26"] = np.where(comp26, "comparacion", np.where(niv26 == "lejos", "lejos", niv26))
    prev26 = r[(r["semana"] >= pd.Timestamp(VENT26[0])) & (r["semana"] < SEM26[0])].groupby("place_id").size()
    prev25 = r[(r["semana"] >= pd.Timestamp(VENT25[0])) & (r["semana"] < EPISODIO[0])].groupby("place_id").size()
    partes = []
    for ep, expo_col, sem_epi, vent, prev in (("2025", "exposicion", EPISODIO, VENT25, prev25),
                                              ("2026", "expo26", SEM26, VENT26, prev26)):
        f = fichas[(fichas["estado"] == "completa") & fichas[expo_col].isin(["alta", "media", "comparacion"])].copy()
        f = f[f["place_id"].map(prev).fillna(0) >= 3]
        f["expuesta_ep"] = f[expo_col].isin(["alta", "media"]).astype(int)
        f["nivel_ep"] = f[expo_col]
        q = panel(f, r, *vent)
        q["episodio"] = ep
        q["trat"] = q["expuesta_ep"] * q["semana"].isin(sem_epi).astype(int)
        q["rel"] = ((q["semana"] - sem_epi[0]).dt.days // 7).clip(-26, 12).astype(int)
        partes.append(q)
        print(f"  episodio {ep}: {q['place_id'].nunique()} fichas | {f[expo_col].value_counts().to_dict()}")
    st = pd.concat(partes, ignore_index=True)
    st["ficha_ep"] = st["place_id"] + "_" + st["episodio"]
    FE_ST = "ficha_ep + rubro^semana^episodio"
    _, b, se = fit(st, f"resenas ~ trat | {FE_ST}")
    # Permutación del apilado: los dos episodios corridos k semanas hacia atrás, dentro del período previo
    plac = []
    for k in range(6, 25):
        q = st.copy()
        q["trat"] = q["expuesta_ep"] * q["rel"].between(-k, -k + (q["episodio"].map({"2025": 1, "2026": 3}))).astype(int)
        q = q[q["rel"] < 0]
        try:
            plac.append(fit(q, f"resenas ~ trat | {FE_ST}")[1])
        except Exception:
            pass
    res.append(fila("SECUNDARIO apilado 2025 + 2026", b, se, st["place_id"].nunique(),
                    {"p_permutacion": float((np.array(plac) <= b).mean()), "n_placebos": len(plac)}))
    q26 = st[st["episodio"] == "2026"]
    _, b, se = fit(q26, "resenas ~ trat | place_id + rubro^semana")
    res.append(fila("SECUNDARIO solo 2026", b, se, q26["place_id"].nunique()))
    q = st[st["zona_busqueda"] != "esquel"]
    _, b, se = fit(q, f"resenas ~ trat | {FE_ST}")
    res.append(fila("SECUNDARIO apilado sin Esquel", b, se, q["place_id"].nunique()))
    st2 = st.copy()
    st2["trat_alta"] = (st2["nivel_ep"] == "alta").astype(int) * st2["trat"]
    st2["trat_media"] = (st2["nivel_ep"] == "media").astype(int) * st2["trat"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mg2 = pf.fepois(f"resenas ~ trat_alta + trat_media | {FE_ST}", data=st2, vcov=VCOV)
    for v, nom in (("trat_alta", "alta"), ("trat_media", "media")):
        t = mg2.tidy().loc[v]
        res.append(fila(f"SECUNDARIO apilado gradiente: {nom}", t["Estimate"], t["Std. Error"], st2["place_id"].nunique()))

    out = pd.DataFrame(res)
    out.to_csv(f"{OUT}/resultados.csv", index=False)
    pd.set_option("display.width", 200)
    cols = ["analisis", "efecto_pct", "ic95_lo_pct", "ic95_hi_pct", "p_una_cola", "p_permutacion", "fichas", "nota"]
    show = out.reindex(columns=cols).copy()
    puntos = show["analisis"].str.startswith("R9")
    for c in ["efecto_pct", "ic95_lo_pct", "ic95_hi_pct"]:
        show[c] = [("" if pd.isna(x) else (f"{x:+.2f} pts" if pt else f"{x:+.0%}")) for x, pt in zip(show[c], puntos)]
    show.loc[puntos, "efecto_pct"] = out.loc[puntos, "beta"].map(lambda x: f"{x:+.2f} pts")
    print("\n" + show.to_string(index=False))
    ok = (out.loc[0, "p_una_cola"] < 0.05) and (p_perm < 0.05) and (p_pre >= 0.10)
    print(f"\nTEST PRINCIPAL (criterio pre-registrado): β = {b0:+.3f} ({np.exp(b0) - 1:+.0%}), p una cola CRV1 = "
          f"{out.loc[0, 'p_una_cola']:.3f}, p permutación = {p_perm:.3f} ({len(placebos)} placebos), "
          f"tendencias previas p = {p_pre:.3f} → {'SUPERADO' if ok else 'NO SUPERADO'}")
    json.dump({"beta": b0, "ee": se0, "p_crv1_una_cola": float(out.loc[0, "p_una_cola"]), "p_permutacion": p_perm,
               "p_tendencias_previas": p_pre, "superado": bool(ok), "fichas": int(p["place_id"].nunique())},
              open(f"{OUT}/principal.json", "w"), indent=2)
    figuras(p, tid, placebos, b0)


def figuras(p, tid, placebos, b0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    os.makedirs(FIGS, exist_ok=True)
    fig, axs = plt.subplots(3, 1, figsize=(9, 9.5))
    # Serie: reseñas por ficha y semana, expuestas vs comparación (media de 4 semanas)
    s = p.groupby(["semana", "expuesta"])["resenas"].mean().unstack().rolling(4, center=True).mean()
    ax = axs[0]
    ax.plot(s.index, s[1], color="#c03a2b", lw=2, label="expuestas (alta + media)")
    ax.plot(s.index, s[0], color="#2a6fdb", lw=2, label="comparación (Villa La Angostura)")
    ax.axvspan(EPISODIO[0], EPISODIO[1] + pd.Timedelta(days=6), color="#f2c14e", alpha=0.4, lw=0, label="episodio 2025")
    ax.set_ylabel("reseñas por ficha y semana\n(media móvil de 4 semanas)")
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Reseñas de Google por ficha y semana", fontsize=10)
    # Event study
    ax = axs[1]
    t = tid.dropna(subset=["rel"])
    ax.axhline(0, color="#888", lw=0.8)
    ax.axvspan(-0.5, 1.5, color="#f2c14e", alpha=0.4, lw=0)
    ax.errorbar(t["rel"], t["Estimate"], yerr=1.96 * t["Std. Error"], fmt="o", ms=3, color="#222", ecolor="#999",
                capsize=0, lw=1)
    ax.set_xlabel("semanas relativas al 17/02/2025 (−1 = referencia; extremos agrupados)")
    ax.set_ylabel("coeficiente (log)")
    ax.set_title("Event study: expuestas − comparación, por semana (IC 95%)", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    # Permutación
    ax = axs[2]
    ax.hist(placebos, bins=25, color="#9db8e6", edgecolor="white")
    ax.axvline(b0, color="#c03a2b", lw=2, label=f"β observado = {b0:+.2f}")
    ax.set_xlabel("β con episodios falsos (pares de semanas sin fuego)")
    ax.set_ylabel("cantidad")
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("Inferencia por permutación", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(f"{FIGS}/alerces_test_2025.png", dpi=160)
    plt.close(fig)
    print(f"Figura: {FIGS}/alerces_test_2025.png")


if __name__ == "__main__":
    main()
