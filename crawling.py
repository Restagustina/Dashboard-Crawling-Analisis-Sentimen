# crawling.py
import streamlit as st
from serpapi import GoogleSearch
from urllib.parse import urlsplit, parse_qsl
from sentiment import save_reviews_to_supabase, update_sentiment_in_supabase
from datetime import datetime
import time
import random

# ========================
# GOOGLE MAPS (SerpApi)
# ========================
def run_serpapi_gmaps_paginated(place_id, api_key, max_reviews=15):
    """Scraping review Google Maps pakai SerpApi dengan pagination."""
    print(f"[INFO] Mulai crawling Google Maps dengan place_id={place_id}")

    params = {
        "engine": "google_maps_reviews",
        "data_id": place_id,
        "hl": "id",  # Bahasa Indonesia
        "api_key": api_key,
    }

    search = GoogleSearch(params)
    all_reviews = []

    while True:
        results = search.get_dict()
        print(f"[DEBUG] Keys di results: {list(results.keys()) if results else 'None'}")

        if not results or "error" in results:
            print(f"[WARNING] Error/Empty dari SerpApi: {results.get('error') if results else 'No data'}")
            break

        review_results = results.get("reviews", []) or results.get("reviews_results", [])
        print(f"[DEBUG] Jumlah review batch ini: {len(review_results)}")
        all_reviews.extend(review_results)

        serpapi_pagination = results.get("serpapi_pagination", {})
        next_url = serpapi_pagination.get("next")

        if next_url and len(all_reviews) < max_reviews:
            search.params_dict.update(dict(parse_qsl(urlsplit(next_url).query)))
            print(f"[INFO] Lanjut ke halaman berikutnya, total review saat ini: {len(all_reviews)}")
        else:
            break

    print(f"[INFO] Total review yang dikumpulkan: {len(all_reviews[:max_reviews])}")

    # Bersihkan hasil
    cleaned_reviews = [
        {
            "review_id": rev.get("review_id"),
            "username": rev.get("user", {}).get("name") if isinstance(rev.get("user"), dict) else rev.get("user"),
            "comment_text": rev.get("snippet"),
            "rating": rev.get("rating"),
            "created_at": rev.get("date"),
        }
        for rev in all_reviews[:max_reviews]
    ]

    return cleaned_reviews


# ========================
# GOOGLE PLAY STORE
# ========================
try:
    from google_play_scraper import reviews as playstore_reviews
except ImportError:
    playstore_reviews = None
    print("⚠️ Module google_play_scraper belum terinstall, Play Store scraping nonaktif.")

def get_playstore_reviews_app(app_package_name, count=10, max_retries=3, max_loops=5):
    if playstore_reviews is None:
        print("[WARNING] google_play_scraper module tidak tersedia.")
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
                    print(f"[DEBUG] batch {loops}, cursor={cursor}")
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


# ========================
# WRAPPER: Crawling + Analisis
# ========================
def run_crawling_and_analysis(source: str, status_placeholder, app_package_name=None):
    place_id = st.secrets.get("PLACE_ID")
    api_key = st.secrets.get("SERPAPI_KEY")

    gmaps_results = []
    playstore_results = []

    # --------- Google Maps ---------
    if source in ["Google Maps", "Keduanya"]:
        status_placeholder.info("⏳ Sedang crawling review Google Maps...")
        gmaps_results = run_serpapi_gmaps_paginated(place_id=place_id, api_key=api_key, max_reviews=15)

        if not gmaps_results:
            status_placeholder.error("⚠️ Tidak ada review Google Maps ditemukan. Stop proses.")
            print("[INFO] Tidak ada review ditemukan dari SerpApi. Stop proses Google Maps.")
        else:
            print(f"[INFO] Simpan {len(gmaps_results)} review Google Maps ke Supabase...")
            save_reviews_to_supabase(gmaps_results, "gmaps")

            updated = update_sentiment_in_supabase()
            status_placeholder.success(f"✅ Analisis sentimen Google Maps selesai. {updated} review dianalisis.")

    # --------- Google Play Store ---------
    if source in ["Google Play Store", "Keduanya"]:
        status_placeholder.info("⏳ Sedang crawling review Google Play Store...")
        if app_package_name:
            playstore_results = get_playstore_reviews_app(app_package_name, count=15)

            if playstore_results:
                save_reviews_to_supabase(playstore_results, "playstore")
                updated = update_sentiment_in_supabase()
                status_placeholder.success(f"✅ Analisis sentimen Play Store selesai. {updated} review dianalisis.")
            else:
                status_placeholder.warning("⚠️ Tidak ada review Play Store yang ditemukan.")

    print("[INFO] Crawling selesai.")
    status_placeholder.info("Crawling selesai! Silakan buka tab lain untuk melihat hasil.")