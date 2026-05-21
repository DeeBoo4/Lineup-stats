import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    """Read from env or Streamlit secrets (Cloud deployment)."""
    # 1. Local .env file (loaded by python-dotenv at the top of this module)
    val = os.getenv(key, "")
    if val:
        return val
    # 2. Streamlit Cloud secrets
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default


TEAM_NAME = "CB TURO A"
TEAM_CODE = "C"
OPPONENT_CODE = "J"

SUPABASE_URL: str = _get("SUPABASE_URL")
SUPABASE_KEY: str = _get("SUPABASE_KEY")
ADMIN_PASSWORD: str = _get("ADMIN_PASSWORD", "admin123")

BASE_URL = "https://www.basquetcatala.cat/estadistiques"
