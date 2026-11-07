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
    # Pestaña vacía donde escribe el escenario de Make (make/README.md): solo encabezados.
    tablas["booking_make"] = pd.DataFrame(columns=["fecha_corrida", "destino", "nombre", "tipo", "precio",
                                                   "moneda", "rating", "reviews", "lat", "lng", "url"])
    escribir_xlsx(tablas, os.path.join(OUT, "humo_mvp.xlsx"))


LEEME = [
    ("humo_mvp — datos del MVP de \"Humo en la temporada\"", None),
    ("Generado por src/export_sheets.py desde data/processed/ (repo montesquieu891/humo-en-la-temporada).", None),
    ("", None),
    ("Pestaña", "Contenido y fuente"),
    ("focos", "NASA FIRMS VIIRS S-NPP (procesamiento estándar), celda de 0,025° × día, solo eventos con ≥50 "
              "detecciones. Bajado el 06/11/2026. Dataset 1 de la consigna."),
    ("alojamientos", "Booking vía Apify voyager/booking-scraper, 07/11/2026. Distancia haversine al foco más "
                     "cercano de cada temporada y banda. precio_ref = estadía 15–17/01/2027 (2 noches, USD): "
                     "vacío en los que vienen de búsquedas sin fechas. Tarifa de referencia para el ROI, nunca outcome."),
    ("panel", "Alojamiento × mes de estadía × temporada (muestra de reviews, sin alojamientos truncados)."),
    ("reviews", "Booking vía Apify voyager/booking-reviews-scraper, 07/11/2026: 1 fila por review en la "
                "ventana nov-2024 a abr-2026. Sin nombres de usuarios."),
    ("booking_make", "Vacía: la llena el escenario de Make (Run Actor → Get Dataset Items → Add a Row)."),
    ("kpi_did", "Primer número y sus chequeos: DiD 2×2, placebo, sin Bariloche y FE alojamiento × mes "
                "calendario (preliminar). Mostrar siempre con su IC95%."),
    ("", None),
    ("Advertencia", "Muestra chica (29 alojamientos en el panel). El placebo invalida el DiD 2×2 de volumen; "
                    "con FE el efecto preliminar es −10% (IC −53% a +71%): con esta muestra no se detecta efecto."),
]


def escribir_xlsx(tablas: dict, ruta: str):
    """Un solo .xlsx con todas las pestañas, para subir a Drive y abrir como Google Sheet."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    fechas = {"focos": ["fecha"], "panel": ["mes"], "reviews": ["fecha_checkin", "mes"]}
    with pd.ExcelWriter(ruta, engine="openpyxl") as xw:
        pd.DataFrame(LEEME).to_excel(xw, sheet_name="leeme", index=False, header=False)
        for nombre, df in tablas.items():
            d = df.copy()
            for c in fechas.get(nombre, []):
                d[c] = pd.to_datetime(d[c], errors="coerce")
            d.to_excel(xw, sheet_name=nombre, index=False)
        wb = xw.book
        base, negrita = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True)
        for ws in wb.worksheets:
            for fila in ws.iter_rows():
                for celda in fila:
                    celda.font = base
            if ws.title == "leeme":
                ws["A1"].font = Font(name="Arial", size=12, bold=True)
                for r in (4, 12):
                    ws.cell(r, 1).font = negrita
                ws.column_dimensions["A"].width = 16
                ws.column_dimensions["B"].width = 110
                for fila in ws.iter_rows(min_col=2, max_col=2):
                    fila[0].alignment = Alignment(wrap_text=True, vertical="top")
                continue
            for celda in ws[1]:
                celda.font = negrita
                celda.fill = PatternFill("solid", fgColor="EEEDE9")
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for i, col in enumerate(tablas[ws.title].columns, start=1):
                valores = [len(str(v)) for v in tablas[ws.title][col].head(200)]
                ancho = min(max([len(str(col))] + valores) + 2, 45)
                ws.column_dimensions[get_column_letter(i)].width = ancho
                if col in fechas.get(ws.title, []):
                    for celda in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                        celda[0].number_format = "yyyy-mm-dd"
    print(f"{ruta}: {len(tablas)} pestañas de datos + leeme")


if __name__ == "__main__":
    main()
