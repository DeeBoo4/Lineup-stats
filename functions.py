"""Lineup reconstruction and pts/40min rating calculations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import pandas as pd

from config import TEAM_CODE


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Stint:
    lineup_key: str           # pipe-separated sorted player names
    players: list[str]
    start_abs: float
    end_abs: float
    pts_for: int = 0
    pts_against: int = 0

    @property
    def duration(self) -> float:
        return max(0.0, self.end_abs - self.start_abs)

    @property
    def off_rating(self) -> float:
        return self.pts_for / self.duration * 40 if self.duration > 0 else 0.0

    @property
    def def_rating(self) -> float:
        return self.pts_against / self.duration * 40 if self.duration > 0 else 0.0

    @property
    def net_rating(self) -> float:
        return self.off_rating - self.def_rating


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _lineup_key(players: list[str]) -> str:
    return "|".join(sorted(players))


def _detect_home_away(events: list[dict], cbturo_players: set[str]) -> bool:
    """Return True if CB Turó is the home team.

    Looks at the first basket scored by a CB Turó player and checks whether
    the home score or the away score went up — that tells us which side we
    are on, regardless of what team_code the scraper assigned.
    """
    prev_h, prev_a = 0, 0
    for evt in events:
        h = int(evt.get("home_score") or prev_h)
        a = int(evt.get("away_score") or prev_a)
        if evt.get("event_type") == "basket" and evt.get("player_name") in cbturo_players:
            if h > prev_h:
                return True   # home score rose → CB Turó is home
            if a > prev_a:
                return False  # away score rose → CB Turó is away
        prev_h, prev_a = h, a
    return True  # fallback (can't determine, assume home)


# ---------------------------------------------------------------------------
# Lineup reconstruction
# ---------------------------------------------------------------------------

def build_stints(pbp_df: pd.DataFrame, box_df: pd.DataFrame) -> list[Stint]:
    """
    Reconstruct CB Turó on-court lineups from play-by-play and box score data.

    pbp_df columns: abs_minute, minute_in_period, period, event_type,
                    player_name, team_code, home_score, away_score
    box_df columns: player_name, team_code, minutes
    """
    if pbp_df.empty:
        return []

    cbturo_players: set[str] = set(
        box_df.loc[
            (box_df["team_code"] == TEAM_CODE) & (box_df["minutes"] > 0),
            "player_name",
        ]
    )

    # Sort: by abs_minute, with end_period events last within the same minute
    events = pbp_df.assign(
        _sort_order=pbp_df["event_type"].map(lambda v: 1 if v == "end_period" else 0)
    ).sort_values(["abs_minute", "_sort_order"]).drop(columns="_sort_order").to_dict("records")

    cbturo_is_home = _detect_home_away(events, cbturo_players)

    active: list[str] = []
    stints: list[Stint] = []
    stint_start: float = 0.0
    score_at_start: tuple[int, int] = (0, 0)

    def close(end_abs: float, h: int, a: int):
        nonlocal stint_start, score_at_start
        if not active or end_abs <= stint_start:
            return
        dh = max(0, h - score_at_start[0])
        da = max(0, a - score_at_start[1])
        stints.append(
            Stint(
                lineup_key=_lineup_key(active),
                players=sorted(active),
                start_abs=stint_start,
                end_abs=end_abs,
                pts_for=dh if cbturo_is_home else da,
                pts_against=da if cbturo_is_home else dh,
            )
        )

    for evt in events:
        abs_min = float(evt.get("abs_minute", 0))
        etype = str(evt.get("event_type", ""))
        player = str(evt.get("player_name") or "")
        team = str(evt.get("team_code") or "")
        h = int(evt.get("home_score") or score_at_start[0])
        a = int(evt.get("away_score") or score_at_start[1])
        period_min = int(evt.get("minute_in_period", 1))

        if etype == "sub_in" and player in cbturo_players:
            # Note: we do NOT filter by team_code here because PBP team codes
            # can be mis-assigned; cbturo_players (from box scores) is the
            # reliable source of truth after PBP-based reclassification.
            if period_min == 0:
                # Period-start batch — accumulate starters without closing
                if player not in active:
                    active.append(player)
            else:
                close(abs_min, h, a)
                if player not in active:
                    active.append(player)
                stint_start = abs_min
                score_at_start = (h, a)

        elif etype == "sub_out" and player in cbturo_players:
            if period_min != 0 and player in active:
                close(abs_min, h, a)
                active.remove(player)
                stint_start = abs_min
                score_at_start = (h, a)

        elif etype == "end_period":
            close(abs_min, h, a)
            stint_start = abs_min
            score_at_start = (h, a)

    return stints


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_stints(stints: list[Stint]) -> pd.DataFrame:
    """Roll up stints into a per-lineup summary DataFrame."""
    if not stints:
        return pd.DataFrame(columns=[
            "lineup_key", "players", "count", "minutes",
            "pts_for", "pts_against", "off_rating", "def_rating", "net_rating",
        ])

    from collections import defaultdict
    grouped: dict[str, list[Stint]] = defaultdict(list)
    for s in stints:
        grouped[s.lineup_key].append(s)

    records = []
    for key, group in grouped.items():
        total_min = sum(s.duration for s in group)
        total_for = sum(s.pts_for for s in group)
        total_against = sum(s.pts_against for s in group)
        off = total_for / total_min * 40 if total_min > 0 else 0.0
        defr = total_against / total_min * 40 if total_min > 0 else 0.0
        records.append({
            "lineup_key": key,
            "players": group[0].players,
            "count": len(group),
            "minutes": round(total_min, 2),
            "pts_for": total_for,
            "pts_against": total_against,
            "off_rating": round(off, 1),
            "def_rating": round(defr, 1),
            "net_rating": round(off - defr, 1),
        })

    return (
        pd.DataFrame(records)
        .sort_values("minutes", ascending=False)
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Player-level calculations
# ---------------------------------------------------------------------------

def on_off_split(stints: list[Stint], player_name: str) -> dict[str, float]:
    """Net rating per 40min when the player is on vs off the court."""
    on = [s for s in stints if player_name in s.players]
    off = [s for s in stints if player_name not in s.players]

    def _net(group: list[Stint]) -> float:
        mins = sum(s.duration for s in group)
        if mins == 0:
            return 0.0
        return (sum(s.pts_for for s in group) - sum(s.pts_against for s in group)) / mins * 40

    return {
        "on_net": round(_net(on), 1),
        "off_net": round(_net(off), 1),
        "diff": round(_net(on) - _net(off), 1),
    }


def stints_for_lineup(stints: list[Stint], players: list[str]) -> list[Stint]:
    """Return stints where the court contains all of the given players."""
    pset = set(players)
    return [s for s in stints if pset.issubset(set(s.players))]


def short_name(full_name: str) -> str:
    """Return first name + first surname only (first two space-separated words).

    Examples:
        "ALEXIA REIXACH FONT"  → "ALEXIA REIXACH"
        "NEREA BENITEZ"        → "NEREA BENITEZ"   (already short)
        "MARIA JOSE GARCIA"    → "MARIA JOSE"
    """
    parts = full_name.strip().split()
    return " ".join(parts[:2]) if len(parts) >= 2 else full_name
