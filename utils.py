# utils.py
import os
import re
import time
import random
from datetime import datetime
import streamlit as st
from supabase import create_client, Client
import dateparser
import platform

# Selenium untuk GMaps pakai Chrome
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Driver manager untuk auto-download ChromeDriver
from webdriver_manager.chrome import ChromeDriverManager

# Sentiment
import nltk
from nltk.corpus import stopwords
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from transformers import pipeline

# Play Store Scraper
try:
    from google_play_scraper import reviews as playstore_reviews
except ImportError:
    playstore_reviews = None
    print("⚠️ Module google_play_scraper belum terinstall, Play Store scraping nonaktif.")

# Supabase client pakai Streamlit Secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

# Chrome Driver Utility
def get_chrome_driver(headless=True):
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    if headless:
        options.add_argument("--headless=new")

    # user-agent optional
    options.add_argument(f"user-agent={os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')}")

    # ChromeDriver otomatis sesuai OS
    driver_path = ChromeDriverManager().install()
    driver = webdriver.Chrome(service=Service(driver_path), options=options)
    return driver

# =======================
# Sentiment Analysis
# =======================
nltk.download('stopwords', quiet=True)
stop_words = set(stopwords.words('indonesian'))
stemmer = StemmerFactory().create_stemmer()
sentiment_pipeline = pipeline("sentiment-analysis", model="mdhugol/indonesia-bert-sentiment-classification")

def preprocess_text(text):
    if not text:
        return ""
    text = re.sub(r"http\S+|www\S+|https\S+", '', text)
    text = re.sub(r'[!?.]{2,}', '.', text)
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return text.lower().strip()

def analyze_sentiment(text):
    if not text:
        return "neutral", 0.0
    clean_text = preprocess_text(text)
    if not clean_text:
        return "neutral", 0.0
    print(f"[DEBUG] Text ke pipeline: {clean_text[:512]}")
    result = sentiment_pipeline(clean_text[:512])
    label = result[0]['label'].lower()   # bisa positive / negative / neutral atau label_0/1/2
    score = float(result[0]['score'])
    print(f"[DEBUG] Label: {label}, Score: {score}")
    return label, score

def analyze_sentiment_with_rating(text, rating=None):
    label, score = analyze_sentiment(text)
    if rating is not None:
        if rating <= 2:
            label, score = "negative", 1.0
        elif rating >= 4:
            label, score = "positive", 1.0
    return label, score

# =======================
# Mapping Label
# =======================
def map_sentiment_label(label):
    """
    Mapping semua kemungkinan output model ke label resmi:
    positif, negatif, netral
    """
    mapping = {
        "positive": "positif",
        "negative": "negatif",
        "neutral": "netral",
        "label_0": "positif",
        "label_1": "negatif",
        "label_2": "netral"
    }
    return mapping.get(label, "netral")  # default netral

# =======================
# Update Sentiment in Supabase
# =======================
def update_sentiment_in_supabase():
    res = supabase.table("comments").select("*").is_("sentimen_label", None).execute()
    for review in res.data:
        text = review.get("comment_text", "")
        rating = review.get("rating")
        label, score = analyze_sentiment_with_rating(text, rating)
        label_mapped = map_sentiment_label(label)  # pakai mapping sebelum simpan

        supabase.table("comments").update({
            "sentimen_label": label_mapped,
            "sentiment_score": score,
            "processed_at": datetime.now().isoformat()
        }).eq("review_id", review["review_id"]).execute()

# =======================
# Supabase Utils
# =======================
def is_review_exist(review_id):
    res = supabase.table("comments").select("review_id").eq("review_id", review_id).execute()
    return bool(res.data)

def save_reviews_to_supabase(reviews, source):
    for review in reviews:
        if not review.get("review_id") or is_review_exist(review["review_id"]):
            continue
        
        created_at_val = review.get("created_at")
        if isinstance(created_at_val, datetime):
            created_at_val = created_at_val.isoformat()
        
        data = {
            "review_id": review["review_id"],
            "source": source,
            "username": review.get("username"),
            "comment_text": review.get("comment_text"),
            "rating": review.get("rating"),
            "created_at": created_at_val,
            "sentimen_label": None,
            "sentiment_score": None,
            "processed_at": None
        }
        try:
            supabase.table("comments").insert(data).execute()
        except Exception as e:
            print(f"⚠️ Gagal insert review {review['review_id']}: {e}")

# =======================
# GMaps Selenium Scraper
# =======================
def get_gmaps_reviews_selenium(place_url, max_reviews=50):
    driver = get_chrome_driver(headless=True)
    driver.get(place_url)
    time.sleep(5)

    # Klik tombol "Ulasan"
    try:
        ulasan_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, '//button[contains(., "Ulasan") or contains(@aria-label, "ulasan")]')
            )
        )
        ulasan_tab.click()
        time.sleep(3)
    except Exception as e:
        print("⚠️ Tidak menemukan tombol 'Ulasan':", e)
        driver.quit()
        return []

    # Scroll untuk load semua review
    review_data = []
    scrollable_div = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'div.m6QErb.DxyBCb.kA9KIf.dS8AEf'))
    )

    last_height = 0
    while len(review_data) < max_reviews:
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
        time.sleep(2)
        new_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
        if new_height == last_height:
            break
        last_height = new_height

        reviews = driver.find_elements(By.CSS_SELECTOR, 'div.jftiEf.fontBodyMedium')
        print(f"📌 Jumlah review terkumpul: {len(reviews)}")

        for elem in reviews[len(review_data):]:
            try:
                # Nama user
                user_name = elem.find_element(By.CSS_SELECTOR, 'div.d4r55').text

                # Isi komentar
                comment = ""
                try:
                    comment = elem.find_element(By.CSS_SELECTOR, 'span.wiI7pd').text
                except:
                    pass

                # Rating
                rating = None
                try:
                    rating_elem = elem.find_element(By.CSS_SELECTOR, 'span.kvMYJc[role="img"]')
                    rating_text = rating_elem.get_attribute("aria-label") or ""  # jika None jadi string kosong
                    match = re.search(r'\d+', rating_text)
                    if match:
                        rating = int(match.group())
                except Exception as e:
                    print(f"⚠️ Error parsing rating: {e}")

                # Tanggal review
                created_at = None
                try:
                    date_text = elem.find_element(By.CSS_SELECTOR, 'span.rsqaWe').text
                    created_dt = dateparser.parse(date_text, languages=['id'])
                    created_at = created_dt.isoformat() if created_dt else datetime.now().isoformat()
                except:
                    created_at = datetime.now().isoformat()
                    
                # Simpan data review
                review_data.append({
                    "review_id": f"gmaps-{len(review_data)+1}-{int(time.time())}",  # generate id unik
                    "username": user_name,
                    "comment_text": comment,
                    "rating": rating,
                    "created_at": created_at
                })

                if len(review_data) >= max_reviews:
                    break
            except Exception as e:
                print("⚠️ Error parsing review:", e)

    driver.quit()
    return review_data

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
# Main Run
# =======================
def run_crawling_and_analysis(gmaps_url=None, app_package_name=None, max_reviews=10):
    # -------------------------
    # Crawling GMaps
    # -------------------------
    if gmaps_url:  # hanya jalan kalau URL dikasih
        print("📌 Crawling GMaps...")
        gmaps_reviews = get_gmaps_reviews_selenium(gmaps_url, max_reviews=max_reviews)
        print(f"DEBUG: Jumlah review GMaps yang ditemukan = {len(gmaps_reviews)}")
        if gmaps_reviews:
            save_reviews_to_supabase(gmaps_reviews, "gmaps")
        else:
            print("⚠️ Tidak ada review GMaps yang ditemukan!")

    # -------------------------
    # Crawling Play Store
    # -------------------------
    if app_package_name:  # hanya jalan kalau package name dikasih
        print("📌 Crawling Play Store...")
        ps_reviews = get_playstore_reviews_app(app_package_name, count=max_reviews)
        print(f"DEBUG: Jumlah review Play Store yang ditemukan = {len(ps_reviews)}")
        if ps_reviews:
            save_reviews_to_supabase(ps_reviews, "playstore")
        else:
            print("⚠️ Tidak ada review Play Store yang ditemukan!")

    # -------------------------
    # Analisis Sentimen
    # -------------------------
    if gmaps_url or app_package_name:  # cuma update kalau ada data baru
        print("📌 Update sentiment...")
        update_sentiment_in_supabase()
        print("✅ Selesai.")
    else:
        print("⚠️ Tidak ada sumber data yang dipilih, proses dibatalkan.")