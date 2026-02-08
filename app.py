import streamlit as st
import pandas as pd
from translator import translate_and_split

st.set_page_config(page_title="Traductor ALVIC (Zenit 06)", layout="wide")
st.title("Traductor ALVIC – Zenit 06 (2 outputs)")

st.markdown(
    """
- Detecta piezas laca (**LAC**) y asigna **ARTICULO** desde la DB ALVIC.
- Separa en **2 outputs**: *mecanizadas* y *sin mecanizar*.
- Regla clave: si **Ancho** o **Alto** < 100 mm → se ajusta a **100 mm** antes del match.
"""
)

db_path = st.text_input("Ruta CSV base ALVIC (en el servidor)", value="BASE DE DATOS ALVIC 2026.csv")
uploaded = st.file_uploader("Sube el CSV input (piezas CUBRO)", type=["csv"])

if uploaded:
    input_df = pd.read_csv(uploaded)
    st.subheader("Preview input")
    st.dataframe(input_df, use_container_width=True)

    if st.button("Traducir y separar (mecanizadas / sin mecanizar)"):
        tmp_in = "input_cubro.csv"
        out_m = "output_alvic_mecanizadas.csv"
        out_nm = "output_alvic_sin_mecanizar.csv"
        input_df.to_csv(tmp_in, index=False)

        try:
            machined_df, non_machined_df = translate_and_split(
                tmp_in,
                db_path,
                output_machined_csv_path=out_m,
                output_non_machined_csv_path=out_nm,
            )

            st.success("Listo. Se generaron dos archivos.")

            c1, c2 = st.columns(2)

            with c1:
                st.subheader("Mecanizadas")
                st.dataframe(machined_df, use_container_width=True)
                with open(out_m, "rb") as f:
                    st.download_button(
                        "Descargar mecanizadas",
                        data=f,
                        file_name="output_alvic_mecanizadas.csv",
                        mime="text/csv",
                    )

            with c2:
                st.subheader("Sin mecanizar")
                st.dataframe(non_machined_df, use_container_width=True)
                with open(out_nm, "rb") as f:
                    st.download_button(
                        "Descargar sin mecanizar",
                        data=f,
                        file_name="output_alvic_sin_mecanizar.csv",
                        mime="text/csv",
                    )

            # Mini resumen QA
            st.divider()
            total_lac = int((input_df.apply(lambda r: "LAC" in str(r.get("Gama","")).upper() or "LAC" in str(r.get("Material","")).upper(), axis=1)).sum())
            st.caption(f"Control rápido: piezas LAC detectadas (aprox): {total_lac}")

        except Exception as e:
            st.error(f"Error: {e}")
