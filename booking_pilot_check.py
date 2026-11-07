"""
Humo en la temporada — evaluador de la prueba de factibilidad (Dataset 2: Booking).

Lee los exports de Apify y responde la pregunta que puede matar el proyecto:
  ¿hay suficientes reviews con fecha de estadía, en alojamientos cerca del fuego,
   durante los meses de fuego?

Entradas (exportar desde Apify como JSON o CSV):
  --listings  resultado de voyager/booking-scraper (todos los alojamientos)
  --reviews   resultado de voyager/booking-reviews-scraper (muestra de ~30 alojamientos)
  --firms     (opcional) firms_detecciones.csv de firms_backfill.py, para medir la
              distancia real al fuego. Sin él, usa puntos de referencia aproximados.

Uso:
  pip install pandas numpy
  python booking_pilot_check.py --listings listings.json --reviews reviews.json --firms firms_detecciones.csv

Criterios de descarte (del plan):
  - menos de 300 reviews (extrapoladas) en zonas tratadas durante los meses de fuego, o
  - menos del 70% de las reviews con fecha de estadía.
Si los nombres de campo del actor no coinciden, pasarlos con --stay-field, --hotel-field, etc.
"""
import argparse
import glob
import json
import re
import sys

import numpy as np
import pandas as pd

RADIO_TRATADO_KM = 15
MIN_REVIEWS_TRATADAS = 300
MIN_SHARE_CON_FECHA = 0.70

# Meses de estadía con fuego activo (la fecha de estadía de Booking viene por mes).
MESES_FUEGO = {
    "2025": ["2025-02"],              # Mallín Ahogado, desde el 30/01/2025
    "2026": ["2026-01", "2026-02"],   # Chubut, desde el 05/01/2026
}

# Fallback si no se pasa --firms: puntos APROXIMADOS de cada foco (verificar con FIRMS).
FOCOS_APROX = {
    "2025": [(-41.83, -71.50)],                                    # Mallín Ahogado
    "2026": [(-42.12, -71.47), (-42.23, -71.37), (-42.51, -71.45),  # Pto. Patriada, Epuyén, Cholila
             (-42.90, -71.60)],                                     # PN Los Alerces
}

MESES = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
MESES.update({m: i for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
     "septiembre", "octubre", "noviembre", "diciembre"], start=1)})

CANDIDATOS = {
    "stay": ["stayDate", "dateOfStay", "stayedIn", "stayMonth", "checkInDate", "checkinDate",
             "checkIn", "stay_date", "date_of_stay"],
    "hotel": ["hotelUrl", "hotel_url", "startUrl", "url", "hotelId", "hotel_id", "propertyUrl"],
    "score": ["rating", "score", "reviewScore", "review_score"],
    "lat": ["location.lat", "location/lat", "lat", "latitude"],
    "lng": ["location.lng", "location/lng", "lng", "lon", "longitude"],
    "id": ["url", "id", "hotelId"],
    "n_reviews": ["reviews", "reviewsCount", "reviewCount"],
}


def leer(path: str) -> pd.DataFrame:
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            return pd.json_normalize(json.load(f))
    return pd.read_csv(path)


def campo(df, tipo, forzado=None):
    if forzado:
        return forzado
    for c in CANDIDATOS[tipo]:
        if c in df.columns:
            return c
    return None


def a_mes(valor) -> str | None:
    """'2026-01-14', 'January 2026', 'enero de 2026', 'Stayed in Jan 2026' -> '2026-01'."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return None
    s = str(valor).strip().lower()
    m = re.search(r"(\d{4})-(\d{1,2})", s)
    if m:
        # Booking usa 1999-12-26 como centinela cuando falta la fecha de estadía (verificado 07/11).
        if int(m.group(1)) < 2010:
            return None
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.search(r"([a-záéíóú]+)\.?\s*(?:de\s*)?(20\d\d)", s)
    if m:
        nombre = m.group(1)
        for k, v in MESES.items():
            if k.startswith(nombre[:3]):
                return f"{m.group(2)}-{v:02d}"
    return None


def haversine_min(lat, lng, puntos: np.ndarray) -> float:
    if len(puntos) == 0:
        return np.inf
    lat1, lng1 = np.radians(lat), np.radians(lng)
    lat2, lng2 = np.radians(puntos[:, 0]), np.radians(puntos[:, 1])
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return float((2 * 6371 * np.arcsin(np.sqrt(a))).min())


def focos_por_temporada(firms_path):
    if not firms_path:
        print("Sin --firms: uso puntos de foco APROXIMADOS. Repetir con FIRMS antes de decidir.\n")
        return {k: np.array(v) for k, v in FOCOS_APROX.items()}
    f = pd.read_csv(firms_path)
    if "evento" in f.columns:
        f = f[f["evento"] >= 0]
    f["acq_date"] = pd.to_datetime(f["acq_date"])
    temporadas = {
        "2025": (f["acq_date"] >= "2024-12-01") & (f["acq_date"] <= "2025-03-31"),
        "2026": (f["acq_date"] >= "2025-12-01") & (f["acq_date"] <= "2026-03-31"),
    }
    return {k: f.loc[m, ["latitude", "longitude"]].to_numpy() for k, m in temporadas.items()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--listings", nargs="+", required=True, help="uno o más JSON/CSV (acepta comodines)")
    p.add_argument("--reviews", nargs="+", required=True, help="uno o más JSON/CSV (acepta comodines)")
    p.add_argument("--firms")
    p.add_argument("--stay-field")
    p.add_argument("--hotel-field", help="campo de la review que identifica al alojamiento")
    p.add_argument("--listing-id-field", help="campo del alojamiento que matchea con --hotel-field")
    a = p.parse_args()

    paths = [x for patron in a.listings for x in (glob.glob(patron) or [patron])]
    lst = pd.concat([leer(x) for x in paths], ignore_index=True)
    rev = pd.concat([leer(x) for patron in a.reviews for x in (glob.glob(patron) or [patron])], ignore_index=True)
    c_lat, c_lng = campo(lst, "lat"), campo(lst, "lng")
    c_id = campo(lst, "id", a.listing_id_field)
    c_nrev = campo(lst, "n_reviews")
    c_stay, c_hotel = campo(rev, "stay", a.stay_field), campo(rev, "hotel", a.hotel_field)
    faltan = [n for n, c in [("lat", c_lat), ("lng", c_lng), ("id alojamiento", c_id),
                             ("fecha de estadía", c_stay), ("alojamiento en review", c_hotel)] if c is None]
    if faltan:
        print("Columnas de listings:", list(lst.columns)[:40])
        print("Columnas de reviews:", list(rev.columns)[:40])
        sys.exit(f"No encontré: {faltan}. Pasalas con --stay-field / --hotel-field / --listing-id-field.")

    # 1) Universo de alojamientos y distancia al fuego por temporada
    for c in (c_lat, c_lng):  # voyager/booking-scraper devuelve las coordenadas como texto
        lst[c] = pd.to_numeric(lst[c], errors="coerce")
    lst = lst.dropna(subset=[c_lat, c_lng]).copy()
    focos = focos_por_temporada(a.firms)
    for temp, pts in focos.items():
        lst[f"dist_{temp}_km"] = [haversine_min(la, ln, pts) for la, ln in zip(lst[c_lat], lst[c_lng])]
        lst[f"tratado_{temp}"] = lst[f"dist_{temp}_km"] <= RADIO_TRATADO_KM
    if c_nrev:
        lst = lst[pd.to_numeric(lst[c_nrev], errors="coerce").fillna(0) >= 10]
    print(f"Alojamientos con coordenadas y 10+ reviews: {len(lst)}")
    for temp in focos:
        print(f"  tratados {temp} (≤{RADIO_TRATADO_KM} km del fuego): {lst[f'tratado_{temp}'].sum()}")

    # 2) Reviews de la muestra
    def norm(u):  # normaliza URLs de Booking para el join
        return re.sub(r"[?#].*$", "", str(u)).rstrip("/").lower()
    lst["_key"] = lst[c_id].map(norm)
    rev["_key"] = rev[c_hotel].map(norm)
    rev["mes_estadia"] = rev[c_stay].map(a_mes)
    share_fecha = rev["mes_estadia"].notna().mean()
    lst["_nrev"] = pd.to_numeric(lst[c_nrev], errors="coerce").fillna(0) if c_nrev else 1.0
    rev = rev.merge(lst[["_key", "_nrev"] + [c for c in lst.columns if c.startswith(("tratado_", "dist_"))]],
                    on="_key", how="left")
    sin_match = rev["tratado_2026"].isna().mean()
    muestra = rev["_key"].nunique()
    print(f"\nReviews en la muestra: {len(rev)} de {muestra} alojamientos | con fecha de estadía: {share_fecha:.0%}"
          f" | sin match con listings: {sin_match:.0%}")

    # 3) Conteo en ventanas de fuego, en zona tratada, y extrapolación al universo
    total_tratadas = 0.0
    for temp, meses in MESES_FUEGO.items():
        r = rev[(rev[f"tratado_{temp}"] == True) & rev["mes_estadia"].isin(meses)]  # noqa: E712
        muestreados = rev.loc[rev[f"tratado_{temp}"] == True].drop_duplicates("_key")  # noqa: E712
        n_trat_muestra = len(muestreados)
        n_trat_univ = lst[f"tratado_{temp}"].sum()
        # Extrapolación ponderada por reviews totales: corrige que la muestra sean los
        # alojamientos más reseñados (contar alojamientos sobreestimaría).
        peso_univ = lst.loc[lst[f"tratado_{temp}"], "_nrev"].sum()
        peso_muestra = muestreados["_nrev"].sum()
        factor = peso_univ / peso_muestra if peso_muestra else np.nan
        extrap = len(r) * factor if peso_muestra else 0
        total_tratadas += extrap
        print(f"  Temporada {temp} {meses}: {len(r)} reviews en la muestra "
              f"({n_trat_muestra} alojamientos tratados muestreados de {n_trat_univ}) "
              f"→ ≈ {extrap:.0f} en el universo")

    # 4) Veredicto
    print("\n=== VEREDICTO ===")
    ok_vol = total_tratadas >= MIN_REVIEWS_TRATADAS
    ok_fecha = share_fecha >= MIN_SHARE_CON_FECHA
    print(f"Reviews tratadas en meses de fuego (extrapoladas): {total_tratadas:.0f} "
          f"(umbral {MIN_REVIEWS_TRATADAS}) → {'OK' if ok_vol else 'NO ALCANZA'}")
    print(f"Reviews con fecha de estadía: {share_fecha:.0%} (umbral {MIN_SHARE_CON_FECHA:.0%}) "
          f"→ {'OK' if ok_fecha else 'NO ALCANZA'}")
    print("SEGUIR con el proyecto." if ok_vol and ok_fecha else
          "DESCARTAR o rediseñar (ampliar zona/meses, sumar Villa La Angostura como control).")


if __name__ == "__main__":
    main()
