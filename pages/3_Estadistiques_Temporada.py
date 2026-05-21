import streamlit as st
import pandas as pd

from postProcessing import load_season_stints, player_season_totals
from database import get_season_mvp_counts
from functions import short_name
from auth import hide_streamlit_ui

st.set_page_config(page_title="Estadístiques Temporada", layout="wide")
hide_streamlit_ui()
st.title("Estadístiques Temporada")

season_id = st.session_state.get("season_id")
season_label = st.session_state.get("season_label", "—")

if not season_id:
    st.info("Selecciona una temporada des de la barra lateral.")
    st.stop()

st.subheader(f"Temporada {season_label}")

with st.spinner("Carregant…"):
    stints = load_season_stints(season_id)
    df = player_season_totals(season_id, stints)
    mvp_counts = get_season_mvp_counts(season_id)

if df.empty:
    st.info("Encara no hi ha dades de jugadores per a aquesta temporada.")
    st.stop()

show_ratings = st.toggle("Mostrar ratings", value=False)

df["mvp"]    = df["player_name"].map(lambda p: mvp_counts.get(p, 0))
df["min_pg"] = (df["minutes"] / df["games"].replace(0, pd.NA)).fillna(0.0).round(1)
df["pts_pg"] = (df["pts"]     / df["games"].replace(0, pd.NA)).fillna(0.0).round(1)

display_df = df.copy()
display_df["player_name"] = display_df["player_name"].apply(short_name)

if not show_ratings:
    # ---- Absolute + per-game stats ----
    cols = {
        "player_name":     "Jugadora",
        "games":           "PJ",
        "minutes":         "MIN",
        "min_pg":          "MIN/PJ",
        "pts":             "PTS",
        "pts_pg":          "PTS/PJ",
        "t2_made":         "T2",
        "t3_made":         "T3",
        "ft_made":         "TL",
        "ft_att":          "TLI",
        "ft_pct":          "TL%",
        "fouls_committed": "FC",
        "plus_minus":      "+/−",
        "mvp":             "MVP",
    }
    cols_present = [c for c in cols if c in display_df.columns]
    out = display_df[cols_present].rename(columns=cols)
    st.dataframe(
        out,
        hide_index=True,
        use_container_width=True,
        column_config={
            "TL%": st.column_config.NumberColumn(format="%.1f%%"),
            "+/−": st.column_config.NumberColumn(format="%+.0f"),
            "MVP": st.column_config.NumberColumn(
                format="%d 🏆", help="Premis MVP aquesta temporada"
            ),
        },
    )
    st.caption(
        "PJ = partits jugats · MIN = minuts totals · MIN/PJ = minuts per partit · "
        "PTS = punts totals · PTS/PJ = punts per partit · "
        "T2/T3 = cistelles de 2/3 anotades · TL/TLI = tirs lliures anotats/intentats · "
        "TL% = % tirs lliures · FC = faltes comeses · "
        "+/− = diferencial total mentre és en pista · MVP = premis MVP"
    )
else:
    # ---- Ratings view ----
    cols = {
        "player_name":    "Jugadora",
        "games":          "PJ",
        "minutes":        "MIN",
        "on_ortg":        "ORtg",
        "on_drtg":        "DRtg",
        "on_net_rating":  "NRtg",
        "off_net_rating": "NRtg Off",
        "on_off_diff":    "On−Off",
    }
    cols_present = [c for c in cols if c in display_df.columns]
    out = display_df[cols_present].rename(columns=cols)
    st.dataframe(
        out,
        hide_index=True,
        use_container_width=True,
        column_config={
            "ORtg":     st.column_config.NumberColumn(format="%+.1f"),
            "DRtg":     st.column_config.NumberColumn(format="%+.1f"),
            "NRtg":     st.column_config.NumberColumn(format="%+.1f"),
            "NRtg Off": st.column_config.NumberColumn(format="%+.1f"),
            "On−Off":   st.column_config.NumberColumn(format="%+.1f"),
        },
    )
    st.caption(
        "ORtg = punts anotats per 40min quan la jugadora és en pista · "
        "DRtg = punts rebuts per 40min quan la jugadora és en pista · "
        "NRtg = rating net (ORtg − DRtg) quan és en pista · "
        "NRtg Off = rating net quan la jugadora és fora · "
        "On−Off = diferència NRtg en pista vs fora (com més alt millor)"
    )
