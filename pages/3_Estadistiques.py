import streamlit as st
import pandas as pd

from postProcessing import load_season_stints, player_season_totals
from database import get_season_mvp_counts
from functions import short_name

st.set_page_config(page_title="Estadístiques", layout="wide")
st.title("Estadístiques")

season_id = st.session_state.get("season_id")
season_label = st.session_state.get("season_label", "—")

if not season_id:
    st.info("Selecciona una temporada des de la barra lateral.")
    st.stop()

with st.spinner("Carregant…"):
    stints = load_season_stints(season_id)
    df = player_season_totals(season_id, stints)
    mvp_counts = get_season_mvp_counts(season_id)

if df.empty:
    st.info("Encara no hi ha dades de jugadores per a aquesta temporada.")
    st.stop()

st.subheader(f"Temporada {season_label}")

show_ratings = st.toggle("Mostrar ratings On/Off", value=False)

# Attach MVP counts
df["mvp"] = df["player_name"].map(lambda p: mvp_counts.get(p, 0))

base_cols = {
    "player_name": "Jugadora",
    "games": "PJ",
    "minutes": "MIN",
    "pts": "PTS",
    "t2_made": "T2",
    "t3_made": "T3",
    "ft_made": "TL",
    "ft_att": "TLI",
    "ft_pct": "TL%",
    "fouls_committed": "FC",
    "plus_minus": "+/−",
    "mvp": "MVP",
}
rating_cols = {
    "on_net_rating": "NRtg On",
    "off_net_rating": "NRtg Off",
    "on_off_diff": "On−Off",
}

selected_cols = dict(base_cols)
if show_ratings:
    selected_cols.update(rating_cols)

cols_present = [c for c in selected_cols if c in df.columns]
display_df = df[cols_present].rename(columns=selected_cols)
display_df["Jugadora"] = display_df["Jugadora"].apply(short_name)

st.dataframe(
    display_df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "TL%": st.column_config.NumberColumn(format="%.1f%%"),
        "+/−": st.column_config.NumberColumn(format="%+.0f"),
        "NRtg On": st.column_config.NumberColumn(format="%+.1f"),
        "NRtg Off": st.column_config.NumberColumn(format="%+.1f"),
        "On−Off": st.column_config.NumberColumn(format="%+.1f"),
        "MVP": st.column_config.NumberColumn(format="%d 🏆", help="Premis MVP aquesta temporada"),
    },
)

st.caption(
    "PJ = partits jugats · MIN = minuts jugats · PTS = punts anotats · "
    "T2/T3 = cistelles de 2/3 anotades · TL/TLI = tirs lliures anotats/intentats · "
    "TL% = percentatge de tirs lliures · FC = faltes comeses · "
    "+/− = diferencial de punts mentre és en pista (total, no per 40min) · "
    "NRtg On/Off = rating net per 40min quan la jugadora és en pista/fora · "
    "MVP = nombre de premis MVP aquesta temporada"
)
