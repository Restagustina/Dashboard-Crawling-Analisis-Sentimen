# gmaps_autocraw.py
import time
import re
import os
import threading
from datetime import datetime
from crawling import get_gmaps_reviews_selenium_debug
from sentiment import save_reviews_to_supabase, update_sentiment_in_supabase
from supabase_utils import get_supabase_client
from apscheduler.schedulers.blocking import BlockingScheduler

# Ambil secrets dari environment variables atau Streamlit secrets
try:
    import streamlit as st
    SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or st.secrets["SUPABASE_KEY"]
    GMAPS_URL = os.environ.get("GMAPS_URL") or st.secrets["GMAPS_URL"]
except (ImportError, KeyError):
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    GMAPS_URL = os.environ.get("GMAPS_URL")

if not all([SUPABASE_URL, SUPABASE_KEY, GMAPS_URL]):
    raise RuntimeError("Missing one or more required secrets: SUPABASE_URL, SUPABASE_KEY, GMAPS_URL")

# Setup Supabase client
supabase = get_supabase_client()

# Konfigurasi crawling
MAX_REVIEWS = 20

def extract_place_id_or_slug(url):
    match = re.search(r"place_id:([^&]+)", url)
    if match:
        return match.group(1)
    slug_match = re.search(r"/maps/place/([^/@]+)", url)
    slug = slug_match.group(1).replace("+", "_") if slug_match else "gmaps_fallback"
    return f"{slug.lower()}_{int(time.time())}"

def heartbeat_logger(interval=30):
    def loop():
        while True:
            print(f"[HEARTBEAT] GMaps crawler aktif - {datetime.now().isoformat()}")
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True).start()

def run_job():
    PLACE_ID = extract_place_id_or_slug(GMAPS_URL)
    print(f"[INFO] Target crawling: {GMAPS_URL}")
    print(f"[INFO] place_id/log key: {PLACE_ID}")
    heartbeat_logger()
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