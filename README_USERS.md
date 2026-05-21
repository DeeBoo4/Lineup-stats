# CB Turó Analytics — Viewer Guide

Welcome! This guide explains how to use the CB Turó basketball analytics app. No technical knowledge needed — if you can use a website, you can use this app.

---

## Opening the App

You will have received a link that looks something like:
`https://cbturo-analytics.streamlit.app`

Open it in any web browser on your phone, tablet, or computer. No account or login is needed to view the data.

---

## Switching Between Seasons

On the left side of every page there is a **sidebar**. At the top of the sidebar you will see a **Season** selector — a dropdown menu where you can choose which season's data to view (for example, "2024/25" or "2025/26").

Once you select a season, all pages update automatically to show data for that season.

---

## The Four Pages

Use the links in the sidebar to navigate between pages.

---

### Dashboard

This is the overview page. It shows three key numbers at the top:

**Offensive Rating**
How many points CB Turó scores per 40 minutes of game time, on average. A higher number means the team is scoring more efficiently. Think of it as: if the team played a full 40-minute game at this rate, how many points would they score?

**Defensive Rating**
How many points the opponents score per 40 minutes. Here, a lower number is better — it means the team is defending well and limiting the other team's scoring.

**Net Rating**
Offensive rating minus defensive rating. This single number captures whether CB Turó is winning or losing the scoring battle overall. A positive number means the team is outscoring opponents; negative means opponents are outscoring them.

Below the three numbers, a **bar chart** shows quarter-by-quarter scoring across the season — how many points CB Turó scores and allows on average in each quarter (Q1 through Q4).

At the bottom, you'll see two tables: **Top 5 Lineups** and **Bottom 5 Lineups**. These show which five-player combinations have performed best and worst this season. You can choose whether to rank them by Net Rating, Offensive Rating, or Defensive Rating using the dropdown above the tables.

---

### Game Log

This page lists all games recorded for the selected season, showing the date, teams, and final score.

If you are an admin (the person managing the app), you will also see options to add new games. Regular viewers only see the list.

---

### Player Stats

This page shows a table with individual statistics for every CB Turó player this season.

**Columns explained:**

| Column | Meaning |
|--------|---------|
| Player | Player's name |
| GP | Games played |
| MIN | Total minutes played |
| PTS | Total points scored |
| 2PM | Two-point field goals made |
| 3PM | Three-point field goals made |
| FTM | Free throws made |
| FTA | Free throws attempted |
| FT% | Free throw percentage |
| FC | Personal fouls committed |
| +/− | Point differential while on court (positive = team outscored opponents, negative = opponents outscored team) |

At the top right of the page there is a toggle called **Show On/Off Ratings**. Turn it on to see two extra columns:

- **On NRtg**: The team's net rating per 40 minutes when this player is on the court.
- **Off NRtg**: The team's net rating per 40 minutes when this player is *not* on the court.
- **On−Off**: The difference between the two. A large positive number means the team performs significantly better with this player on the court.

---

### Lineup Explorer

This is the most powerful page. It lets you explore how specific combinations of players perform together.

**Selecting players**

At the top of the page there is a search box labelled **"Select 1–5 players to filter lineups"**. Click it and type a player's name to search, or scroll through the list. You can select up to 5 players.

Once you select players, the table below will show only the lineups that include all of your selected players. For example, if you select two players, you'll see every five-man lineup that contained both of them.

Leave the selector empty to see all lineups for the season.

**Reading the table**

Each row in the table represents one specific five-player combination. The columns are:

| Column | Meaning |
|--------|---------|
| Lineup | The five players in this combination |
| Stints | How many separate stretches of play this group had together |
| MIN | Total minutes this lineup played together |
| PTS For | Total points CB Turó scored while this lineup was on court |
| PTS Vs | Total points the opponents scored while this lineup was on court |
| ORtg | Offensive rating: points scored per 40 minutes |
| DRtg | Defensive rating: points allowed per 40 minutes |
| NRtg | Net rating: ORtg minus DRtg |

**Sorting the table**

You can sort by any column by clicking the column header button. Click once to sort descending (highest first); click again to sort ascending (lowest first). An arrow (▲ or ▼) shows the current sort direction. The **Lineup** column is not sortable. By default, the table is sorted by Minutes (most time on court first).

**Hover tooltips**

If you hover your mouse over a column header for about three seconds, a small tooltip appears explaining what that statistic means. It disappears when you move the mouse away.

**The green row at the bottom**

Below the table, there is always a green row labelled **CB Turó (Full Season)**. This shows the team's overall ratings for the entire season — no matter what filters you have applied above. It is pinned there so you always have a reference point to compare individual lineups against. If a lineup has a higher NRtg than the green row, that lineup has outperformed the team average.

---

## Questions?

If something doesn't look right or you have questions about the data, contact the person who shared this link with you.
