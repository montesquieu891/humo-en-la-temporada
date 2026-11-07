"""
Humo en la temporada — CSV listos para subir a la Google Sheet "humo_mvp" (una pestaña por archivo).

Pestañas (data/processed/sheets/):
  focos.csv         FIRMS celda × día (Dataset 1 de la consigna), con temporada y fecha
  alojamientos.csv  alojamientos de Booking con localidad, distancia y banda por temporada
  panel.csv         panel apilado alojamiento × mes de estadía × temporada (para la serie por banda)
  reviews.csv       (extra) Dataset 2 de la consigna: 1 fila por review en la ventana
  kpi_did.csv       (extra) β del DiD 2×2 para el KPI del dashboard

Formato pensado para Sheets / Looker Studio: UTF-8, coma como separador, punto decimal,
fechas ISO (YYYY-MM-DD) y meses como YYYY-MM-01 para que Looker los tome como fecha.

Uso (desde humo/, después de firms_backfill.py, build_panel.py y did_baseline.py):
  python src/export_sheets.py
"""
import os

import pandas as pd

PROC = "data/processed"
OUT = os.path.join(PROC, "sheets")


def temporada_de(fecha: pd.Series) -> pd.Series:
    return (pd.to_datetime(fecha) >= "2025-06-01").map({False: "2025", True: "2026"})


def main():
    os.makedirs(OUT, exist_ok=True)

    focos = pd.read_csv(f"{PROC}/firms_celda_dia.csv")
    focos.insert(0, "temporada", temporada_de(focos["acq_date"]))
    focos = focos.rename(columns={"acq_date": "fecha", "celda_lat": "lat", "celda_lon": "lng"})
    focos = focos.round({"lat": 4, "lng": 4, "frp_total_mw": 1, "frp_max_mw": 1, "bright_ti4_max": 1,
                         "share_noche": 2})

    aloj = pd.read_csv(f"{PROC}/alojamientos.csv")
    aloj = aloj.round({"dist_2025_km": 1, "dist_2026_km": 1, "lat": 5, "lng": 5})

    panel = pd.read_csv(f"{PROC}/panel_stacked.csv", dtype={"temporada": str})
    panel["mes"] = panel["mes_estadia"] + "-01"
    panel = panel[["aloj_id", "nombre", "localidad", "tipo", "temporada", "mes", "mes_cal", "rel_t", "fuego",
                   "cerca", "banda", "dist_km", "n_reviews", "nota_media", "pct_humo", "precio_ref", "rating",
                   "lat", "lng"]].round({"dist_km": 1, "nota_media": 2, "pct_humo": 3})

    rev = pd.read_csv(f"{PROC}/reviews_dataset.csv")
    rev["mes"] = rev["mes_estadia"] + "-01"
    rev = rev.round({"dist_2025_km": 1, "dist_2026_km": 1})

    # KPI: las tres especificaciones juntas, para no mostrar solo el número más favorable.
    did = pd.read_csv(f"{PROC}/did_baseline.csv", dtype={"temporada": str}).assign(especificacion="DiD 2x2")
    rob_path, fe_path = f"{PROC}/did_baseline_robustez.csv", f"{PROC}/fe_preliminar.csv"
    if os.path.exists(rob_path):
        rob = pd.read_csv(rob_path).rename(columns={"variante": "especificacion"}).assign(temporada="apilado")
        did = pd.concat([did, rob], ignore_index=True)
    if os.path.exists(fe_path):
        fe = pd.read_csv(fe_path).rename(columns={"coef": "beta", "efecto_pct": "pct_contrafactual"})
        fe["especificacion"] = "FE alojamiento x mes calendario (preliminar)"
        fe["temporada"] = "ambas"
        did = pd.concat([did, fe.drop(columns=["modelo", "n"])], ignore_index=True)
    did = did[["especificacion", "outcome", "temporada", "beta", "ic95_lo", "ic95_hi", "pct_contrafactual",
               "n_cerca", "n_lejos"]].round(3)

    tablas = {"focos": focos, "alojamientos": aloj, "panel": panel, "reviews": rev, "kpi_did": did}
    for nombre, df in tablas.items():
        ruta = os.path.join(OUT, f"{nombre}.csv")
        df.to_csv(ruta, index=False, encoding="utf-8")
        print(f"{ruta}: {len(df)} filas × {len(df.columns)} columnas")


if __name__ == "__main__":
    main()
