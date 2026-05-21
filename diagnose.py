"""Test the updated scraper against the real game page."""
from scraper import scrape_game

URL = "https://www.basquetcatala.cat/estadistiques/2025/68e291f61c33a20001315a05"

print("Scraping game...")
game = scrape_game(URL)

print(f"\nHome: {game.home_team}  {game.home_score}")
print(f"Away: {game.away_team}  {game.away_score}")
print(f"MVP:  {game.mvp_player_name or '(none found)'}")

print(f"\n--- Box scores ({len(game.box_scores)} rows) ---")
for r in game.box_scores:
    print(f"  [{r.team_code}] {r.player_name}: PTS={r.pts} MIN={r.minutes} "
          f"T2={r.t2_made} T3={r.t3_made} FT={r.ft_made}/{r.ft_att} FC={r.fouls_committed}")

print(f"\n--- Play-by-play ({len(game.pbp)} events) ---")
for e in game.pbp[:20]:
    print(f"  P{e.period} min{e.minute_in_period} [{e.team_code}] "
          f"{e.event_type} {e.player_name or ''} {e.home_score}-{e.away_score}")

print("\nDone.")
