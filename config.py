import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    """Read from env or Streamlit secrets (Cloud deployment)."""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


TEAM_NAME = "CB TURO A"
TEAM_CODE = "C"
OPPONENT_CODE = "J"

SUPABASE_URL: str = _get("SUPABASE_URL")
SUPABASE_KEY: str = _get("SUPABASE_KEY")
ADMIN_PASSWORD: str = _get("ADMIN_PASSWORD", "admin123")

BASE_URL = "https://www.basquetcatala.cat/estadistiques"
