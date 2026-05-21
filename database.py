from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def season_label(d: date) -> str:
    """Return '2024/25' style label for a game date."""
    if d.month >= 9:
        return f"{d.year}/{str(d.year + 1)[-2:]}"
    return f"{d.year - 1}/{str(d.year)[-2:]}"


# ---------------------------------------------------------------------------
# Seasons
# ---------------------------------------------------------------------------

def upsert_season(label: str) -> int:
    """Insert season if not present, return its id."""
    sb = get_client()
    resp = sb.table("seasons").select("id").eq("label", label).execute()
    if resp.data:
        return resp.data[0]["id"]
    resp = sb.table("seasons").insert({"label": label}).execute()
    return resp.data[0]["id"]


def list_seasons() -> pd.DataFrame:
    sb = get_client()
    resp = sb.table("seasons").select("*").order("label", desc=True).execute()
    return _df(resp.data)


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------

def upsert_game(
    season_id: int,
    game_url: str,
    game_date: date,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    is_home: bool,
    mvp_player_name: str | None = None,
) -> int:
    sb = get_client()
    resp = sb.table("games").select("id").eq("game_url", game_url).execute()
    payload = {
        "season_id": season_id,
        "game_url": game_url,
        "game_date": game_date.isoformat(),
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "is_home": is_home,
        "mvp_player_name": mvp_player_name,
    }
    if resp.data:
        gid = resp.data[0]["id"]
        sb.table("games").update(payload).eq("id", gid).execute()
        return gid
    resp = sb.table("games").insert(payload).execute()
    return resp.data[0]["id"]


def set_game_mvp(game_id: int, player_name: str | None):
    sb = get_client()
    sb.table("games").update({"mvp_player_name": player_name}).eq("id", game_id).execute()


def get_season_mvp_counts(season_id: int) -> dict[str, int]:
    """Return {player_name: mvp_count} for all games in a season."""
    sb = get_client()
    resp = (
        sb.table("games")
        .select("mvp_player_name")
        .eq("season_id", season_id)
        .not_.is_("mvp_player_name", "null")
        .execute()
    )
    counts: dict[str, int] = {}
    for row in resp.data:
        name = row["mvp_player_name"]
        if name:
            counts[name] = counts.get(name, 0) + 1
    return counts


def list_games(season_id: int) -> pd.DataFrame:
    sb = get_client()
    resp = (
        sb.table("games")
        .select("*")
        .eq("season_id", season_id)
        .order("game_date", desc=True)
        .execute()
    )
    return _df(resp.data)


def get_game(game_id: int) -> dict | None:
    sb = get_client()
    resp = sb.table("games").select("*").eq("id", game_id).execute()
    return resp.data[0] if resp.data else None


def delete_game(game_id: int):
    sb = get_client()
    sb.table("play_by_play_events").delete().eq("game_id", game_id).execute()
    sb.table("player_box_scores").delete().eq("game_id", game_id).execute()
    sb.table("lineup_stints").delete().eq("game_id", game_id).execute()
    sb.table("lineups").delete().eq("game_id", game_id).execute()
    sb.table("games").delete().eq("id", game_id).execute()


# ---------------------------------------------------------------------------
# Player box scores
# ---------------------------------------------------------------------------

def upsert_box_scores(game_id: int, rows: list[dict[str, Any]]):
    sb = get_client()
    sb.table("player_box_scores").delete().eq("game_id", game_id).execute()
    if rows:
        for r in rows:
            r["game_id"] = game_id
        sb.table("player_box_scores").insert(rows).execute()


def get_box_scores(game_id: int) -> pd.DataFrame:
    sb = get_client()
    resp = sb.table("player_box_scores").select("*").eq("game_id", game_id).execute()
    return _df(resp.data)


def get_season_box_scores(season_id: int) -> pd.DataFrame:
    sb = get_client()
    # First get game IDs for this season, then fetch box scores for those games
    games_resp = sb.table("games").select("id").eq("season_id", season_id).execute()
    if not games_resp.data:
        return pd.DataFrame()
    game_ids = [r["id"] for r in games_resp.data]
    resp = (
        sb.table("player_box_scores")
        .select("*")
        .in_("game_id", game_ids)
        .execute()
    )
    return _df(resp.data)


# ---------------------------------------------------------------------------
# Play-by-play
# ---------------------------------------------------------------------------

def upsert_pbp(game_id: int, rows: list[dict[str, Any]]):
    sb = get_client()
    sb.table("play_by_play_events").delete().eq("game_id", game_id).execute()
    if rows:
        for r in rows:
            r["game_id"] = game_id
        sb.table("play_by_play_events").insert(rows).execute()


def get_pbp(game_id: int) -> pd.DataFrame:
    sb = get_client()
    resp = (
        sb.table("play_by_play_events")
        .select("*")
        .eq("game_id", game_id)
        .order("abs_minute")
        .execute()
    )
    return _df(resp.data)


# ---------------------------------------------------------------------------
# Lineups & stints
# ---------------------------------------------------------------------------

def upsert_lineups(game_id: int, lineup_rows: list[dict], stint_rows: list[dict]):
    sb = get_client()
    sb.table("lineup_stints").delete().eq("game_id", game_id).execute()
    sb.table("lineups").delete().eq("game_id", game_id).execute()

    lineup_id_map: dict[str, int] = {}
    for lr in lineup_rows:
        lr["game_id"] = game_id
        resp = sb.table("lineups").insert(lr).execute()
        lineup_id_map[lr["lineup_key"]] = resp.data[0]["id"]

    for sr in stint_rows:
        sr["game_id"] = game_id
        sr["lineup_id"] = lineup_id_map[sr.pop("lineup_key")]
    if stint_rows:
        sb.table("lineup_stints").insert(stint_rows).execute()


def get_stints(season_id: int) -> pd.DataFrame:
    sb = get_client()
    lineup_resp = sb.table("lineups").select("id").eq("season_id", season_id).execute()
    if not lineup_resp.data:
        return pd.DataFrame()
    lineup_ids = [r["id"] for r in lineup_resp.data]
    resp = (
        sb.table("lineup_stints")
        .select("*, lineups(lineup_key)")
        .in_("lineup_id", lineup_ids)
        .execute()
    )
    return _df(resp.data)


def get_all_stints_for_season(season_id: int) -> pd.DataFrame:
    """Return stints joined with lineup_key — two-step to avoid cross-filter issues."""
    sb = get_client()
    lineup_resp = (
        sb.table("lineups")
        .select("id, lineup_key, player1, player2, player3, player4, player5")
        .eq("season_id", season_id)
        .execute()
    )
    if not lineup_resp.data:
        return pd.DataFrame()
    lineup_ids = [r["id"] for r in lineup_resp.data]
    stints_resp = (
        sb.table("lineup_stints")
        .select("*")
        .in_("lineup_id", lineup_ids)
        .execute()
    )
    return _df(stints_resp.data)
