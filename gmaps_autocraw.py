import time
import re
import os
from datetime import datetime
from crawling import get_gmaps_reviews_selenium_debug
from sentiment import save_reviews_to_supabase, update_sentiment_in_supabase
from supabase_utils import get_supabase_client
import signal

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
TIMEOUT_SECONDS = 600  # 10 menit

def extract_place_id_or_slug(url):
    match = re.search(r"place_id:([^&]+)", url)
    if match:
        return match.group(1)
    slug_match = re.search(r"/maps/place/([^/@]+)", url)
    slug = slug_match.group(1).replace("+", "_") if slug_match else "gmaps_fallback"
    return f"{slug.lower()}_{int(time.time())}"

# Timeout handler untuk hentikan crawling kalau lewat batas waktu
def timeout_handler(signum, frame):
    raise TimeoutError("⏱ Crawling GMaps timeout exceeded.")

def run_job():
    PLACE_ID = extract_place_id_or_slug(GMAPS_URL)
    print(f"[INFO] Target crawling: {GMAPS_URL}")
    print(f"[INFO] place_id/log key: {PLACE_ID}")
    start_time = time.time()
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(TIMEOUT_SECONDS)  # Pasang timer timeout

    try:
        reviews = get_gmaps_reviews_selenium_debug(GMAPS_URL, max_reviews=MAX_REVIEWS)
        signal.alarm(0)  # Matikan alarm jika berhasil selesai
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

    except TimeoutError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        status = "error"
        error_msg = str(e)
        review_count = None
        print(f"❌ Timeout: {error_msg}")
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

if __name__ == "__main__":
    run_job()