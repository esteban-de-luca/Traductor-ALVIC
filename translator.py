import os
import pandas as pd
from typing import Dict, Tuple, Optional, List


# -----------------------------
# Config: columnas esperadas input sin cabecera
# -----------------------------
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


# -----------------------------
# Config: colores (orden exacto)
# -----------------------------
# Orden EXACTO según tu lista de colores CUBRO:
# Blanco, Negro, Tinta, Seda, Tipo, Crema, Humo, Zafiro, Celeste, Pino, Noche, Marga, Argil, Curry, Roto, Ave
CUBRO_COLORS_ORDER = [
    "Blanco", "Negro", "Tinta", "Seda", "Tipo", "Crema", "Humo", "Zafiro",
    "Celeste", "Pino", "Noche", "Marga", "Argil", "Curry", "Roto", "Ave"
]

# Códigos internos ALVIC en el MISMO orden
ALVIC_COLOR_CODES_ORDER = [
    "L3806",
    "L4596",
    "L4706",
    "L5266",
    "L5276",
    "L5556",
    "L5866",
    "L5906",
    "L6766",
    "L9146",
    "L9166",
    "L9556",
    "LA056",
    "LA066",
    "LA076",
    "LA086",
]

# CUBRO -> texto ALVIC (para filtrar DB si la DB usa nombres)
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

# CUBRO -> código interno ALVIC
COLOR_CODE_MAP: Dict[str, str] = {
    c.casefold(): code for c, code in zip(CUBRO_COLORS_ORDER, ALVIC_COLOR_CODES_ORDER)
}


# -----------------------------
# Helpers
# -----------------------------
def _norm_str(x) -> str:
    return str(x).strip()

def _norm_key(x) -> str:
    return _norm_str(x).casefold()

def clamp_min_100(x: int) -> int:
    return 100 if x < 100 else x


# -----------------------------
# Normalización de columnas de input
# -----------------------------
def _canonicalize(col: str) -> str:
    """
    Normaliza un nombre de columna para poder compararlo:
    - quita espacios extremos
    - colapsa espacios internos
    - lower
    """
    s = str(col).strip()
    s = " ".join(s.split())
    return s.casefold()

def _rename_columns_with_synonyms(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renombra columnas de input a los nombres canónicos que usa el traductor:
    Ancho, Alto, Acabado, Material, Gama, Mecanizado o sin mecanizar (vacío)
    """
    synonyms = {
        "ancho": ["ancho", "width", "w", "anchura"],
        "alto": ["alto", "height", "h", "altura"],
        "acabado": ["acabado", "color", "acabado color", "finish", "acabo"],
        "material": ["material", "mat", "materiales"],
        "gama": ["gama", "serie", "range"],
        "mecanizado o sin mecanizar (vacío)": [
            "mecanizado o sin mecanizar (vacío)",
            "mecanizado o sin mecanizar",
            "mecanizado",
            "cnc",
            "mecanizada",
            "mecanizado/sin mecanizar",
        ],
    }

    # Construir mapa actual->nuevo
    current_cols = list(df.columns)
    canon_map = {c: _canonicalize(c) for c in current_cols}

    rename_dict = {}
    for target, keys in synonyms.items():
        keys_canon = set(_canonicalize(k) for k in keys)
        for col in current_cols:
            if canon_map[col] in keys_canon:
                # Asignar al nombre esperado por el traductor (con mayúscula estándar)
                if target == "ancho":
                    rename_dict[col] = "Ancho"
                elif target == "alto":
                    rename_dict[col] = "Alto"
                elif target == "acabado":
                    rename_dict[col] = "Acabado"
                elif target == "material":
                    rename_dict[col] = "Material"
                elif target == "gama":
                    rename_dict[col] = "Gama"
                elif target == "mecanizado o sin mecanizar (vacío)":
                    rename_dict[col] = "Mecanizado o sin mecanizar (vacío)"

    if rename_dict:
        df = df.rename(columns=rename_dict)

    # Limpia espacios en nombres restantes (sin cambiar significado)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def load_input_csv(path: str) -> pd.DataFrame:
    """
    Carga el CSV CUBRO tolerando:
    - con cabecera correcta (o similar)
    - sin cabecera (primera fila es dato)
    Además normaliza nombres de columnas (ej. 'acabado', 'Acabado ', etc.)
    """
    # 1) Intento normal
    df = pd.read_csv(path)
    df = _rename_columns_with_synonyms(df)

    # Si ya vienen columnas clave, listo
    if all(c in df.columns for c in ["Ancho", "Alto", "Acabado"]):
        return df

    # 2) Releer sin header
    df2 = pd.read_csv(path, header=None)

    # Si tiene suficientes columnas, asignar EXPECTED_COLS
    if df2.shape[1] >= len(EXPECTED_COLS):
        df2 = df2.iloc[:, :len(EXPECTED_COLS)]
        df2.columns = EXPECTED_COLS
        df2 = _rename_columns_with_synonyms(df2)
        return df2

    # 3) Error claro
    raise ValueError(
        "CSV input no tiene el formato esperado.\n"
        f"- Columnas detectadas (lectura con header): {df.columns.tolist()}\n"
        f"- Columnas detectadas (lectura sin header): {df2.shape[1]} columnas\n"
        "Esperaba al menos columnas equivalentes a: Ancho, Alto, Acabado."
    )


# -----------------------------
# DB ALVIC
# -----------------------------
def load_alvic_db(db_csv_path: str) -> pd.DataFrame:
    if not os.path.exists(db_csv_path):
        raise FileNotFoundError(
            f"No se encontró la base ALVIC en '{db_csv_path}'. "
            "Revisa el nombre del archivo y la ruta (ej: data/base_datos_alvic_2026.csv)."
        )

    db = pd.read_csv(db_csv_path)

    # Normalización básica
    db["Modelo"] = db["Modelo"].astype(str).str.upper().str.strip()

    # La DB puede tener en Color:
    # - texto: "BLANCO SM"
    # - o código interno: "L3806"
    db["Color_raw"] = db["Color"].astype(str).str.upper().str.strip()

    for c in ["Alto", "Ancho", "Grueso"]:
        if c in db.columns:
            db[c] = pd.to_numeric(db[c], errors="coerce")

    db = db.dropna(subset=["ARTICULO", "Color_raw", "Alto", "Ancho"])

    # Solo 06 ZENIT
    db = db[
        db["Modelo"].str.contains("ZENIT", na=False)
        & db["Modelo"].str.contains("06", na=False)
    ].copy()

    return db


# -----------------------------
# Detección LAC / mecanizado
# -----------------------------
def detect_is_lac(row: pd.Series) -> bool:
    candidates = []
    for col in ["Gama", "Material"]:
        if col in row.index:
            candidates.append(_norm_str(row[col]))
    return any("LAC" in c.upper() for c in candidates)

def detect_is_machined(row: pd.Series) -> bool:
    """
    Columna: 'Mecanizado o sin mecanizar (vacío)'.
    - Vacío => SIN mecanizar
    - Cualquier valor => MECANIZADA
    """
    col = "Mecanizado o sin mecanizar (vacío)"
    if col not in row.index:
        return False  # seguro por defecto

    val = _norm_str(row[col])
    return val != "" and val.lower() not in {"nan", "none", "null"}


# -----------------------------
# Mapeo de color CUBRO -> ALVIC
# -----------------------------
def map_color_cubro_to_alvic_text(cubro_color: str) -> Optional[str]:
    return COLOR_TEXT_MAP.get(_norm_key(cubro_color))

def map_color_cubro_to_alvic_code(cubro_color: str) -> Optional[str]:
    return COLOR_CODE_MAP.get(_norm_key(cubro_color))


def _filter_db_by_color(db: pd.DataFrame, color_text: Optional[str], color_code: Optional[str]) -> Tuple[pd.DataFrame, str]:
    """
    Intenta filtrar DB por color usando:
    1) código interno
    2) texto SM
    Si no encuentra nada, devuelve DB completa (fallback) y lo marca.
    """
    if color_code:
        d_code = db[db["Color_raw"] == color_code.upper()]
        if not d_code.empty:
            return d_code, "CODE"

    if color_text:
        d_text = db[db["Color_raw"] == color_text.upper()]
        if not d_text.empty:
            return d_text, "TEXT"

    return db, "FALLBACK_NO_COLOR_FILTER"


# -----------------------------
# Matching tamaños
# -----------------------------
def find_best_match(db: pd.DataFrame, w: int, h: int) -> Tuple[Optional[pd.Series], str]:
    """
    Devuelve (fila_db, match_type)
    match_type: EXACT | ROTATED_EXACT | FIT | ROTATED_FIT | NO_MATCH
    """
    # Exacto
    exact = db[(db["Alto"] == h) & (db["Ancho"] == w)]
    if not exact.empty:
        return exact.iloc[0], "EXACT"

    # Rotación exacta
    rexact = db[(db["Alto"] == w) & (db["Ancho"] == h)]
    if not rexact.empty:
        return rexact.iloc[0], "ROTATED_EXACT"

    # Fit (mínimo panel que contenga)
    fit = db[(db["Alto"] >= h) & (db["Ancho"] >= w)].copy()
    if not fit.empty:
        fit["area"] = fit["Alto"] * fit["Ancho"]
        fit = fit.sort_values(["area", "Alto", "Ancho"])
        return fit.iloc[0], "FIT"

    # Rotated fit
    rfit = db[(db["Alto"] >= w) & (db["Ancho"] >= h)].copy()
    if not rfit.empty:
        rfit["area"] = rfit["Alto"] * rfit["Ancho"]
        rfit = rfit.sort_values(["area", "Alto", "Ancho"])
        return rfit.iloc[0], "ROTATED_FIT"

    return None, "NO_MATCH"


# -----------------------------
# Motor principal: traducir y separar
# -----------------------------
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

    # Cargar input de forma robusta
    inp = load_input_csv(input_csv_path)

    # Validación de columnas (ya normalizadas)
    required = [acabado_col, ancho_col, alto_col]
    missing = [c for c in required if c not in inp.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas obligatorias en input: {missing}. "
            f"Columnas disponibles: {inp.columns.tolist()}"
        )

    out_rows: List[dict] = []

    for _, row in inp.iterrows():
        is_lac = detect_is_lac(row)
        is_machined = detect_is_machined(row)
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

        # Dimensiones + regla mínimo 100 mm
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

        d_color, color_filter_mode = _filter_db_by_color(db, color_text=color_text, color_code=color_code)

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


    return machined, non_machined
