import time
import re
from datetime import datetime
from crawling import get_gmaps_reviews_selenium_debug
from sentiment import save_reviews_to_supabase, update_sentiment_in_supabase
from supabase import create_client
from apscheduler.schedulers.blocking import BlockingScheduler

# Ambil secrets
try:
    import streamlit as st
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GMAPS_URL = st.secrets["GMAPS_URL"]
except ImportError:
    import toml
    secrets = toml.load("secrets.toml")
    SUPABASE_URL = secrets["SUPABASE_URL"]
    SUPABASE_KEY = secrets["SUPABASE_KEY"]
    GMAPS_URL = secrets["GMAPS_URL"]

# Setup Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Konfigurasi crawling
MAX_REVIEWS = 20

# Ekstrak place_id dari URL jika tersedia
match = re.search(r"place_id:([^&]+)", GMAPS_URL)
PLACE_ID = match.group(1) if match else "gmaps_indralaya"

def run_job():
    start_time = time.time()
    print(f"⏰ [{datetime.now().isoformat()}] Mulai crawling GMaps...")

    try:
        reviews = get_gmaps_reviews_selenium_debug(GMAPS_URL, max_reviews=MAX_REVIEWS)
        duration_ms = int((time.time() - start_time) * 1000)
        review_count = len(reviews)

        if reviews:
            save_reviews_to_supabase(reviews, source="gmaps")
            update_sentiment_in_supabase()
            status = "success"
            error_msg = None
            print(f"✅ Crawling selesai. Jumlah review: {review_count}")
        else:
            status = "partial"
            error_msg = "Tidak ada review ditemukan."
            print("⚠️ Tidak ada review yang berhasil diambil.")

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        status = "error"
        error_msg = str(e)
        review_count = None
        print(f"❌ Crawling gagal: {error_msg}")

    # Simpan log ke Supabase
    supabase.table("crawl_logs_gmaps").insert({
        "place_id": PLACE_ID,
        "timestamp": datetime.utcnow().isoformat(),
        "status": status,
        "error_msg": error_msg,
        "review_count": review_count,
        "processed_at": datetime.utcnow().isoformat(),
        "duration_ms": duration_ms,
        "source": "gmaps_autocraw",
        "notes": None
    }).execute()

def start_scheduler():
    scheduler = BlockingScheduler()
    scheduler.add_job(run_job, 'interval', days=3)
    print("🕒 Scheduler aktif. Crawling akan dijalankan setiap 3 hari sekali...")
    scheduler.start()

if __name__ == "__main__":
    start_scheduler()