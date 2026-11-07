"""
Humo en la temporada — Dataset 1: focos de calor NASA FIRMS (VIIRS).

Qué hace:
  1. Descarga detecciones VIIRS en un bbox, por ventanas de 10 días (límite de la API).
  2. Filtra por confianza (nominal / alta).
  3. Agrupa las detecciones en "eventos de fuego" con DBSCAN en espacio-tiempo.
  4. Guarda el CSV limpio y un resumen por evento.
  5. Si quedan más de 2.000 filas, agrega a celda × día (consigna: 700–2.000 registros).

Uso:
  pip install pandas numpy scikit-learn requests
  python firms_backfill.py --key TU_MAP_KEY
  python firms_backfill.py --key TU_MAP_KEY --source VIIRS_SNPP_NRT   # si SP no cubre 2026

Pedir la MAP_KEY (gratis): https://firms.modaps.eosdis.nasa.gov/api/map_key/
"""
import argparse
import io
import os
import sys
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests
from sklearn.cluster import DBSCAN

try:  # FIRMS_KEY desde .env si no se pasa --key (el secreto nunca va en el código)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Comarca Andina + Bariloche + Esquel (oeste, sur, este, norte). Ajustar en el piloto.
BBOX_DEFAULT = "-72.3,-43.4,-70.8,-40.8"

# Dos temporadas de fuego: Mallín Ahogado (ene–feb 2025) y Chubut (ene–feb 2026).
PERIODOS_DEFAULT = [("2024-12-01", "2025-03-31"), ("2025-12-01", "2026-03-31")]

API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{bbox}/{days}/{start}"


def ventanas(inicio: str, fin: str, paso: int = 10):
    d, f = date.fromisoformat(inicio), date.fromisoformat(fin)
    while d <= f:
        dias = min(paso, (f - d).days + 1)
        yield d, dias
        d += timedelta(days=dias)


def descargar(key: str, source: str, bbox: str, periodos, paso: int = 10) -> pd.DataFrame:
    partes = []
    for inicio, fin in periodos:
        for d, dias in ventanas(inicio, fin, paso):
            url = API.format(key=key, source=source, bbox=bbox, days=dias, start=d.isoformat())
            try:
                r = requests.get(url, timeout=60)
            except requests.RequestException as e:  # el mensaje de requests incluye la URL (con la key)
                sys.exit(f"Error de red en {d}: {type(e).__name__}")
            if r.status_code != 200 or r.text.lower().startswith("invalid"):
                # No imprimir la URL: contiene la MAP_KEY.
                sys.exit(f"Error en {d}: HTTP {r.status_code} — {r.text[:200].replace(key, '***')}")
            df = pd.read_csv(io.StringIO(r.text))
            print(f"  {d} (+{dias} días): {len(df)} detecciones")
            partes.append(df)
            time.sleep(1)  # respetar el límite de transacciones
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def limpiar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # VIIRS usa l / n / h. (MODIS usa 0–100: si aparece numérico, quedarse con >= 50.)
    if pd.api.types.is_numeric_dtype(df["confidence"]):
        df = df[df["confidence"] >= 50]
    else:
        df = df[df["confidence"].astype(str).str.lower().isin(["n", "h", "nominal", "high"])]
    hhmm = df["acq_time"].astype(int).astype(str).str.zfill(4)
    df["fecha_hora_utc"] = pd.to_datetime(df["acq_date"] + " " + hhmm, format="%Y-%m-%d %H%M")
    # Duplicados por pasadas superpuestas del satélite.
    df = df.drop_duplicates(subset=["latitude", "longitude", "acq_date", "acq_time"])
    return df.reset_index(drop=True)


def agrupar_eventos(df: pd.DataFrame, eps_km: float = 2.0, dias_equiv: float = 3.0,
                    min_samples: int = 3) -> pd.DataFrame:
    """DBSCAN en (x_km, y_km, t). 'dias_equiv' días pesan lo mismo que eps_km kilómetros."""
    df = df.copy()
    lat0 = np.deg2rad(df["latitude"].mean())
    x = np.deg2rad(df["longitude"]) * 6371 * np.cos(lat0)
    y = np.deg2rad(df["latitude"]) * 6371
    t_dias = (df["fecha_hora_utc"] - df["fecha_hora_utc"].min()).dt.total_seconds() / 86400
    t = t_dias * (eps_km / dias_equiv)
    labels = DBSCAN(eps=eps_km, min_samples=min_samples).fit_predict(np.c_[x, y, t])
    df["evento"] = labels  # -1 = ruido (detección aislada: quema, falso positivo)
    return df


def resumen_eventos(df: pd.DataFrame) -> pd.DataFrame:
    ev = df[df["evento"] >= 0].groupby("evento").agg(
        inicio=("fecha_hora_utc", "min"),
        fin=("fecha_hora_utc", "max"),
        detecciones=("frp", "size"),
        frp_total_mw=("frp", "sum"),
        frp_max_mw=("frp", "max"),
        lat_centro=("latitude", "mean"),
        lon_centro=("longitude", "mean"),
    )
    ev["dias"] = (ev["fin"] - ev["inicio"]).dt.total_seconds() / 86400
    return ev.sort_values("frp_total_mw", ascending=False)


def agregar_celda_dia(df: pd.DataFrame, res_grados: float = 0.02) -> pd.DataFrame:
    """Si hay más de 2.000 filas: una fila = 'esta celda (~2 km) ardió este día'.
    (Con la librería h3 se puede usar H3 resolución 7; acá se usa una grilla simple.)"""
    g = df[df["evento"] >= 0].copy()
    g["celda_lat"] = (g["latitude"] / res_grados).round() * res_grados
    g["celda_lon"] = (g["longitude"] / res_grados).round() * res_grados
    return g.groupby(["evento", "acq_date", "celda_lat", "celda_lon"]).agg(
        detecciones=("frp", "size"),
        frp_total_mw=("frp", "sum"),
        frp_max_mw=("frp", "max"),
        bright_ti4_max=("bright_ti4", "max"),
        share_noche=("daynight", lambda s: (s == "N").mean()),
    ).reset_index()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--key", default=os.getenv("FIRMS_KEY"), help="MAP_KEY de FIRMS (por defecto, FIRMS_KEY del .env)")
    p.add_argument("--source", default="VIIRS_SNPP_SP")
    p.add_argument("--bbox", default=BBOX_DEFAULT)
    p.add_argument("--desde-csv", help="Usar un CSV ya descargado en vez de la API")
    p.add_argument("--dias", type=int, default=10, help="días por llamada (máx. 10; usar 5 si da error de rango)")
    p.add_argument("--salida", default="firms", help="prefijo de los CSV de salida (puede incluir carpeta)")
    p.add_argument("--raw", help="si se indica, guarda acá el CSV crudo descargado")
    p.add_argument("--min-det-evento", type=int, default=50,
                   help="celda×día y *_eventos50.csv usan solo eventos con al menos N detecciones "
                        "(decisión del grupo 07/11: los clusters chicos no cuentan como foco)")
    p.add_argument("--res-celda", type=float, default=0.025, help="lado de la celda en grados (0,025° ≈ 2,8 km)")
    a = p.parse_args()

    if a.desde_csv:
        crudo = pd.read_csv(a.desde_csv)
    else:
        if not a.key:
            sys.exit("Falta --key, FIRMS_KEY en .env, o --desde-csv.")
        print(f"Descargando {a.source} en {a.bbox} ...")
        crudo = descargar(a.key, a.source, a.bbox, PERIODOS_DEFAULT, a.dias)
        if a.raw:
            crudo.to_csv(a.raw, index=False)
    if crudo.empty:
        sys.exit("FIRMS no devolvió detecciones: revisar bbox, fechas o fuente (probar NRT).")

    limpio = agrupar_eventos(limpiar(crudo))
    eventos = resumen_eventos(limpio)
    limpio.to_csv(f"{a.salida}_detecciones.csv", index=False)
    eventos.to_csv(f"{a.salida}_eventos.csv")

    print(f"\nDetecciones crudas: {len(crudo)} | tras filtro: {len(limpio)} | "
          f"en eventos: {(limpio['evento'] >= 0).sum()} | ruido: {(limpio['evento'] < 0).sum()}")
    print("\nEventos principales (por FRP total):")
    print(eventos.head(10).round({"frp_total_mw": 1, "frp_max_mw": 1, "lat_centro": 3,
                                  "lon_centro": 3, "dias": 1}).to_string())

    tam = limpio.loc[limpio["evento"] >= 0].groupby("evento").size()
    grandes = limpio[limpio["evento"].isin(tam[tam >= a.min_det_evento].index)]
    grandes.to_csv(f"{a.salida}_detecciones_eventos{a.min_det_evento}.csv", index=False)
    print(f"\nEventos con ≥{a.min_det_evento} detecciones: {(tam >= a.min_det_evento).sum()} de {len(tam)} "
          f"({len(grandes)} detecciones) → {a.salida}_detecciones_eventos{a.min_det_evento}.csv")

    n_ev = len(grandes)
    if n_ev > 2000:
        celdas = agregar_celda_dia(grandes, a.res_celda)
        celdas.to_csv(f"{a.salida}_celda_dia.csv", index=False)
        print(f"{n_ev} detecciones > 2.000: se generó {a.salida}_celda_dia.csv con {len(celdas)} filas "
              f"(celdas de {a.res_celda}°, solo eventos ≥{a.min_det_evento}).")
    elif n_ev < 700:
        print(f"\nOjo: {n_ev} detecciones < 700. Ampliar bbox/fechas o usar NOAA-20 además de SNPP.")
    else:
        print(f"\n{n_ev} detecciones: dentro del rango de la consigna (700–2.000).")


if __name__ == "__main__":
    main()
