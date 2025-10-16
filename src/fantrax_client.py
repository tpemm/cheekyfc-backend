from .config import settings
from fantraxapi import League

def fetch_league_objects():
    league = League(settings.league_id, username=settings.fantrax_username, password=settings.fantrax_password)
    return league

def get_team_roster_slots(league, week: int):
    rows = []
    for team in league.teams:
        roster = team.roster(week=week)
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
