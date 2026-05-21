import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from postProcessing import (
    load_season_stints,
    team_season_rating,
    top_bottom_lineups,
    quarter_scoring,
)
from functions import short_name

st.set_page_config(page_title="Tauler", layout="wide")
st.title("Tauler")

season_id = st.session_state.get("season_id")
season_label = st.session_state.get("season_label", "—")

if not season_id:
    st.info("Selecciona una temporada des de la barra lateral.")
    st.stop()

st.subheader(f"Temporada {season_label}")

with st.spinner("Carregant dades de la temporada…"):
    stints = load_season_stints(season_id)
    rating_dict = team_season_rating(stints)
    quarter_df = quarter_scoring(season_id)

# ---------------------------------------------------------------------------
# Team ratings
# ---------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)
col1.metric(
    "Rating ofensiu",
    f"{rating_dict['off_rating']}",
    help="Punts anotats per 40 minuts de joc",
)
col2.metric(
    "Rating defensiu",
    f"{rating_dict['def_rating']}",
    help="Punts rebuts per 40 minuts de joc",
)
col3.metric(
    "Rating net",
    f"{rating_dict['net_rating']:+.1f}",
    help="Rating ofensiu menys rating defensiu",
)

st.divider()

# ---------------------------------------------------------------------------
# Quarter-by-quarter scoring chart
# ---------------------------------------------------------------------------
if not quarter_df.empty:
    st.subheader("Puntuació per quarts (Mitjanes de temporada)")
    fig = go.Figure()
    fig.add_bar(
        name="Punts a favor",
        x=quarter_df["quarter"].apply(lambda q: f"Q{q}"),
        y=quarter_df["avg_pts_for"],
        marker_color="#1f77b4",
    )
    fig.add_bar(
        name="Punts en contra",
        x=quarter_df["quarter"].apply(lambda q: f"Q{q}"),
        y=quarter_df["avg_pts_against"],
        marker_color="#d62728",
    )
    fig.update_layout(
        barmode="group",
        yaxis_title="Punts mitjans",
        xaxis_title="Quart",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Top / Bottom 5 lineups
# ---------------------------------------------------------------------------
rating_choice = st.selectbox(
    "Ordenar alineacions per",
    ["net_rating", "off_rating", "def_rating"],
    format_func=lambda x: {
        "net_rating": "Rating net",
        "off_rating": "Rating ofensiu",
        "def_rating": "Rating defensiu",
    }[x],
)

top5, bottom5 = top_bottom_lineups(stints, rating=rating_choice, n=5)

# Shorten player names in lineup display
def _shorten_lineup_names(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "players" not in df.columns:
        return df
    df = df.copy()
    df["lineup_name"] = df["players"].apply(lambda p: " / ".join(short_name(x) for x in p))
    return df

top5 = _shorten_lineup_names(top5)
bottom5 = _shorten_lineup_names(bottom5)

col_top, col_bot = st.columns(2)

DISPLAY_COLS = ["lineup_name", "minutes", "off_rating", "def_rating", "net_rating"]
COL_LABELS = {
    "lineup_name": "Alineació",
    "minutes": "MIN",
    "off_rating": "ORtg",
    "def_rating": "DRtg",
    "net_rating": "NRtg",
}

with col_top:
    st.markdown("#### 5 millors alineacions")
    if not top5.empty:
        st.dataframe(
            top5[DISPLAY_COLS].rename(columns=COL_LABELS),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("Encara no hi ha prou dades.")

with col_bot:
    st.markdown("#### 5 pitjors alineacions")
    if not bottom5.empty:
        st.dataframe(
            bottom5[DISPLAY_COLS].rename(columns=COL_LABELS),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("Encara no hi ha prou dades.")
