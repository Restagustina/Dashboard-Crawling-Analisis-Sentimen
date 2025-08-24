import os

try:
    import streamlit as st
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except (ImportError, AttributeError, KeyError):
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

from supabase import create_client, Client

def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)