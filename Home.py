"""Entry point for the CB Turó Analytics app."""
import streamlit as st

from auth import login_form, is_admin, hide_streamlit_ui
from database import list_seasons, upsert_season
from config import SUPABASE_URL, SUPABASE_KEY

st.set_page_config(
    page_title="CB Turó Anàlisi",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

hide_streamlit_ui()

# ---------------------------------------------------------------------------
# Sidebar — season selector + admin login
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("CB Turó Anàlisi")
    st.caption("Tauler d'anàlisi de bàsquet")

    login_form()
    st.divider()

    st.subheader("Temporada")

    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Credencials de Supabase no configurades. Revisa el fitxer .env.")
        st.stop()

    try:
        seasons_df = list_seasons()
    except Exception as e:
        st.error(f"No s'ha pogut connectar a la base de dades: {e}")
        st.stop()

    season_options = {}
    if not seasons_df.empty:
        for _, row in seasons_df.iterrows():
            season_options[row["label"]] = row["id"]

    season_labels = list(season_options.keys())

    if season_labels:
        selected_label = st.selectbox(
            "Selecciona temporada",
            season_labels,
            index=0,
        )
        st.session_state["season_id"] = season_options[selected_label]
        st.session_state["season_label"] = selected_label
    else:
        st.info("Encara no hi ha temporades.")

    if is_admin():
        st.divider()
        st.subheader("Administrador")
        with st.expander("Crear nova temporada"):
            new_label = st.text_input("Etiqueta de temporada (p.ex. 2025/26)", key="new_season_label")
            if st.button("Crear temporada"):
                if new_label.strip():
                    upsert_season(new_label.strip())
                    st.success(f"Temporada '{new_label}' creada.")
                    st.rerun()
                else:
                    st.error("Introdueix una etiqueta de temporada vàlida.")

# ---------------------------------------------------------------------------
# Home page content
# ---------------------------------------------------------------------------
st.title("CB Turó Anàlisi 🏀")

if not st.session_state.get("season_id"):
    st.markdown(
        """
        Benvinguda al tauler d'anàlisi de bàsquet del CB Turó.

        Utilitza la **barra lateral** per seleccionar una temporada i navega a qualsevol de les cinc pàgines:

        - **Tauler** — valoració de l'equip i puntuació per quarts
        - **Registre Partits** — llista de partits i (admin) afegir-ne de nous
        - **Estadístiques Temporada** — totals i estadístiques individuals de la temporada
        - **Estadístiques Partits** — estadístiques detallades per partit
        - **Explorador Alineacions** — analitza i compara alineacions específiques
        """
    )
else:
    lbl = st.session_state.get("season_label", "")
    st.markdown(
        f"""
        Temporada **{lbl}** seleccionada. Navega amb els enllaços de la barra lateral.

        - **Tauler** — valoració de l'equip, millors/pitjors alineacions
        - **Registre Partits** — llista de partits{" · afegir partits" if is_admin() else ""}
        - **Estadístiques Temporada** — totals i estadístiques individuals
        - **Estadístiques Partits** — estadístiques detallades per partit
        - **Explorador Alineacions** — filtra i compara alineacions
        """
    )
