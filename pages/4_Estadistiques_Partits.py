import streamlit as st

from database import list_games, get_box_scores, get_pbp
from functions import short_name, build_stints
from config import TEAM_CODE

st.set_page_config(page_title="Estadístiques Partits", layout="wide")
st.title("Estadístiques Partits")

season_id = st.session_state.get("season_id")
season_label = st.session_state.get("season_label", "—")

if not season_id:
    st.info("Selecciona una temporada des de la barra lateral.")
    st.stop()

st.subheader(f"Temporada {season_label}")

games_df = list_games(season_id)

if games_df.empty:
    st.info("Encara no hi ha partits per a aquesta temporada.")
    st.stop()


def _game_label(row) -> str:
    opp    = row["away_team"] if row["is_home"] else row["home_team"]
    our    = row["home_score"] if row["is_home"] else row["away_score"]
    them   = row["away_score"] if row["is_home"] else row["home_score"]
    result = "V" if our > them else "D"
    loc    = "L" if row["is_home"] else "V"
    return f"{row['game_date']}  ·  {loc}  ·  {opp}  ·  {our}–{them} ({result})"


game_options = {
    _game_label(row): row["id"]
    for _, row in games_df.iterrows()
}

sel = st.selectbox("Selecciona el partit", list(game_options.keys()))
gid = game_options[sel]

box = get_box_scores(gid)

if box.empty:
    st.info("No hi ha estadístiques per a aquest partit.")
    st.stop()

cb_box = box[box["team_code"] == TEAM_CODE].copy()

if cb_box.empty:
    st.info("No hi ha estadístiques del CB Turó per a aquest partit.")
    st.stop()

# +/- per player from stints
pbp = get_pbp(gid)
if not pbp.empty:
    game_stints = build_stints(pbp, box)
    pm_map = {}
    for pname in cb_box["player_name"]:
        p_stints = [s for s in game_stints if pname in s.players]
        total_min = sum(s.duration for s in p_stints)
        pm_map[pname] = (
            round(sum(s.pts_for - s.pts_against for s in p_stints))
            if total_min > 0 else 0
        )
    cb_box["plus_minus"] = cb_box["player_name"].map(pm_map).fillna(0)
else:
    cb_box["plus_minus"] = 0

cb_box["ft_pct"] = cb_box.apply(
    lambda r: round(r["ft_made"] / r["ft_att"] * 100, 1)
    if r["ft_att"] > 0 else 0.0,
    axis=1,
)

cb_box = cb_box.sort_values("minutes", ascending=False)
cb_box["player_name"] = cb_box["player_name"].apply(short_name)

display_cols = [
    "player_name", "minutes", "pts",
    "t2_made", "t3_made",
    "ft_made", "ft_att", "ft_pct",
    "fouls_committed", "plus_minus",
]
col_labels = {
    "player_name":     "Jugadora",
    "minutes":         "MIN",
    "pts":             "PTS",
    "t2_made":         "T2",
    "t3_made":         "T3",
    "ft_made":         "TL",
    "ft_att":          "TLI",
    "ft_pct":          "TL%",
    "fouls_committed": "FC",
    "plus_minus":      "+/−",
}

game_display = cb_box[display_cols].rename(columns=col_labels)

st.dataframe(
    game_display,
    hide_index=True,
    use_container_width=True,
    column_config={
        "TL%": st.column_config.NumberColumn(format="%.1f%%"),
        "+/−": st.column_config.NumberColumn(format="%+.0f"),
    },
)

# Team totals
totals = cb_box[["minutes", "pts", "t2_made", "t3_made",
                  "ft_made", "ft_att", "fouls_committed"]].sum()
ft_pct_total = (
    round(totals["ft_made"] / totals["ft_att"] * 100, 1)
    if totals["ft_att"] > 0 else 0.0
)
st.markdown(
    f"**Totals equip** — "
    f"MIN: {int(totals['minutes'])} · "
    f"PTS: {int(totals['pts'])} · "
    f"T2: {int(totals['t2_made'])} · "
    f"T3: {int(totals['t3_made'])} · "
    f"TL: {int(totals['ft_made'])}/{int(totals['ft_att'])} ({ft_pct_total}%) · "
    f"FC: {int(totals['fouls_committed'])}"
)
