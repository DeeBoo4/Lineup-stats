"""Playwright-based scraper for basquetcatala.cat — body-text parsing (no HTML tables)."""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout
from config import TEAM_NAME, TEAM_CODE, OPPONENT_CODE


# ---------------------------------------------------------------------------
# Accent-insensitive team matching
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Strip accents and uppercase for fuzzy team-name comparison.

    "CB Turó A" and "CB TURO A" both normalise to "CB TURO A".
    """
    return ''.join(
        c for c in unicodedata.normalize('NFKD', s) if ord(c) < 128
    ).upper()


_TEAM_NAME_NORM = _norm(TEAM_NAME)


def _is_cbturo(team_name: str) -> bool:
    """Return True if *team_name* refers to CB Turó (accent-insensitive)."""
    return _TEAM_NAME_NORM in _norm(team_name)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BoxScoreRow:
    player_name: str
    team_code: str
    pts: int = 0
    minutes: int = 0
    t2_made: int = 0
    t3_made: int = 0
    ft_made: int = 0
    ft_att: int = 0
    fouls_committed: int = 0


@dataclass
class PBPEvent:
    period: int
    minute_in_period: int
    abs_minute: int
    event_type: str
    player_name: Optional[str]
    team_code: str
    points: int = 0
    home_score: int = 0
    away_score: int = 0


@dataclass
class ScrapedGame:
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    box_scores: list[BoxScoreRow] = field(default_factory=list)
    pbp: list[PBPEvent] = field(default_factory=list)
    mvp_player_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Stealth init script
# ---------------------------------------------------------------------------

STEALTH_JS = """() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['ca', 'es', 'en-US'] });
    window.chrome = { runtime: {} };
}"""


# ---------------------------------------------------------------------------
# Regex for player stat lines in TIRS body text (single-line format)
# Format: #NUM NAME PTS MIN TL_m/TL_a TL% T2_m/T2_a T2% T3_m/T3_a T3% FC
# ---------------------------------------------------------------------------

STAT_LINE_RE = re.compile(
    r'^#\d+\s+'
    r'([A-ZÁÀÈÉÍÏÒÓÚÜÇÑ][A-ZÁÀÈÉÍÏÒÓÚÜÇÑ\s]+?)(?=\s+\d+\s+\d+\s+\d+/)'
    r'\s+(\d+)'           # PTS
    r'\s+(\d+)'           # MIN
    r'\s+(\d+)/(\d+)'     # TL made/att
    r'\s+(?:\d+%|-)'      # TL%
    r'\s+(\d+)/(\d+)'     # T2 made/att
    r'\s+(?:\d+%|-)'      # T2%
    r'\s+(\d+)/(\d+)'     # T3 made/att
    r'\s+(?:\d+%|-)'      # T3%
    r'\s+(\d+)',          # FC
    re.UNICODE,
)

# Stat labels that appear between values in multi-line format
_STAT_LABELS = {'PTS', 'MIN', 'TL', 'T1', 'T2', 'T3', 'FC', 'FR', 'ASS',
                'PER', 'REC', 'TAP', 'MAT', 'RO', 'RD', 'RT', 'CA', 'VAL'}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _abs_minute(period: int, minute: int) -> int:
    return (period - 1) * 10 + minute


def _parse_score(s: str) -> tuple[int, int]:
    m = re.match(r'^(\d+)-(\d+)$', s.strip())
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


# ---------------------------------------------------------------------------
# Body-text parsers
# ---------------------------------------------------------------------------

def _parse_teams_and_score(body: str) -> tuple[str, str, int, int]:
    """Extract home team, away team, home score, away score from RESUM body text."""
    lines = [l.strip() for l in body.split('\n')]
    found: list[tuple[int, str]] = []

    i = 0
    while i < len(lines) and len(found) < 2:
        if lines[i] == 'P4' and i + 3 < len(lines):
            try:
                int(lines[i + 1])          # Q4 score (discard)
                total = int(lines[i + 2])  # total score
                name = lines[i + 3].strip()
                if total >= 20 and re.match(r'^[A-ZÁÀÈÉÍÏÒÓÚÜÇÑ]', name) and len(name) > 3:
                    found.append((total, name))
                    i += 4
                    continue
            except (ValueError, IndexError):
                pass
        i += 1

    if len(found) >= 2:
        return found[0][1], found[1][1], found[0][0], found[1][0]
    return "Home", "Away", 0, 0


def _parse_mvp(body: str) -> Optional[str]:
    """Extract MVP player name from RESUM body text.
    The site labels the MVP with 'MVP', 'Millor jugador/a', or similar.
    The player name appears on one of the next lines.
    """
    lines = [l.strip() for l in body.split('\n') if l.strip()]
    _MVP_KEYWORDS = {'mvp', 'millor jugador', 'millor jugadora', 'millor jugador/a'}

    for i, line in enumerate(lines):
        if line.lower() in _MVP_KEYWORDS or line.lower().startswith('mvp'):
            # Scan the next few lines for a capitalised full name
            for j in range(i + 1, min(i + 5, len(lines))):
                candidate = lines[j]
                if (
                    re.match(r'^[A-ZÁÀÈÉÍÏÒÓÚÜÇÑ][A-ZÁÀÈÉÍÏÒÓÚÜÇÑ\s]+$', candidate, re.UNICODE)
                    and ' ' in candidate
                    and len(candidate) > 5
                ):
                    return candidate.strip()
    return None


def _parse_section_single(body: str) -> list[dict]:
    """Parse stats using the single-line regex. Returns [] if nothing matched."""
    parsed: list[dict] = []
    seen: set[str] = set()
    for line in body.splitlines():
        m = STAT_LINE_RE.match(line.strip())
        if not m:
            continue
        g = m.groups()
        name = g[0].strip()
        if name not in seen:
            seen.add(name)
            parsed.append({
                'player_name': name,
                'pts': int(g[1]), 'minutes': int(g[2]),
                'ft_made': int(g[3]), 'ft_att': int(g[4]),
                't2_made': int(g[5]), 't3_made': int(g[7]),
                'fouls_committed': int(g[9]),
            })
    return parsed


def _parse_tirs_body(body: str, home_team: str, away_team: str, home_score: int, away_score: int = 0) -> list[BoxScoreRow]:
    """Parse box scores from TIRS tab body text.

    Primary strategy: locate the two team-name headers the site prints before
    each team's stats block and use them as section boundaries. This correctly
    handles zero-point players at the team boundary.

    The split is validated by comparing point totals against the known scores,
    so that early false matches (e.g. team names in breadcrumb navigation) are
    rejected in favour of the correct stats-section split.

    Fallback: cumulative-PTS split (used when team names can't be found).
    """
    home_is_cbturo = _is_cbturo(home_team)

    # Normalize non-breaking and thin spaces that browsers emit
    body_clean = re.sub(r'[\xa0   ]', ' ', body)

    home_code = TEAM_CODE if home_is_cbturo else OPPONENT_CODE
    away_code = OPPONENT_CODE if home_is_cbturo else TEAM_CODE

    def _rows(parsed: list[dict], code: str) -> list[BoxScoreRow]:
        return [
            BoxScoreRow(
                player_name=r['player_name'], team_code=code,
                pts=r['pts'], minutes=r['minutes'],
                ft_made=r['ft_made'], ft_att=r['ft_att'],
                t2_made=r['t2_made'], t3_made=r['t3_made'],
                fouls_committed=r['fouls_committed'],
            )
            for r in parsed
        ]

    # ---- Strategy 1: split on team-name headers (accent-insensitive, all occurrences) ----
    # The page often has the team names in breadcrumb/nav as well as the actual
    # stats section header.  We collect ALL positions and try each combination
    # until we find one where BOTH sections contain at least one player.
    body_norm = _norm(body_clean)
    home_norm = _norm(home_team)
    away_norm = _norm(away_team)

    def _all_positions(text: str, sub: str) -> list[int]:
        pos, positions = 0, []
        while True:
            p = text.find(sub, pos)
            if p == -1:
                break
            positions.append(p)
            pos = p + 1
        return positions

    h_positions = _all_positions(body_norm, home_norm)
    a_positions = _all_positions(body_norm, away_norm)

    for h_pos in h_positions:
        for a_pos in a_positions:
            if h_pos == a_pos:
                continue
            if h_pos < a_pos:
                home_section = body_clean[h_pos:a_pos]
                away_section = body_clean[a_pos:]
            else:
                away_section = body_clean[a_pos:h_pos]
                home_section = body_clean[h_pos:]

            home_parsed = _parse_section_single(home_section) or _parse_tirs_multiline(home_section)
            away_parsed = _parse_section_single(away_section) or _parse_tirs_multiline(away_section)

            # Accept only when BOTH sections have players AND the PTS totals
            # match the known scores.  This rejects false splits caused by team
            # names appearing in navigation / breadcrumbs earlier in the page.
            if home_parsed and away_parsed:
                h_pts = sum(r['pts'] for r in home_parsed)
                a_pts = sum(r['pts'] for r in away_parsed)
                pts_ok = (h_pts == home_score) and (away_score == 0 or a_pts == away_score)
                if pts_ok:
                    return _rows(home_parsed, home_code) + _rows(away_parsed, away_code)

    # ---- Strategy 2 (fallback): best-fit PTS split ----
    # Instead of greedily accumulating PTS (which fails when cumsum skips past
    # home_score or when 3 pts are missing due to parsing gaps), try every
    # possible split point and pick the one that minimises the total point
    # discrepancy against the known scores.  Among ties, prefer the later split
    # so that 0-pt home players at the team boundary stay in the home block.
    all_parsed = _parse_section_single(body_clean) or _parse_tirs_multiline(body_clean)

    if not all_parsed:
        return []

    best_i = len(all_parsed) - 1
    best_score_val = float('inf')
    for i in range(len(all_parsed)):
        h_pts = sum(r['pts'] for r in all_parsed[:i + 1])
        a_pts = sum(r['pts'] for r in all_parsed[i + 1:])
        s = abs(h_pts - home_score) + (abs(a_pts - away_score) if away_score else 0)
        # Prefer later split on tie so 0-pt boundary players stay in home block
        if s < best_score_val or (s == best_score_val and i > best_i):
            best_score_val = s
            best_i = i

    return _rows(all_parsed[:best_i + 1], home_code) + _rows(all_parsed[best_i + 1:], away_code)


def _parse_tirs_multiline(body: str) -> list[dict]:
    """
    Parse TIRS stats when each value is on its own line.
    Expected token order per player: PTS, MIN, TL_frac, TL%, T2_frac, T2%, T3_frac, T3%, FC
    Labels (PTS / MIN / TL / T2 / T3 / FC) may appear interleaved and are ignored.
    """
    lines = [l.strip() for l in body.split('\n') if l.strip()]
    result: list[dict] = []
    seen: set[str] = set()

    SECTION_BREAKS = {'Llegenda', 'Rambla', 'Copyright', 'Departaments',
                      'Jugador/a', 'Estadístiques'}

    i = 0
    while i < len(lines):
        line = lines[i]

        # Stop at page footer
        if any(b in line for b in SECTION_BREAKS):
            i += 1
            continue

        # --- Detect player entry: "#NUM" alone OR "#NUM NAME" combined ---
        jersey_solo = re.match(r'^#(\d+)$', line)
        jersey_with_name = re.match(r'^#\d+\s+([A-ZÁÀÈÉÍÏÒÓÚÜÇÑ][A-ZÁÀÈÉÍÏÒÓÚÜÇÑ\s]+)$', line, re.UNICODE)

        if jersey_with_name:
            name = jersey_with_name.group(1).strip()
            token_start = i + 1
        elif jersey_solo and i + 1 < len(lines):
            name_line = lines[i + 1]
            # Verify it looks like a name (all caps, not a label or number)
            if (re.match(r'^[A-ZÁÀÈÉÍÏÒÓÚÜÇÑ][A-ZÁÀÈÉÍÏÒÓÚÜÇÑ\s]+$', name_line, re.UNICODE)
                    and name_line not in _STAT_LABELS):
                name = name_line.strip()
                token_start = i + 2
            else:
                i += 1
                continue
        else:
            i += 1
            continue

        if name in seen:
            i += 1
            continue

        # --- Collect tokens after the name ---
        j = token_start
        # Skip optional position letter (single alpha char)
        if j < len(lines) and len(lines[j]) == 1 and lines[j].isalpha():
            j += 1

        raw_tokens: list[str] = []
        while j < len(lines) and len(raw_tokens) < 20:
            t = lines[j]
            if re.match(r'^#\d+', t):   # next player
                break
            if any(b in t for b in SECTION_BREAKS):
                break
            raw_tokens.append(t)
            j += 1

        # --- Parse tokens: drop labels, collect ints/fracs/pcts ---
        values: list[tuple] = []   # ('int', n) or ('frac', made, att) or ('pct', p)
        for t in raw_tokens:
            if t in _STAT_LABELS:
                continue
            if re.match(r'^\d+/\d+$', t):
                parts = t.split('/')
                values.append(('frac', int(parts[0]), int(parts[1])))
            elif re.match(r'^\d+%$', t) or t == '-':
                values.append(('pct', 0))
            elif re.match(r'^\d+$', t):
                values.append(('int', int(t)))

        # --- Extract stats in expected order ---
        # Order: PTS(int), MIN(int), TL(frac), TL%(pct), T2(frac), T2%(pct),
        #         T3(frac), T3%(pct), FC(int)
        row = _extract_player_stats(name, values)
        if row:
            seen.add(name)
            result.append(row)

        i = j

    return result


def _extract_player_stats(name: str, values: list[tuple]) -> Optional[dict]:
    """Convert ordered token list to a player stat dict."""
    ints = [v for v in values if v[0] == 'int']
    fracs = [v for v in values if v[0] == 'frac']

    if len(ints) < 2 or len(fracs) < 1:
        return None

    pts = ints[0][1]
    mins = ints[1][1] if len(ints) > 1 else 0

    ft_made = fracs[0][1] if len(fracs) > 0 else 0
    ft_att  = fracs[0][2] if len(fracs) > 0 else 0
    t2_made = fracs[1][1] if len(fracs) > 1 else 0
    t3_made = fracs[2][1] if len(fracs) > 2 else 0

    # FC is the last integer after the fracs section
    # Find last int that appears after the 3rd fraction in original sequence
    fc = ints[-1][1] if len(ints) >= 3 else 0

    return {
        'player_name': name,
        'pts': pts, 'minutes': mins,
        'ft_made': ft_made, 'ft_att': ft_att,
        't2_made': t2_made, 't3_made': t3_made,
        'fouls_committed': fc,
    }


def _classify_event(text: str) -> tuple[str, int]:
    tl = text.lower()
    m = re.search(r'cistella de (\d)', tl)
    if m:
        return 'basket', int(m.group(1))
    if 'entra al camp' in tl:
        return 'sub_in', 0
    if 'surt del camp' in tl:
        return 'sub_out', 0
    if 'intent fallat de' in tl:
        return 'missed_ft', 0
    if any(k in tl for k in ['personal', 'antiesportiva', 'tècnica', 'tecnica', 'falta en atac']):
        return 'foul', 0
    if 'temps mort' in tl:
        return 'timeout', 0
    if 'final de període' in tl or 'final de periode' in tl:
        return 'end_period', 0
    return 'unknown', 0


def _lookup_team(name: Optional[str], home_players: set[str],
                 away_players: set[str], home_is_cbturo: bool) -> str:
    if not name:
        return TEAM_CODE
    nu = name.upper().strip()
    if _is_cbturo(nu):
        return TEAM_CODE
    for p in home_players:
        if p.upper() in nu or nu in p.upper():
            return TEAM_CODE if home_is_cbturo else OPPONENT_CODE
    for p in away_players:
        if p.upper() in nu or nu in p.upper():
            return OPPONENT_CODE if home_is_cbturo else TEAM_CODE
    return TEAM_CODE


def _parse_jugades_body(
    body: str,
    home_team: str,
    home_players: set[str],
    away_players: set[str],
) -> list[PBPEvent]:
    """Parse play-by-play events from JUGADES tab body text."""
    home_is_cbturo = _is_cbturo(home_team)
    lines = [l.strip() for l in body.split('\n')]

    events: list[PBPEvent] = []
    in_section = False

    # State
    cur_player: Optional[str] = None
    cur_etype: Optional[str] = None
    cur_pts: int = 0
    cur_min: Optional[int] = None
    cur_period: Optional[int] = None
    cur_score: Optional[str] = None
    waiting: Optional[str] = None  # 'minute' | 'period' | 'score'

    SKIP_EVENTS = {'salt guanyat', 'salt perdut'}

    def emit():
        nonlocal cur_etype, cur_min, cur_period, cur_score
        if cur_etype and cur_period is not None and cur_score and cur_etype != 'unknown':
            team = _lookup_team(cur_player, home_players, away_players, home_is_cbturo)
            h, a = _parse_score(cur_score)
            events.append(PBPEvent(
                period=cur_period,
                minute_in_period=cur_min or 0,
                abs_minute=_abs_minute(cur_period, cur_min or 0),
                event_type=cur_etype,
                player_name=cur_player,
                team_code=team,
                points=cur_pts,
                home_score=h,
                away_score=a,
            ))
        cur_etype = None
        cur_min = None
        cur_period = None
        cur_score = None

    for line in lines:
        if not line:
            continue

        # Detect section start/end
        if 'cronologia del partit' in line.lower():
            in_section = True
            continue
        if any(s in line for s in ['Rambla Guipúscoa', 'Copyright', 'Departaments']):
            break
        if not in_section:
            continue

        # --- Waiting for a value ---
        if waiting == 'minute':
            try:
                cur_min = int(line)
                waiting = None
            except ValueError:
                if 'Període' in line:
                    waiting = 'period'
                elif 'Marcador' in line:
                    waiting = 'score'
            continue

        if waiting == 'period':
            try:
                cur_period = int(line)
                waiting = None
            except ValueError:
                if 'Marcador' in line:
                    waiting = 'score'
            continue

        if waiting == 'score':
            if re.match(r'^\d{1,3}-\d{1,3}$', line):
                cur_score = line
                waiting = None
                emit()
            continue

        # --- Label lines ---
        if line == 'Min:' or line.startswith('Min: '):
            val = line[4:].strip()
            if val.isdigit():
                cur_min = int(val)
            else:
                waiting = 'minute'
            continue

        if 'Període:' in line:
            val = line.split('Període:')[-1].strip()
            if val.isdigit():
                cur_period = int(val)
            else:
                waiting = 'period'
            continue

        if 'Marcador:' in line:
            val = line.split('Marcador:')[-1].strip()
            if re.match(r'^\d{1,3}-\d{1,3}$', val):
                cur_score = val
                emit()
            else:
                waiting = 'score'
            continue

        # --- Skip single-letter initials ---
        if len(line) == 1 and line.isalpha():
            continue

        # --- Skip known non-events ---
        if any(s in line.lower() for s in SKIP_EVENTS):
            continue

        # --- Player line (#NUM NAME) ---
        pm = re.match(r'^#\d+\s+([A-ZÁÀÈÉÍÏÒÓÚÜÇÑ][A-ZÁÀÈÉÍÏÒÓÚÜÇÑ\s]+)$', line, re.UNICODE)
        if pm:
            cur_player = pm.group(1).strip()
            continue

        # --- Team name as entity (for timeouts etc.) ---
        if re.match(r'^[A-ZÁÀÈÉÍÏÒÓÚÜÇÑ][A-ZÁÀÈÉÍÏÒÓÚÜÇÑ\s]+$', line, re.UNICODE) and len(line) > 4:
            if any(k in line.upper() for k in ['CB ', 'CLUB ', 'BÀSQUET', 'BASQUET', 'CAMPING', 'BIANYA', 'TURO']):
                cur_player = line
                continue

        # --- Event line ---
        etype, pts = _classify_event(line)
        if etype != 'unknown':
            cur_etype = etype
            cur_pts = pts

    return events


# ---------------------------------------------------------------------------
# Browser setup
# ---------------------------------------------------------------------------

def _make_browser_context(playwright):
    try:
        browser = playwright.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
    except Exception:
        browser = playwright.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 768},
        locale="ca-ES",
        timezone_id="Europe/Madrid",
    )
    ctx.add_init_script(STEALTH_JS)
    return browser, ctx


def _dismiss_overlays(page: Page):
    for sel in ["text=Acceptar", "text=Accept", "text=D'acord",
                "#onetrust-accept-btn-handler", "[class*='accept']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1500):
                el.click()
                time.sleep(0.8)
                return
        except Exception:
            pass


def _wait_for_real_page(page: Page, timeout_s: int = 180):
    """Block until reCAPTCHA clears or timeout.

    Detects the captcha page by title keywords, then waits until the title
    changes AND the body has enough content to be a real game page.
    """
    _CAPTCHA_KEYS = ("Verificació", "Verifica", "reCAPTCHA", "Robot", "robot")

    for _ in range(timeout_s):
        title = page.title()
        on_captcha = any(k in title for k in _CAPTCHA_KEYS)
        if not on_captcha:
            # Make sure it's not a blank/loading page either
            try:
                if len(page.inner_text("body")) > 300:
                    return
            except Exception:
                pass
        time.sleep(1)

    raise RuntimeError(
        "La pàgina de protecció anti-bot no s'ha tancat després de resoldre el captcha. "
        "Torna-ho a provar d'aquí a uns minuts."
    )


def _click_tab(page: Page, label: str):
    for sel in [f"text={label}", f"a:has-text('{label}')", f"[role='tab']:has-text('{label}')"]:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                el.click(timeout=4000)
                time.sleep(2)
                return
        except Exception:
            continue


# ---------------------------------------------------------------------------
# PBP-based box score correction
# ---------------------------------------------------------------------------

def _replace_code(row: BoxScoreRow, code: str) -> BoxScoreRow:
    return BoxScoreRow(
        player_name=row.player_name, team_code=code,
        pts=row.pts, minutes=row.minutes,
        t2_made=row.t2_made, t3_made=row.t3_made,
        ft_made=row.ft_made, ft_att=row.ft_att,
        fouls_committed=row.fouls_committed,
    )


def _canonical_name(pbp_name: str, norm_to_tirs: dict[str, str]) -> Optional[str]:
    """Resolve a PBP player name to its canonical TIRS spelling.

    Tries exact match first, then accent-insensitive match.  Returns None if
    the name doesn't correspond to any box-score player.
    """
    if pbp_name in norm_to_tirs.values():
        return pbp_name
    return norm_to_tirs.get(_norm(pbp_name))


def _expand_via_subs(
    pbp: list[PBPEvent],
    init_cbturo: set[str],
    init_opp: set[str],
    all_names: set[str],
) -> tuple[set[str], set[str]]:
    """
    Expand team membership for 0-pt players using substitution pairing.

    Principle: when N confirmed CB Turó players sub OUT at a given minute
    and exactly N unidentified players sub IN at that same minute, those
    N players must be CB Turó replacements (and vice-versa for opponents).
    We iterate until no new identifications can be made.

    All player names are normalised to their canonical TIRS spelling so that
    minor accent differences between the TIRS and JUGADES tabs don't cause
    players to be silently dropped.
    """
    from collections import defaultdict

    # Build accent-insensitive lookup: normalised name → canonical TIRS name
    norm_to_tirs: dict[str, str] = {_norm(n): n for n in all_names}

    # Normalise the initial scorer sets to canonical TIRS spellings
    def _canonicalise(names: set[str]) -> set[str]:
        result: set[str] = set()
        for n in names:
            canon = _canonical_name(n, norm_to_tirs)
            if canon:
                result.add(canon)
        return result

    cbturo: set[str] = _canonicalise(init_cbturo)
    opp:    set[str] = _canonicalise(init_opp)

    # Group sub events by (absolute minute, team_code) so that substitutions
    # from different teams at the same dead-ball stoppage are never paired
    # together.  Without this, a CB Turó sub-out and an opponent sub-in at the
    # same minute would be mistakenly treated as a CB Turó replacement pair.
    groups: dict[tuple, dict[str, list[str]]] = defaultdict(
        lambda: {"out": [], "in": []}
    )
    for evt in pbp:
        raw_name = evt.player_name
        if not raw_name:
            continue
        canon = _canonical_name(raw_name, norm_to_tirs)
        if not canon:
            continue   # not a box-score player
        key = (evt.abs_minute, evt.team_code)
        if evt.event_type == "sub_out":
            groups[key]["out"].append(canon)
        elif evt.event_type == "sub_in":
            groups[key]["in"].append(canon)

    changed = True
    while changed:
        changed = False
        for t in sorted(groups.keys()):
            g = groups[t]
            for my_set, other_set in [(cbturo, opp), (opp, cbturo)]:
                n_my_out  = sum(1 for p in g["out"] if p in my_set)
                n_my_in   = sum(1 for p in g["in"]  if p in my_set)
                n_needed  = n_my_out - n_my_in   # how many new same-team sub-ins
                candidates = [
                    p for p in g["in"]
                    if p not in my_set and p not in other_set
                ]
                if n_needed > 0 and len(candidates) == n_needed:
                    for p in candidates:
                        my_set.add(p)
                    changed = True

    return cbturo, opp


def _reclassify_with_pbp(
    box_scores: list[BoxScoreRow],
    pbp: list[PBPEvent],
    home_is_cbturo: bool,
) -> list[BoxScoreRow]:
    """
    Correct team-code assignments using PBP data alone (no TIRS heuristics).

    Two passes:
    1. *Scorers*: walk basket events; when home_score rises the scorer is on
       the home team, when away_score rises they are on the away team.
       This is entirely objective — no team-code assumptions needed.
    2. *0-pt players*: use substitution pairing.  When N confirmed CB Turó
       players sub OUT at a given minute and exactly N unidentified players
       sub IN, those players are CB Turó (and symmetrically for opponents).
       Iterates until stable.

    Players not identified by either pass keep the code already assigned by
    _parse_tirs_body (Strategy 1 section split).

    All name comparisons are accent-insensitive so that minor spelling
    differences between the TIRS and JUGADES tabs don't cause mis-classification.
    """
    if not pbp:
        return box_scores

    # Accent-insensitive lookup for the final application step
    all_names = {r.player_name for r in box_scores}
    norm_to_tirs: dict[str, str] = {_norm(n): n for n in all_names}

    def _resolve(pbp_name: str) -> Optional[str]:
        """Map a PBP name to its canonical TIRS name (accent-insensitive)."""
        if pbp_name in all_names:
            return pbp_name
        return norm_to_tirs.get(_norm(pbp_name))

    # ---- Pass 1: scorers from score deltas ----
    # Use canonical TIRS names so the sets are directly comparable with box_scores.
    home_scorers: set[str] = set()
    away_scorers: set[str] = set()
    prev_h = prev_a = 0
    for evt in pbp:
        if evt.event_type == "basket" and evt.player_name:
            h = evt.home_score or prev_h
            a = evt.away_score or prev_a
            canon = _resolve(evt.player_name)
            if canon:
                if h > prev_h:
                    home_scorers.add(canon)
                if a > prev_a:
                    away_scorers.add(canon)
            prev_h = max(h, prev_h)
            prev_a = max(a, prev_a)

    cbturo_scorers = home_scorers if home_is_cbturo else away_scorers
    opp_scorers    = away_scorers if home_is_cbturo else home_scorers

    # ---- Pass 2: expand via substitution pairing ----
    cbturo_all, opp_all = _expand_via_subs(pbp, cbturo_scorers, opp_scorers, all_names)

    # ---- Apply: only override players we identified; rest keep original code ----
    result = list(box_scores)
    for i, r in enumerate(box_scores):
        if r.player_name in cbturo_all:
            result[i] = _replace_code(r, TEAM_CODE)
        elif r.player_name in opp_all:
            result[i] = _replace_code(r, OPPONENT_CODE)

    return result


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def scrape_game(url: str) -> ScrapedGame:
    with sync_playwright() as p:
        browser, ctx = _make_browser_context(p)
        page = ctx.new_page()
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            _wait_for_real_page(page)
            time.sleep(1)
            _dismiss_overlays(page)

            # Team names + scores + MVP from RESUM (current tab)
            resum_body = page.inner_text("body")
            home_team, away_team, home_score, away_score = _parse_teams_and_score(resum_body)
            mvp_player_name = _parse_mvp(resum_body)

            # TIRS tab — box scores
            _click_tab(page, "TIRS")
            tirs_body = page.inner_text("body")
            box_scores = _parse_tirs_body(tirs_body, home_team, away_team, home_score, away_score)

            # Build rosters for team lookup in JUGADES
            home_players = {r.player_name for r in box_scores
                            if r.team_code == (TEAM_CODE if _is_cbturo(home_team) else OPPONENT_CODE)}
            away_players = {r.player_name for r in box_scores
                            if r.team_code != (TEAM_CODE if _is_cbturo(home_team) else OPPONENT_CODE)}

            # JUGADES tab — play-by-play
            _click_tab(page, "JUGADES")
            jugades_body = page.inner_text("body")
            pbp = _parse_jugades_body(jugades_body, home_team, home_players, away_players)

            # Final score: use last PBP score if available
            if pbp:
                last = pbp[-1]
                if last.home_score or last.away_score:
                    home_score = last.home_score
                    away_score = last.away_score

            # Correct team assignments using PBP score deltas.
            # This fixes 0-pt boundary players (e.g. Julia Riu / Nerea Benitez)
            # that cumulative-PTS splitting mis-classifies.
            home_is_cbturo = _is_cbturo(home_team)
            box_scores = _reclassify_with_pbp(box_scores, pbp, home_is_cbturo)

            return ScrapedGame(
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                box_scores=box_scores,
                pbp=pbp,
                mvp_player_name=mvp_player_name,
            )
        finally:
            browser.close()
