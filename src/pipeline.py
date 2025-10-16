import pandas as pd
from pathlib import Path
from .config import settings
from .fantrax_client import fetch_league_objects, get_team_roster_slots
from .soccerdata_client import pull_fbref_player_stats
from .merge import build_or_update_idmap, merge_fantrax_fbref
from .metrics import add_basic_metrics

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ID_MAP_PATH = DATA_DIR / "id_map.csv"

def run(week: int):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    league = fetch_league_objects()
    roster_rows = get_team_roster_slots(league, week=week)
    fantrax_df = pd.DataFrame(roster_rows)
    fantrax_df.to_csv(DATA_DIR / f"cheekyfc_lineups_week{week}.csv", index=False)

    fbref_df = pull_fbref_player_stats()
    fbref_df.to_parquet(DATA_DIR / "cheekyfc_fbref_season_stats.parquet")

    id_map = build_or_update_idmap(fantrax_df, fbref_df, str(ID_MAP_PATH))

    merged = merge_fantrax_fbref(fantrax_df, fbref_df, id_map)
    merged = add_basic_metrics(merged)

    out_parquet = DATA_DIR / f"cheekyfc_player_analysis_week{week}.parquet"
    out_csv = DATA_DIR / f"cheekyfc_player_analysis_week{week}.csv"
    merged.to_parquet(out_parquet, index=False)
    merged.to_csv(out_csv, index=False)

    return str(out_csv)
