import os
import streamlit as st
import pandas as pd

from translator import translate_and_split, load_input_csv

st.set_page_config(page_title="Traductor ALVIC (Zenit 06)", layout="wide")

st.title("Traductor ALVIC – Zenit 06")
st.caption(
    "Sube un CSV de piezas CUBRO. Detecta LAC, aplica mínimos de 100 mm, traduce a ARTICULO ALVIC y separa en 2 outputs."
)

st.markdown(
    """
**Reglas principales**
- Detecta LAC automáticamente (buscando `LAC` en *Gama* o *Material*).
- Aplica mínimo 100 mm por lado: si **Ancho** o **Alto** < 100 → se convierte a **100**.
- Matching: exacto → rotado → encaje mínimo (*FIT*).
- Output: 2 CSV → **mecanizadas** y **sin mecanizar**.
"""
)

def file_exists(path: str) -> bool:
    return isinstance(path, str) and path.strip() != "" and os.path.exists(path)

# Paths "inteligentes" por defecto:
# - Si lo tienes en /data, mejor.
# - Si lo tienes en root, también vale.
DEFAULT_DB_CANDIDATES = [
    "data/base_datos_alvic_2026.csv",
    "data/base_datos_alvic_2026",          # por si le quitaste .csv
    "base_datos_alvic_2026.csv",
    "base_datos_alvic_2026",               # por si le quitaste .csv
    "BASE DE DATOS ALVIC 2026.csv",        # legacy
]

default_db_path = next((p for p in DEFAULT_DB_CANDIDATES if file_exists(p)), DEFAULT_DB_CANDIDATES[0])

with st.expander("⚙️ Configuración", expanded=False):
    db_path = st.text_input(
        "Ruta del CSV base ALVIC (en el repo)",
        value=default_db_path,
        help="Ej recomendado: data/base_datos_alvic_2026.csv",
    )

    # Test de lectura base
    if st.button("🧪 Probar lectura de la base ALVIC"):
        if not file_exists(db_path):
            st.error(f"No existe el archivo en esta ruta: '{db_path}'")
            st.info("Revisa el nombre exacto y si está en /data o en la raíz del repo.")
        else:
            try:
                db_preview = pd.read_csv(db_path)
                st.success(f"OK: base cargada. Filas: {len(db_preview)} | Columnas: {len(db_preview.columns)}")
                st.dataframe(db_preview.head(20), use_container_width=True)
            except Exception as e:
                st.error(f"No pude leer la base desde '{db_path}'. Error: {e}")

uploaded = st.file_uploader("Sube el CSV input (piezas CUBRO)", type=["csv"])

if uploaded:
    tmp_in = "input_cubro.csv"
    with open(tmp_in, "wb") as f:
        f.write(uploaded.getbuffer())

    try:
        input_df = load_input_csv(tmp_in)
    except Exception as e:
        st.error(f"No pude leer el CSV input. Error: {e}")
        st.stop()

    st.subheader("Preview input")
    st.dataframe(input_df, use_container_width=True, height=360)

    colA, colB, colC = st.columns([1, 1, 2])
    with colA:
        st.metric("Filas", len(input_df))
    with colB:
        # Estimación rápida de LAC
        lac_guess = 0
        for c in ["Gama", "Material"]:
            if c in input_df.columns:
                lac_guess += input_df[c].astype(str).str.upper().str.contains("LAC", na=False).sum()
        lac_guess = int(min(lac_guess, len(input_df)))
        st.metric("LAC (estimado)", lac_guess)

    if st.button("Traducir y separar (mecanizadas / sin mecanizar)", type="primary"):
        if not file_exists(db_path):
            st.error(f"No existe el archivo de base ALVIC en: '{db_path}'")
            st.info("Solución: ajusta la ruta en Configuración para que coincida con el nombre real del CSV en GitHub.")
            st.stop()

        out_m = "output_alvic_mecanizadas.csv"
        out_nm = "output_alvic_sin_mecanizar.csv"

        try:
            machined_df, non_machined_df = translate_and_split(
                input_csv_path=tmp_in,
                db_csv_path=db_path,
                output_machined_csv_path=out_m,
                output_non_machined_csv_path=out_nm,
            )
        except Exception as e:
            st.error(f"Error ejecutando traductor: {e}")
            st.stop()

        st.success("Listo. Se generaron dos outputs.")

        # QA resumen
        st.divider()
        st.subheader("Resumen QA")

        def count_no_match(df: pd.DataFrame) -> int:
            if "Match_type" not in df.columns:
                return 0
            return int((df["Match_type"] == "NO_MATCH").sum())

        total_out = len(machined_df) + len(non_machined_df)
        no_match_total = count_no_match(machined_df) + count_no_match(non_machined_df)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total output", total_out)
        c2.metric("Mecanizadas", len(machined_df))
        c3.metric("Sin mecanizar", len(non_machined_df))
        c4.metric("NO_MATCH", no_match_total)

        st.divider()
        left, right = st.columns(2)

        with left:
            st.subheader("Mecanizadas")
            st.dataframe(machined_df, use_container_width=True, height=420)
            with open(out_m, "rb") as f:
                st.download_button(
                    "Descargar mecanizadas",
                    data=f,
                    file_name="output_alvic_mecanizadas.csv",
                    mime="text/csv",
                )

        with right:
            st.subheader("Sin mecanizar")
            st.dataframe(non_machined_df, use_container_width=True, height=420)
            with open(out_nm, "rb") as f:
                st.download_button(
                    "Descargar sin mecanizar",
                    data=f,
                    file_name="output_alvic_sin_mecanizar.csv",
                    mime="text/csv",
                )
else:
    st.info("Sube un CSV para comenzar.")
