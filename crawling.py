# crawling.py
import requests
import time
import random
from datetime import datetime
from sentiment import save_reviews_to_supabase, update_sentiment_in_supabase
import streamlit as st

# Lobstr.io API untuk crawling GMaps
LOBSTR_API_TOKEN = st.secrets.get("LOBSTR_API_TOKEN")  # ambil langsung dari secrets Streamlit
LOBSTR_API_BASE = "https://api.lobstr.io/v1"

# Play Store Scraper
try:
    from google_play_scraper import reviews as playstore_reviews
except ImportError:
    playstore_reviews = None
    print("⚠️ Module google_play_scraper belum terinstall, Play Store scraping nonaktif.")

# =======================
# Panggil API eksternal Lobstr.io tambah task
# =======================
def call_external_api(payload=None):
    api_url = f"{LOBSTR_API_BASE}/tasks"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {LOBSTR_API_TOKEN}"
    }
    try:
        if payload is None:
            payload = {}
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Gagal memanggil API eksternal: {e}")
        return None

# =======================
# Fungsi panggilan crawling dengan payload task
# =======================
def start_crawling_with_lobstr(squid_id, urls):
    payload = {
        "cluster": squid_id,
        "tasks": [{"url": url} for url in urls]
    }
    result = call_external_api(payload)
    return result

# =======================
# GMaps Scraper via Lobstr.io API
# =======================
def get_gmaps_reviews_lobstr(gmaps_url, max_reviews=10):
    headers = {
        "Authorization": f"Token {LOBSTR_API_TOKEN}",
        "Accept": "application/json",
    }

    endpoint = f"{LOBSTR_API_BASE}/crawlers/google_maps/reviews"

    params = {
        "url": gmaps_url,
        "max_results": max_reviews,
    }

    response = requests.get(endpoint, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        reviews = []
        for item in data.get("reviews", []):
            reviews.append({
                "review_id": item.get("id"),
                "username": item.get("user_name"),
                "comment_text": item.get("comment"),
                "rating": item.get("rating"),
                "created_at": item.get("time"),
            })
        return reviews
    else:
        print(f"Failed fetching Lobstr GMaps reviews: {response.status_code} {response.text}")
        return []

# =======================
# Play Store Scraper
# =======================
def get_playstore_reviews_app(app_package_name, count=10, max_retries=3, max_loops=5):
    if playstore_reviews is None:
        return []

    all_reviews = []
    cursor = None
    loops = 0

    try:
        while loops < max_loops:
            loops += 1
            for attempt in range(1, max_retries + 1):
                try:
                    result, cursor = playstore_reviews(
                        app_package_name,
                        lang='id',
                        count=count,
                        continuation_token=cursor
                    )
                    print(f"DEBUG: batch {loops}, cursor={cursor}")
                    time.sleep(random.uniform(1.5, 3.0))
                    break
                except Exception as e:
                    print(f"⚠️ Error scraping Play Store (attempt {attempt}): {e}")
                    if attempt == max_retries:
                        return all_reviews
                    time.sleep(random.uniform(2, 5))

            for rev in result:
                all_reviews.append({
                    "review_id": str(rev.get("reviewId")),
                    "username": rev.get("userName"),
                    "comment_text": rev.get("content"),
                    "rating": rev.get("score"),
                    "created_at": rev.get("at").isoformat() if isinstance(rev.get("at"), datetime) else None
                })

            if cursor is None:
                break

    except Exception as e:
        print(f"⚠️ Fatal error scraping Play Store: {e}")
    return all_reviews

# =======================
# Main Run crawling dan Analisis
# =======================
def run_crawling_and_analysis(gmaps_url=None, app_package_name=None, max_reviews=10):
    # Crawling GMaps
    if gmaps_url:
        print("📌 Crawling GMaps...")
        gmaps_reviews = get_gmaps_reviews_lobstr(gmaps_url, max_reviews=max_reviews)
        print(f"DEBUG: Jumlah review GMaps yang ditemukan = {len(gmaps_reviews)}")
        if gmaps_reviews:
            save_reviews_to_supabase(gmaps_reviews, "gmaps")
        else:
            print("⚠️ Tidak ada review GMaps yang ditemukan!")

    # Crawling Play Store
    if app_package_name:
        print("📌 Crawling Play Store...")
        ps_reviews = get_playstore_reviews_app(app_package_name, count=max_reviews)
        print(f"DEBUG: Jumlah review Play Store yang ditemukan = {len(ps_reviews)}")
        if ps_reviews:
            save_reviews_to_supabase(ps_reviews, "playstore")
        else:
            print("⚠️ Tidak ada review Play Store yang ditemukan!")

    # Analisis Sentimen (jika ada data baru)
    if gmaps_url or app_package_name:
        print("📌 Update sentiment...")
        update_sentiment_in_supabase()
        print("✅ Selesai.")
    else:
        print("⚠️ Tidak ada sumber data yang dipilih, proses dibatalkan.")