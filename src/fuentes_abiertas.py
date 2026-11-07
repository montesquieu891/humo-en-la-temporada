"""
Humo en la temporada — validación con fuentes abiertas (docs/preregistro_fuentes_abiertas.md).

  A. Visitas mensuales a Parques Nacionales  → data/raw/parques*.csv (bajado a mano: el portal tiene anti-bots)
  B. Empleo por departamento y rama CLAE2    → data/raw/puestos_depto_priv_por_clae2.csv
                                                + data/raw/diccionario_cod_depto.csv (CEP XXI, bajados a mano)
  C. Empleo por departamento y sector (OEDE) → se baja solo de argentina.gob.ar. EXPLORATORIO.

Modelo común: feols(log(y) ~ trat | unidad^mes_calendario + periodo), sin 2020–2021. Inferencia por permutación
sobre los meses sin fuego de la unidad tratada (pocos clusters: el error clusterizado no sirve).

Uso (desde humo/): python src/fuentes_abiertas.py
"""
import glob
import io
import os
import re
import warnings

import numpy as np
import pandas as pd
import pyfixest as pf
import requests

OUT = "data/processed/fuentes_abiertas"
H = {"User-Agent": "humo-capstone/0.1 (investigacion academica)"}
MESES_TRAT = {"2024": ["2024-02"], "2025": ["2025-02"], "2026": ["2026-01"]}
# Meses con fuego cerca de alguna unidad (FIRMS) que no pueden ser placebo, ni tratados ni controles limpios
EXCLUIR_PANDEMIA = [f"{a}-{m:02d}" for a in (2020, 2021) for m in range(1, 13)]


def vecinos(meses, k=2):
    out = set()
    for m in meses:
        p = pd.Period(m, "M")
        out |= {str(p + i) for i in range(-k, k + 1)}
    return out


def did_perm(df, unidad, y, tratada, meses_trat, excluir=(), etiqueta=""):
    """df con columnas [unidad, 'mes' (YYYY-MM), y]. Devuelve β (log), efecto %, p de permutación y chequeo previo."""
    d = df[~df["mes"].isin(EXCLUIR_PANDEMIA) & ~df["mes"].isin(excluir)].copy()
    d = d[d[y] > 0]
    d["ly"] = np.log(d[y])
    d["mc"] = d["mes"].str[5:7]
    d["um"] = d[unidad].astype(str) + "_" + d["mc"]

    def beta(meses):
        q = d.assign(trat=((d[unidad] == tratada) & d["mes"].isin(meses)).astype(int))
        if q["trat"].sum() == 0:
            return np.nan
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return pf.feols("ly ~ trat | um + mes", data=q).coef()["trat"]

    b = beta(meses_trat)
    todos_trat = [m for v in MESES_TRAT.values() for m in v]
    prohib = vecinos(todos_trat) | set(excluir) | set(EXCLUIR_PANDEMIA)
    cand = sorted(set(d.loc[d[unidad] == tratada, "mes"]) - prohib)
    plac = np.array([beta([m]) for m in cand])
    plac = plac[~np.isnan(plac)]
    p = float((plac <= b).mean()) if len(plac) else np.nan
    previos = [str(pd.Period(meses_trat[0], "M") - i) for i in range(3, 9)]
    bp = np.nanmean([beta([m]) for m in previos if m in set(d["mes"])])
    lo, hi = np.percentile(plac, [5, 95]) if len(plac) else (np.nan, np.nan)
    return {"analisis": etiqueta, "tratada": tratada, "meses": ",".join(meses_trat), "beta": b,
            "efecto_pct": np.exp(b) - 1, "p_permutacion": p, "n_placebos": len(plac),
            "previos_media": bp, "previos_ok": bool(lo <= bp <= hi) if len(plac) else None,
            "unidades": d[unidad].nunique()}


def oede():
    r = requests.get("https://www.argentina.gob.ar/sites/default/files/"
                     "departamento_series_empleo_y_salarios_mensual_sector_1.csv", headers=H, timeout=120)
    d = pd.read_csv(io.StringIO(r.content.decode("latin-1")), sep=None, engine="python")
    d["Empleo"] = pd.to_numeric(d["Empleo"].astype(str).str.replace(",", "."), errors="coerce")
    d["mes"] = d["Periodo"].astype(str).str[:4] + "-" + d["Periodo"].astype(str).str[4:6]
    res = []
    for sec in ("Servicios", "Comercio"):
        s = d[(d["Sector"] == sec) & d["Departamento"].isin(["FUTALEUFU", "CUSHAMEN", "LOS LAGOS", "LACAR"])]
        s = s[["Departamento", "mes", "Empleo"]]
        for ep, meses in (("2024", MESES_TRAT["2024"]), ("2025", MESES_TRAT["2025"])):
            sub = s[s["Departamento"] != "CUSHAMEN"]
            res.append(did_perm(sub, "Departamento", "Empleo", "FUTALEUFU", meses,
                                etiqueta=f"C OEDE {sec} Futaleufú {ep} (EXPLORATORIO)"))
        sub = s[s["Departamento"] != "FUTALEUFU"]
        res.append(did_perm(sub, "Departamento", "Empleo", "CUSHAMEN", ["2025-01", "2025-02"],
                            etiqueta=f"C OEDE {sec} Cushamen ene–feb 2025 (EXPLORATORIO)"))
    return res


def parques():
    """El portal publica las visitas por REGIÓN, no por parque (verificado 07/11 con los dos CSV bajados): el análisis
    pre-registrado de PN Los Alerces no se puede hacer. Queda una exploración: Patagonia contra las demás regiones.
    Mezcla Nahuel Huapi, Lanín, Los Glaciares, Los Alerces, etc. En feb-2025 hubo fuego en varios parques patagónicos.
    Los Alerces falta solo en nov-2024 (nota del archivo)."""
    f = "data/raw/serie-tiempo-parques-nacionales-mensual.csv"
    if not os.path.exists(f):
        print("A. Parques: falta data/raw/serie-tiempo-parques-nacionales-mensual.csv")
        return []
    d = pd.read_csv(f)
    d["mes"] = pd.to_datetime(d["indice_tiempo"], format="%Y-%m-%d").dt.strftime("%Y-%m")
    regiones = ["buenos_aires", "cordoba", "cuyo", "litoral", "norte", "patagonia"]
    largo = d.melt(id_vars="mes", value_vars=[f"{r}_total" for r in regiones], var_name="region", value_name="visitas")
    largo["region"] = largo["region"].str.replace("_total", "")
    print(f"A. Parques: solo por región ({', '.join(regiones)}), {d['mes'].min()} → {d['mes'].max()}. "
          f"El análisis por parque pre-registrado NO es ejecutable.")
    res = []
    for ep, meses in MESES_TRAT.items():
        res.append(did_perm(largo, "region", "visitas", "patagonia", meses,
                            etiqueta=f"A' Parques Patagonia vs otras regiones {ep} (EXPLORATORIO)"))
    return res


def cep():
    f = "data/raw/puestos_depto_priv_por_clae2.csv"
    dic = "data/raw/diccionario_cod_depto.csv"
    if not os.path.exists(f):
        print("B. CEP: falta data/raw/puestos_depto_priv_por_clae2.csv")
        return []
    if not os.path.exists(dic):
        # Códigos INDEC consultados en la API Georef (apis.datos.gob.ar) el 07/11/2026.
        d = pd.read_csv(f)
        cod = {"FUTALEUFU": 26035, "CUSHAMEN": 26014, "LOS LAGOS": 58070, "LACAR": 58056}
        print(f"B. CEP: {f} cubre {d['fecha'].min()} → {d['fecha'].max()} | códigos INDEC (Georef): {cod}")
        if d["fecha"].max() < "2024-02-01":
            print("   El archivo termina antes del primer episodio (feb-2024): el análisis B NO es ejecutable.")
            return [{"analisis": "B CEP CLAE 55/56", "nota": f"no ejecutable: el archivo termina en {d['fecha'].max()}"}]
        return []
    d = pd.read_csv(f, sep=None, engine="python")
    dd = pd.read_csv(dic, sep=None, engine="python", encoding_errors="replace")
    print(f"B. CEP: columnas {list(d.columns)} | diccionario {list(dd.columns)}")
    c_cod = next(c for c in dd.columns if re.search(r"cod.*depto|codigo_departamento|id_depto", c, re.I))
    c_nom = next(c for c in dd.columns if re.search(r"nombre.*depto|departamento", c, re.I) and c != c_cod)
    nombres = {"FUTALEUFU": r"futaleuf", "LOS LAGOS": r"^los lagos", "LACAR": r"l[aá]car", "CUSHAMEN": r"cushamen"}
    cod = {}
    for k, pat in nombres.items():
        m = dd[dd[c_nom].astype(str).str.contains(pat, case=False, regex=True)]
        if len(m):
            cod[k] = m[c_cod].iloc[0]
    print("   códigos:", cod)
    c_dc = next(c for c in d.columns if re.search(r"cod.*depto|codigo_departamento|id_depto", c, re.I))
    c_cl = next(c for c in d.columns if re.search(r"clae", c, re.I))
    c_t = next(c for c in d.columns if re.search(r"fecha|periodo|mes", c, re.I))
    c_y = next(c for c in d.columns if re.search(r"puestos|empleo", c, re.I))
    inv = {v: k for k, v in cod.items()}
    s = d[d[c_dc].isin(cod.values()) & d[c_cl].astype(str).isin(["55", "56"])].copy()
    s["Departamento"] = s[c_dc].map(inv)
    s["mes"] = pd.to_datetime(s[c_t].astype(str).str[:10], errors="coerce").dt.strftime("%Y-%m")
    s["y"] = pd.to_numeric(s[c_y], errors="coerce")
    res = []
    for rama, filtro in (("55+56", ["55", "56"]), ("55 alojamiento", ["55"]), ("56 gastronomía", ["56"])):
        g = s[s[c_cl].astype(str).isin(filtro)].groupby(["Departamento", "mes"], as_index=False)["y"].sum()
        for ep, meses in MESES_TRAT.items():
            sub = g[g["Departamento"].isin(["FUTALEUFU", "LOS LAGOS", "LACAR"])]
            if not set(meses) & set(sub["mes"]):
                continue
            tipo = "PRINCIPAL" if (ep == "2025" and rama == "55+56") else "secundario"
            res.append(did_perm(sub, "Departamento", "y", "FUTALEUFU", meses,
                                etiqueta=f"B CEP {rama} Futaleufú {ep} ({tipo})"))
        sub = g[g["Departamento"].isin(["CUSHAMEN", "LOS LAGOS", "LACAR"])]
        res.append(did_perm(sub, "Departamento", "y", "CUSHAMEN", ["2025-01", "2025-02"],
                            etiqueta=f"B CEP {rama} Cushamen ene–feb 2025 (hipótesis surgida de los datos)"))
    return res


def main():
    os.makedirs(OUT, exist_ok=True)
    res = parques() + cep() + oede()
    r = pd.DataFrame(res)
    r.to_csv(f"{OUT}/resultados.csv", index=False)
    pd.set_option("display.width", 220)
    show = r[["analisis", "efecto_pct", "p_permutacion", "n_placebos", "previos_ok", "unidades"]].copy()
    show["efecto_pct"] = show["efecto_pct"].map(lambda x: f"{x:+.1%}" if pd.notna(x) else "")
    print("\n" + show.to_string(index=False))
    print(f"\nGuardado: {OUT}/resultados.csv")


if __name__ == "__main__":
    main()
