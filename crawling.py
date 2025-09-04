# crawling.py
import time
import random
from datetime import datetime
from sentiment import save_reviews_to_supabase, update_sentiment_in_supabase
import streamlit as st
from apify_client import ApifyClient

# Ambil API TOKEN Apify dari Streamlit secrets
API_TOKEN = st.secrets["API_TOKEN"]
client = ApifyClient(API_TOKEN)
ACTOR_ID = 'compass/Google-Maps-Scraper'  # ID actor Google Maps Scraper terbaru

# Fungsi untuk scraping Google Maps via Apify
def run_google_maps_scraper(search_term, max_reviews=15):
    run_input = {
        "searchStringsArray": [search_term],   # ✅ wajib array
        "includeReviews": True,
        "maxReviews": max_reviews,
        "maxCrawledPlacesPerSearch": 50,
        "includeImages": False,
        "includeCompanyContacts": False,
        "includeBusinessLeads": False
    }
    run = client.actor(ACTOR_ID).call(run_input=run_input)
    dataset_id = run["defaultDatasetId"]
    items = client.dataset(dataset_id).list_items().items
    return items

# Modul google_play_scraper ambil review Google Play
try:
    from google_play_scraper import reviews as playstore_reviews
except ImportError:
    playstore_reviews = None
    print("⚠️ Module google_play_scraper belum terinstall, Play Store scraping nonaktif.")

# Fungsi scraping review dari Google Play Store
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

# Fungsi utama menjalankan crawling dan analisis
def run_crawling_and_analysis(search_term=None, app_package_name=None, max_reviews=15, status_placeholder=None):
    # --- Google Maps ---
    if search_term:
        if status_placeholder:
            status_placeholder.text("📌 Crawling Google Maps via Apify...")
        try:
            gmaps_results = run_google_maps_scraper(search_term, max_reviews)
            if gmaps_results:
                if status_placeholder:
                    status_placeholder.text(f"Berhasil ambil {len(gmaps_results)} review Google Maps, menyimpan ke Supabase...")
                saved = save_reviews_to_supabase(gmaps_results, "gmaps")
                if saved:
                    if status_placeholder:
                        status_placeholder.success(f"{len(gmaps_results)} review Google Maps berhasil disimpan ke Supabase.")
                else:
                    if status_placeholder:
                        status_placeholder.error("⚠️ Beberapa review Google Maps gagal disimpan ke Supabase, cek log.")
            else:
                if status_placeholder:
                    status_placeholder.warning("⚠️ Tidak ada review Google Maps yang ditemukan.")
        except Exception as e:
            msg = f"⚠️ Gagal crawling dan simpan data dari Apify: {e}"
            if status_placeholder:
                status_placeholder.error(msg)
            print(msg)

    # --- Play Store ---
    if app_package_name:
        if status_placeholder:
            status_placeholder.text("📌 Crawling Play Store...")
        ps_reviews = get_playstore_reviews_app(app_package_name, count=max_reviews)
        if ps_reviews:
            if status_placeholder:
                status_placeholder.text(f"Berhasil ambil {len(ps_reviews)} review Play Store, menyimpan ke Supabase...")
            try:
                saved = save_reviews_to_supabase(ps_reviews, "playstore")
                if saved:
                    if status_placeholder:
                        status_placeholder.success(f"{len(ps_reviews)} review Play Store berhasil disimpan ke Supabase.")
                else:
                    if status_placeholder:
                        status_placeholder.error("⚠️ Beberapa review Play Store gagal disimpan ke Supabase, cek log.")
            except Exception as e:
                error_msg = f"⚠️ Gagal simpan review Play Store ke Supabase: {e}"
                print(error_msg)
                if status_placeholder:
                    status_placeholder.error(error_msg)
        else:
            if status_placeholder:
                status_placeholder.warning("⚠️ Tidak ada review Play Store ditemukan.")

    # --- Analisis Sentimen ---
    if search_term or app_package_name:
        if status_placeholder:
            status_placeholder.text("📌 Memulai update sentimen...")
        update_sentiment_in_supabase()
        if status_placeholder:
            status_placeholder.success("✅ Analisis sentimen selesai.")
    else:
        if status_placeholder:
            status_placeholder.warning("⚠️ Tidak ada sumber data yang dipilih, proses dibatalkan.")