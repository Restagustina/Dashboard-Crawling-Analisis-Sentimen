import os

try:
    import streamlit as st
    SUPABASE_URL = st.secrets.get("SUPABASE_URL")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
except Exception:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

from supabase import create_client, Client

def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)