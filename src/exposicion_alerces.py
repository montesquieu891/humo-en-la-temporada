"""
Humo en la temporada — episodios de incendio y ventanas de exposición por zona (reformulación Alerces 2025).

Solo usa NASA FIRMS (VIIRS S-NPP SP). No usa reseñas: la exposición se define ANTES de mirar Google Maps
(docs/preregistro_alerces.md).

Qué hace:
  1. Junta todos los crudos data/raw/firms_crudo_sp*.csv (bbox sur y norte, nov-2023 a mar-2026), limpia igual que
     firms_backfill.py (confianza n/h, sin duplicados) y vuelve a agrupar en eventos con la misma regla
     (DBSCAN 2 km ≈ 3 días, min_samples=3; foco = evento con ≥ 50 detecciones, decisión 8).
  2. Para cada localidad de referencia y cada radio (5, 15, 25 y 40 km): los días con al menos una detección de un
     evento ≥ 50 a esa distancia, agrupados en episodios (se unen días separados por ≤ 3 días).
  3. Verifica las zonas de comparación: ningún foco ≥ 50 a ≤ 40 km en la ventana del episodio 2025 ± 4 semanas.
  4. Figuras del EDA: mapa de focos 2025 con las localidades, y línea de tiempo semanal por zona.

Las localidades son puntos de referencia (centro aproximado) para el EDA y para elegir el grupo de comparación. En el
test, la exposición se calcula ficha por ficha con su coordenada de Google Maps y la misma regla.

Uso (desde humo/): python src/exposicion_alerces.py
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from firms_backfill import agrupar_eventos, limpiar  # noqa: E402

OUT = "data/processed/firms_alerces"
FIGS = "docs/figs"
MIN_DET = 50
RADIOS = [5, 15, 25, 40]
GAP_DIAS = 3
VENTANA_ANALISIS = ("2024-03-01", "2025-12-31")
MARGEN_COMPARACION_DIAS = 28
RADIO_COMPARACION_KM = 40

# Centros aproximados (WGS84). rol: candidata a "expuesta" o a "comparación" según la propuesta; lo confirma FIRMS.
LOCALIDADES = {
    "Villa Futalaufquen (PN Los Alerces)": (-42.895, -71.600, "expuesta"),
    "Trevelin": (-43.087, -71.464, "expuesta"),
    "Esquel": (-42.911, -71.319, "expuesta"),
    "Corcovado": (-43.538, -71.465, "comparación"),
    "Villa La Angostura": (-40.762, -71.646, "comparación"),
    "San Martín de los Andes": (-40.158, -71.353, "comparación"),
    "Junín de los Andes": (-39.950, -71.069, "comparación"),
    "Bariloche": (-41.133, -71.310, "referencia"),
    "El Bolsón": (-41.964, -71.534, "referencia"),
    "Cholila": (-42.513, -71.447, "referencia"),
}


def haversine(lat, lon, lats, lons):
    la1, lo1, la2, lo2 = map(np.radians, (lat, lon, lats, lons))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def cargar() -> pd.DataFrame:
    crudos = sorted(glob.glob("data/raw/firms_crudo_sp*.csv"))
    df = pd.concat([pd.read_csv(p) for p in crudos], ignore_index=True)
    print(f"Crudos: {crudos} → {len(df)} detecciones")
    # VIIRS 'type': 0 = presunto incendio de vegetación, 1 = volcán activo, 2 = otra fuente fija, 3 = sobre agua.
    # Verificado 07/11: el bbox norte incluye el volcán Villarrica (Chile), con 229 detecciones de tipo 1 que DBSCAN
    # agrupaba como "evento" de 196 detecciones en ene–mar 2024. Se descartan los tipos 1 y 2. El tipo 3 se conserva:
    # puede ser fuego real en la costa de un lago (en el bbox sur hay 157 y entraron al MVP).
    if "type" in df.columns:
        fijas = df["type"].isin([1, 2])
        print(f"Se descartan {fijas.sum()} detecciones de volcanes o fuentes fijas (type 1/2)")
        df = df[~fijas]
    d = agrupar_eventos(limpiar(df))
    d["acq_date"] = pd.to_datetime(d["acq_date"])
    tam = d.loc[d["evento"] >= 0].groupby("evento").size()
    d["evento50"] = d["evento"].isin(tam[tam >= MIN_DET].index)
    print(f"Tras limpiar: {len(d)} | cobertura {d['acq_date'].min().date()} → {d['acq_date'].max().date()} | "
          f"eventos: {len(tam)}, con ≥{MIN_DET}: {(tam >= MIN_DET).sum()} ({d['evento50'].sum()} detecciones)")
    meses = d.groupby(d["acq_date"].dt.to_period("M")).size()
    faltan = [str(m) for m in pd.period_range("2023-11", "2026-03", freq="M") if m not in meses.index]
    print(f"Meses sin ninguna detección (cobertura o sin fuego): {faltan or 'ninguno'}")
    return d


def episodios(dias: list) -> list[tuple]:
    if not dias:
        return []
    dias = sorted(dias)
    out, ini, fin = [], dias[0], dias[0]
    for x in dias[1:]:
        if (x - fin).days <= GAP_DIAS + 1:
            fin = x
        else:
            out.append((ini, fin))
            ini = fin = x
    out.append((ini, fin))
    return out


def tabla_episodios(f50: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for nombre, (lat, lon, rol) in LOCALIDADES.items():
        dist = haversine(lat, lon, f50["latitude"].to_numpy(), f50["longitude"].to_numpy())
        for r in RADIOS:
            sub = f50[dist <= r]
            for ini, fin in episodios(list(sub["acq_date"].dt.date.unique())):
                s = sub[(sub["acq_date"].dt.date >= ini) & (sub["acq_date"].dt.date <= fin)]
                d = haversine(lat, lon, s["latitude"].to_numpy(), s["longitude"].to_numpy())
                filas.append({"localidad": nombre, "rol": rol, "radio_km": r, "inicio": ini, "fin": fin,
                              "dias": (fin - ini).days + 1, "dias_con_foco": s["acq_date"].dt.date.nunique(),
                              "detecciones": len(s), "dist_min_km": round(float(d.min()), 1),
                              "eventos": ",".join(map(str, sorted(s["evento"].unique())))})
    return pd.DataFrame(filas)


def verificar_comparacion(f50: pd.DataFrame, ini, fin) -> pd.DataFrame:
    a = pd.Timestamp(ini) - pd.Timedelta(days=MARGEN_COMPARACION_DIAS)
    b = pd.Timestamp(fin) + pd.Timedelta(days=MARGEN_COMPARACION_DIAS)
    filas = []
    for nombre, (lat, lon, rol) in LOCALIDADES.items():
        s = f50[(f50["acq_date"] >= a) & (f50["acq_date"] <= b)]
        d = haversine(lat, lon, s["latitude"].to_numpy(), s["longitude"].to_numpy())
        w = f50[(f50["acq_date"] >= VENTANA_ANALISIS[0]) & (f50["acq_date"] <= VENTANA_ANALISIS[1])]
        dw = haversine(lat, lon, w["latitude"].to_numpy(), w["longitude"].to_numpy())
        otras = sorted(w.loc[dw <= RADIO_COMPARACION_KM, "acq_date"].dt.date.unique())
        filas.append({"localidad": nombre, "rol": rol,
                      "dist_min_km_ventana": round(float(d.min()), 1) if len(d) else np.nan,
                      f"limpia_{RADIO_COMPARACION_KM}km": bool(len(d) == 0 or d.min() > RADIO_COMPARACION_KM),
                      "episodios_40km_en_ventana_analisis": "; ".join(f"{i}→{j}" for i, j in episodios(otras))})
    return pd.DataFrame(filas)


def figuras(d: pd.DataFrame, f50: pd.DataFrame, ini, fin):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(FIGS, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    # 1) Mapa en dos paneles: región completa (dic-2024 a mar-2025) y zoom a la Comarca en el episodio 2025.
    s = f50[(f50["acq_date"] >= "2024-12-01") & (f50["acq_date"] <= "2025-03-31")]
    top = s.groupby("evento").size().sort_values(ascending=False)
    paleta = ["#2a6fdb", "#d9822b", "#1b998b", "#c03a2b", "#7d5ba6"]
    color = {ev: (paleta[k] if k < len(paleta) else "#9a9a9a") for k, ev in enumerate(top.index)}
    desplaz = {"Esquel": (6, -10), "Villa Futalaufquen (PN Los Alerces)": (-8, 8), "Trevelin": (6, -4),
               "Corcovado": (6, -4), "Junín de los Andes": (6, 2)}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 8.2), gridspec_kw={"width_ratios": [1, 1.25]})
    for ax, zoom in ((a1, False), (a2, True)):
        g0 = s if not zoom else s[(s["acq_date"] >= ini - pd.Timedelta(days=3)) & (s["acq_date"] <= fin)
                                  & s["latitude"].between(-43.65, -42.6) & s["longitude"].between(-72.1, -70.9)]
        pal_zoom = ["#c03a2b", "#d9822b", "#7d5ba6", "#1b998b", "#2a6fdb"]
        orden = g0.groupby("evento").size().sort_values(ascending=False).index
        for k, ev in enumerate(orden):
            g = g0[g0["evento"] == ev]
            c = color[ev] if not zoom else pal_zoom[k % len(pal_zoom)]
            lab = (f"evento {ev}: {g['acq_date'].min():%d/%m}–{g['acq_date'].max():%d/%m} ({len(g)} det.)"
                   if zoom else None)
            ax.scatter(g["longitude"], g["latitude"], s=5 if not zoom else 9, color=c, alpha=0.75,
                       linewidths=0, label=lab)
        if zoom:
            ax.legend(loc="lower left", fontsize=7.5, frameon=False, title="Eventos del episodio", title_fontsize=8)
        for nombre, (lat, lon, rol) in LOCALIDADES.items():
            if zoom and not (-43.7 <= lat <= -42.6):
                continue
            m = {"expuesta": "^", "comparación": "s", "referencia": "o"}[rol]
            ax.scatter(lon, lat, marker=m, s=46, facecolor="white", edgecolor="#222", zorder=5)
            dx, dy = desplaz.get(nombre, (6, 3))
            ha = "right" if dx < 0 else "left"
            ax.annotate(nombre, (lon, lat), xytext=(dx, dy), textcoords="offset points", fontsize=7.5,
                        color="#222", ha=ha)
        ax.set_aspect(1 / np.cos(np.radians(-41.5 if not zoom else -43.0)))
        ax.grid(color="#e5e5e5", linewidth=0.6)
        ax.set_xlabel("longitud")
    a1.set_ylabel("latitud")
    a1.set_xlim(-72.3, -70.5)
    a1.set_title("Región: focos dic-2024 a mar-2025", fontsize=9)
    a2.set_xlim(-72.1, -70.9)
    a2.set_ylim(-43.65, -42.6)
    a2.set_title(f"Comarca de los Alerces: episodio {ini:%d/%m}–{fin:%d/%m/%Y}", fontsize=9)
    from matplotlib.lines import Line2D
    h = [Line2D([], [], marker="o", ls="", color=color[ev], markersize=5,
                label=f"evento {ev}: {s.loc[s['evento'] == ev, 'acq_date'].min():%d/%m}–"
                      f"{s.loc[s['evento'] == ev, 'acq_date'].max():%d/%m/%Y} ({n} det.)")
         for ev, n in list(top.items())[:5]]
    h.append(Line2D([], [], marker="o", ls="", color="#9a9a9a", markersize=5, label=f"otros eventos ≥ {MIN_DET}"))
    h += [Line2D([], [], marker=m, ls="", markerfacecolor="white", markeredgecolor="#222", markersize=7, label=l)
          for m, l in (("^", "candidata expuesta"), ("s", "candidata a comparación"), ("o", "referencia"))]
    fig.legend(handles=h, loc="lower center", ncol=3, fontsize=7.5, frameon=False)
    fig.suptitle(f"Focos FIRMS VIIRS S-NPP (eventos con ≥ {MIN_DET} detecciones; sin volcanes)", fontsize=10)
    fig.tight_layout(rect=(0, 0.09, 1, 0.97))
    fig.savefig(f"{FIGS}/alerces_mapa_focos_2025.png", dpi=160)
    plt.close(fig)

    # 2) Línea de tiempo: detecciones por semana a ≤ 40 km de cada localidad (small multiples, misma escala).
    w0, w1 = pd.Timestamp("2023-11-01"), pd.Timestamp("2026-03-31")
    semanas = pd.date_range(w0, w1, freq="W-MON")
    nombres = list(LOCALIDADES)
    fig, axs = plt.subplots(len(nombres), 1, figsize=(9, 1.0 * len(nombres) + 1), sharex=True, sharey=True)
    for ax, nombre in zip(axs, nombres):
        lat, lon, rol = LOCALIDADES[nombre]
        dist = haversine(lat, lon, f50["latitude"].to_numpy(), f50["longitude"].to_numpy())
        g = f50[dist <= RADIO_COMPARACION_KM]
        serie = g.groupby(g["acq_date"].dt.to_period("W-SUN").dt.start_time).size().reindex(semanas, fill_value=0)
        ax.bar(serie.index, serie.values, width=6, color="#c03a2b" if rol == "expuesta" else "#2a6fdb")
        ax.axvspan(pd.Timestamp(ini), pd.Timestamp(fin), color="#f2c14e", alpha=0.35, linewidth=0)
        ax.set_yscale("symlog", linthresh=10)
        ax.text(0.005, 0.80, f"{nombre} ({rol})", transform=ax.transAxes, fontsize=7.5)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=7)
    axs[-1].set_xlabel("semana")
    fig.suptitle(f"Detecciones semanales de eventos ≥ {MIN_DET} a ≤ {RADIO_COMPARACION_KM} km de cada localidad "
                 "(escala log)\nFranja amarilla: episodio 2025 en la Comarca de los Alerces "
                 f"({ini:%d/%m}–{fin:%d/%m/%Y})", fontsize=9)
    fig.tight_layout()
    fig.savefig(f"{FIGS}/alerces_linea_tiempo.png", dpi=160)
    plt.close(fig)
    print(f"Figuras: {FIGS}/alerces_mapa_focos_2025.png, {FIGS}/alerces_linea_tiempo.png")


TEMPORADAS = {"2024": ("2023-11-01", "2024-04-30"), "2025": ("2024-11-01", "2025-04-30"),
              "2026": ("2025-11-01", "2026-04-30")}
SEMANAS_ANTES, SEMANAS_DESPUES = 26, 12  # ventana del event study de cada episodio (pre-registro §4)


def apilado(epi: pd.DataFrame, f50: pd.DataFrame) -> pd.DataFrame:
    """Los tres episodios de la Comarca con la misma regla que el de 2025 (días con foco ≥ 50 a ≤ 25 km de alguna
    localidad expuesta), y para cada uno: distancia de cada localidad al episodio, si la comparación está limpia
    (≤ 40 km, episodio ± 28 días) y si en su ventana de análisis (−26/+12 semanas) hay OTRO episodio a ≤ 40 km."""
    filas = []
    e = epi[(epi["rol"] == "expuesta") & (epi["radio_km"] == 25)].copy()
    e["inicio"], e["fin"] = pd.to_datetime(e["inicio"]), pd.to_datetime(e["fin"])
    for temp, (a, b) in TEMPORADAS.items():
        t = e[(e["inicio"] >= a) & (e["inicio"] <= b)]
        if t.empty:
            continue
        ini, fin = t["inicio"].min(), t["fin"].max()
        s_epi = f50[f50["acq_date"].between(ini, fin)]  # toda la región en esas fechas (para los controles)
        cerca = np.zeros(len(s_epi), dtype=bool)
        for lat, lon, rol in LOCALIDADES.values():
            if rol == "expuesta":
                cerca |= haversine(lat, lon, s_epi["latitude"].to_numpy(), s_epi["longitude"].to_numpy()) <= 25
        n_local = int(cerca.sum())
        v0 = ini - pd.Timedelta(weeks=SEMANAS_ANTES)
        v1 = ini + pd.Timedelta(weeks=SEMANAS_DESPUES)
        m0, m1 = ini - pd.Timedelta(days=MARGEN_COMPARACION_DIAS), fin + pd.Timedelta(days=MARGEN_COMPARACION_DIAS)
        for nombre, (lat, lon, rol) in LOCALIDADES.items():
            d_epi = haversine(lat, lon, s_epi["latitude"].to_numpy(), s_epi["longitude"].to_numpy())
            w = f50[f50["acq_date"].between(m0, m1)]
            d_m = haversine(lat, lon, w["latitude"].to_numpy(), w["longitude"].to_numpy())
            # Otros episodios a ≤ 40 km en la ventana de análisis, fuera del propio episodio ± 28 días.
            o = f50[f50["acq_date"].between(v0, v1) & ~f50["acq_date"].between(m0, m1)]
            d_o = haversine(lat, lon, o["latitude"].to_numpy(), o["longitude"].to_numpy())
            otros = episodios(sorted(o.loc[d_o <= RADIO_COMPARACION_KM, "acq_date"].dt.date.unique()))
            dmin = float(d_epi.min()) if len(d_epi) else np.nan
            nivel = "alta" if dmin <= 5 else "media" if dmin <= 25 else "gris" if dmin <= 40 else "lejos"
            filas.append({"temporada": temp, "episodio_inicio": ini.date(), "episodio_fin": fin.date(),
                          "dias_episodio": (fin - ini).days + 1, "detecciones_episodio": n_local,
                          "localidad": nombre, "rol": rol, "dist_min_episodio_km": round(dmin, 1),
                          "nivel": nivel,
                          "limpia_40km_ventana": bool(len(d_m) == 0 or d_m.min() > RADIO_COMPARACION_KM),
                          "dist_min_ventana_km": round(float(d_m.min()), 1) if len(d_m) else np.nan,
                          "otros_episodios_en_analisis": "; ".join(f"{i}→{j}" for i, j in otros)})
    return pd.DataFrame(filas)


def main():
    os.makedirs(OUT, exist_ok=True)
    d = cargar()
    f50 = d[d["evento50"]].copy()
    ev = f50.groupby("evento").agg(inicio=("acq_date", "min"), fin=("acq_date", "max"), detecciones=("frp", "size"),
                                   frp_total_mw=("frp", "sum"), lat_centro=("latitude", "mean"),
                                   lon_centro=("longitude", "mean")).sort_values("inicio")
    ev.round(3).to_csv(f"{OUT}/eventos50.csv")
    f50.to_csv(f"{OUT}/detecciones_eventos50.csv", index=False)

    epi = tabla_episodios(f50)
    epi.to_csv(f"{OUT}/episodios_por_localidad.csv", index=False)
    # Episodio 2025 de la Comarca: días con foco a ≤ 25 km de Esquel, Trevelin o Villa Futalaufquen en ene–mar 2025.
    e25 = epi[(epi["rol"] == "expuesta") & (epi["radio_km"] == 25) & (pd.to_datetime(epi["inicio"]) >= "2025-01-01")
              & (pd.to_datetime(epi["inicio"]) <= "2025-03-31")]
    ini, fin = pd.to_datetime(e25["inicio"]).min(), pd.to_datetime(e25["fin"]).max()
    print(f"\nEpisodio 2025 en la Comarca (≤ 25 km de alguna localidad expuesta): {ini.date()} → {fin.date()}")
    print(epi[(pd.to_datetime(epi["inicio"]) >= "2024-12-01") & (pd.to_datetime(epi["inicio"]) <= "2025-03-31")
              & (epi["rol"] != "referencia")].to_string(index=False))

    comp = verificar_comparacion(f50, ini, fin)
    comp.to_csv(f"{OUT}/verificacion_comparacion.csv", index=False)
    print(f"\nComparación: ningún foco ≥ {MIN_DET} a ≤ {RADIO_COMPARACION_KM} km entre "
          f"{(ini - pd.Timedelta(days=MARGEN_COMPARACION_DIAS)).date()} y "
          f"{(fin + pd.Timedelta(days=MARGEN_COMPARACION_DIAS)).date()}:")
    print(comp.to_string(index=False))
    figuras(d, f50, ini, fin)

    ap = apilado(epi, f50)
    ap.to_csv(f"{OUT}/episodios_apilados.csv", index=False)
    print("\nEpisodios para apilar (misma regla que 2025):")
    for temp, g in ap.groupby("temporada"):
        r = g.iloc[0]
        print(f"\n  {temp}: {r['episodio_inicio']} → {r['episodio_fin']} ({r['dias_episodio']} días, "
              f"{r['detecciones_episodio']} detecciones a ≤ 25 km de las localidades expuestas)")
        print(g[["localidad", "rol", "dist_min_episodio_km", "nivel", "limpia_40km_ventana", "dist_min_ventana_km",
                 "otros_episodios_en_analisis"]].to_string(index=False))
    print(f"\nGuardado en {OUT}/: eventos50.csv, detecciones_eventos50.csv, episodios_por_localidad.csv, "
          f"verificacion_comparacion.csv")


if __name__ == "__main__":
    main()
