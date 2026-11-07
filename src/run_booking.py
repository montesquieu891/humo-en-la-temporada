"""
Humo en la temporada — Dataset 2: corre los actores de Booking en Apify.

Subcomandos:
  schema    imprime el input schema REAL de cada actor (no adivinar nombres de campos)
  cuenta    plan, crédito y gasto del mes de la cuenta de Apify
  listings  voyager/booking-scraper, una corrida por destino → data/raw/listings_<destino>.json
  reviews   elige la muestra y corre voyager/booking-reviews-scraper → data/raw/reviews.json

Control de gasto (consigna del MVP: USD 10 en total):
  - Cada corrida muestra el costo estimado antes de lanzarse (con --dry-run no lanza nada).
  - Cada corrida se lanza con max_total_charge_usd = min(estimado × 1,15, lo que queda del tope):
    Apify corta el actor ahí, así que el tope es duro aunque la estimación falle.
  - El gasto real de cada corrida se anota en data/processed/apify_gastos.csv (sin secretos).

Uso (desde humo/, con APIFY_TOKEN en .env):
  python src/run_booking.py schema
  python src/run_booking.py listings --dry-run
  python src/run_booking.py listings
  python src/run_booking.py reviews --firms data/processed/firms_detecciones.csv --dry-run
"""
import argparse
import glob
import json
import os
import random
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal

import numpy as np
import pandas as pd
import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from booking_pilot_check import haversine_min  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
except ImportError:
    pass

ACTOR_LISTINGS = "voyager/booking-scraper"
ACTOR_REVIEWS = "voyager/booking-reviews-scraper"
# Tope duro de gasto acumulado (todas las cuentas, según apify_gastos.csv). USD 10 = regla del MVP.
# Para el Producto 2 el grupo puede subirlo con TOPE_USD_TOTAL en .env; sin esa variable sigue en 10.
TOPE_USD = float(os.getenv("TOPE_USD_TOTAL", "10"))
GASTOS = os.path.join(RAIZ, "data", "processed", "apify_gastos.csv")
RAW = os.path.join(RAIZ, "data", "raw")

# Precio por evento del tier FREE (verificado vía API el 06/11/2026; el tier pago es más barato).
PRECIO_FREE = {ACTOR_LISTINGS: 0.005, ACTOR_REVIEWS: 0.002}
PRECIO_START = 0.00005 * 2  # apify-actor-start: 1 evento por GB de memoria (2 GB por defecto)

# Una corrida por destino. maxItems acota el costo: si el destino tiene menos, cuesta menos.
# Orden: primero la zona tratada. Recortado al crédito del plan FREE (USD 5/mes, ver apify_gastos.csv).
DESTINOS = {
    "el_bolson": {"search": "El Bolsón, Río Negro, Argentina", "maxItems": 180},
    "lago_puelo": {"search": "Lago Puelo, Chubut, Argentina", "maxItems": 130},
    # Booking limita la búsqueda a la ciudad: "Lago Puelo" no trae El Hoyo (verificado 07/11).
    "el_hoyo": {"search": "El Hoyo, Chubut, Argentina", "maxItems": 60},
    "esquel": {"search": "Esquel, Chubut, Argentina", "maxItems": 130},
    "bariloche": {"search": "San Carlos de Bariloche, Río Negro, Argentina", "maxItems": 120},
    # Segunda tanda (cuenta 2): zona tratada 2026 que la búsqueda por ciudad no trajo, y un control extra.
    "epuyen": {"search": "Epuyén, Chubut, Argentina", "maxItems": 60},
    "cholila": {"search": "Cholila, Chubut, Argentina", "maxItems": 60},
    "trevelin": {"search": "Trevelin, Chubut, Argentina", "maxItems": 120},
    "villa_la_angostura": {"search": "Villa La Angostura, Neuquén, Argentina", "maxItems": 300},
    "dina_huapi": {"search": "Dina Huapi, Río Negro, Argentina", "maxItems": 60},
}
CHECK_IN, CHECK_OUT = "2027-01-15", "2027-01-17"
# Universo sin fechas medido el 07/11 (el actor informa "N properties found" antes de scrapear).
# Con fechas 15–17/01/2027 Booking devolvía ~la mitad (solo alojamientos con calendario abierto).
UNIVERSO_SIN_FECHAS = {"el_bolson": 209, "lago_puelo": 93, "el_hoyo": 33, "esquel": 212, "trevelin": 108,
                       "epuyen": 14, "cholila": 14, "villa_la_angostura": 280, "bariloche": 1386}

# Reviews: newest first hasta el 01/11/2024 (una review se publica después de la estadía, así que
# todo lo publicado antes no puede ser una estadía de la ventana nov-2024 → abr-2026).
CUTOFF_REVIEWS = "2024-11-01"
MAX_REVIEWS_POR_HOTEL = 400  # tope de seguridad; los que lo alcanzan quedan marcados como truncados
# Fracción de las reviews totales de un alojamiento que cae en los últimos 24 meses (Booking
# muestra ~36 meses). SUPUESTO para estimar costo; se recalibra con lo que devuelva la corrida.
FRAC_VENTANA = 24 / 36


# Variable del .env con el token a usar (--cuenta 2 → APIFY_TOKEN_2). El crédito FREE es por cuenta;
# el tope del MVP (TOPE_USD) se controla sobre el total de apify_gastos.csv, sumando todas las cuentas.
TOKEN_VAR = "APIFY_TOKEN"


def token() -> str:
    t = os.getenv(TOKEN_VAR)
    if not t:
        sys.exit(f"Falta {TOKEN_VAR} en .env (ver .env.example).")
    return t


def cliente():
    from apify_client import ApifyClient
    return ApifyClient(token())


def schema(actor: str) -> dict:
    """Input schema del build por defecto, leído de la API pública de Apify."""
    r = requests.get(f"https://api.apify.com/v2/acts/{actor.replace('/', '~')}/builds/default", timeout=30)
    r.raise_for_status()
    d = r.json()["data"]
    s = d.get("inputSchema") or (d.get("actorDefinition") or {}).get("input")
    return json.loads(s) if isinstance(s, str) else s


def validar_input(actor: str, run_input: dict):
    props = schema(actor)["properties"]
    malas = [k for k in run_input if k not in props]
    if malas:
        sys.exit(f"{actor}: claves de input que no están en el schema: {malas}. Disponibles: {list(props)}")
    for k, v in run_input.items():
        enum = props[k].get("enum")
        if enum and v not in enum:
            sys.exit(f"{actor}: {k}={v!r} no está en {enum}")


def credito_cuenta() -> float:
    """Lo que le queda a la cuenta en el ciclo actual (el plan FREE corta en USD 5/mes)."""
    lim = a_dict(cliente().user().limits())
    maximo = (lim.get("limits") or {}).get("maxMonthlyUsageUsd")
    usado = (lim.get("current") or {}).get("monthlyUsageUsd") or 0
    return float("inf") if maximo is None else float(maximo) - float(usado)


def disponible() -> float:
    """Tope efectivo: lo menor entre lo que queda del tope del MVP y el crédito real (con margen)."""
    return min(TOPE_USD - gastado(), credito_cuenta() - 0.03)


def gastado() -> float:
    if not os.path.exists(GASTOS):
        return 0.0
    return float(pd.read_csv(GASTOS)["usd"].sum())


def costo_real(actor, run: dict, items: int = 0) -> float:
    """Lo cobrado. Verificado 07/11: el cobro se asienta DESPUÉS de que termina la corrida y al final
    se cobra cada ítem entregado (1.101 reviews → USD 2,20 aunque al terminar figuraban 1.009 eventos).
    Se toma el mayor entre ítems × precio, eventos × precio y usageTotalUsd, para no subestimar nunca."""
    ev = run.get("chargedEventCounts") or {}
    por_eventos = sum(n * (PRECIO_FREE[actor] if k.endswith("scraped") and "additional" not in k
                           else 0.005 if "additional" in k else 0.00005) for k, n in ev.items())
    por_items = items * PRECIO_FREE[actor] + PRECIO_START
    return max(por_eventos, por_items, float(run.get("usageTotalUsd") or 0))


def anotar(actor, etiqueta, run: dict, items: int, estimado: float):
    fila = pd.DataFrame([{
        "fecha_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "cuenta": TOKEN_VAR, "actor": actor, "etiqueta": etiqueta, "run_id": run.get("id"), "status": run.get("status"),
        "items": items, "usd_estimado": round(estimado, 4), "usd": round(costo_real(actor, run, items), 4),
        "usage_total_usd": run.get("usageTotalUsd"), "eventos": json.dumps(run.get("chargedEventCounts") or {}),
    }])
    os.makedirs(os.path.dirname(GASTOS), exist_ok=True)
    fila.to_csv(GASTOS, mode="a", header=not os.path.exists(GASTOS), index=False)


def a_dict(obj) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    return obj.model_dump(by_alias=True, mode="json")  # apify-client 3.x devuelve modelos pydantic


def correr(actor, run_input, estimado, etiqueta, max_items=None, dry_run=False):
    """Valida contra el schema, muestra el costo y corre con tope duro. Devuelve los items."""
    validar_input(actor, run_input)
    resto = disponible()
    tope = round(min(estimado * 1.15 + 0.01, resto), 2)
    print(f"\n[{etiqueta}] {actor}\n  input: {json.dumps(run_input, ensure_ascii=False)[:300]}"
          f"\n  costo estimado: USD {estimado:.2f} | tope duro de esta corrida: USD {tope:.2f}"
          f" | disponible: USD {resto:.2f} (gastado en el repo: USD {gastado():.2f})")
    if dry_run:
        return None
    if resto <= 0.02 or estimado > resto:
        sys.exit(f"  FRENO: la corrida estimada (USD {estimado:.2f}) supera lo que queda del tope (USD {resto:.2f}).")
    c = cliente()
    run = a_dict(c.actor(actor).call(run_input=run_input, max_items=max_items,
                                     max_total_charge_usd=Decimal(str(tope)), logger=None))
    if not run:
        sys.exit("  La corrida no devolvió información (¿timeout?). Revisar en la consola de Apify antes de reintentar.")
    run = a_dict(c.run(run["id"]).get())  # releer para tener el costo final
    items = list(c.dataset(run["defaultDatasetId"]).iterate_items())
    anotar(actor, etiqueta, run, len(items), estimado)
    print(f"  status: {run.get('status')} | items: {len(items)} | costo real: USD {costo_real(actor, run, len(items)):.3f}"
          f" | eventos: {run.get('chargedEventCounts')}")
    return items


# ---------------------------------------------------------------- subcomandos
def cmd_schema(_):
    for actor in (ACTOR_LISTINGS, ACTOR_REVIEWS):
        s = schema(actor)
        print(f"\n=== {actor} (required: {s.get('required', [])})")
        for k, v in s["properties"].items():
            print(f"  {k}: {v.get('type')} default={v.get('default')!r}"
                  + (f" enum={v['enum']}" if v.get("enum") else ""))


def cmd_cuenta(_):
    c = cliente()
    u = a_dict(c.user().get())
    lim = a_dict(c.user().limits())
    plan = (u.get("plan") or {})
    print(f"Plan: {plan.get('id')} | crédito mensual: USD {plan.get('monthlyUsageCreditsUsd')}")
    cur = (lim.get("current") or {})
    lims = (lim.get("limits") or {})
    print(f"Gasto del mes: USD {cur.get('monthlyUsageUsd')} | límite mensual: USD {lims.get('maxMonthlyUsageUsd')}")
    print(f"Gastado en este repo (apify_gastos.csv): USD {gastado():.3f} de {TOPE_USD:.0f}")


def cmd_listings(a):
    destinos = a.solo or list(DESTINOS)
    for nombre in destinos:
        cfg = DESTINOS[nombre]
        sufijo = "_sinfechas" if a.sin_fechas else ""
        salida = os.path.join(RAW, f"listings_{nombre}{sufijo}.json")
        if os.path.exists(salida) and not a.forzar:
            print(f"\n[{nombre}] ya existe {salida}: se saltea (usar --forzar para volver a pagar).")
            continue
        max_items = a.max_items or (UNIVERSO_SIN_FECHAS.get(nombre) if a.sin_fechas else None) or cfg["maxItems"]
        if a.sin_fechas:
            # Sin fechas Booking lista todo el universo (con fechas a 14 meses solo aparecen los que ya
            # abrieron calendario: verificado 07/11). No trae precio: el precio sale de la corrida con fechas.
            run_input = {"search": cfg["search"], "maxItems": max_items, "currency": "USD", "language": "es",
                         "sortBy": "distance_from_search", "extractAdditionalHotelData": False}
        else:
            run_input = {"search": cfg["search"], "maxItems": max_items, "checkIn": CHECK_IN,
                         "checkOut": CHECK_OUT, "currency": "USD", "language": "es", "adults": 2, "rooms": 1,
                         "sortBy": "distance_from_search", "extractAdditionalHotelData": False}
        est = max_items * PRECIO_FREE[ACTOR_LISTINGS] + PRECIO_START
        items = correr(ACTOR_LISTINGS, run_input, est, f"listings_{nombre}{sufijo}", max_items, a.dry_run)
        if items is not None:
            for it in items:
                it["destino_busqueda"] = nombre
                it["con_fechas"] = not a.sin_fechas
            with open(salida, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False)
            print(f"  -> {salida}")


def focos_principales(firms_path, min_det):
    f = pd.read_csv(firms_path)
    tam = f[f["evento"] >= 0].groupby("evento").size()
    grandes = tam[tam >= min_det].index
    f = f[f["evento"].isin(grandes)]
    return f[["latitude", "longitude"]].to_numpy(), len(grandes)


def cmd_reviews(a):
    files = sorted(glob.glob(os.path.join(RAW, "listings_*.json")))
    if not files:
        sys.exit("No hay data/raw/listings_*.json: correr primero 'listings'.")
    lst = pd.concat([pd.json_normalize(json.load(open(p, encoding="utf-8"))) for p in files], ignore_index=True)
    lst["url_norm"] = lst["url"].map(lambda u: re.sub(r"[?#].*$", "", str(u)).rstrip("/").lower())
    for c in ("location.lat", "location.lng"):  # el actor las devuelve como texto
        lst[c] = pd.to_numeric(lst[c], errors="coerce")
    lst["_con_precio"] = pd.to_numeric(lst.get("price"), errors="coerce").notna()
    lst = lst.sort_values("_con_precio", ascending=False)  # al deduplicar, preferir la corrida con fechas
    lst = lst.drop_duplicates("url_norm").dropna(subset=["location.lat", "location.lng"]).copy()
    lst["n_rev"] = pd.to_numeric(lst["reviews"], errors="coerce").fillna(0)
    pts, n_ev = focos_principales(a.firms, a.min_det_evento)
    lst["dist_foco_km"] = [haversine_min(la, ln, pts) for la, ln in zip(lst["location.lat"], lst["location.lng"])]
    print(f"Alojamientos únicos: {len(lst)} | focos: detecciones de {n_ev} eventos con ≥{a.min_det_evento} detecciones"
          f" (ambas temporadas)")

    elegibles = lst[lst["n_rev"] >= 10]
    cerca = elegibles[elegibles["dist_foco_km"] <= a.radio_km].copy()
    cerca["grupo"] = "cerca_40km"
    barilo = elegibles[(elegibles["destino_busqueda"] == "bariloche") & (elegibles["dist_foco_km"] > a.radio_km)]
    barilo_todos = barilo.copy()
    barilo_todos["grupo"] = "control_bariloche"
    barilo = barilo.sample(frac=1, random_state=a.seed).head(a.n_bariloche).copy()
    barilo["grupo"] = "control_bariloche"
    muestra = pd.concat([cerca, barilo])
    if a.grupos:
        muestra = muestra[muestra["grupo"].isin(a.grupos)]
    ya = set()
    for f in glob.glob(os.path.join(RAW, "reviews*.json")):
        ya |= {r.get("startUrl") for r in json.load(open(f, encoding="utf-8"))}
    ya_pedidos = os.path.join(RAIZ, "data", "processed", "muestra_reviews.csv")
    if os.path.exists(ya_pedidos):  # incluye los pedidos que volvieron sin reviews: no pagar dos veces
        ya |= set(pd.read_csv(ya_pedidos)["url"])
    antes = len(muestra)
    if a.reintentar:
        # Diagnóstico 07/11 (logs del actor): "No reviews found for the provided property" en la primera
        # página aunque el alojamiento tiene reviews (bloqueo transitorio). Se reintentan solo los pedidos
        # que no devolvieron NINGUNA review: no se paga dos veces. Los truncados a mitad no se reintentan.
        devueltos = set()
        for f in glob.glob(os.path.join(RAW, "reviews*.json")):
            devueltos |= {r.get("startUrl") for r in json.load(open(f, encoding="utf-8"))}
        pedidos = pd.read_csv(ya_pedidos)
        pend = set(pedidos.loc[~pedidos["url"].isin(devueltos), "url"])
        muestra = pd.concat([cerca, barilo_todos])
        muestra = muestra[muestra["url"].isin(pend)].drop_duplicates("url").copy()
        muestra["grupo"] = pedidos.set_index("url").loc[muestra["url"], "grupo"].values
        print(f"Reintento: {len(muestra)} alojamientos pedidos que no devolvieron reviews.")
        ya = set()
        antes = len(muestra)
    muestra = muestra[~muestra["url"].isin(ya)].copy()
    if antes - len(muestra):
        print(f"Se excluyen {antes - len(muestra)} alojamientos ya pedidos en corridas anteriores.")
    muestra["rev_est"] = np.minimum(muestra["n_rev"] * FRAC_VENTANA, MAX_REVIEWS_POR_HOTEL)
    precio = PRECIO_FREE[ACTOR_REVIEWS]

    def resumen(m, titulo):
        print(f"\n{titulo}")
        g = m.groupby("grupo").agg(alojamientos=("url", "size"), reviews_totales=("n_rev", "sum"),
                                   reviews_est_ventana=("rev_est", "sum"))
        g["usd_est"] = g["reviews_est_ventana"] * precio
        print(g.round(1).to_string())
        print(f"  total estimado: {m['rev_est'].sum():.0f} reviews ≈ USD {m['rev_est'].sum() * precio:.2f}")

    resumen(muestra, f"Muestra completa (≥10 reviews; cerca = ≤{a.radio_km} km de un foco)")
    presupuesto = min(a.presupuesto or float("inf"), disponible() - 0.05)
    if muestra["rev_est"].sum() * precio > presupuesto:
        # Recorte al azar (IMPLEMENTATION.md): orden aleatorio dentro de cada grupo, y se agregan
        # alojamientos mientras entren en la parte del presupuesto de su grupo (proporcional a su
        # costo estimado). Saltear los que no entran aprovecha mejor el crédito, a costa de un
        # leve sesgo hacia alojamientos chicos al final del recorrido (documentarlo).
        total = muestra["rev_est"].sum() * precio
        partes = []
        for _, g in muestra.groupby("grupo"):
            cupo = presupuesto * (g["rev_est"].sum() * precio) / total / precio
            usado, keep = 0.0, []
            for i, r in g.sample(frac=1, random_state=a.seed).iterrows():
                if usado + r["rev_est"] <= cupo:
                    keep.append(i)
                    usado += r["rev_est"]
            partes.append(g.loc[keep])
        muestra = pd.concat(partes)
        resumen(muestra, f"Recortada al azar dentro de cada grupo para entrar en USD {presupuesto:.2f}")

    salida = os.path.join(RAW, a.salida)
    if os.path.exists(salida) and not a.dry_run:
        sys.exit(f"Ya existe {salida}: elegir otro --salida (no se pisa una corrida paga).")
    if not a.dry_run:  # registro acumulado de todo lo pedido (con la corrida de origen)
        m = muestra[["url", "name", "destino_busqueda", "grupo", "n_rev", "dist_foco_km", "rev_est"]].assign(corrida=a.salida)
        m.to_csv(ya_pedidos, mode="a", header=not os.path.exists(ya_pedidos), index=False)
    run_input = {
        "startUrls": [{"url": u, "userData": {"aloj_url": u, "grupo": g}}
                      for u, g in zip(muestra["url"], muestra["grupo"])],
        "maxReviewsPerHotel": MAX_REVIEWS_POR_HOTEL,
        "sortReviewsBy": "f_recent_desc",
        "cutoffDate": CUTOFF_REVIEWS,
        "reviewScores": ["ALL"],
    }
    est = muestra["rev_est"].sum() * precio + PRECIO_START
    etiqueta = "reviews_muestra" if a.salida == "reviews.json" else os.path.splitext(a.salida)[0]
    items = correr(ACTOR_REVIEWS, run_input, est, etiqueta, None, a.dry_run)
    if items is not None:
        with open(salida, "w", encoding="utf-8") as fh:
            json.dump(items, fh, ensure_ascii=False)
        print(f"  -> {salida}")


# Piloto de ventana larga (docs/decisiones_abiertas.md §3, opción C): estadías desde nov-2023.
CUTOFF_LARGO = "2023-11-01"
DIR_LARGO = os.path.join(RAW, "ventana_larga")  # fuera del glob reviews*.json: no entra al panel principal


def cmd_ventana_larga(a):
    """Vuelve a pedir, con cutoff 2023-11-01, alojamientos cuya historia corta quedó COMPLETA
    (reviews_cobertura.csv). Así se compara el error estándar con ventana corta y larga sobre las mismas
    unidades (src/piloto_ventana.py). Prioriza El Bolsón: es el que gana un febrero sin fuego (2024)."""
    cob = pd.read_csv(os.path.join(RAIZ, "data", "processed", "reviews_cobertura.csv"))
    m = cob[(cob["estado"] == "completo") & cob["grupo"].isin(a.grupos)].drop_duplicates("url").copy()
    # Booking muestra ~36 meses y nov-2023 → hoy son ~36: se estima con TODAS las reviews visibles.
    m["rev_est"] = m["n_rev"].astype(float)
    grandes = m["rev_est"] > MAX_REVIEWS_POR_HOTEL
    if grandes.any():
        print(f"Se excluyen {grandes.sum()} alojamientos con más de {MAX_REVIEWS_POR_HOTEL} reviews (quedarían truncados).")
        m = m[~grandes]
    m["prioridad"] = np.where(m["destino_busqueda"].eq("el_bolson"), 0, 1)
    m = m.sample(frac=1, random_state=a.seed).sort_values("prioridad", kind="stable")
    precio = PRECIO_FREE[ACTOR_REVIEWS]
    presupuesto = min(a.presupuesto, disponible() - 0.05) if not a.dry_run else a.presupuesto
    m["acum"] = m["rev_est"].cumsum() * precio + PRECIO_START
    m = m[m["acum"] <= presupuesto]
    if m.empty:
        sys.exit(f"No entra ningún alojamiento en USD {presupuesto:.2f}.")
    print(m.groupby(["grupo", "destino_busqueda"]).agg(alojamientos=("url", "size"), reviews_est=("rev_est", "sum"))
          .assign(usd=lambda g: g["reviews_est"] * precio).round(2).to_string())
    print(f"  total: {len(m)} alojamientos, ≈ {m['rev_est'].sum():.0f} reviews ≈ USD {m['rev_est'].sum() * precio:.2f}"
          f" (presupuesto USD {presupuesto:.2f})")
    os.makedirs(DIR_LARGO, exist_ok=True)
    salida = os.path.join(DIR_LARGO, a.salida)
    if os.path.exists(salida) and not a.dry_run:
        sys.exit(f"Ya existe {salida}: elegir otro --salida (no se pisa una corrida paga).")
    run_input = {
        "startUrls": [{"url": u, "userData": {"aloj_url": u, "grupo": g}} for u, g in zip(m["url"], m["grupo"])],
        "maxReviewsPerHotel": MAX_REVIEWS_POR_HOTEL,
        "sortReviewsBy": "f_recent_desc",
        "cutoffDate": CUTOFF_LARGO,
        "reviewScores": ["ALL"],
    }
    est = m["rev_est"].sum() * precio + PRECIO_START
    # Etiqueta sin el prefijo "reviews": cmd_cobertura no la mezcla con la muestra principal.
    items = correr(ACTOR_REVIEWS, run_input, est, "ventana_larga_piloto", None, a.dry_run)
    if items is not None:
        with open(salida, "w", encoding="utf-8") as fh:
            json.dump(items, fh, ensure_ascii=False)
        m[["url", "name", "destino_busqueda", "grupo", "n_rev", "rev_est"]].to_csv(
            os.path.join(DIR_LARGO, "pedidos.csv"), index=False)
        print(f"  -> {salida}")


def cmd_cobertura(_):
    """Estado de cada alojamiento pedido al actor de reviews, a partir de los LOGS de cada corrida
    (evidencia directa) y de lo que devolvió. Escribe data/processed/reviews_cobertura.csv.
      completo              el log dice "Cutoff date was reached", o devolvió todas sus reviews
      truncado_falla_actor  el log dice "No reviews found" después de haber devuelto algo
      truncado_tope         llegó a MAX_REVIEWS_POR_HOTEL
      truncado_tope_gasto   la corrida terminó por max_total_charge_usd antes de completarlo
      sin_reviews           no devolvió nada (falla del actor en la 1ª página)
    Los truncados se excluyen del panel (build_panel.py) porque sus meses viejos quedan subcontados."""
    global TOKEN_VAR
    g = pd.read_csv(GASTOS)
    estado, corte_gasto = {}, set()
    for cta, rid, et in zip(g["cuenta"], g["run_id"], g["etiqueta"]):
        if not str(et).startswith("reviews"):
            continue
        TOKEN_VAR = cta
        log = cliente().run(rid).log().get() or ""
        if re.search(r"max(imum)? total charge|maxTotalChargeUsd|charge limit", log, re.I):
            corte_gasto.add(et)
        for linea in log.splitlines():
            m = re.search(r"hotel/ar/([^.?\"]+)", linea)
            if not m:
                continue
            slug = m.group(1)
            if "Cutoff date was reached" in linea:
                estado[slug] = "completo"
            elif "Remaining items limit" in linea or "Reached max items" in linea:
                estado[slug] = "truncado_tope"
            elif "No reviews found" in linea:
                estado[slug] = "falla_actor"
    pedidos = pd.read_csv(os.path.join(RAIZ, "data", "processed", "muestra_reviews.csv")).drop_duplicates("url")
    rev = []
    for f in sorted(glob.glob(os.path.join(RAW, "reviews*.json"))):
        rev += [{"url": r.get("startUrl"), "id": r.get("id"), "pub": r.get("reviewDate"),
                 "total": r.get("hotelReviews")} for r in json.load(open(f, encoding="utf-8"))]
    rev = pd.DataFrame(rev).drop_duplicates("id")
    c = rev.groupby("url").agg(reviews_devueltas=("id", "size"), pub_min=("pub", "min"))
    cob = pedidos.merge(c, left_on="url", right_index=True, how="left")
    cob["reviews_devueltas"] = cob["reviews_devueltas"].fillna(0).astype(int)
    cob["pub_min"] = cob["pub_min"].str[:10]
    slug = cob["url"].str.extract(r"hotel/ar/([^.?]+)")[0]
    e = slug.map(estado).fillna("sin_evento")
    e = np.where((e == "falla_actor") & (cob["reviews_devueltas"] > 0), "truncado_falla_actor", e)
    e = np.where((e == "falla_actor") & (cob["reviews_devueltas"] == 0), "sin_reviews", e)
    e = np.where(cob["reviews_devueltas"] >= cob["n_rev"], "completo", e)
    # Sin evento en el log: si su corrida se cortó por gasto, es truncado; si no devolvió nada, sin reviews.
    sin_ev = e == "sin_evento"
    etiqueta_corrida = cob["corrida"].str.replace(".json", "", regex=False).replace({"reviews": "reviews_muestra"})
    e = np.where(sin_ev & etiqueta_corrida.isin(corte_gasto), "truncado_tope_gasto", e)
    e = np.where(sin_ev & (cob["reviews_devueltas"] == 0), "sin_reviews", e)
    e = np.where(e == "sin_evento", "completo", e)  # terminó la paginación sin llegar al cutoff
    cob["estado"] = e
    salida = os.path.join(RAIZ, "data", "processed", "reviews_cobertura.csv")
    cob.to_csv(salida, index=False)
    print(pd.crosstab(cob["corrida"], cob["estado"], margins=True).to_string())
    if corte_gasto:
        print(f"Corridas cortadas por el tope de gasto: {sorted(corte_gasto)}")
    print(f"-> {salida}")


def main():
    global TOKEN_VAR
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuenta", default="1", help="1 = APIFY_TOKEN, 2 = APIFY_TOKEN_2, ...")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("schema")
    sub.add_parser("cuenta")
    sub.add_parser("cobertura")
    p = sub.add_parser("listings")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--solo", nargs="+", choices=list(DESTINOS))
    p.add_argument("--forzar", action="store_true")
    p.add_argument("--sin-fechas", action="store_true", help="universo completo, sin precio (ver UNIVERSO_SIN_FECHAS)")
    p.add_argument("--max-items", type=int, help="pisa el maxItems del destino")
    p = sub.add_parser("reviews")
    p.add_argument("--firms", default=os.path.join(RAIZ, "data", "processed", "firms_detecciones.csv"))
    p.add_argument("--radio-km", type=float, default=40)
    p.add_argument("--min-det-evento", type=int, default=50,
                   help="eventos FIRMS con menos detecciones no cuentan como foco para elegir la muestra")
    p.add_argument("--n-bariloche", type=int, default=50, help="0 = sin control de Bariloche (MVP con crédito FREE)")
    p.add_argument("--presupuesto", type=float, help="USD máximos para las reviews (por defecto, todo lo disponible)")
    p.add_argument("--grupos", nargs="+", choices=["cerca_40km", "control_bariloche"])
    p.add_argument("--reintentar", action="store_true", help="solo los pedidos que no devolvieron reviews")
    p.add_argument("--salida", default="reviews.json", help="archivo en data/raw/ (nunca se pisa)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("ventana-larga", help="piloto: re-pedir con cutoff 2023-11-01 alojamientos completos")
    p.add_argument("--grupos", nargs="+", default=["cerca_40km"], choices=["cerca_40km", "control_bariloche"])
    p.add_argument("--presupuesto", type=float, default=3.0, help="USD máximos (por defecto 3)")
    p.add_argument("--salida", default="reviews_desde_2023-11.json", help="archivo en data/raw/ventana_larga/")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cuenta == "1":
        TOKEN_VAR = "APIFY_TOKEN"
    else:  # acepta APIFY_TOKEN_2 o APIFY_TOKEN2
        TOKEN_VAR = next((v for v in (f"APIFY_TOKEN_{a.cuenta}", f"APIFY_TOKEN{a.cuenta}") if os.getenv(v)),
                         f"APIFY_TOKEN_{a.cuenta}")
    {"schema": cmd_schema, "cuenta": cmd_cuenta, "listings": cmd_listings, "reviews": cmd_reviews,
     "cobertura": cmd_cobertura, "ventana-larga": cmd_ventana_larga}[a.cmd](a)


if __name__ == "__main__":
    main()
