import streamlit as st
import pandas as pd
from datetime import date

from auth import is_admin, hide_streamlit_ui
from database import (
    upsert_game,
    upsert_box_scores,
    upsert_pbp,
    upsert_lineups,
    list_games,
    delete_game,
    set_game_mvp,
    get_box_scores,
    season_label as make_season_label,
)
from functions import build_stints, _lineup_key
from postProcessing import load_season_stints, quarter_scoring, player_season_totals
from config import TEAM_NAME

st.set_page_config(page_title="Registre de Partits", layout="wide")
hide_streamlit_ui()
st.title("Registre de Partits")

season_id = st.session_state.get("season_id")
season_lbl = st.session_state.get("season_label", "—")

if not season_id:
    st.info("Selecciona una temporada des de la barra lateral.")
    st.stop()

# ---------------------------------------------------------------------------
# Game list
# ---------------------------------------------------------------------------
games_df = list_games(season_id)

st.subheader(f"Temporada {season_lbl} — {len(games_df)} partit(s)")

if not games_df.empty:
    display_df = games_df[["game_date", "home_team", "away_team", "home_score", "away_score"]].copy()
    display_df.columns = ["Data", "Local", "Visitant", "Punts Local", "Punts Visitant"]
    display_df["Resultat"] = display_df.apply(
        lambda r: f"{r['Punts Local']} – {r['Punts Visitant']}", axis=1
    )
    mvp_col = games_df["mvp_player_name"] if "mvp_player_name" in games_df.columns else None
    display_df["MVP"] = mvp_col.fillna("—") if mvp_col is not None else "—"

    # Determine win/loss for each row
    is_win = games_df.apply(
        lambda r: (r["home_score"] > r["away_score"]) if r.get("is_home", True)
                  else (r["away_score"] > r["home_score"]),
        axis=1,
    )

    show_cols = ["Data", "Local", "Visitant", "Resultat", "MVP"]

    def _color_result_col(col):
        """Apply background colour only to the Resultat column."""
        return [
            f"background-color: {'#c6efce' if is_win.loc[idx] else '#ffc7ce'}; color: #000000"
            for idx in col.index
        ]

    styled = display_df[show_cols].style.apply(
        _color_result_col, subset=["Resultat"], axis=0
    )

    st.dataframe(
        styled,
        hide_index=True,
        use_container_width=True,
    )

    if is_admin():
        with st.expander("Canviar MVP del partit (detectat automàticament — només per corregir)"):
            game_options = {
                f"{row['game_date']} — {row['home_team']} vs {row['away_team']}": row["id"]
                for _, row in games_df.iterrows()
            }
            sel_mvp = st.selectbox("Selecciona el partit", list(game_options.keys()), key="mvp_game_sel")
            selected_game_id = game_options[sel_mvp]
            box = get_box_scores(selected_game_id)
            from config import TEAM_CODE
            cb_players = sorted(box.loc[box["team_code"] == TEAM_CODE, "player_name"].tolist()) if not box.empty else []
            if cb_players:
                current_mvp = games_df.loc[games_df["id"] == selected_game_id, "mvp_player_name"].values
                current_mvp = current_mvp[0] if len(current_mvp) > 0 and current_mvp[0] else None
                mvp_choice = st.selectbox(
                    "Jugadora MVP",
                    ["(cap)"] + cb_players,
                    index=(cb_players.index(current_mvp) + 1) if current_mvp in cb_players else 0,
                    key="mvp_player_sel",
                )
                if st.button("Desar MVP", key="save_mvp_btn"):
                    set_game_mvp(selected_game_id, None if mvp_choice == "(cap)" else mvp_choice)
                    st.success("MVP desat.")
                    st.rerun()
            else:
                st.info("No hi ha estadístiques de CB Turó per a aquest partit — importa primer el partit per URL.")

        with st.expander("Eliminar un partit"):
            game_options_del = {
                f"{row['game_date']} — {row['home_team']} vs {row['away_team']}": row["id"]
                for _, row in games_df.iterrows()
            }
            sel = st.selectbox("Selecciona el partit a eliminar", list(game_options_del.keys()), key="del_game_sel")
            if st.button("Eliminar partit", type="primary"):
                delete_game(game_options_del[sel])
                load_season_stints.clear()
                quarter_scoring.clear()
                player_season_totals.clear()
                st.success("Partit eliminat.")
                st.rerun()

st.divider()

if not is_admin():
    st.info("Cal accés d'administrador per afegir partits.")
    st.stop()

# ---------------------------------------------------------------------------
# Add game section (admin only)
# ---------------------------------------------------------------------------
st.subheader("Afegir un nou partit")

from scraper import scrape_game, _is_cbturo

tab_url, tab_manual = st.tabs(["Importar per URL", "Entrada manual"])

# ---- URL scraper ----
with tab_url:
    # -- Session cookie --
    with st.expander("🔑 Cookie de sessió (necessària per importar)", expanded="fcbq_cookie" not in st.session_state):
        st.markdown(
            """
**Com obtenir la cookie:**
1. Obre Chrome i visita qualsevol pàgina de **www.basquetcatala.cat** (per exemple, la URL del partit que vols importar).
2. Obre DevTools amb **F12** → pestanya **Application** → **Storage** → **Cookies** → `www.basquetcatala.cat`.
3. Cerca la cookie **`fcbq_rc`** i copia el seu valor.
4. Enganxa'l aquí a continuació.

*La cookie caduca cada pocs dies. Torna a copiar-la si la importació falla amb un error de cookie.*
            """
        )
        cookie_input = st.text_area(
            "Valor de la cookie `fcbq_rc`",
            value=st.session_state.get("fcbq_cookie", ""),
            height=80,
            placeholder="eyJzdGF0dXMiOiJ...",
            key="cookie_input_field",
        )
        if st.button("Desar cookie", key="save_cookie_btn"):
            st.session_state["fcbq_cookie"] = cookie_input.strip()
            st.success("Cookie desada per a aquesta sessió.")

    session_cookie = st.session_state.get("fcbq_cookie", "").strip()

    url_input = st.text_input(
        "URL del partit",
        placeholder="https://www.basquetcatala.cat/estadistiques/2025/12345",
    )
    if st.button("Importar i desar", key="scrape_btn"):
        if not url_input.strip():
            st.error("Introdueix una URL.")
        elif not session_cookie:
            st.error("Cal introduir la cookie de sessió abans d'importar. Desplega la secció '🔑 Cookie de sessió' a dalt.")
        else:
            with st.spinner("Descarregant i processant el partit…"):
                try:
                    game_data = scrape_game(url_input.strip(), session_cookie=session_cookie)

                        game_date_guess = date.today()
                        slabel = make_season_label(game_date_guess)
                        is_home = _is_cbturo(game_data.home_team)

                        gid = upsert_game(
                            season_id=season_id,
                            game_url=url_input.strip(),
                            game_date=game_date_guess,
                            home_team=game_data.home_team,
                            away_team=game_data.away_team,
                            home_score=game_data.home_score,
                            away_score=game_data.away_score,
                            is_home=is_home,
                            mvp_player_name=game_data.mvp_player_name,
                        )

                        box_rows = [
                            {
                                "player_name": r.player_name,
                                "team_code": r.team_code,
                                "pts": r.pts,
                                "minutes": r.minutes,
                                "t2_made": r.t2_made,
                                "t3_made": r.t3_made,
                                "ft_made": r.ft_made,
                                "ft_att": r.ft_att,
                                "fouls_committed": r.fouls_committed,
                            }
                            for r in game_data.box_scores
                        ]
                        upsert_box_scores(gid, box_rows)

                        pbp_rows = [
                            {
                                "period": e.period,
                                "minute_in_period": e.minute_in_period,
                                "abs_minute": e.abs_minute,
                                "event_type": e.event_type,
                                "player_name": e.player_name,
                                "team_code": e.team_code,
                                "points": e.points,
                                "home_score": e.home_score,
                                "away_score": e.away_score,
                            }
                            for e in game_data.pbp
                        ]
                        upsert_pbp(gid, pbp_rows)

                        # Build and save lineups/stints
                        import pandas as pd
                        pbp_df = pd.DataFrame(pbp_rows)
                        box_df = pd.DataFrame(box_rows)
                        stints = build_stints(pbp_df, box_df)

                        from collections import defaultdict
                        lineup_rows = []
                        seen_keys: set[str] = set()
                        for s in stints:
                            if s.lineup_key not in seen_keys:
                                seen_keys.add(s.lineup_key)
                                players = s.players + [""] * (5 - len(s.players))
                                lineup_rows.append({
                                    "lineup_key": s.lineup_key,
                                    "season_id": season_id,
                                    "player1": players[0] if len(players) > 0 else "",
                                    "player2": players[1] if len(players) > 1 else "",
                                    "player3": players[2] if len(players) > 2 else "",
                                    "player4": players[3] if len(players) > 3 else "",
                                    "player5": players[4] if len(players) > 4 else "",
                                })

                        stint_rows = [
                            {
                                "lineup_key": s.lineup_key,
                                "start_abs": s.start_abs,
                                "end_abs": s.end_abs,
                                "duration": s.duration,
                                "pts_for": s.pts_for,
                                "pts_against": s.pts_against,
                            }
                            for s in stints
                        ]
                        upsert_lineups(gid, lineup_rows, stint_rows)

                        load_season_stints.clear()
                        quarter_scoring.clear()
                        player_season_totals.clear()
                        mvp_msg = f" · MVP: {game_data.mvp_player_name}" if game_data.mvp_player_name else ""
                        st.success(f"Partit desat! {game_data.home_team} {game_data.home_score} – {game_data.away_score} {game_data.away_team}{mvp_msg}")
                        st.rerun()

                    except Exception as exc:
                        st.error(f"Error en la importació: {exc}")
                        st.warning("Pots introduir el partit manualment a la pestanya 'Entrada manual' a continuació.")

# ---- Manual entry ----
with tab_manual:
    st.caption("Utilitza això si la importació falla o el partit no és al web de la federació.")
    with st.form("manual_game_form"):
        col1, col2 = st.columns(2)
        with col1:
            m_date = st.date_input("Data del partit", value=date.today())
            m_home = st.text_input("Equip local", value=TEAM_NAME)
            m_away = st.text_input("Equip visitant", placeholder="Nom de l'adversari")
        with col2:
            m_url = st.text_input("URL (opcional)", placeholder="https://…")
            m_home_score = st.number_input("Punts local", min_value=0, value=0, step=1)
            m_away_score = st.number_input("Punts visitant", min_value=0, value=0, step=1)
        m_is_home = st.checkbox("El CB Turó juga de local", value=True)
        submitted = st.form_submit_button("Desar partit")

    if submitted:
        if not m_away.strip():
            st.error("Introdueix el nom de l'adversari.")
        else:
            gid = upsert_game(
                season_id=season_id,
                game_url=m_url.strip() or f"manual_{m_date.isoformat()}_{m_away}",
                game_date=m_date,
                home_team=m_home.strip(),
                away_team=m_away.strip(),
                home_score=int(m_home_score),
                away_score=int(m_away_score),
                is_home=m_is_home,
            )
            load_season_stints.clear()
            quarter_scoring.clear()
            player_season_totals.clear()
            st.success(f"Partit desat (id={gid}). Sense dades de jugades — les valoracions no estaran disponibles per a aquest partit.")
            st.rerun()
