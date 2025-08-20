# app.py
import os
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from dotenv import load_dotenv
from streamlit_option_menu import option_menu
from wordcloud import STOPWORDS
import dateparser

import utils  # utils.py terbaru dengan scraper dan sentiment

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="Analisis Sentimen Review", page_icon="📊", layout="wide")
load_dotenv()

PRIMARY = "#20B2AA"
BG = "#f5f7fa"

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {BG}; }}
    .card {{
        background: rgba(255,255,255,0.94) !important;
        border-radius: 12px;
        padding: 14px;
        box-shadow: 0 8px 24px rgba(15,23,42,0.04);
    }}
    .app-footer {{
        text-align: center;
        color: #6b7280;
        padding: 10px 0;
        font-size: 0.95rem;
        margin-top: 24px;
    }}
    .stButton>button {{
        background-color: {PRIMARY} !important;
        color: white !important;
        border-radius: 8px;
        border: none;
    }}
    h1, h2, h3, a {{ color: {PRIMARY} !important; }}
    .stRadio>div>div>label, .stSelectbox>div>div>label {{ color: {PRIMARY} !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Supabase client dari utils
# -------------------------
supabase = utils.supabase

# -------------------------
# Defaults dari .env
# -------------------------
DEFAULT_GMAPS_URL = os.getenv("GMAPS_URL", "")
DEFAULT_PLAY_PACKAGE = os.getenv("PLAYSTORE_PACKAGE", "")

# -------------------------
# Helpers
# -------------------------
@st.cache_data(ttl=300)
def load_comments():
    try:
        resp = supabase.table("comments").select("*").execute()
        data = resp.data or []
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        # Parse created_at untuk Play Store + GMaps
        if "created_at" in df.columns:
            df["created_at"] = df["created_at"].apply(lambda x: dateparser.parse(str(x)) if pd.notnull(x) else pd.NaT)
        else:
            df["created_at"] = pd.NaT
        for col in ["comment_text", "username", "sentimen_label", "sentiment_score", "rating", "source", "review_id"]:
            if col not in df.columns:
                df[col] = None
        df = df.sort_values("created_at", ascending=False, na_position="last").reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Gagal mengambil data dari Supabase: {e}")
        return pd.DataFrame()

def generate_wordcloud(text_series, max_words=150):
    text = " ".join(text_series.dropna().astype(str).values)
    if not text.strip():
        return None
    # Stopwords default + khusus bahasa Indonesia
    stopwords = set(STOPWORDS)
    custom_stopwords = {"dan", "nya", "di", "yang", "untuk", "ini", "ke", "dari", "pada", "dengan", "juga"}
    stopwords.update(custom_stopwords)
    
    wc = WordCloud(
        width=900,
        height=400,
        background_color="white",
        max_words=max_words,
        stopwords=stopwords
    ).generate(text)
    return wc

def clear_cache():
    load_comments.clear()

# -------------------------
# Top navigation
# -------------------------
selected = option_menu(
    menu_title="",
    options=["Home", "Crawl Data", "Analisis", "Visualisasi", "Tentang"],
    icons=["house", "cloud-download", "graph-up", "bar-chart", "info-circle"],
    default_index=0,
    orientation="horizontal",
)

# -------------------------
# Home
# -------------------------
if selected == "Home":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h2 style='margin:0'>Analisis Sentimen Review</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;margin-top:6px'>Dashboard ringkasan sentimen komentar publik dari Google Maps & Play Store.</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    df = load_comments()
    c1, c2, c3, c4 = st.columns([1,1,1,1])
    total = len(df)
    pos = int((df["sentimen_label"] == "positif").sum()) if not df.empty else 0
    neg = int((df["sentimen_label"] == "negatif").sum()) if not df.empty else 0
    neu = int((df["sentimen_label"] == "netral").sum()) if not df.empty else 0
    with c1: st.metric("Total Komentar", total)
    with c2: st.metric("Positif", pos)
    with c3: st.metric("Netral", neu)
    with c4: st.metric("Negatif", neg)

    st.markdown("---")
    st.subheader("Komentar terbaru")
    if df.empty:
        st.info("Belum ada data. Silakan lakukan Crawling Data.")
    else:
        st.dataframe(
            df[["source", "username", "comment_text", "rating", "sentimen_label", "sentiment_score", "created_at"]].head(12),
            height=350,
            use_container_width=True
        )
    st.button("🔄 Refresh data", on_click=clear_cache)

# -------------------------
# Crawl Data
# -------------------------
elif selected == "Crawl Data":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("Crawl Data Review")

    source = st.radio(
        "Pilih sumber review:",
        ["Google Maps", "Google Play Store", "Keduanya"],
        index=0,
        horizontal=True
    )

    gmaps_url = st.text_input(
        "Google Maps Place URL (support place_id URL)",
        value=DEFAULT_GMAPS_URL,
        placeholder="https://www.google.com/maps/place/?q=place_id:XXXX"
    ) if source in ["Google Maps", "Keduanya"] else ""

    app_pkg = st.text_input(
        "Play Store Package Name",
        value=DEFAULT_PLAY_PACKAGE,
        placeholder="com.example.app"
    ) if source in ["Google Play Store", "Keduanya"] else ""

    run_btn = st.button("🚀 Mulai Crawling & Analisis", type="primary", use_container_width=True)

    if run_btn:
        with st.spinner("Menjalankan crawling dan analisis..."):
            try:
                gmaps_param = gmaps_url if source in ["Google Maps", "Keduanya"] and gmaps_url.strip() else None
                play_param = app_pkg if source in ["Google Play Store", "Keduanya"] and app_pkg.strip() else None

                if not gmaps_param and not play_param:
                    st.warning("Isi minimal salah satu: Google Maps URL atau Play Store Package.")
                else:
                    utils.run_crawling_and_analysis(gmaps_url=gmaps_param, app_package_name=play_param)
                    clear_cache()
                    st.success("Crawling & analisis selesai! Silakan buka tab lain untuk melihat hasil.")
            except Exception as e:
                st.error(f"Gagal: {e}")

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Analisis
# -------------------------
elif selected == "Analisis":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("Analisis Komentar")

    df = load_comments()
    if df.empty:
        st.info("Belum ada data. Silakan lakukan Crawling Data.")
    else:
        # Filter per sumber
        sumber_filter = st.selectbox(
            "Pilih Sumber",
            options=["Semua"] + sorted(df["source"].dropna().unique().tolist()),
            index=0
        )
        df_filtered = df.copy()
        if sumber_filter != "Semua":
            df_filtered = df_filtered[df_filtered["source"] == sumber_filter]

        # Ringkasan sentimen
        total = len(df_filtered)
        pos = int((df_filtered["sentimen_label"] == "positif").sum())
        neg = int((df_filtered["sentimen_label"] == "negatif").sum())
        neu = int((df_filtered["sentimen_label"] == "netral").sum())
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Total Komentar", total)
        with c2: st.metric("Positif", pos)
        with c3: st.metric("Netral", neu)
        with c4: st.metric("Negatif", neg)

        st.markdown("---")
        st.subheader("Komentar Detail")
        st.dataframe(
            df_filtered[["source", "username", "comment_text", "rating", "sentimen_label", "sentiment_score", "created_at"]],
            height=400,
            use_container_width=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Visualisasi
# -------------------------
elif selected == "Visualisasi":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("Visualisasi Sentimen")

    df = load_comments()
    if df.empty:
        st.info("Belum ada data untuk divisualisasikan.")
    else:
        # Filter per sumber
        sumber_filter = st.selectbox(
            "Pilih Sumber",
            options=["Semua"] + sorted(df["source"].dropna().unique().tolist()),
            index=0
        )
        df_filtered = df.copy()
        if sumber_filter != "Semua":
            df_filtered = df_filtered[df_filtered["source"] == sumber_filter]

        # Normalisasi label
        df_filtered["sentimen_label"] = df_filtered["sentimen_label"].astype(str).str.strip().str.lower()

        # ---- Visualisasi berdampingan ----
        col1, col2 = st.columns(2)

        # Pie chart
        with col1:
            st.subheader("Persentase Sentimen")
            overall = df_filtered["sentimen_label"].value_counts()
            labels = overall.index.tolist()
            sizes = overall.values.tolist()
            if sizes:
                fig1, ax1 = plt.subplots(figsize=(4,4))
                ax1.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
                ax1.axis("equal")
                st.pyplot(fig1, use_container_width=True)
            else:
                st.info("Tidak ada data untuk pie chart.")

        # WordCloud
        with col2:
            st.subheader("WordCloud (Komentar)")
            wc = generate_wordcloud(df_filtered["comment_text"])
            if wc:
                fig2, ax2 = plt.subplots(figsize=(6,4))
                ax2.imshow(wc, interpolation="bilinear")
                ax2.axis("off")
                st.pyplot(fig2, use_container_width=True)
            else:
                st.info("Tidak ada teks untuk WordCloud.")

        # Tren komentar per bulan (full width)
        st.subheader("Tren Komentar per Bulan")
        df_trend = df_filtered.dropna(subset=["created_at"]).copy()
        if not df_trend.empty:
            # Group per bulan
            df_trend["month"] = df_trend["created_at"].dt.to_period("M").dt.to_timestamp()
            trend = df_trend.groupby("month").size().reset_index(name="count")
            if not trend.empty:
                fig3, ax3 = plt.subplots(figsize=(12,4))
                ax3.plot(
                    trend["month"], 
                    trend["count"], 
                    marker='o', 
                    markersize=12,      # titik lebih besar
                    linestyle='-', 
                    linewidth=2,         # garis tebal
                    color="#20B2AA"      # sesuai tema
                )
                ax3.set_xlabel("Bulan")
                ax3.set_ylabel("Jumlah Komentar")
                ax3.grid(alpha=0.3)
                ax3.set_ylim(0, max(trend["count"])*1.4)  # beri margin atas
                # Tambahkan label angka di atas tiap titik
                for x, y in zip(trend["month"], trend["count"]):
                    ax3.text(x, y + 0.1, str(y), ha='center', va='bottom', fontsize=10)
                st.pyplot(fig3, use_container_width=True)
        else:
            st.info("Tidak ada data untuk tren komentar.")



# -------------------------
# Tentang
# -------------------------
elif selected == "Tentang":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("Tentang")
    st.write(
        "Dashboard ini menggabungkan ulasan dari Google Maps dan Google Play Store, melakukan preprocessing, "
        "analisis sentimen (IndoBERT), lalu menyimpan hasilnya ke Supabase untuk ditampilkan."
    )
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Footer
# -------------------------
st.markdown(f"<div class='app-footer'>© {pd.Timestamp.now().year} UPTB Samsat Palembang 1</div>", unsafe_allow_html=True)