# sentiment.py
import os
import re
from datetime import datetime
import streamlit as st
from supabase_utils import get_supabase_client


# Sentiment
import nltk
from nltk.corpus import stopwords
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from transformers import pipeline

# Setup Supabase client
supabase = get_supabase_client()

USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

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