import streamlit as st
import pandas as pd

from postProcessing import load_season_stints, team_season_rating, top_bottom_lineups
from functions import aggregate_stints, stints_for_lineup, short_name

st.set_page_config(page_title="Explorador de Alineacions", layout="wide")
st.title("Explorador de Alineacions")

season_id = st.session_state.get("season_id")
season_label = st.session_state.get("season_label", "—")

if not season_id:
    st.info("Selecciona una temporada des de la barra lateral.")
    st.stop()

with st.spinner("Carregant dades de la temporada…"):
    all_stints = load_season_stints(season_id)
    full_df = aggregate_stints(all_stints)
    team_rating = team_season_rating(all_stints)

if full_df.empty:
    st.info("Encara no hi ha dades d'alineacions. Afegeix partits amb jugades primer.")
    st.stop()

# ---------------------------------------------------------------------------
# Player pill selector
# ---------------------------------------------------------------------------
all_players: list[str] = sorted(
    {p for s in all_stints for p in s.players}
)

st.subheader("Filtrar per jugadores")
selected_players: list[str] = st.multiselect(
    "Selecciona 1–5 jugadores per filtrar alineacions",
    options=all_players,
    default=[],
    format_func=short_name,
    help="Només es mostraran les alineacions que incloguin TOTES les jugadores seleccionades.",
    max_selections=5,
)

# ---------------------------------------------------------------------------
# Rating selector
# ---------------------------------------------------------------------------
rating_choice = st.selectbox(
    "Ordenar per defecte per",
    ["net_rating", "off_rating", "def_rating", "minutes"],
    format_func=lambda x: {
        "net_rating": "Rating net",
        "off_rating": "Rating ofensiu",
        "def_rating": "Rating defensiu",
        "minutes": "Minuts",
    }[x],
)

# ---------------------------------------------------------------------------
# Filter stints
# ---------------------------------------------------------------------------
if selected_players:
    filtered_stints = stints_for_lineup(all_stints, selected_players)
else:
    filtered_stints = all_stints

lineup_df = aggregate_stints(filtered_stints)

if lineup_df.empty:
    st.warning("Cap alineació coincideix amb les jugadores seleccionades.")
    st.stop()

lineup_df["lineup_name"] = lineup_df["players"].apply(
    lambda p: " / ".join(short_name(x) for x in p)
)

# ---------------------------------------------------------------------------
# Summary cards
# ---------------------------------------------------------------------------
total_lineups = len(lineup_df)
total_minutes = lineup_df["minutes"].sum()
avg_net = lineup_df["net_rating"].mean()

c1, c2, c3 = st.columns(3)
c1.metric("Combinacions d'alineació", total_lineups)
c2.metric("Minuts totals", f"{total_minutes:.1f}")
c3.metric("Rating net mitjà", f"{avg_net:+.1f}")

st.divider()

# ---------------------------------------------------------------------------
# Sortable table via session state
# ---------------------------------------------------------------------------
SORTABLE_COLS = ["minutes", "pts_for", "pts_against", "off_rating", "def_rating", "net_rating", "count"]
COL_TOOLTIPS = {
    "minutes": "Minuts totals que aquesta alineació ha estat en pista conjuntament",
    "count": "Nombre de torns separats d'aquesta alineació",
    "pts_for": "Punts totals anotats pel CB Turó mentre aquesta alineació era en pista",
    "pts_against": "Punts totals rebuts mentre aquesta alineació era en pista",
    "off_rating": "Punts anotats per 40 minuts mentre aquesta alineació era en pista",
    "def_rating": "Punts rebuts per 40 minuts mentre aquesta alineació era en pista",
    "net_rating": "Rating ofensiu menys rating defensiu (com més alt millor)",
}
COL_LABELS = {
    "lineup_name": "Alineació",
    "count": "Torns",
    "minutes": "MIN",
    "pts_for": "PTS A favor",
    "pts_against": "PTS En contra",
    "off_rating": "ORtg",
    "def_rating": "DRtg",
    "net_rating": "NRtg",
}

sort_col_key = "lineup_sort_col"
sort_asc_key = "lineup_sort_asc"

if sort_col_key not in st.session_state:
    st.session_state[sort_col_key] = rating_choice
if sort_asc_key not in st.session_state:
    st.session_state[sort_asc_key] = False  # descending by default

# Column header buttons for sorting
st.markdown("**Clica una capçalera per ordenar. Clica de nou per invertir.**")

header_cols = st.columns([3, 1, 1, 1, 1, 1, 1, 1])
col_keys = ["lineup_name", "count", "minutes", "pts_for", "pts_against", "off_rating", "def_rating", "net_rating"]

for i, (hcol, ckey) in enumerate(zip(header_cols, col_keys)):
    label = COL_LABELS[ckey]
    if ckey in SORTABLE_COLS:
        is_active = st.session_state[sort_col_key] == ckey
        direction = " ▲" if (is_active and st.session_state[sort_asc_key]) else " ▼" if is_active else ""
        tooltip = COL_TOOLTIPS.get(ckey, "")
        if hcol.button(
            f"{label}{direction}",
            key=f"sort_btn_{ckey}",
            help=tooltip,
            use_container_width=True,
        ):
            if st.session_state[sort_col_key] == ckey:
                st.session_state[sort_asc_key] = not st.session_state[sort_asc_key]
            else:
                st.session_state[sort_col_key] = ckey
                st.session_state[sort_asc_key] = False
            st.rerun()
    else:
        hcol.markdown(f"**{label}**")

# Apply sort
active_sort = st.session_state[sort_col_key]
active_asc = st.session_state[sort_asc_key]

if active_sort in lineup_df.columns:
    sorted_df = lineup_df.sort_values(active_sort, ascending=active_asc).reset_index(drop=True)
else:
    sorted_df = lineup_df.sort_values("minutes", ascending=False).reset_index(drop=True)

# ---------------------------------------------------------------------------
# Render rows
# ---------------------------------------------------------------------------
DISPLAY_COLS = ["lineup_name", "count", "minutes", "pts_for", "pts_against", "off_rating", "def_rating", "net_rating"]

for _, row in sorted_df[DISPLAY_COLS].iterrows():
    row_cols = st.columns([3, 1, 1, 1, 1, 1, 1, 1])
    values = [
        row["lineup_name"],
        int(row["count"]),
        f"{row['minutes']:.1f}",
        int(row["pts_for"]),
        int(row["pts_against"]),
        f"{row['off_rating']:+.1f}",
        f"{row['def_rating']:+.1f}",
        f"{row['net_rating']:+.1f}",
    ]
    for rc, val in zip(row_cols, values):
        rc.write(val)

st.divider()

# ---------------------------------------------------------------------------
# Pinned team season row (green background)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .team-footer {
        background-color: #1a7a4a;
        color: white;
        padding: 10px 8px;
        border-radius: 6px;
        font-weight: bold;
        margin-top: 8px;
    }
    .team-footer span { margin-right: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("**Temporada completa de l'equip (fixat)**")
total_min_all = sum(s.duration for s in all_stints)
total_for_all = sum(s.pts_for for s in all_stints)
total_against_all = sum(s.pts_against for s in all_stints)
off_all = total_for_all / total_min_all * 40 if total_min_all > 0 else 0
def_all = total_against_all / total_min_all * 40 if total_min_all > 0 else 0
net_all = off_all - def_all

st.markdown(
    f"""
    <div class="team-footer">
        <span>CB Turó (Temporada completa)</span>
        <span>MIN: {total_min_all:.1f}</span>
        <span>PTS a favor: {total_for_all}</span>
        <span>PTS en contra: {total_against_all}</span>
        <span>ORtg: {off_all:+.1f}</span>
        <span>DRtg: {def_all:+.1f}</span>
        <span>NRtg: {net_all:+.1f}</span>
    </div>
    """,
    unsafe_allow_html=True,
)
