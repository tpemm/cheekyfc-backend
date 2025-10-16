import pandas as pd
from rapidfuzz import process, fuzz

def build_or_update_idmap(fantrax_df: pd.DataFrame, fbref_df: pd.DataFrame, id_map_path: str) -> pd.DataFrame:
    try:
        id_map = pd.read_csv(id_map_path)
    except FileNotFoundError:
        id_map = pd.DataFrame(columns=["player_id", "player_name", "fbref_id", "fbref_player_name", "confidence"])

    fbref_names = fbref_df["fbref_player_name"].dropna().unique().tolist()
    new_rows = []
    for pid, pname in fantrax_df[["player_id", "player_name"]].drop_duplicates().itertuples(index=False):
        if (id_map["player_id"] == pid).any():
            continue
        match = process.extractOne(pname, fbref_names, scorer=fuzz.WRatio)
        if match:
            fb_name, score, _ = match
            fb_rows = fbref_df[fbref_df["fbref_player_name"] == fb_name]
            fb_id = fb_rows.index[0] if fb_rows.index.size > 0 else None
            new_rows.append({
                "player_id": pid,
                "player_name": pname,
                "fbref_id": fb_id,
                "fbref_player_name": fb_name,
                "confidence": score
            })
    if new_rows:
        id_map = pd.concat([id_map, pd.DataFrame(new_rows)], ignore_index=True)
    id_map = id_map.sort_values(["player_id","confidence"], ascending=[True, False]).drop_duplicates("player_id", keep="first")
    id_map.to_csv(id_map_path, index=False)
    return id_map

def merge_fantrax_fbref(fantrax_df: pd.DataFrame, fbref_df: pd.DataFrame, id_map: pd.DataFrame) -> pd.DataFrame:
    merged = fantrax_df.merge(id_map[["player_id","fbref_id","fbref_player_name","confidence"]], on="player_id", how="left")
    tmp = fantrax_df.merge(fbref_df, left_on="player_name", right_on="fbref_player_name", how="left", suffixes=("","_fb"))
    for col in ["goals","assists","xg","xa","npxg","matches","minutes","team_name_fbref","pos_fbref"]:
        if col in tmp:
            merged[col] = merged[col].fillna(tmp[col])
    return merged
