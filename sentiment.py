# sentiment.py
import os
import re
from datetime import datetime
from supabase_utils import get_supabase_client

import nltk
from nltk.corpus import stopwords
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from transformers import pipeline

# Setup Supabase client
supabase = get_supabase_client()

# Download stopwords bahasa Indonesia (jika belum)
nltk.download('stopwords', quiet=True)
stop_words = set(stopwords.words('indonesian'))

# Setup stemmer Bahasa Indonesia
stemmer_factory = StemmerFactory()
stemmer = stemmer_factory.create_stemmer()

# Setup sentiment analysis pipeline dengan model IndoBERT
sentiment_pipeline = pipeline("sentiment-analysis", model="mdhugol/indonesia-bert-sentiment-classification")

def preprocess_text(text):
    if not text:
        return ""
    text = re.sub(r"http\S+|www\S+|https\S+", '', text)  # Hapus URL
    text = re.sub(r'[!?.]{2,}', '.', text)               # Ganti tanda baca berulang jadi satu
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)           # Hapus karakter non-alphanumeric
    text = text.lower().strip()
    # Optionally: lakukan stemming di sini
    tokens = text.split()
    tokens_stemmed = [stemmer.stem(token) for token in tokens if token not in stop_words]
    return " ".join(tokens_stemmed)

def analyze_sentiment(text):
    if not text:
        return "neutral", 0.0
    clean_text = preprocess_text(text)
    if not clean_text:
        return "neutral", 0.0
    print(f"[DEBUG] Text ke pipeline: {clean_text[:512]}")
    result = sentiment_pipeline(clean_text[:512])
    label = result[0]['label'].lower()
    score = float(result[0]['score'])
    print(f"[DEBUG] Label: {label}, Score: {score}")
    return label, score

def analyze_sentiment_with_rating(text, rating=None):
    label, score = analyze_sentiment(text)
    if rating is not None:
        # Overwrite label dan score berdasarkan rating untuk akurasi label manual
        if rating <= 2:
            label, score = "negative", 1.0
        elif rating >= 4:
            label, score = "positive", 1.0
    return label, score

def map_sentiment_label(label):
    mapping = {
        "positive": "positif",
        "negative": "negatif",
        "neutral": "netral",
        "label_0": "positif",
        "label_1": "negatif",
        "label_2": "netral"
    }
    return mapping.get(label, "netral")

def update_sentiment_in_supabase():
    res = supabase.table("comments").select("*").is_("sentimen_label", None).execute()
    for review in res.data:
        text = review.get("comment_text", "")
        rating = review.get("rating")
        label, score = analyze_sentiment_with_rating(text, rating)
        label_mapped = map_sentiment_label(label)

        supabase.table("comments").update({
            "sentimen_label": label_mapped,
            "sentiment_score": score,
            "processed_at": datetime.now().isoformat()
        }).eq("review_id", review["review_id"]).execute()

def save_reviews_to_supabase(reviews, source):
    success_count = 0
    total = len(reviews)

    for review in reviews:
        if not review.get("review_id"):
            continue  # Abaikan review tanpa ID unik

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
            response = supabase.table("comments").upsert(data, on_conflict="review_id").execute()
            print(f"Upsert response status: {response.status_code}, response data: {response.data}")
            if response.status_code in (200, 201):
                print(f"✔️ Review ID {review['review_id']} berhasil disimpan/upsert.")
                success_count += 1
            else:
                print(f"❌ Gagal simpan review ID {review['review_id']}, status code: {response.status_code}, response: {response.data}")
        except Exception as e:
            print(f"⚠️ Exception saat simpan review ID {review['review_id']}: {e}")

    print(f"✅ {success_count} dari {total} review berhasil disimpan.")
    return success_count == total