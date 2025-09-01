# crawling.py
import requests
import time
import random
from datetime import datetime
from sentiment import save_reviews_to_supabase, update_sentiment_in_supabase
import streamlit as st

# Lobstr.io API untuk crawling GMaps
LOBSTR_API_TOKEN = st.secrets.get("LOBSTR_API_TOKEN")
LOBSTR_API_BASE = "https://api.lobstr.io/v1"

# Play Store Scraper
try:
    from google_play_scraper import reviews as playstore_reviews
except ImportError:
    playstore_reviews = None
    print("⚠️ Module google_play_scraper belum terinstall, Play Store scraping nonaktif.")

# Fungsi helper memanggil API Lobstr.io
def call_external_api(payload=None, endpoint="tasks"):
    api_url = f"{LOBSTR_API_BASE}/{endpoint}"
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

# Tambah task ke squid
def add_tasks_to_squid(squid_id, urls):
    payload = {
        "cluster": squid_id,
        "tasks": [{"url": url} for url in urls]
    }
    return call_external_api(payload, endpoint="tasks")

# Run squid
def run_squid(squid_id):
    payload = {"cluster": squid_id}
    return call_external_api(payload, endpoint="runs")

# Cek status run berdasarkan run_id
def get_run_status(run_id):
    url = f"{LOBSTR_API_BASE}/runs/{run_id}"
    headers = {"Authorization": f"Token {LOBSTR_API_TOKEN}"}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Gagal cek status run: {e}")
        return None

# Tunggu sampai run selesai atau timeout
def wait_run_complete(run_id, timeout=300, interval=10):
    elapsed = 0
    while elapsed < timeout:
        status = get_run_status(run_id)
        if not status:
            print("Gagal ambil status run, coba ulang.")
        else:
            if status.get("is_done"):
                print("Run Task selesai.")
                return True
            elif status.get("status") == "failed":
                print("Run Task gagal.")
                return False
        time.sleep(interval)
        elapsed += interval
        print(f"Tunggu run selesai... {elapsed}s berlalu")
    print("Timeout menunggu run selesai.")
    return False

# Fungsi ambil review dari Lobstr.io (mengubah hasil csv/json jadi dict sesuai kolom penting Lobstr)
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
            # Sesuaikan mapping dengan kolom disesuaikan dari CSV Lobstr yang diberikan:
            reviews.append({
                "review_id": item.get("ID") or item.get("INTERNAL REVIEW ID") or item.get("id"),
                "username": item.get("USER NAME") or item.get("user_name"),
                "comment_text": item.get("TEXT") or item.get("comment") or item.get("content"),
                "rating": float(item.get("SCORE", 0)),
                "created_at": item.get("PUBLISHED AT DATETIME") or item.get("time"),
            })
        return reviews
    else:
        print(f"Failed fetching Lobstr GMaps reviews: {response.status_code} {response.text}")
        return []

# Play Store Scraper (tetap sama)
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

# Fungsi utama run crawling dan analisis terintegrasi dengan crawling Lobstr dan Play Store
def run_crawling_and_analysis(gmaps_url=None, app_package_name=None, max_reviews=10, squid_id=None, status_placeholder=None):
    if gmaps_url and squid_id:
        if status_placeholder:
            status_placeholder.text("📌 Crawling Google Maps...")
        if not add_tasks_to_squid(squid_id, [gmaps_url]):
            if status_placeholder:
                status_placeholder.error("⚠️ Gagal tambah tasks ke Lobstr")
            return
        run_resp = run_squid(squid_id)
        if not run_resp or "id" not in run_resp:
            if status_placeholder:
                status_placeholder.error("⚠️ Gagal trigger run squid.")
            return
        run_id = run_resp["id"]
        if status_placeholder:
            status_placeholder.text(f"Menunggu run selesai, run id: {run_id}...")
        if not wait_run_complete(run_id):
            if status_placeholder:
                status_placeholder.error("⚠️ Run task gagal atau timeout")
            return
        if status_placeholder:
            status_placeholder.text("Mengambil data review hasil crawling...")
        reviews = get_gmaps_reviews_lobstr(gmaps_url, max_reviews)
        if reviews:
            if status_placeholder:
                status_placeholder.text(f"Berhasil ambil {len(reviews)} review, menyimpan ke Supabase...")
            save_reviews_to_supabase(reviews, "gmaps")
            if status_placeholder:
                status_placeholder.success(f"{len(reviews)} review berhasil disimpan ke Supabase.")
        else:
            if status_placeholder:
                status_placeholder.warning("⚠️ Tidak ada review yang ditemukan.")
    # Play Store crawling tetap
    if app_package_name:
        if status_placeholder:
            status_placeholder.text("📌 Crawling Play Store...")
        ps_reviews = get_playstore_reviews_app(app_package_name, count=max_reviews)
        if ps_reviews:
            if status_placeholder:
                status_placeholder.text(f"Berhasil ambil {len(ps_reviews)} review Play Store, menyimpan ke Supabase...")
            save_reviews_to_supabase(ps_reviews, "playstore")
            if status_placeholder:
                status_placeholder.success(f"{len(ps_reviews)} review Play Store berhasil disimpan ke Supabase.")
        else:
            if status_placeholder:
                status_placeholder.warning("⚠️ Tidak ada review Play Store ditemukan.")
    # Update sentimen
    if gmaps_url or app_package_name:
        if status_placeholder:
            status_placeholder.text("📌 Memulai update sentimen...")
        update_sentiment_in_supabase()
        if status_placeholder:
            status_placeholder.success("✅ Analisis sentimen selesai.")
    else:
        if status_placeholder:
            status_placeholder.warning("⚠️ Tidak ada sumber data yang dipilih, proses dibatalkan.")