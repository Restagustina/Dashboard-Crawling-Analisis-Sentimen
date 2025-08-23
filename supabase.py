from supabase import create_client as create_supabase_client

def create_client(url, key):
    return create_supabase_client(url, key)