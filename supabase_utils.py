from supabase import create_client, Client

def get_supabase_client(url=None, key=None) -> Client:
    import os
    try:
        import streamlit as st
        url = url or os.environ.get("SUPABASE_URL") or st.secrets["SUPABASE_URL"]
        key = key or os.environ.get("SUPABASE_KEY") or st.secrets["SUPABASE_KEY"]
    except (ImportError, KeyError):
        url = url or os.environ.get("SUPABASE_URL")
        key = key or os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY")

    return create_client(url, key)