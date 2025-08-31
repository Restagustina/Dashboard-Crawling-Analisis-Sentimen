# app.py
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS
from streamlit_option_menu import option_menu
import dateparser
import plotly.express as px
from crawling import run_crawling_and_analysis
from supabase_utils import get_supabase_client

@st.cache_resource
def get_client():
    return get_supabase_client()

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="Analisis Sentimen Review", page_icon="📊", layout="wide")
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
# Helpers
# -------------------------
@st.cache_data(ttl=300)
def load_comments():
    try:
        supabase = get_client()
        resp = supabase.table("comments").select("*").execute()
        data = resp.data or []
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
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
    stopwords_set = set(STOPWORDS)
    stopwords_set.update({"dan", "nya", "di", "yang", "untuk", "ini", "ke", "dari", "pada", "dengan", "juga"})
    wc = WordCloud(width=900, height=400, background_color="white", max_words=max_words, stopwords=stopwords_set).generate(text)
    return wc


def clear_cache():
    load_comments.clear()


# -------------------------
# Default values untuk Crawl dari secrets (fallback kalau tidak ada)
# -------------------------
DEFAULT_GMAPS_URL = st.secrets.get("GMAPS_URL", "https://www.google.com/maps/place/Samsat+UPTB+Palembang+1/@-2.9870757,104.7412692,17z/data=!4m6!3m5!1s0x2e3b75e6afb58fa1:0xb83c1a47293793d7!8m2!3d-2.9870757!4d104.7438441!16s%2Fg%2F11c6rj50mr?entry=ttu&g_ep=EgoyMDI1MDgxMC4wIKXMDSoASAFQAw%3D%3D")
DEFAULT_PLAY_PACKAGE = st.secrets.get("PLAYSTORE_PACKAGE", "app.signal.id")


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

    if not df.empty and "created_at" in df.columns:
        today = pd.Timestamp.now().normalize()
        yesterday = today - pd.Timedelta(days=1)

        df_today = df[(df["created_at"] >= today) & (df["created_at"] < today + pd.Timedelta(days=1))]
        df_yesterday = df[(df["created_at"] >= yesterday) & (df["created_at"] < today)]

        score_today = df_today["sentiment_score"].dropna().mean() if not df_today.empty else None
        score_yesterday = df_yesterday["sentiment_score"].dropna().mean() if not df_yesterday.empty else None

        def sentiment_score_to_0_100(score):
            if score is None or pd.isna(score):
                return 0
            return int((score + 1) * 50)

        score_today_100 = sentiment_score_to_0_100(score_today)

        def warna_performance(persen):
            if persen >= 70:
                return "green"
            elif persen >= 40:
                return "orange"
            else:
                return "red"

        warna = warna_performance(score_today_100)

        st.markdown("---")
        st.subheader("Performa Perbaikan Sentimen")
        st.markdown(f"<h1 style='color:{warna}; font-weight:bold;'>{score_today_100}%</h1>", unsafe_allow_html=True)
    
    else:
        st.info("Data sentimen untuk hari ini dan kemarin tidak cukup untuk menampilkan performa.")


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

    source = st.radio("Pilih sumber review:", ["Google Maps", "Google Play Store", "Keduanya"], index=0, horizontal=True)

    gmaps_url = st.text_input(
        "Google Maps Place URL (support place_id URL)",
        value=DEFAULT_GMAPS_URL if source in ["Google Maps", "Keduanya"] else "",
        placeholder="https://www.google.com/maps/place/?q=place_id:XXXX"
    ) if source in ["Google Maps", "Keduanya"] else ""

    app_pkg = st.text_input(
        "Play Store Package Name",
        value=DEFAULT_PLAY_PACKAGE if source in ["Google Play Store", "Keduanya"] else "",
        placeholder="com.example.app"
    ) if source in ["Google Play Store", "Keduanya"] else ""

    run_btn = st.button("🚀 Mulai Crawling & Analisis", type="primary", use_container_width=True)

    if run_btn:
        with st.spinner("Menjalankan crawling dan analisis..."):
            try:
                gmaps_param = gmaps_url.strip() if gmaps_url and source in ["Google Maps", "Keduanya"] else None
                play_param = app_pkg.strip() if app_pkg and source in ["Google Play Store", "Keduanya"] else None

                if not gmaps_param and not play_param:
                    st.warning("Isi minimal salah satu: Google Maps URL atau Play Store Package.")
                else:
                    if play_param:
                        run_crawling_and_analysis(
                            gmaps_url=None,  # Hanya crawl Play Store
                            app_package_name=play_param
                        )
                        clear_cache()
                        st.success("Crawling Play Store selesai! Silakan buka tab lain untuk melihat hasil.")

                    if gmaps_param:
                        run_crawling_and_analysis(
                            gmaps_url=gmaps_param,  # Crawl Google Maps secara manual saat klik tombol
                            app_package_name=None
                        )
                        clear_cache()
                        st.success("Crawling Google Maps selesai! Silakan buka tab lain untuk melihat hasil.")

            except Exception as e:
                st.error(f"Gagal menjalankan crawling: {e}")

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
        sumber_filter = st.selectbox(
            "Pilih Sumber", 
            options=["Semua"] + sorted(df["source"].dropna().unique().tolist()), 
            index=0
        )
        df_filtered = df.copy()
        if sumber_filter != "Semua":
            df_filtered = df_filtered[df_filtered["source"] == sumber_filter]

        total = len(df_filtered)
        pos = int((df_filtered["sentimen_label"] == "positif").sum())
        neg = int((df_filtered["sentimen_label"] == "negatif").sum())
        neu = int((df_filtered["sentimen_label"] == "netral").sum())
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Total Komentar", total)
        with c2: st.metric("Positif", pos)
        with c3: st.metric("Netral", neu)
        with c4: st.metric("Negatif", neg)

        aspek_keywords = {
            "Registrasi & Verifikasi": ["daftar", "verifikasi", "akun", "gagal", "data tidak sesuai"],
            "Pembayaran": ["bayar", "gagal bayar", "kode bayar", "metode", "transaksi"],
            "Pengiriman Dokumen": ["kirim", "lambat", "pos", "stnk", "dokumen"],
            "Pelayanan & CS": ["cs", "customer service", "live chat", "respon", "pelayanan"],
            "Aplikasi & Sistem": ["error", "crash", "lambat", "gagal", "eror"],
            "Jaringan & Koneksi": ["koneksi", "internet", "sinyal", "tidak bisa"],
            "Data Pribadi & Dokumen": ["ktp", "stnk", "data", "foto", "identifikasi"]
        }

        df_negatif = df_filtered[df_filtered["sentimen_label"] == "negatif"]

        area_perbaikan = {}
        for aspek, keywords in aspek_keywords.items():
            count = df_negatif["comment_text"].str.lower().apply(
                lambda x: any(kw in x for kw in keywords) if isinstance(x, str) else False
            ).sum()
            area_perbaikan[aspek] = count

        area_perbaikan = {k: v for k, v in sorted(area_perbaikan.items(), key=lambda item: item[1], reverse=True) if v > 0}

        st.markdown("---")
        st.subheader("Area Perbaikan (dari komentar negatif)")
        if area_perbaikan:
            for aspek, jumlah in area_perbaikan.items():
                st.write(f"- **{aspek}**: {jumlah} komentar negatif")
        else:
            st.info("Tidak terdeteksi area perbaikan yang signifikan.")

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
        st.info("Tidak ada data untuk divisualisasikan.")
    else:
        sumber_filter = st.selectbox("Pilih Sumber", options=["Semua"] + sorted(df["source"].dropna().unique().tolist()), index=0)
        df_filtered = df.copy()
        if sumber_filter != "Semua":
            df_filtered = df_filtered[df_filtered["source"] == sumber_filter]

        df_filtered["sentimen_label"] = df_filtered["sentimen_label"].astype(str).str.strip().str.lower()

        sentimen_counts = df_filtered["sentimen_label"].value_counts().reset_index()
        sentimen_counts.columns = ["Sentimen", "Jumlah"]
        sentimen_counts["Sentimen"] = sentimen_counts["Sentimen"].str.capitalize()

        fig_bar = px.bar(
            sentimen_counts,
            x="Sentimen",
            y="Jumlah",
            color="Sentimen",
            color_discrete_map={"Positif": "green", "Netral": "gray", "Negatif": "red"},
            title="Jumlah Komentar per Kategori Sentimen",
            labels={"Jumlah": "Jumlah Komentar", "Sentimen": "Kategori Sentimen"},
            text="Jumlah"
        )
        fig_bar.update_traces(textposition="outside")
        fig_bar.update_layout(yaxis=dict(dtick=1))

        st.plotly_chart(fig_bar, use_container_width=True)

        col1, col2 = st.columns(2)
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

        st.subheader("Tren Komentar per Bulan")
        df_trend = df_filtered.dropna(subset=["created_at"]).copy()
        if not df_trend.empty:
            df_trend["month"] = df_trend["created_at"].dt.to_period("M").dt.to_timestamp()
            trend = df_trend.groupby("month").size().reset_index(name="count")
            if not trend.empty:
                fig3, ax3 = plt.subplots(figsize=(12,4))
                ax3.plot(trend["month"], trend["count"], marker='o', markersize=12, linestyle='-', linewidth=2, color="#20B2AA")
                ax3.set_xlabel("Bulan")
                ax3.set_ylabel("Jumlah Komentar")
                ax3.grid(alpha=0.3)
                ax3.set_ylim(0, max(trend["count"]) * 1.4)
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