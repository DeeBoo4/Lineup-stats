-- CB Turó Analytics — Supabase PostgreSQL schema
-- Run this in the Supabase SQL editor to create all required tables.

-- -----------------------------------------------------------------------
-- Seasons
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS seasons (
    id      BIGSERIAL PRIMARY KEY,
    label   TEXT NOT NULL UNIQUE   -- e.g. "2024/25"
);

-- -----------------------------------------------------------------------
-- Games
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS games (
    id          BIGSERIAL PRIMARY KEY,
    season_id   BIGINT NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    game_url    TEXT UNIQUE,
    game_date   DATE NOT NULL,
    home_team   TEXT NOT NULL,
    away_team   TEXT NOT NULL,
    home_score  INTEGER NOT NULL DEFAULT 0,
    away_score  INTEGER NOT NULL DEFAULT 0,
    is_home     BOOLEAN NOT NULL DEFAULT TRUE   -- TRUE = CB Turó is home team
);

-- -----------------------------------------------------------------------
-- Player box scores  (one row per player per game)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS player_box_scores (
    id              BIGSERIAL PRIMARY KEY,
    game_id         BIGINT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    player_name     TEXT NOT NULL,
    team_code       TEXT NOT NULL,   -- "C" = CB Turó, "J" = opponent
    pts             INTEGER NOT NULL DEFAULT 0,
    minutes         INTEGER NOT NULL DEFAULT 0,
    t2_made         INTEGER NOT NULL DEFAULT 0,
    t3_made         INTEGER NOT NULL DEFAULT 0,
    ft_made         INTEGER NOT NULL DEFAULT 0,
    ft_att          INTEGER NOT NULL DEFAULT 0,
    fouls_committed INTEGER NOT NULL DEFAULT 0
);

-- -----------------------------------------------------------------------
-- Play-by-play events
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS play_by_play_events (
    id                 BIGSERIAL PRIMARY KEY,
    game_id            BIGINT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    period             INTEGER NOT NULL,          -- 1–4
    minute_in_period   INTEGER NOT NULL,          -- 0–10
    abs_minute         NUMERIC(6,2) NOT NULL,     -- (period-1)*10 + minute
    event_type         TEXT NOT NULL,
        -- sub_in | sub_out | basket | missed_ft | foul | timeout | end_period | unknown
    player_name        TEXT,
    team_code          TEXT NOT NULL,             -- "C" or "J"
    points             INTEGER NOT NULL DEFAULT 0,
    home_score         INTEGER NOT NULL DEFAULT 0,
    away_score         INTEGER NOT NULL DEFAULT 0
);

-- -----------------------------------------------------------------------
-- Lineups  (unique 5-man group, season-scoped)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lineups (
    id          BIGSERIAL PRIMARY KEY,
    game_id     BIGINT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    season_id   BIGINT NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    lineup_key  TEXT NOT NULL,   -- pipe-separated sorted player names
    player1     TEXT,
    player2     TEXT,
    player3     TEXT,
    player4     TEXT,
    player5     TEXT
);

-- -----------------------------------------------------------------------
-- Lineup stints  (one row per continuous on-court interval)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lineup_stints (
    id          BIGSERIAL PRIMARY KEY,
    game_id     BIGINT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    lineup_id   BIGINT NOT NULL REFERENCES lineups(id) ON DELETE CASCADE,
    start_abs   NUMERIC(6,2) NOT NULL,
    end_abs     NUMERIC(6,2) NOT NULL,
    duration    NUMERIC(6,2) NOT NULL,
    pts_for     INTEGER NOT NULL DEFAULT 0,
    pts_against INTEGER NOT NULL DEFAULT 0
);

-- -----------------------------------------------------------------------
-- Row-level security: admin role writes, authenticated/anon reads
-- -----------------------------------------------------------------------

ALTER TABLE seasons          ENABLE ROW LEVEL SECURITY;
ALTER TABLE games            ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_box_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE play_by_play_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE lineups          ENABLE ROW LEVEL SECURITY;
ALTER TABLE lineup_stints    ENABLE ROW LEVEL SECURITY;

-- Allow anyone to SELECT (public read-only)
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'seasons','games','player_box_scores',
        'play_by_play_events','lineups','lineup_stints'
    ]) LOOP
        EXECUTE format(
            'CREATE POLICY "%s_select_all" ON %I FOR SELECT USING (true)',
            tbl, tbl
        );
    END LOOP;
END $$;

-- The app uses the service-role key (admin) for all writes.
-- No additional INSERT/UPDATE/DELETE policies are needed because
-- the service-role key bypasses RLS entirely.
