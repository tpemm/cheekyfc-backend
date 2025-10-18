import os
import requests

# ---------- Cookie/session helpers ----------

def _parse_cookie_header(raw: str):
    cookies = {}
    for pair in raw.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        cookies[k.strip()] = v.strip()
    return cookies

def _make_session():
    """Build a requests.Session with your Fantrax cookies loaded."""
    auth = os.getenv("FANTRAX_COOKIE")         # optional: just the _FantraxAuth token
    raw  = os.getenv("FANTRAX_COOKIES_RAW")    # optional: the full Cookie header value

    if not auth and not raw:
        raise RuntimeError(
            "No Fantrax cookie provided. Set FANTRAX_COOKIES_RAW (full Cookie header) "
            "or FANTRAX_COOKIE (_FantraxAuth token)."
        )
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (CheekyFC/1.0)"
    })
    # Prefer explicit _FantraxAuth if present
    if auth:
        sess.cookies.set("_FantraxAuth", auth, domain="www.fantrax.com")
    # Also set everything from the raw header if provided (JSESSIONID, cf_clearance, etc.)
    if raw:
        for k, v in _parse_cookie_header(raw).items():
            sess.cookies.set(k, v, domain="www.fantrax.com")
    return sess

# ---------- League loader compatible with multiple fantraxapi layouts ----------

def _get_league_class():
    import fantraxapi
    # modern layout: fantraxapi.League
    if hasattr(fantraxapi, "League"):
        return fantraxapi.League
    # older layout: fantraxapi.objs.League
    try:
        from fantraxapi.objs import League as LeagueObj
        return LeagueObj
    except Exception:
        pass
    if hasattr(fantraxapi, "objs") and hasattr(fantraxapi.objs, "League"):
        return fantraxapi.objs.League
    raise ImportError("Could not locate League class in fantraxapi (tried top-level and fantraxapi.objs).")

def fetch_league_objects():
    """Returns a League object with an authenticated session injected."""
    from .config import settings  # avoid import loop
    League = _get_league_class()
    sess = _make_session()

    # Try constructor variants
    try:
        # many 1.x builds accept session=
        league = League(settings.league_id, session=sess)
        return league
    except TypeError:
        pass
    try:
        # some builds accept client= (requests.Session)
        league = League(settings.league_id, client=sess)
        return league
    except TypeError:
        pass

    # Fallback: construct then attach session attribute used internally
    league = League(settings.league_id)
    if hasattr(league, "session"):
        league.session = sess
        return league
    if hasattr(league, "_session"):
        league._session = sess
        return league

    raise TypeError("League constructed but session could not be injected for this fantraxapi build.")

# ---------- Period/roster resolution that tries all variants ----------

def _list_periods(league):
    """Stable ordered list of (key, ScoringPeriod)."""
    periods = league.scoring_periods()  # dict-like
    items = list(periods.items())
    try:
        items.sort(key=lambda kv: getattr(kv[1], "number"))
    except Exception:
        pass
    return items

def _resolve_week_index(league, week: int):
    items = _list_periods(league)
    if week < 1 or week > len(items):
        raise ValueError(f"Week {week} out of range (1..{len(items)})")
    key, sp = items[week - 1]

    candidates = []
    candidates.append(("raw_key", key))         # could be int or 'Aug 15'
    try:
        candidates.append(("str_key", str(key)))
    except Exception:
        pass
    num = getattr(sp, "number", None)
    if num is not None:
        try:
            candidates.append(("number_int", int(num)))
        except Exception:
            candidates.append(("number_raw", num))
    candidates.append(("index_based", week - 1))
    return candidates, sp

def _call_roster_any(team, candidates, sp):
    """Try many calling conventions for team.roster(...)."""
    last_err = None
    for label, val in candidates:
        # positional
        try:
            return team.roster(val)
        except Exception as e:
            last_err = e
        # keyword variants
        for kw in ("week", "period", "scoring_period", "scoringPeriod", "period_number", "periodNumber"):
            try:
                return team.roster(**{kw: val})
            except Exception as e:
                last_err = e
    raise TypeError(f"team.roster failed for all variants; last error={last_err}")

def _league_team_roster_any(league, team, candidates, sp):
    """Try league.team_roster(team.id, period_number=<int>) and variants."""
    last_err = None
    ints = []
    for label, val in candidates:
        if isinstance(val, int):
            ints.append(val)
        elif isinstance(val, str) and val.isdigit():
            ints.append(int(val))

    for v in ints:
        # keyword variants
        for kw in ("period_number", "period", "scoring_period"):
            try:
                return league.team_roster(team.id, **{kw: v})
            except Exception as e:
                last_err = e
        # positional
        try:
            return league.team_roster(team.id, v)
        except Exception as e:
            last_err = e

    raise TypeError(f"league.team_roster failed for all variants; last error={last_err}")

def get_team_roster_slots(league, week: int):
    candidates, sp = _resolve_week_index(league, week)
    rows = []
    for team in league.teams:
        roster = None
        try:
            roster = _call_roster_any(team, candidates, sp)
        except Exception as team_err:
            try:
                roster = _league_team_roster_any(league, team, candidates, sp)
            except Exception as lg_err:
                raise TypeError(
                    f"Roster retrieval failed for team {team.name}. "
                    f"team.roster error: {team_err}; league.team_roster error: {lg_err}"
                )
        for slot in roster.slots:
            rows.append({
                "team_id": team.id,
                "team_name": team.name,
                "player_id": slot.player.id,
                "player_name": slot.player.name,
                "position": getattr(slot, "position", None) or getattr(slot, "slot", None),
                "is_bench": getattr(slot, "is_bench", False),
            })
    return rows
