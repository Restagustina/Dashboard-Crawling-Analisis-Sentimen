# crawling.py
import time
import random
from datetime import datetime
from sentiment import save_reviews_to_supabase, update_sentiment_in_supabase
import streamlit as st
from serpapi import GoogleSearch


def run_serpapi_gmaps(place_id, max_reviews=15):
    """Scraping review Google Maps pakai SerpApi (pakai Place ID)."""
    api_key = st.secrets["SERPAPI_KEY"]

    search = GoogleSearch({
        "engine": "google_maps_reviews",
        "data_id": place_id,   # Gunakan Place ID Google Maps
        "hl": "id",            # Bahasa Indonesia
        "api_key": api_key
    })

    results = search.get_dict()
    reviews = results.get("reviews", [])

    cleaned_reviews = []
    for rev in reviews[:max_reviews]:
        cleaned_reviews.append({
            "review_id": rev.get("review_id"),
            "username": rev.get("user", {}).get("name") if isinstance(rev.get("user"), dict) else rev.get("user"),
            "comment_text": rev.get("snippet"),
            "rating": rev.get("rating"),
            "created_at": rev.get("date")
        })
    return cleaned_reviews


# --- GOOGLE PLAY STORE ---
try:
    from google_play_scraper import reviews as playstore_reviews
except ImportError:
    playstore_reviews = None
    print("⚠️ Module google_play_scraper belum terinstall, Play Store scraping nonaktif.")


def get_playstore_reviews_app(app_package_name, count=10, max_retries=3, max_loops=5):
    """Scraping review Play Store pakai google_play_scraper."""
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


# --- FUNGSIONAL UTAMA ---
def run_crawling_and_analysis(place_id=None, app_package_name=None, max_reviews=15, status_placeholder=None):
    # --- Google Maps ---
    if place_id:
        if status_placeholder:
            status_placeholder.text("📌 Crawling Google Maps via SerpApi...")
        try:
            gmaps_results = run_serpapi_gmaps(place_id, max_reviews)
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
            msg = f"⚠️ Gagal crawling dan simpan data dari SerpApi: {e}"
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
    if place_id or app_package_name:
        if status_placeholder:
            status_placeholder.text("📌 Memulai update sentimen...")
        update_sentiment_in_supabase()
        if status_placeholder:
            status_placeholder.success("✅ Analisis sentimen selesai.")
    else:
        if status_placeholder:
            status_placeholder.warning("⚠️ Tidak ada sumber data yang dipilih, proses dibatalkan.")