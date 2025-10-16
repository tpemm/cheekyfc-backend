from pydantic import BaseModel
from dotenv import load_dotenv
import os
load_dotenv()
class Settings(BaseModel):
    fantrax_username: str = os.getenv("FANTRAX_USERNAME", "")
    fantrax_password: str = os.getenv("FANTRAX_PASSWORD", "")
    league_id: str = os.getenv("LEAGUE_ID", "")
    season: str = os.getenv("SEASON", "2025-2026")
    competition: str = os.getenv("COMPETITION", "Premier League")
settings = Settings()
