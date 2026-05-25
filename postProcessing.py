"""Season-level aggregations built from database data."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from functions import aggregate_stints, Stint, build_stints, on_off_split
from database import get_season_box_scores, list_games, get_pbp, get_box_scores


# ---------------------------------------------------------------------------
# Season stints
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_season_stints(season_id: int) -> list[Stint]:
    """Load all game PBPs for a season and reconstruct stints."""
    games_df = list_games(season_id)
    if games_df.empty:
        return []

    all_stints: list[Stint] = []
    for _, game in games_df.iterrows():
        gid = game["id"]
        pbp = get_pbp(gid)
        box = get_box_scores(gid)
        if pbp.empty or box.empty:
            continue
        stints = build_stints(pbp, box)
        all_stints.extend(stints)
    return all_stints


# ---------------------------------------------------------------------------
# Team season rating
# ---------------------------------------------------------------------------

def team_season_rating(stints: list[Stint]) -> dict[str, float]:
    """Overall team offensive/defensive/net rating for the season."""
    total_min = sum(s.duration for s in stints)
    if total_min == 0:
        return {"off_rating": 0.0, "def_rating": 0.0, "net_rating": 0.0}
    pts_for = sum(s.pts_for for s in stints)
    pts_against = sum(s.pts_against for s in stints)
    off = pts_for / total_min * 40
    defr = pts_against / total_min * 40
    return {
        "off_rating": round(off, 1),
        "def_rating": round(defr, 1),
        "net_rating": round(off - defr, 1),
    }


# ---------------------------------------------------------------------------
# Top / bottom lineups
# ---------------------------------------------------------------------------

def top_bottom_lineups(
    stints: list[Stint],
    rating: str = "net_rating",
    n: int = 5,
    min_minutes: float = 2.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (top_n, bottom_n) DataFrames sorted by selected rating."""
    df = aggregate_stints(stints)
    if df.empty:
        return df, df
    df = df[df["minutes"] >= min_minutes].copy()
    df["lineup_name"] = df["players"].apply(lambda p: " / ".join(p))
    top = df.nlargest(n, rating)
    bottom = df.nsmallest(n, rating)
    return top, bottom


# ---------------------------------------------------------------------------
# Quarter-by-quarter scoring
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def quarter_scoring(season_id: int) -> pd.DataFrame:
    """
    Average points scored and allowed per quarter across all season games.
    Returns DataFrame with columns: quarter, avg_pts_for, avg_pts_against.
    """
    games_df = list_games(season_id)
    if games_df.empty:
        return pd.DataFrame()

    records: list[dict] = []
    for _, game in games_df.iterrows():
        gid = game["id"]
        pbp = get_pbp(gid)
        if pbp.empty:
            continue

        is_home = bool(game.get("is_home", True))
        end_events = pbp[pbp["event_type"] == "end_period"].copy()
        end_events = end_events.sort_values("abs_minute")

        prev_home, prev_away = 0, 0
        for i, row in end_events.iterrows():
            period = int(row.get("period", 0))
            if period < 1 or period > 4:
                continue
            h = int(row.get("home_score", 0))
            a = int(row.get("away_score", 0))
            pts_for = (h - prev_home) if is_home else (a - prev_away)
            pts_against = (a - prev_away) if is_home else (h - prev_home)
            records.append({
                "quarter": period,
                "pts_for": max(0, pts_for),
                "pts_against": max(0, pts_against),
            })
            prev_home, prev_away = h, a

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    summary = (
        df.groupby("quarter")
        .agg(avg_pts_for=("pts_for", "mean"), avg_pts_against=("pts_against", "mean"))
        .round(1)
        .reset_index()
    )
    return summary


# ---------------------------------------------------------------------------
# Player season totals
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def player_season_totals(season_id: int, stints: list[Stint]) -> pd.DataFrame:
    """
    Aggregate box score stats for all players in a season, plus +/- per player.
    """
    box_df = get_season_box_scores(season_id)
    if box_df.empty:
        return pd.DataFrame()

    from config import TEAM_CODE
    box_df = box_df[box_df["team_code"] == TEAM_CODE].copy()

    if box_df.empty:
        return pd.DataFrame()

    agg = (
        box_df.groupby("player_name")
        .agg(
            games=("minutes", lambda x: (x > 0).sum()),  # only count games with actual playing time
            minutes=("minutes", "sum"),
            pts=("pts", "sum"),
            t2_made=("t2_made", "sum"),
            t3_made=("t3_made", "sum"),
            ft_made=("ft_made", "sum"),
            ft_att=("ft_att", "sum"),
            fouls_committed=("fouls_committed", "sum"),
        )
        .reset_index()
    )

    agg["ft_pct"] = agg.apply(
        lambda r: round(r["ft_made"] / r["ft_att"] * 100, 1) if r["ft_att"] > 0 else 0.0,
        axis=1,
    )
    agg["pts_per_min"] = (
        agg["pts"] / agg["minutes"].replace(0, pd.NA)
    ).fillna(0.0).round(2)

    # +/- per player from stints
    plus_minus_map: dict[str, float] = {}
    on_off_map: dict[str, dict] = {}
    for _, row in agg.iterrows():
        pname = row["player_name"]
        pm_stints = [s for s in stints if pname in s.players]
        total_min = sum(s.duration for s in pm_stints)
        if total_min > 0:
            net = sum(s.pts_for - s.pts_against for s in pm_stints)
            plus_minus_map[pname] = round(net, 0)
        else:
            plus_minus_map[pname] = 0.0
        on_off_map[pname] = on_off_split(stints, pname)

    agg["plus_minus"] = agg["player_name"].map(plus_minus_map)
    agg["on_ortg"]      = agg["player_name"].map(lambda p: on_off_map[p]["on_ortg"])
    agg["on_drtg"]      = agg["player_name"].map(lambda p: on_off_map[p]["on_drtg"])
    agg["on_net_rating"]  = agg["player_name"].map(lambda p: on_off_map[p]["on_net"])
    agg["off_net_rating"] = agg["player_name"].map(lambda p: on_off_map[p]["off_net"])
    agg["on_off_diff"]    = agg["player_name"].map(lambda p: on_off_map[p]["diff"])

    return agg.sort_values("minutes", ascending=False).reset_index(drop=True)
