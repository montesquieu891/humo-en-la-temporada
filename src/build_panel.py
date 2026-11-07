"""
Humo en la temporada — arma el panel alojamiento × mes de estadía.

Entradas:
  --listings  uno o más JSON/CSV de voyager/booking-scraper
  --reviews   JSON/CSV de voyager/booking-reviews-scraper
  --firms     firms_detecciones.csv (de firms_backfill.py)

Salidas (en --out, por defecto data/processed/):
  alojamientos.csv    1 fila por alojamiento: localidad, distancias y bandas por temporada
  reviews_clean.csv   1 fila por review: mes de estadía, nota, menciona_humo
  panel.csv           alojamiento × mes (nov-2024 a abr-2026): n_reviews, nota_media, pct_humo
  panel_stacked.csv   panel apilado por temporada (2025 y 2026) con cerca / fuego / rel_t,
                      listo para did_baseline.py y pyfixest

Uso (desde la carpeta humo/):
  python src/build_panel.py --listings data/raw/listings_*.json --reviews data/raw/reviews.json \
      --firms firms_detecciones.csv
"""
import argparse
import glob
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from booking_pilot_check import a_mes, campo, focos_por_temporada, haversine_min, leer  # noqa: E402

RADIO_CERCA_KM = 15
BANDAS = [0, 15, 40, 80, np.inf]
ETIQUETAS_BANDA = ["0-15", "15-40", "40-80", ">80"]

# Ventana de cada temporada (meses de estadía) e inicio del evento.
TEMPORADAS = {
    "2025": {"desde": "2024-11", "hasta": "2025-04", "inicio": "2025-02", "fuego": ["2025-02"]},
    "2026": {"desde": "2025-11", "hasta": "2026-04", "inicio": "2026-01", "fuego": ["2026-01", "2026-02"]},
}

# Centros aproximados de cada localidad (para asignar localidad por cercanía).
LOCALIDADES = {
    "Bariloche": (-41.133, -71.310),
    "Villa La Angostura": (-40.762, -71.646),
    "El Bolsón": (-41.964, -71.534),
    "Lago Puelo": (-42.066, -71.600),
    "El Hoyo": (-42.067, -71.517),
    "Epuyén": (-42.231, -71.367),
    "Cholila": (-42.513, -71.447),
    "Esquel": (-42.911, -71.319),
    "Trevelin": (-43.087, -71.464),
}

PATRON_HUMO = re.compile(r"\b(?:humo|incendi\w*|fuego\w*|ceniza\w*|smoke|fire\w*|wildfire\w*)\b", re.I)


def norm_url(u) -> str:
    return re.sub(r"[?#].*$", "", str(u)).rstrip("/").lower()


def meses(desde: str, hasta: str) -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(desde, hasta, freq="M")]


def localidad_mas_cercana(lat, lng) -> str:
    pts = np.array(list(LOCALIDADES.values()))
    d = [haversine_min(lat, lng, pts[i:i + 1]) for i in range(len(pts))]
    return list(LOCALIDADES)[int(np.argmin(d))]


def preparar_alojamientos(paths, focos, f_id=None) -> pd.DataFrame:
    lst = pd.concat([leer(p) for p in paths], ignore_index=True)
    c_lat, c_lng, c_id = campo(lst, "lat"), campo(lst, "lng"), campo(lst, "id", f_id)
    c_nrev = campo(lst, "n_reviews")
    if None in (c_lat, c_lng, c_id):
        sys.exit(f"Faltan columnas en listings. Disponibles: {list(lst.columns)[:40]}")
    for c in (c_lat, c_lng):  # el actor devuelve las coordenadas como texto
        lst[c] = pd.to_numeric(lst[c], errors="coerce")
    lst = lst.dropna(subset=[c_lat, c_lng]).copy()
    lst["aloj_id"] = lst[c_id].map(norm_url)
    # Un alojamiento puede venir de la corrida con fechas (trae precio) y de la sin fechas: preferir la primera.
    lst["_con_precio"] = pd.to_numeric(lst.get("price"), errors="coerce").notna()
    lst = lst.sort_values("_con_precio", ascending=False, kind="stable").drop_duplicates("aloj_id")
    out = pd.DataFrame({
        "aloj_id": lst["aloj_id"],
        "nombre": lst.get("name"),
        "tipo": lst.get("type"),
        # "stars" no se usa: 89–98% nulo en los datos reales (verificado 07/11).
        "precio_ref": pd.to_numeric(lst.get("price"), errors="coerce"),
        "moneda": lst.get("currency"),
        "rating": pd.to_numeric(lst.get("rating"), errors="coerce"),
        "n_reviews_total": pd.to_numeric(lst[c_nrev], errors="coerce") if c_nrev else np.nan,
        "lat": lst[c_lat].astype(float),
        "lng": lst[c_lng].astype(float),
    })
    out["localidad"] = [localidad_mas_cercana(a, b) for a, b in zip(out["lat"], out["lng"])]
    for temp, pts in focos.items():
        out[f"dist_{temp}_km"] = [haversine_min(a, b, pts) for a, b in zip(out["lat"], out["lng"])]
        out[f"banda_{temp}"] = pd.cut(out[f"dist_{temp}_km"], BANDAS, labels=ETIQUETAS_BANDA, right=True)
        out[f"cerca_{temp}"] = (out[f"dist_{temp}_km"] <= RADIO_CERCA_KM).astype(int)
    return out.reset_index(drop=True)


def preparar_reviews(paths, f_stay=None, f_hotel=None) -> pd.DataFrame:
    rev = pd.concat([leer(p) for p in paths], ignore_index=True)
    c_stay, c_hotel, c_score = campo(rev, "stay", f_stay), campo(rev, "hotel", f_hotel), campo(rev, "score")
    if None in (c_stay, c_hotel):
        sys.exit(f"Faltan columnas en reviews (usar --stay-field/--hotel-field). Disponibles: {list(rev.columns)[:40]}")
    textos = [c for c in rev.columns if re.search(r"text|liked|disliked|negative|positive|title|comment", c, re.I)]
    texto = rev[textos].fillna("").astype(str).agg(" ".join, axis=1) if textos else pd.Series("", index=rev.index)
    out = pd.DataFrame({
        "review_id": rev.get("id"),
        "aloj_id": rev[c_hotel].map(norm_url),
        "fecha_checkin": rev[c_stay].astype(str).str[:10],
        "mes_estadia": rev[c_stay].map(a_mes),
        "noches": pd.to_numeric(rev.get("numberOfNights"), errors="coerce"),
        "nota": pd.to_numeric(rev[c_score], errors="coerce") if c_score else np.nan,
        "tipo_viajero": rev.get("travelerType"),
        "menciona_humo": texto.str.contains(PATRON_HUMO).astype(int),
    })
    antes = len(out)
    out = out.drop_duplicates("review_id") if out["review_id"].notna().all() else out
    if antes - len(out):
        print(f"Reviews duplicadas entre archivos: {antes - len(out)} (se descartan)")
    print(f"Reviews: {len(out)} | con mes de estadía: {out['mes_estadia'].notna().mean():.0%} | "
          f"columnas de texto usadas: {textos or 'ninguna'}")
    return out.dropna(subset=["mes_estadia"])


def excluir_truncados(rev: pd.DataFrame, cobertura_path) -> pd.DataFrame:
    """Saca los alojamientos cuya historia de reviews quedó truncada (falla del actor o tope por hotel).
    En ellos los meses más viejos están subcontados y eso fabrica saltos falsos (verificado 07/11:
    el β apilado de volumen pasaba de −2,3 a −7,5 con ellos). Ver data/processed/reviews_cobertura.csv."""
    if not cobertura_path or not os.path.exists(cobertura_path):
        print("Sin reviews_cobertura.csv: no se excluyen truncados.")
        return rev
    cob = pd.read_csv(cobertura_path)
    trunc = set(cob.loc[cob["estado"].str.startswith("truncado"), "url"].map(norm_url))
    fuera = rev["aloj_id"].isin(trunc)
    print(f"Se excluyen {rev.loc[fuera, 'aloj_id'].nunique()} alojamientos truncados ({fuera.sum()} reviews).")
    return rev[~fuera]


def dataset_reviews(rev: pd.DataFrame, aloj: pd.DataFrame) -> pd.DataFrame:
    """Dataset 2 de la consigna: 1 fila por review en la ventana del panel, con coordenadas y distancia."""
    cols_aloj = ["aloj_id", "localidad", "lat", "lng", "dist_2025_km", "dist_2026_km"]
    d = rev[rev["mes_estadia"].between("2024-11", "2026-04")].merge(aloj[cols_aloj], on="aloj_id", how="left")
    return d[["review_id", "aloj_id", "localidad", "lat", "lng", "fecha_checkin", "mes_estadia", "noches",
              "nota", "tipo_viajero", "menciona_humo", "dist_2025_km", "dist_2026_km"]]


def armar_panel(aloj: pd.DataFrame, rev: pd.DataFrame) -> pd.DataFrame:
    todos_meses = meses("2024-11", "2026-04")
    con_reviews = aloj[aloj["aloj_id"].isin(rev["aloj_id"])]
    base = pd.MultiIndex.from_product([con_reviews["aloj_id"], todos_meses],
                                      names=["aloj_id", "mes_estadia"]).to_frame(index=False)
    agg = rev.groupby(["aloj_id", "mes_estadia"]).agg(
        n_reviews=("nota", "size"), nota_media=("nota", "mean"), pct_humo=("menciona_humo", "mean"))
    panel = base.merge(agg.reset_index(), on=["aloj_id", "mes_estadia"], how="left")
    panel["n_reviews"] = panel["n_reviews"].fillna(0).astype(int)
    # Un alojamiento cuenta como activo desde su primer mes con review en la muestra.
    primero = rev.groupby("aloj_id")["mes_estadia"].min().rename("primer_mes")
    panel = panel.merge(primero, on="aloj_id")
    panel = panel[panel["mes_estadia"] >= panel["primer_mes"]].drop(columns="primer_mes")
    panel["mes_cal"] = panel["mes_estadia"].str[5:7].astype(int)
    return panel.merge(aloj, on="aloj_id", how="left")


def apilar(panel: pd.DataFrame) -> pd.DataFrame:
    partes = []
    for temp, cfg in TEMPORADAS.items():
        p = panel[panel["mes_estadia"].isin(meses(cfg["desde"], cfg["hasta"]))].copy()
        p["temporada"] = temp
        p["cerca"] = p[f"cerca_{temp}"]
        p["dist_km"] = p[f"dist_{temp}_km"]
        p["banda"] = p[f"banda_{temp}"]
        p["fuego"] = p["mes_estadia"].isin(cfg["fuego"]).astype(int)
        ini = pd.Period(cfg["inicio"], "M")
        p["rel_t"] = [(pd.Period(m, "M") - ini).n for m in p["mes_estadia"]]
        partes.append(p)
    cols_temp = [c for c in panel.columns if re.match(r"(dist|banda|cerca)_20\d\d", c)]
    return pd.concat(partes, ignore_index=True).drop(columns=cols_temp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listings", nargs="+", required=True)
    ap.add_argument("--reviews", nargs="+", required=True)
    ap.add_argument("--firms", help="firms_detecciones.csv (sin él, focos aproximados)")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--stay-field")
    ap.add_argument("--hotel-field")
    ap.add_argument("--listing-id-field")
    ap.add_argument("--cobertura", default="data/processed/reviews_cobertura.csv",
                    help="estado por alojamiento (de run_booking.py); se excluyen los truncados")
    ap.add_argument("--incluir-truncados", action="store_true", help="no excluir truncados (sensibilidad)")
    a = ap.parse_args()

    paths = [p for patron in a.listings for p in glob.glob(patron)] or a.listings
    os.makedirs(a.out, exist_ok=True)
    focos = focos_por_temporada(a.firms)
    aloj = preparar_alojamientos(paths, focos, a.listing_id_field)
    rev_paths = [p for patron in a.reviews for p in glob.glob(patron)] or a.reviews
    rev = preparar_reviews(rev_paths, a.stay_field, a.hotel_field)
    rev_ds = dataset_reviews(rev, aloj)  # el dataset de la consigna conserva todas las reviews válidas
    if not a.incluir_truncados:
        rev = excluir_truncados(rev, a.cobertura)
    panel = armar_panel(aloj, rev)
    stacked = apilar(panel)

    aloj.to_csv(f"{a.out}/alojamientos.csv", index=False)
    rev.to_csv(f"{a.out}/reviews_clean.csv", index=False)
    rev_ds.to_csv(f"{a.out}/reviews_dataset.csv", index=False)
    panel.to_csv(f"{a.out}/panel.csv", index=False)
    stacked.to_csv(f"{a.out}/panel_stacked.csv", index=False)

    print(f"\nAlojamientos: {len(aloj)} (consigna 700–2.000) | con reviews en la muestra: {panel['aloj_id'].nunique()}")
    print(aloj.groupby("localidad").size().rename("alojamientos").to_string())
    print(f"Dataset de reviews (consigna): {len(rev_ds)} filas × {len(rev_ds.columns)} columnas | "
          f"nulos máx: {rev_ds.isna().mean().max():.0%}")
    print(f"\nPanel: {len(panel)} filas | apilado: {len(stacked)} filas")
    for temp in TEMPORADAS:
        s = stacked[stacked["temporada"] == temp]
        print(f"  Temporada {temp}: cerca={s.loc[s['cerca'] == 1, 'aloj_id'].nunique()} "
              f"lejos={s.loc[s['cerca'] == 0, 'aloj_id'].nunique()} alojamientos | "
              f"reviews en meses de fuego cerca: {s.loc[(s['cerca'] == 1) & (s['fuego'] == 1), 'n_reviews'].sum()}")


if __name__ == "__main__":
    main()
