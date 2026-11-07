"""
Humo en la temporada — piloto de Google Maps vía Apify (reformulación Alerces 2025).

Reutiliza el control de gasto de src/run_booking.py: validación contra el schema, estimación, tope duro por
corrida (max_total_charge_usd), tope acumulado TOPE_USD_TOTAL y registro en data/processed/apify_gastos.csv.

Pasos del piloto (docs/plan_reformulacion_alerces.md §5; reglas en docs/preregistro_alerces.md):
  catalogo     compass/crawler-google-places: catálogo mínimo por localidad, sin detalles ni filtros (cobran extra)
  seleccion    elige ~15 fichas con reglas fijas (estrato × rubro, tamaños mezclados, semilla) usando SOLO FIRMS y
               datos del catálogo. No mira reseñas.
  resenas      compass/google-maps-reviews-scraper por Place ID: todos los orígenes, desde 2024-01-01,
               sin datos personales, máximo 800 por ficha
  diagnostico  formato de fecha, origen, profundidad y cobertura semanal. NO compara expuestos contra
               comparación durante el episodio (pre-registro §6).

Uso (desde humo/; siempre primero --dry-run):
  python src/run_maps.py --cuenta 3 catalogo --dry-run
  python src/run_maps.py --cuenta 3 catalogo
  python src/run_maps.py seleccion
  python src/run_maps.py --cuenta 3 resenas --dry-run
  python src/run_maps.py --cuenta 3 resenas
  python src/run_maps.py diagnostico
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_booking as rb  # noqa: E402

ACTOR_CATALOGO = "compass/crawler-google-places"
ACTOR_RESENAS = "compass/google-maps-reviews-scraper"
# Precios del tier FREE verificados en la API pública el 07/11/2026 (por ficha y por reseña).
rb.PRECIO_FREE.update({ACTOR_CATALOGO: 0.004, ACTOR_RESENAS: 0.0006})

RAW = os.path.join(rb.RAIZ, "data", "raw", "maps")
PROC = os.path.join(rb.RAIZ, "data", "processed")
TERMINOS = ["hotel", "cabañas", "restaurante", "camping", "excursiones", "atracción turística"]
# Una corrida por zona. El parque se define con un punto y un radio, porque como texto el geocoder puede no
# resolverlo. Las fichas que caen en más de una zona se deduplican por placeId.
ZONAS = {
    "esquel": {"locationQuery": "Esquel, Chubut, Argentina"},
    "trevelin": {"locationQuery": "Trevelin, Chubut, Argentina"},
    "pn_los_alerces": {"customGeolocation": {"type": "Point", "coordinates": [-71.70, -42.82], "radiusKm": 25}},
    "villa_la_angostura": {"locationQuery": "Villa La Angostura, Neuquén, Argentina"},
}
EPISODIO = ("2025-02-16", "2025-03-01")
VENTANA_COMPARACION = ("2025-01-19", "2025-03-29")  # episodio ± 28 días
CUPOS = {  # estrato → {rubro: fichas}. Plan §5.
    "alta": {"camping": 2, "excursiones": 1, "atractivo": 1, "alojamiento": 1},
    "media_esquel": {"alojamiento": 2, "gastronomia": 2},
    "media_trevelin": {"alojamiento": 1, "gastronomia": 1, "atractivo": 1},
    "comparacion": {"alojamiento": 1, "gastronomia": 1, "camping": 1},
}
RUBROS = [  # se evalúa en orden: la primera coincidencia gana (sobre categoryName + categories)
    ("camping", r"camping|campground|campamento|área de acampe"),
    ("alojamiento", r"hotel|hoster[ií]a|caba[ñn]a|apart|hostel|hospedaje|lodge|alojamiento|posada|bed & breakfast|"
                    r"departamento|casa de hu[eé]spedes|resort|motel"),
    ("excursiones", r"excursi|turismo|agencia de viajes|tour|rafting|kayak|navegaci|pesca|cabalgata|operador"),
    ("gastronomia", r"restaurante|restaurant|parrilla|cervecer|caf[eé]|casa de t[eé]|t[eé] gal[eé]s|pizzer|"
                    r"comida|bar\b|confiter|helader|panader|bistro|brewery"),
    ("atractivo", r"atracci|mirador|parque|museo|cascada|sendero|lago|playa|monumento|punto de inter|"
                  r"reserva natural|centro de esqu|molino|iglesia|capilla|bosque"),
]


def usar_cuenta(c: str):
    rb.TOKEN_VAR = "APIFY_TOKEN" if c == "1" else next(
        (v for v in (f"APIFY_TOKEN_{c}", f"APIFY_TOKEN{c}") if os.getenv(v)), f"APIFY_TOKEN_{c}")


def guardar(items, nombre):
    os.makedirs(RAW, exist_ok=True)
    ruta = os.path.join(RAW, nombre)
    if os.path.exists(ruta):
        sys.exit(f"Ya existe {ruta}: no se pisa una corrida paga.")
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False)
    print(f"  -> {ruta}")


def cmd_catalogo(a):
    zonas = a.solo or list(ZONAS)
    for z in zonas:
        run_input = {"searchStringsArray": TERMINOS, "maxCrawledPlacesPerSearch": a.max_por_busqueda,
                     "language": "es", "skipClosedPlaces": False, "scrapePlaceDetailPage": False,
                     "maxReviews": 0, "maxImages": 0, "scrapeContacts": False, **ZONAS[z]}
        est = len(TERMINOS) * a.max_por_busqueda * rb.PRECIO_FREE[ACTOR_CATALOGO] + rb.PRECIO_START * 4
        items = rb.correr(ACTOR_CATALOGO, run_input, est, f"maps_catalogo_{z}", None, a.dry_run)
        if items is not None:
            guardar(items, f"catalogo_{z}.json")


def leer_catalogo() -> pd.DataFrame:
    filas = []
    for p in sorted(glob.glob(os.path.join(RAW, "catalogo_*.json"))):
        zona = re.sub(r"^catalogo_|\.json$", "", os.path.basename(p))
        for it in json.load(open(p, encoding="utf-8")):
            loc = it.get("location") or {}
            filas.append({"place_id": it.get("placeId"), "nombre": it.get("title"), "zona_busqueda": zona,
                          "categoria": it.get("categoryName"),
                          "categorias": "|".join(it.get("categories") or []),
                          "lat": loc.get("lat"), "lng": loc.get("lng"), "rating": it.get("totalScore"),
                          "n_resenas": it.get("reviewsCount"), "ciudad": it.get("city"),
                          "cerrado_perm": bool(it.get("permanentlyClosed")),
                          "cerrado_temp": bool(it.get("temporarilyClosed")), "url": it.get("url"),
                          "busqueda": it.get("searchString")})
    if not filas:
        sys.exit("No hay data/raw/maps/catalogo_*.json: correr primero 'catalogo'.")
    return pd.DataFrame(filas).dropna(subset=["place_id", "lat", "lng"]).drop_duplicates("place_id")


def rubro_de(texto: str) -> str:
    t = (texto or "").lower()
    for r, pat in RUBROS:
        if re.search(pat, t):
            return r
    return "otro"


def exposicion(cat: pd.DataFrame) -> pd.DataFrame:
    """Distancia mínima a detecciones de eventos ≥ 50 durante el episodio, y chequeo de la ventana de comparación
    (reglas del pre-registro §2)."""
    f = pd.read_csv(os.path.join(PROC, "firms_alerces", "detecciones_eventos50.csv"), parse_dates=["acq_date"])
    epi = f[f["acq_date"].between(*EPISODIO)][["latitude", "longitude"]].to_numpy()
    ven = f[f["acq_date"].between(*VENTANA_COMPARACION)][["latitude", "longitude"]].to_numpy()

    def dmin(lat, lng, pts):
        la1, lo1, la2, lo2 = map(np.radians, (lat, lng, pts[:, 0], pts[:, 1]))
        h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
        return float((2 * 6371 * np.arcsin(np.sqrt(h))).min())

    cat = cat.copy()
    cat["dist_episodio_km"] = [dmin(a, b, epi) for a, b in zip(cat["lat"], cat["lng"])]
    cat["dist_ventana_km"] = [dmin(a, b, ven) for a, b in zip(cat["lat"], cat["lng"])]
    nivel = np.select([cat["dist_episodio_km"] <= 5, cat["dist_episodio_km"] <= 25, cat["dist_episodio_km"] <= 40],
                      ["alta", "media", "gris"], default="lejos")
    comp = (cat["zona_busqueda"] == "villa_la_angostura") & (cat["dist_ventana_km"] > 40)
    cat["exposicion"] = np.where(comp, "comparacion", np.where(nivel == "lejos", "lejos_no_comparacion", nivel))
    return cat


def cmd_seleccion(a):
    cat = exposicion(leer_catalogo())
    cat["rubro"] = [rubro_de(f"{c} {cs}") for c, cs in zip(cat["categoria"], cat["categorias"])]
    cat.to_csv(os.path.join(PROC, "maps_catalogo_piloto.csv"), index=False)
    print(f"Catálogo: {len(cat)} fichas únicas")
    print(pd.crosstab(cat["exposicion"], cat["rubro"], margins=True).to_string())
    print("\nCiudad por nivel (para ver dónde cae cada estrato):")
    print(pd.crosstab(cat["ciudad"].fillna("?"), cat["exposicion"]).to_string())

    elig = cat[cat["n_resenas"].between(a.min_resenas, a.max_resenas) & ~cat["cerrado_perm"]].copy()
    ciudad = elig["ciudad"].fillna("").str.lower()
    elig["estrato"] = np.select(
        [elig["exposicion"] == "alta",
         (elig["exposicion"] == "media") & ciudad.str.contains("esquel"),
         (elig["exposicion"] == "media") & ciudad.str.contains("trevelin"),
         elig["exposicion"] == "comparacion"],
        ["alta", "media_esquel", "media_trevelin", "comparacion"], default="")
    rng = np.random.default_rng(a.seed)
    elegidas, faltan = [], []
    for est, cupos in CUPOS.items():
        for rub, n in cupos.items():
            pool = elig[(elig["estrato"] == est) & (elig["rubro"] == rub)]
            if pool.empty:
                faltan.append(f"{est}/{rub}")
                continue
            # Tamaños mezclados: la mitad del cupo del tercio superior de reseñas, el resto del resto.
            corte = pool["n_resenas"].quantile(2 / 3)
            grandes, resto = pool[pool["n_resenas"] >= corte], pool[pool["n_resenas"] < corte]
            k_g = min(len(grandes), int(np.ceil(n / 2)))
            sel = grandes.sample(k_g, random_state=int(rng.integers(1e9))) if k_g else grandes.iloc[:0]
            k_r = min(len(resto), n - k_g)
            sel = pd.concat([sel, resto.sample(k_r, random_state=int(rng.integers(1e9)))]) if k_r else sel
            if len(sel) < n:  # completar con lo que quede del estrato y el rubro
                extra = pool.drop(sel.index)
                sel = pd.concat([sel, extra.sample(min(len(extra), n - len(sel)), random_state=a.seed)])
            elegidas.append(sel.assign(estrato=est))
    sel = pd.concat(elegidas) if elegidas else pd.DataFrame()
    if faltan:
        print(f"\nCupos sin candidatas (se informan, no se reemplazan): {faltan}")
    salida = os.path.join(PROC, "maps_piloto_seleccion.csv")
    sel.to_csv(salida, index=False)
    print(f"\nSeleccionadas: {len(sel)} → {salida}")
    if len(sel):
        print(sel[["estrato", "rubro", "nombre", "ciudad", "n_resenas", "dist_episodio_km"]].round(1).to_string(index=False))


def cmd_resenas(a):
    sel = pd.read_csv(os.path.join(PROC, "maps_piloto_seleccion.csv"))
    # Estimación: fracción de las reseñas totales publicadas desde 2024-01 (SUPUESTO 0,5; se mide en el piloto).
    est_res = np.minimum(sel["n_resenas"] * a.frac_desde_2024, a.max_por_ficha).sum()
    est = est_res * rb.PRECIO_FREE[ACTOR_RESENAS] + rb.PRECIO_START * 4
    print(f"{len(sel)} fichas | reseñas estimadas desde {a.desde}: {est_res:.0f} (fracción supuesta "
          f"{a.frac_desde_2024}) | presupuesto {a.presupuesto}")
    est = min(est, a.presupuesto)  # el tope duro de la corrida sale de acá: Apify corta al llegar
    run_input = {"placeIds": sel["place_id"].tolist(), "maxReviews": a.max_por_ficha, "reviewsSort": "newest",
                 "reviewsStartDate": a.desde, "reviewsOrigin": "all", "language": "es", "personalData": False}
    items = rb.correr(ACTOR_RESENAS, run_input, est, "maps_resenas_piloto", None, a.dry_run)
    if items is not None:
        guardar(items, "resenas_piloto.json")


def cmd_diagnostico(a):
    sel = pd.read_csv(os.path.join(PROC, "maps_piloto_seleccion.csv"))
    items = json.load(open(os.path.join(RAW, "resenas_piloto.json"), encoding="utf-8"))
    r = pd.DataFrame(items)
    print(f"Reseñas: {len(r)} | campos: {sorted(r.columns)}\n")
    c_fecha = next((c for c in ["publishedAtDate", "publishAt", "date"] if c in r), None)
    c_origen = next((c for c in r.columns if re.search(r"origin|source", c, re.I)), None)
    c_place = next((c for c in ["placeId", "place_id"] if c in r), None)
    print(f"Campo de fecha: {c_fecha} | ejemplos: {r[c_fecha].head(3).tolist() if c_fecha else '-'}")
    fecha = pd.to_datetime(r[c_fecha], errors="coerce", utc=True) if c_fecha else pd.Series(pd.NaT, index=r.index)
    print(f"  1) fecha exacta parseable: {fecha.notna().mean():.0%}  (si es baja, no hay análisis semanal)")
    if c_origen:
        print(f"  4) origen ({c_origen}): {r[c_origen].value_counts(dropna=False).to_dict()}")
    else:
        print("  4) NO se encontró un campo de origen: revisar a mano un par de reseñas de Tripadvisor u otros")
    r["fecha"] = fecha.dt.tz_convert("America/Argentina/Buenos_Aires")
    r["place_id"] = r[c_place]
    if c_origen:
        r = r[r[c_origen].astype(str).str.lower().str.contains("google")]
    g = r.groupby("place_id").agg(n=("fecha", "size"), primera=("fecha", "min"), ultima=("fecha", "max"))
    d = sel.set_index("place_id")[["estrato", "rubro", "nombre", "n_resenas"]].join(g)
    d["truncada"] = d["n"] >= a.max_por_ficha
    d["llega_a_2024_01"] = d["primera"].dt.strftime("%Y-%m") <= "2024-01"
    print("\n  2) profundidad por ficha (reseñas de Google desde 2024-01):")
    print(d[["estrato", "rubro", "nombre", "n_resenas", "n", "primera", "truncada", "llega_a_2024_01"]]
          .to_string())
    # Cobertura semanal en ene–mar 2025 (sin separar expuestos de comparación ni mirar el episodio aparte).
    t = r[r["fecha"].between("2025-01-01", "2025-03-31 23:59", inclusive="both")]
    semanas = pd.date_range("2024-12-30", "2025-03-31", freq="W-MON", tz="America/Argentina/Buenos_Aires")
    sem = t.groupby(["place_id", t["fecha"].dt.to_period("W-SUN").dt.start_time.dt.tz_localize(
        "America/Argentina/Buenos_Aires")]).size().unstack(fill_value=0).reindex(columns=semanas, fill_value=0)
    sem = sem.reindex(d.index, fill_value=0)
    print(f"\n  3) reseñas de Google por ficha y semana, ene–mar 2025: mediana {np.median(sem.values):.1f} | "
          f"media {sem.values.mean():.2f} | % ficha-semanas con 0: {(sem.values == 0).mean():.0%}")
    print("     por rubro (media por semana):", sem.mean(axis=1).groupby(d["rubro"]).mean().round(2).to_dict())
    pre = r[r["fecha"].between("2024-03-01", "2025-01-31 23:59")].groupby("place_id").size().reindex(d.index,
                                                                                                    fill_value=0)
    print(f"     reseñas en el período previo (mar-2024 a ene-2025) por ficha: {pre.describe().round(1).to_dict()}")
    d.join(pre.rename("n_previo")).to_csv(os.path.join(PROC, "maps_piloto_diagnostico.csv"))
    print(f"\nGuardado: {PROC}/maps_piloto_diagnostico.csv. Con esto se completan las reglas del pre-registro §6.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuenta", default="3", help="1 = APIFY_TOKEN, 3 = APIFY_TOKEN3, ...")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("catalogo")
    p.add_argument("--solo", nargs="+", choices=list(ZONAS))
    p.add_argument("--max-por-busqueda", type=int, default=15)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("seleccion")
    p.add_argument("--min-resenas", type=int, default=50)
    p.add_argument("--max-resenas", type=int, default=3000)
    p.add_argument("--seed", type=int, default=2025)
    p = sub.add_parser("resenas")
    p.add_argument("--desde", default="2024-01-01")
    p.add_argument("--max-por-ficha", type=int, default=800)
    p.add_argument("--frac-desde-2024", type=float, default=0.5)
    p.add_argument("--presupuesto", type=float, default=3.0)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("diagnostico")
    p.add_argument("--max-por-ficha", type=int, default=800)
    a = ap.parse_args()
    usar_cuenta(a.cuenta)
    {"catalogo": cmd_catalogo, "seleccion": cmd_seleccion, "resenas": cmd_resenas,
     "diagnostico": cmd_diagnostico}[a.cmd](a)


if __name__ == "__main__":
    main()
