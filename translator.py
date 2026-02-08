import pandas as pd
from typing import Dict, Tuple, Optional

import pandas as pd

EXPECTED_COLS = [
    "ID de Proyecto",
    "SKU",
    "ID de pieza",
    "Tipología de pieza",
    "Ancho",
    "Alto",
    "Material",
    "Gama",
    "Acabado",
    "Mecanizado o sin mecanizar (vacío)",
    "Modelo de tirador",
    "Posición de tirador",
    "Dirección de apertura de puerta",
    "Acabado de tirador",
]

def load_input_csv(path: str) -> pd.DataFrame:
    """
    Carga el CSV CUBRO tolerando:
    - con cabecera correcta
    - sin cabecera (primera fila es dato)
    """
    # 1) Intento normal
    df = pd.read_csv(path)

    # Si ya vienen columnas esperadas, perfecto
    if all(c in df.columns for c in ["Ancho", "Alto", "Acabado"]):
        return df

    # 2) Si parece que no hay header real, re-lee sin header
    df2 = pd.read_csv(path, header=None)

    # Si tiene al menos 14 columnas, asigna las esperadas
    if df2.shape[1] >= len(EXPECTED_COLS):
        df2 = df2.iloc[:, :len(EXPECTED_COLS)]
        df2.columns = EXPECTED_COLS
        return df2

    # Si no, error explícito
    raise ValueError(
        f"CSV input no tiene el formato esperado. Columnas detectadas: {df.columns.tolist()} "
        f"(sin header: {df2.shape[1]} columnas)."
    )


# Orden EXACTO según tu lista original de colores CUBRO:
# Blanco, Negro, Tinta, Seda, Tipo, Crema, Humo, Zafiro, Celeste, Pino, Noche, Marga, Argil, Curry, Roto, Ave
CUBRO_COLORS_ORDER = [
    "Blanco", "Negro", "Tinta", "Seda", "Tipo", "Crema", "Humo", "Zafiro",
    "Celeste", "Pino", "Noche", "Marga", "Argil", "Curry", "Roto", "Ave"
]

# Códigos internos ALVIC en el MISMO orden que los colores anteriores
ALVIC_COLOR_CODES_ORDER = [
    "L3806", "L4596", "L4706", "L5266", "L5276", "L5556", "L5866", "L5906",
    "L6766", "L9146", "L9166", "L9556", "LA056", "LA066", "LA076", "LA086"
]

# Mapeo CUBRO -> "Color ALVIC (texto)" (para filtrar DB si hace falta)
COLOR_TEXT_MAP: Dict[str, str] = {
    "blanco": "BLANCO SM",
    "negro": "NEGRO SM",
    "tinta": "GRIS PLOMO SM",
    "seda": "CASHMERE SM",
    "tipo": "BASALTO SM",
    "crema": "MAGNOLIA SM",
    "humo": "GRIS NUBE SM",
    "zafiro": "AZUL ÍNDIGO SM",
    "celeste": "AGUA MARINA SM",
    "pino": "VERDE SALVIA SM",
    "noche": "AZUL MARINO SM",
    "marga": "COTTO SM",
    "argil": "ALMAGRA SM",
    "curry": "CAMEL SM",
    "roto": "ARENA SM",
    "ave": "TORTORA SM",
}

# Mapeo CUBRO -> "Código color interno ALVIC"
COLOR_CODE_MAP: Dict[str, str] = {
    c.casefold(): code for c, code in zip(CUBRO_COLORS_ORDER, ALVIC_COLOR_CODES_ORDER)
}

def _norm_str(x) -> str:
    return str(x).strip()

def _norm_key(x) -> str:
    return _norm_str(x).casefold()

def clamp_min_100(x: int) -> int:
    return 100 if x < 100 else x

def load_alvic_db(db_csv_path: str) -> pd.DataFrame:
    db = pd.read_csv(db_csv_path)

    # Normalización básica
    db["Modelo"] = db["Modelo"].astype(str).str.upper().str.strip()
    # Importante: en vuestra DB puede haber Color como texto o como código interno.
    # Creamos dos columnas normalizadas para poder filtrar por cualquiera.
    db["Color_raw"] = db["Color"].astype(str).str.upper().str.strip()

    for c in ["Alto", "Ancho", "Grueso"]:
        if c in db.columns:
            db[c] = pd.to_numeric(db[c], errors="coerce")

    db = db.dropna(subset=["ARTICULO", "Color_raw", "Alto", "Ancho"])

    # Solo 06 ZENIT (según requisito)
    db = db[db["Modelo"].str.contains("ZENIT", na=False) & db["Modelo"].str.contains("06", na=False)].copy()

    return db

def detect_is_lac(row: pd.Series) -> bool:
    candidates = []
    for col in ["Gama", "Material"]:
        if col in row.index:
            candidates.append(_norm_str(row[col]))
    return any("LAC" in c.upper() for c in candidates)

def detect_is_machined(row: pd.Series) -> bool:
    """
    Columna: 'Mecanizado o sin mecanizar (vacío)'.
    - Si viene vacía => SIN mecanizar
    - Si tiene algo => MECANIZADA
    """
    # Probamos varios nombres por robustez
    possible_cols = [
        "Mecanizado o sin mecanizar (vacío)",
        "Mecanizado o sin mecanizar",
        "Mecanizado",
        "Mecanizado_o_sin_mecanizar",
    ]
    col = next((c for c in possible_cols if c in row.index), None)
    if not col:
        # Si no existe la columna, asumimos SIN mecanizar (más seguro para no “inventar CNC”)
        return False
    val = _norm_str(row[col])
    return val != "" and val.lower() not in {"nan", "none", "null"}

def map_color_cubro_to_alvic_text(cubro_color: str) -> Optional[str]:
    return COLOR_TEXT_MAP.get(_norm_key(cubro_color))

def map_color_cubro_to_alvic_code(cubro_color: str) -> Optional[str]:
    return COLOR_CODE_MAP.get(_norm_key(cubro_color))

def _filter_db_by_color(db: pd.DataFrame, color_text: Optional[str], color_code: Optional[str]) -> pd.DataFrame:
    """
    Intenta filtrar la DB por el color usando:
    1) código interno (si la DB lo contiene)
    2) texto SM (si la DB lo contiene)
    Si no encuentra nada, devuelve sin filtrar por color (pero marcamos luego que fue fallback).
    """
    d = db
    if color_code:
        d_code = d[d["Color_raw"] == color_code.upper()]
        if not d_code.empty:
            return d_code

    if color_text:
        d_text = d[d["Color_raw"] == color_text.upper()]
        if not d_text.empty:
            return d_text

    # fallback: no filtramos por color (último recurso)
    return d

def find_best_match(db: pd.DataFrame, w: int, h: int) -> Tuple[Optional[pd.Series], str]:
    """
    Devuelve (fila_db, match_type)
    match_type: EXACT | ROTATED_EXACT | FIT | ROTATED_FIT | NO_MATCH
    """
    # 1) Exacto
    exact = db[(db["Alto"] == h) & (db["Ancho"] == w)]
    if not exact.empty:
        return exact.iloc[0], "EXACT"

    # 2) Rotación exacta
    rexact = db[(db["Alto"] == w) & (db["Ancho"] == h)]
    if not rexact.empty:
        return rexact.iloc[0], "ROTATED_EXACT"

    # 3) Fit (mínimo que contenga)
    fit = db[(db["Alto"] >= h) & (db["Ancho"] >= w)].copy()
    if not fit.empty:
        fit["area"] = fit["Alto"] * fit["Ancho"]
        fit = fit.sort_values(["area", "Alto", "Ancho"])
        return fit.iloc[0], "FIT"

    # 4) Rotated fit
    rfit = db[(db["Alto"] >= w) & (db["Ancho"] >= h)].copy()
    if not rfit.empty:
        rfit["area"] = rfit["Alto"] * rfit["Ancho"]
        rfit = rfit.sort_values(["area", "Alto", "Ancho"])
        return rfit.iloc[0], "ROTATED_FIT"

    return None, "NO_MATCH"

def translate_and_split(
    input_csv_path: str,
    db_csv_path: str,
    output_machined_csv_path: str,
    output_non_machined_csv_path: str,
    acabado_col: str = "Acabado",
    ancho_col: str = "Ancho",
    alto_col: str = "Alto",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    db = load_alvic_db(db_csv_path)
    inp = pd.read_csv(input_csv_path)

    for col in [acabado_col, ancho_col, alto_col]:
        if col not in inp.columns:
            raise ValueError(f"Falta columna obligatoria en input: '{col}'")

    out_rows = []
    for _, row in inp.iterrows():
        is_lac = detect_is_lac(row)
        is_machined = detect_is_machined(row)

        # Copia base
        base = row.to_dict()

        if not is_lac:
            out_rows.append({
                **base,
                "Codigo_ALVIC": "",
                "Color_ALVIC_text": "",
                "Color_ALVIC_code": "",
                "Match_type": "",
                "Color_filter_mode": "",
                "Input_Ancho_norm": "",
                "Input_Alto_norm": "",
                "DB_Ancho": "",
                "DB_Alto": "",
                "Es_LAC": False,
                "Es_Mecanizada": is_machined,
            })
            continue

        cubro_color = _norm_str(row.get(acabado_col, ""))
        color_text = map_color_cubro_to_alvic_text(cubro_color)
        color_code = map_color_cubro_to_alvic_code(cubro_color)

        # Dimensiones (con regla mínimo 100mm por lado)
        try:
            w_raw = int(float(row[ancho_col]))
            h_raw = int(float(row[alto_col]))
            w = clamp_min_100(w_raw)
            h = clamp_min_100(h_raw)
        except Exception:
            out_rows.append({
                **base,
                "Codigo_ALVIC": "",
                "Color_ALVIC_text": color_text or "",
                "Color_ALVIC_code": color_code or "",
                "Match_type": "BAD_DIMS",
                "Color_filter_mode": "",
                "Input_Ancho_norm": "",
                "Input_Alto_norm": "",
                "DB_Ancho": "",
                "DB_Alto": "",
                "Es_LAC": True,
                "Es_Mecanizada": is_machined,
            })
            continue

        if not (color_text or color_code):
            out_rows.append({
                **base,
                "Codigo_ALVIC": "",
                "Color_ALVIC_text": "",
                "Color_ALVIC_code": "",
                "Match_type": "UNKNOWN_COLOR",
                "Color_filter_mode": "",
                "Input_Ancho_norm": w,
                "Input_Alto_norm": h,
                "DB_Ancho": "",
                "DB_Alto": "",
                "Es_LAC": True,
                "Es_Mecanizada": is_machined,
            })
            continue

        # Filtrado por color con fallback
        d_color = _filter_db_by_color(db, color_text=color_text, color_code=color_code)
        if color_code and (not d_color.empty) and (d_color["Color_raw"].iloc[0] == color_code.upper()):
            color_filter_mode = "CODE"
        elif color_text and (not d_color.empty) and (d_color["Color_raw"].iloc[0] == color_text.upper()):
            color_filter_mode = "TEXT"
        else:
            color_filter_mode = "FALLBACK_NO_COLOR_FILTER"

        match, match_type = find_best_match(d_color, w=w, h=h)

        if match is None:
            out_rows.append({
                **base,
                "Codigo_ALVIC": "",
                "Color_ALVIC_text": color_text or "",
                "Color_ALVIC_code": color_code or "",
                "Match_type": "NO_MATCH",
                "Color_filter_mode": color_filter_mode,
                "Input_Ancho_norm": w,
                "Input_Alto_norm": h,
                "DB_Ancho": "",
                "DB_Alto": "",
                "Es_LAC": True,
                "Es_Mecanizada": is_machined,
            })
        else:
            out_rows.append({
                **base,
                "Codigo_ALVIC": match["ARTICULO"],
                "Color_ALVIC_text": color_text or "",
                "Color_ALVIC_code": color_code or "",
                "Match_type": match_type,
                "Color_filter_mode": color_filter_mode,
                "Input_Ancho_norm": w,
                "Input_Alto_norm": h,
                "DB_Ancho": int(match["Ancho"]) if pd.notna(match["Ancho"]) else "",
                "DB_Alto": int(match["Alto"]) if pd.notna(match["Alto"]) else "",
                "Es_LAC": True,
                "Es_Mecanizada": is_machined,
            })

    out = pd.DataFrame(out_rows)

    machined = out[out["Es_Mecanizada"] == True].copy()
    non_machined = out[out["Es_Mecanizada"] == False].copy()

    machined.to_csv(output_machined_csv_path, index=False)
    non_machined.to_csv(output_non_machined_csv_path, index=False)

    return machined, non_machined
