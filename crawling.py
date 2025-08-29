# crawling.py
import os
import time
import dateparser
import re
import signal
import random
from datetime import datetime
from sentiment import save_reviews_to_supabase, update_sentiment_in_supabase
from webdriver_manager.core.os_manager import OperationSystemManager
import tempfile

# Selenium untuk GMaps
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Play Store Scraper
try:
    from google_play_scraper import reviews as playstore_reviews
except ImportError:
    playstore_reviews = None
    print("⚠️ Module google_play_scraper belum terinstall, Play Store scraping nonaktif.")

# 🔧 Chrome Driver Setup
def get_chrome_driver(headless=True):
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--blink-settings=imagesEnabled=false")
    if headless:
        options.add_argument("--headless=new")

    user_data_dir = tempfile.mkdtemp()
    options.add_argument(f"--user-data-dir={user_data_dir}")

    # Pakai user agent custom biar aman dari blokir
    user_agent = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    options.add_argument(f"user-agent={user_agent}")

    driver = webdriver.Chrome(options=options)
    return driver

# =======================
# GMaps Selenium Scraper
# =======================
def get_gmaps_reviews_selenium_debug(place_url, max_reviews=50):
    driver = get_chrome_driver(headless=False)  # Disarankan headless=False untuk debug
    try:
        driver.get(place_url)
        print(f"[DEBUG] Mulai parsing review di URL: {place_url}")
        time.sleep(5)  # waktu loading awal
        
        # Tunggu panel review muncul
        try:
            scrollable_div = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.m6QErb'))
            )
        except Exception as e:
            print("⚠️ Tidak menemukan panel review:", e)
            return []
    
        review_data = []
        scroll_attempts = 0
        max_scroll_attempts = 5
        last_scroll_height = 0
        i = 0
        
        while len(review_data) < max_reviews and scroll_attempts < max_scroll_attempts:
            print(f"[DEBUG] Scroll loop iterasi ke-{i}")
            i += 1
                
            # Scroll bertahap 500px
            driver.execute_script("arguments[0].scrollTop += 500", scrollable_div)
            time.sleep(3)  # beri waktu muat review baru
                
            new_scroll_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
            if new_scroll_height == last_scroll_height:
                scroll_attempts += 1
                print(f"⚠️ Scroll stuck attempt {scroll_attempts}/{max_scroll_attempts}")
            else:
                scroll_attempts = 0
            last_scroll_height = new_scroll_height
            
            reviews = scrollable_div.find_elements(By.XPATH, './/div[@role="article"]')
            print(f"📌 Jumlah review terkumpul: {len(reviews)}")
                
            for elem in reviews[len(review_data):]:
                review_info = {"username": None, "comment_text": None, "rating": None, "created_at": None}
                try:
                    review_info["username"] = elem.find_element(By.CSS_SELECTOR, 'div.d4r55').text
                except:
                    pass
                try:
                    review_info["comment_text"] = elem.find_element(By.CSS_SELECTOR, 'div.MyEnf > span.vlJ0lp > span').text
                    try:
                        see_more = elem.find_element(By.CSS_SELECTOR, 'button.w8nwRe.kyuRq')
                        if see_more.get_attribute("aria-expanded") == "false":
                            see_more.click()
                            time.sleep(1)
                            review_info["comment_text"] = elem.find_element(By.CSS_SELECTOR, 'div.MyfNed').text
                    except:
                        pass
                except:
                    pass
                try:
                    rating_text = elem.find_element(By.CSS_SELECTOR, 'div.kwW0Pc[role="img"]').get_attribute('aria-label')
                    match = re.search(r'\d+', rating_text)
                    review_info["rating"] = int(match.group()) if match else None
                except:
                    pass
                try:
                    date_text = elem.find_element(By.CSS_SELECTOR, 'span.rqsai6').text
                    created_dt = dateparser.parse(date_text, languages=['id'])
                    review_info["created_at"] = created_dt.isoformat() if created_dt else datetime.now().isoformat()
                except:
                    review_info["created_at"] = datetime.now().isoformat()
                    
                review_data.append(review_info)
                
                if len(review_data) >= max_reviews:
                    break
        
        return review_data
    finally:
        driver.quit()

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
def timeout_handler(signum, frame):
    raise TimeoutError("⏱ Crawling GMaps timeout exceeded.")

def run_crawling_and_analysis(gmaps_url=None, app_package_name=None, max_reviews=10):
    # -------------------------
    # Crawling GMaps
    # -------------------------
    if gmaps_url:
        print("📌 Crawling GMaps...")

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(600)  # ⏱ Timeout 10 menit

        try:
            gmaps_reviews = get_gmaps_reviews_selenium_debug(gmaps_url, max_reviews=max_reviews)
            signal.alarm(0)  # Matikan alarm kalau sukses
        except TimeoutError as e:
            print(f"❌ Timeout: {e}")
            gmaps_reviews = []

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