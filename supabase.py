import os
from supabase import create_client as create_supabase_client

def create_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    return create_supabase_client(url, key)