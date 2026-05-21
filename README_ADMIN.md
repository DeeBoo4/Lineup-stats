# CB Turó Analytics — Admin Guide

This guide is for the person managing the app: setting it up, adding games, deploying to the cloud, and handling common issues.

---

## 1. Initial Setup (Local)

### Prerequisites
- Python 3.11 or newer
- Git
- A Supabase account (free tier is fine)

### Clone and install

```bash
git clone <your-repo-url>
cd Lineups
pip install -r requirements.txt
python -m playwright install chromium
```

### Configure your .env file

Copy the example file and fill it in:

```bash
cp .env.example .env
```

Open `.env` in a text editor and set:

```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-service-role-key
ADMIN_PASSWORD=choose-something-strong
```

- **SUPABASE_URL**: Found in your Supabase project → Settings → API → Project URL.
- **SUPABASE_KEY**: Use the **service role** key (Settings → API → `service_role`). This key bypasses row-level security for writes. Keep it secret — never commit it to a public repo.
- **ADMIN_PASSWORD**: Any password you choose. Share it only with people who need to add games.

### Set up the Supabase database

1. Go to your Supabase project → SQL Editor.
2. Paste the contents of `schema.sql` and run it.
3. This creates all required tables and read-only policies for public users.

### Run the app locally

```bash
python -m streamlit run main.py
```

The app opens at `http://localhost:8501`.

> **Windows note:** Use `python -m streamlit run main.py` instead of `streamlit run main.py` — Windows doesn't always add pip scripts to the PATH, so the bare `streamlit` command may not be recognised.

---

## 2. Adding a Game

Log in via the sidebar ("Admin login" expander). Then go to **Game Log**.

### Scraping from URL

1. Find the game on [basquetcatala.cat](https://www.basquetcatala.cat).
2. Open the game page. The URL looks like: `https://www.basquetcatala.cat/estadistiques/2025/12345`
3. Paste the URL into the "Scrape from URL" tab and click **Scrape & Save**.
4. The scraper takes 30–60 seconds. It fetches both the box score (Tirs tab) and play-by-play (Jugades tab), saves everything to the database, and rebuilds lineup stints.

> **What happens behind the scenes:** The scraper launches a headless Chromium browser, navigates to the page, clicks each tab, reads the tables, then closes the browser. All data is saved to Supabase automatically.

### Manual entry fallback

If the scraper fails (see Troubleshooting below), switch to the **Manual Entry** tab:

- Enter the date, team names, and final score.
- You can leave the URL field blank or enter the game URL for reference.
- **Note:** Without play-by-play data, lineup ratings will not be available for that game. Box score stats (points, minutes, etc.) will also be missing unless you enter them separately.

---

## 3. Deploy to Streamlit Community Cloud

Streamlit Community Cloud lets you host the app for free so all staff can access it via a shared URL.

### Steps

1. Push your code to a **public or private GitHub repository**.
   - Make sure `.env` is in `.gitignore` — never commit credentials.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app** → select your repository, branch, and set the main file to `main.py`.
4. Under **Advanced settings → Secrets**, add your credentials in TOML format:

```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_KEY = "your-service-role-key"
ADMIN_PASSWORD = "your-admin-password"
```

5. Click **Deploy**. Streamlit builds and hosts the app. You get a public URL like `https://your-app-name.streamlit.app`.
6. Share that URL with your staff. They can view everything without logging in.

> **Playwright on Cloud:** Streamlit Community Cloud supports Playwright but requires the browser to be installed at runtime. Add this file to your repo:

**`packages.txt`** (create this file):
```
chromium
chromium-driver
```

This installs Chromium on the cloud server automatically.

---

## 4. Starting a New Season

1. Log in as admin.
2. On the home page sidebar, open **Create new season** and type the label (e.g. `2025/26`).
3. Click **Create Season**.
4. The new season now appears in the season selector for all users.
5. Switch to the new season and start adding games.

> Seasons run September–May. A game played in October 2025 and one in March 2026 both belong to `2025/26`. The app does not auto-assign season based on date — you select the season manually before adding a game.

---

## 5. Troubleshooting Common Scraper Issues

### Bot block / page doesn't load
The federation site occasionally blocks automated browsers. Try:
- Wait a few minutes and retry — rate limiting often resets.
- Check that the URL is correct and the game page loads in a normal browser.
- If blocked repeatedly, use the Manual Entry fallback and record stats by hand.

### Game ID not found (404 or empty page)
- Double-check the URL. The pattern is `.../estadistiques/{year}/{game_id}`.
- Some games may not be published yet or may have been removed.
- Older seasons may have different URL structures.

### Player name mismatch
The scraper cross-references names between the box score and play-by-play. If a player appears differently in each tab (e.g. accent differences, abbreviated names), they may be counted as two separate players in the lineup data.

**Fix:** After scraping, if you notice duplicated players in the Lineup Explorer or Player Stats, you can manually edit the player names in the Supabase table editor (Table Editor → `player_box_scores` or `play_by_play_events`). Make the names consistent, then re-run the lineup calculation by deleting and re-adding the game.

### Lineup data missing despite PBP being scraped
This happens if the play-by-play has no substitution events, or if all players sub in at minute 0 of each period (which counts as a lineup reset, not individual subs). Check the raw PBP in the Supabase `play_by_play_events` table to verify events were captured.

### App error on startup ("Cannot connect to database")
- Check that your `.env` file (local) or Streamlit secrets (Cloud) are correctly set.
- Verify the Supabase project is active (free-tier projects pause after 1 week of inactivity — you can unpause from the Supabase dashboard).

---

## 6. Repository Structure

```
main.py              — App entry point and sidebar
pages/
  1_Dashboard.py     — Season overview
  2_Game_Log.py      — Game list and add-game form
  3_Player_Stats.py  — Player season totals
  4_Lineup_Explorer.py — Lineup filter and comparison
scraper.py           — Playwright scraper (Tirs + Jugades tabs)
database.py          — Supabase read/write functions
functions.py         — Lineup reconstruction and ratings
postProcessing.py    — Season aggregations
auth.py              — Admin login/logout logic
config.py            — Reads credentials from .env or Streamlit secrets
schema.sql           — Database schema (run once in Supabase)
requirements.txt     — Python dependencies
packages.txt         — System packages for Streamlit Cloud (Chromium)
.env.example         — Template for local credentials
```
