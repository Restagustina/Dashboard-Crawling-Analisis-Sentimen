# app.py
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS
from streamlit_option_menu import option_menu
import dateparser
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from crawling import run_crawling_and_analysis
from supabase_utils import get_supabase_client

# -------------------------
# Supabase client
# -------------------------
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
            df["created_at"] = df["created_at"].apply(
                lambda x: dateparser.parse(str(x)) if pd.notnull(x) else pd.NaT
            )
        else:
            df["created_at"] = pd.NaT

        for col in ["comment_text", "username", "sentimen_label",
                    "sentiment_score", "rating", "source", "review_id"]:
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
    return WordCloud(width=900, height=400, background_color="white",
                     max_words=max_words, stopwords=stopwords_set).generate(text)

def clear_cache():
    load_comments.clear()

# -------------------------
# Default values (fix ke Samsat Palembang 1)
# -------------------------
PLACE_ID = "ChIJoY-1r-Z1Oy4R15M3KUcaPLg"  # Google Maps Place ID Samsat Palembang 1
DEFAULT_PLAY_PACKAGE = st.secrets.get("PLAYSTORE_PACKAGE", "app.signal.id")

# -------------------------
# Navigation
# -------------------------
selected = option_menu(
    menu_title="",
    options=["Home", "Crawl Data", "Analisis", "Visualisasi", "Tentang"],
    icons=["house", "cloud-download", "graph-up", "bar-chart", "info-circle"],
    default_index=0,
    orientation="horizontal",
)
st.markdown(
    """
    <style>
    /* Naikin posisi navbar option_menu */
    div[data-testid="stHorizontalBlock"] div[role="tablist"] {
        margin-top: -5px;  /* ubah sesuai kebutuhan */
    }
    </style>
    """,
    unsafe_allow_html=True
)

# load material icons
st.markdown("""
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
""", unsafe_allow_html=True)

# -------------------------
# Home
# -------------------------
if selected == "Home":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h2 style='margin:0'>Analisis Sentimen Review</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;margin-top:6px'>Dashboard ringkasan sentimen komentar publik dari Google Maps & Play Store.</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    df = load_comments()
    total = len(df)
    pos = int((df["sentimen_label"] == "positif").sum()) if not df.empty else 0
    neg = int((df["sentimen_label"] == "negatif").sum()) if not df.empty else 0
    neu = int((df["sentimen_label"] == "netral").sum()) if not df.empty else 0

    # Helper function untuk card
    def render_card(content: str):
        st.markdown(
            f"""
            <div style='background:white; border-radius:12px; padding:16px; 
                        text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.08);'>
                {content}
            </div>
            """,
            unsafe_allow_html=True
        )

    c1, c2, c3, c4 = st.columns(4)

    # Total Komentar
    with c1:
        render_card(f"""
            <div style='display:flex; justify-content:center; align-items:center; gap:6px; margin-bottom:6px;'>
                <div style='width:32px; height:32px; border-radius:50%; background-color:#6b7280;
                            display:flex; align-items:center; justify-content:center; color:white;'>
                    <span class="material-icons" style="font-size:20px;">chat</span>
                </div>
                <span style='color:#374151; font-weight:bold;'>Total Komentar</span>
            </div>
            <div style='font-size:28px; font-weight:bold; color:#374151;'>{total}</div>
        """)

    # Positif
    with c2:
        render_card(f"""
            <div style='display:flex; justify-content:center; align-items:center; gap:6px; margin-bottom:6px;'>
                <div style='width:32px; height:32px; border-radius:50%; background-color:#4CAF50;
                            display:flex; align-items:center; justify-content:center; color:white;'>
                    <span class="material-icons" style="font-size:20px;">sentiment_satisfied</span>
                </div>
                <span style='color:#4CAF50; font-weight:bold;'>Positif</span>
            </div>
            <div style='font-size:28px; font-weight:bold; color:#374151;'>{pos}</div>
        """)

    # Netral
    with c3:
        render_card(f"""
            <div style='display:flex; justify-content:center; align-items:center; gap:6px; margin-bottom:6px;'>
                <div style='width:32px; height:32px; border-radius:50%; background-color:#ffcc00;
                            display:flex; align-items:center; justify-content:center; color:white;'>
                    <span class="material-icons" style="font-size:20px;">sentiment_neutral</span>
                </div>
                <span style='color:#ff9900; font-weight:bold;'>Netral</span>
            </div>
            <div style='font-size:28px; font-weight:bold; color:#374151;'>{neu}</div>
        """)

    # Negatif
    with c4:
        render_card(f"""
            <div style='display:flex; justify-content:center; align-items:center; gap:6px; margin-bottom:6px;'>
                <div style='width:32px; height:32px; border-radius:50%; background-color:#f44336;
                            display:flex; align-items:center; justify-content:center; color:white;'>
                    <span class="material-icons" style="font-size:20px;">sentiment_dissatisfied</span>
                </div>
                <span style='color:#f44336; font-weight:bold;'>Negatif</span>
            </div>
            <div style='font-size:28px; font-weight:bold; color:#374151;'>{neg}</div>
        """)

    # --- Sentiment Meter ---
    if not df.empty:
        score_all = df["sentiment_score"].dropna().mean() if not df.empty else None

        def score_to_percent(score):
            if score is None or pd.isna(score): return 0
            return int((score + 1) * 50)
        score_all_100 = score_to_percent(score_all)

        # HTML untuk ikon + teks
        def interpret_sentiment(score_percent):
            if score_percent == 0:
                return "ℹ️ Belum ada data."
            elif score_percent < 40:
                return """
                <div style='display:inline-flex; align-items:center; gap:8px; justify-content:center;'>
                    <div style='width:32px; height:32px; border-radius:50%; background-color:#ff4d4d;
                                display:flex; align-items:center; justify-content:center; color:white;'>
                        <span class="material-icons" style="font-size:20px;">sentiment_dissatisfied</span>
                    </div>
                    <span><b style='color:red;'>Negatif</b> – Banyak keluhan, segera lakukan perbaikan.</span>
                </div>
                """
            elif score_percent < 70:
                return """
                <div style='display:inline-flex; align-items:center; gap:8px; justify-content:center;'>
                    <div style='width:32px; height:32px; border-radius:50%; background-color:#ffcc00;
                                display:flex; align-items:center; justify-content:center; color:white;'>
                        <span class="material-icons" style="font-size:20px;">sentiment_neutral</span>
                    </div>
                    <span><b style='color:orange;'>Netral</b> – Umpan balik campuran, ada kritik & apresiasi.</span>
                </div>
                """
            else:
                return """
                <div style='display:inline-flex; align-items:center; gap:8px; justify-content:center;'>
                    <div style='width:32px; height:32px; border-radius:50%; background-color:#4CAF50;
                                display:flex; align-items:center; justify-content:center; color:white;'>
                        <span class="material-icons" style="font-size:20px;">sentiment_satisfied</span>
                    </div>
                    <span><b style='color:green;'>Positif</b> – Mayoritas puas, pertahankan tren baik ini.</span>
                </div>
                """

        st.markdown("---")
        # --- Gauge ---
        st.subheader("Indeks Keberhasilan Perbaikan")
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge",
            value=score_all_100,
            title={'text': "Sentimen Terbaru"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "rgba(0,0,0,0)"},  # bar transparan
                'steps': [
                    {'range': [0, 40], 'color': "red"},
                    {'range': [40, 70], 'color': "orange"},
                    {'range': [70, 100], 'color': "green"},
                ],
            }
        ))

        # Hitung posisi jarum
        angle = (score_all_100 / 100) * 180
        radians = np.deg2rad(angle)
        needle_length = 0.17
        center_x, center_y = 0.5, 0.38

        x = center_x + needle_length * np.cos(np.pi - radians)
        y = center_y + needle_length * np.sin(np.pi - radians)

        # Jarum
        fig_gauge.add_shape(type="line",
            x0=center_x, y0=center_y, x1=x, y1=y,
            line=dict(color="black", width=3)
        )

        # Bulatan tengah
        fig_gauge.add_shape(type="circle",
            x0=center_x-0.015, y0=center_y-0.015,
            x1=center_x+0.015, y1=center_y+0.015,
            fillcolor="black", line_color="black"
        )

        # --- Scatter transparan supaya hover aktif ---
        theta = np.linspace(0, np.pi, 200)
        xs = 0.5 + 0.35 * np.cos(theta)
        ys = 0.38 + 0.35 * np.sin(theta)

        fig_gauge.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="lines",
            line=dict(width=0),
            fill="toself",
            fillcolor="rgba(0,0,0,0)",
            hoverinfo="text",
            text=[f"<b>{score_all_100}%</b>"]*len(xs),
            showlegend=False,
            name=""   
        ))

        fig_gauge.update_layout(
            height=400,
            margin=dict(l=40, r=40, t=40, b=40),
            paper_bgcolor="white",
            plot_bgcolor="white",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )

        st.plotly_chart(fig_gauge, use_container_width=True)

        # --- Keterangan detail di bawah gauge (tengah) ---
        st.markdown(
            f"<div style='text-align:center; margin-top:12px;'>{interpret_sentiment(score_all_100)}</div>",
            unsafe_allow_html=True
        )

    else:
        st.info("Data sentimen belum cukup untuk ditampilkan.")

    # --- Tabel komentar terbaru ---
    st.markdown("---")
    st.subheader("Komentar terbaru")
    if df.empty:
        st.info("Belum ada data. Silakan lakukan Crawling Data.")
    else:
        st.dataframe(
            df[["source", "username", "comment_text", "rating", "sentimen_label", "sentiment_score", "created_at"]].head(12),
            height=350,
            use_container_width=True,
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

    # kalau pilih Playstore atau Keduanya, baru munculkan input package
    app_pkg = st.text_input(
        "Play Store Package Name",
        value=DEFAULT_PLAY_PACKAGE if source in ["Google Play Store", "Keduanya"] else "",
        placeholder="com.example.app",
    ) if source in ["Google Play Store", "Keduanya"] else ""

    run_btn = st.button("🚀 Mulai Crawling & Analisis", type="primary", use_container_width=True)
    if run_btn:
        status_placeholder = st.empty()
        with st.spinner("Menjalankan crawling dan analisis..."):
            try:
                run_crawling_and_analysis(
                    source=source,
                    place_id=PLACE_ID if source in ["Google Maps", "Keduanya"] else None,
                    app_package_name=app_pkg.strip() if source in ["Google Play Store", "Keduanya"] else None,
                    status_placeholder=status_placeholder,
                )
                clear_cache()
                st.success("Crawling selesai! Silakan buka tab lain untuk melihat hasil.")
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
        sumber_filter = st.selectbox("Pilih Sumber", options=["Semua"] + sorted(df["source"].dropna().unique().tolist()), index=0)
        df_filtered = df if sumber_filter == "Semua" else df[df["source"] == sumber_filter]

        total = len(df_filtered)
        pos = int((df_filtered["sentimen_label"] == "positif").sum())
        neg = int((df_filtered["sentimen_label"] == "negatif").sum())
        neu = int((df_filtered["sentimen_label"] == "netral").sum())

        # Helper function untuk card
        def render_card(content: str):
            st.markdown(
                f"""
                <div style='background:white; border-radius:12px; padding:16px; 
                            text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.08);'>
                    {content}
                </div>
                """,
                unsafe_allow_html=True
            )

        c1, c2, c3, c4 = st.columns(4)

        # Total Komentar
        with c1:
            render_card(f"""
                <div style='display:flex; justify-content:center; align-items:center; gap:6px; margin-bottom:6px;'>
                    <div style='width:32px; height:32px; border-radius:50%; background-color:#6b7280;
                                display:flex; align-items:center; justify-content:center; color:white;'>
                        <span class="material-icons" style="font-size:20px;">chat</span>
                    </div>
                    <span style='color:#374151; font-weight:bold;'>Total Komentar</span>
                </div>
                <div style='font-size:28px; font-weight:bold; color:#374151;'>{total}</div>
            """)

        # Positif
        with c2:
            render_card(f"""
                <div style='display:flex; justify-content:center; align-items:center; gap:6px; margin-bottom:6px;'>
                    <div style='width:32px; height:32px; border-radius:50%; background-color:#4CAF50;
                                display:flex; align-items:center; justify-content:center; color:white;'>
                        <span class="material-icons" style="font-size:20px;">sentiment_satisfied</span>
                    </div>
                    <span style='color:#4CAF50; font-weight:bold;'>Positif</span>
                </div>
                <div style='font-size:28px; font-weight:bold; color:#374151;'>{pos}</div>
            """)

        # Netral
        with c3:
            render_card(f"""
                <div style='display:flex; justify-content:center; align-items:center; gap:6px; margin-bottom:6px;'>
                    <div style='width:32px; height:32px; border-radius:50%; background-color:#ffcc00;
                                display:flex; align-items:center; justify-content:center; color:white;'>
                        <span class="material-icons" style="font-size:20px;">sentiment_neutral</span>
                    </div>
                    <span style='color:#ff9900; font-weight:bold;'>Netral</span>
                </div>
                <div style='font-size:28px; font-weight:bold; color:#374151;'>{neu}</div>
            """)

        # Negatif
        with c4:
            render_card(f"""
                <div style='display:flex; justify-content:center; align-items:center; gap:6px; margin-bottom:6px;'>
                    <div style='width:32px; height:32px; border-radius:50%; background-color:#f44336;
                                display:flex; align-items:center; justify-content:center; color:white;'>
                        <span class="material-icons" style="font-size:20px;">sentiment_dissatisfied</span>
                    </div>
                    <span style='color:#f44336; font-weight:bold;'>Negatif</span>
                </div>
                <div style='font-size:28px; font-weight:bold; color:#374151;'>{neg}</div>
            """)

        aspek_keywords = {
            "Registrasi & Verifikasi": ["daftar", "verifikasi", "akun", "gagal", "data tidak sesuai"],
            "Pembayaran": ["bayar", "gagal bayar", "kode bayar", "metode", "transaksi"],
            "Pengiriman Dokumen": ["kirim", "lambat", "pos", "stnk", "dokumen"],
            "Pelayanan & CS": ["cs", "customer service", "live chat", "respon", "pelayanan"],
            "Aplikasi & Sistem": ["error", "crash", "lambat", "gagal", "eror"],
            "Jaringan & Koneksi": ["koneksi", "internet", "sinyal", "tidak bisa"],
            "Data Pribadi & Dokumen": ["ktp", "stnk", "data", "foto", "identifikasi"],
        }

        df_negatif = df_filtered[df_filtered["sentimen_label"] == "negatif"]
        area_perbaikan = {}
        for aspek, keywords in aspek_keywords.items():
            count = df_negatif["comment_text"].str.lower().apply(
                lambda x: any(kw in x for kw in keywords) if isinstance(x, str) else False
            ).sum()
            if count > 0:
                area_perbaikan[aspek] = count

        st.markdown("---")
        st.subheader("Area Perbaikan (dari komentar negatif)")

        if area_perbaikan:
            # Convert dict → DataFrame
            area_df = pd.DataFrame(list(area_perbaikan.items()), columns=["Area Perbaikan", "Jumlah Komentar"])
            total_neg = df_negatif.shape[0]
            area_df["Persentase"] = (area_df["Jumlah Komentar"] / total_neg * 100).round(1)

            # Urutkan berdasarkan jumlah komentar terbanyak
            area_df = area_df.sort_values("Jumlah Komentar", ascending=False).reset_index(drop=True)

            # Highlight tabel + format persen
            styled_table = (
                area_df.style
                .background_gradient(cmap="Reds", subset=["Jumlah Komentar"])
                .format({"Persentase": "{:.1f}%"})  # format jadi persen
            )
            st.dataframe(styled_table, use_container_width=True)

            # Insight storytelling
            top_issue = area_df.iloc[0]
            insight_text = f"""
            📊 Dari total **{total_neg} komentar negatif**, 
            area terbanyak adalah **{top_issue['Area Perbaikan']}** 
            dengan **{top_issue['Jumlah Komentar']} komentar ({top_issue['Persentase']}%)**.
            """
            if len(area_df) > 1:
                second_issue = area_df.iloc[1]
                insight_text += f" Disusul oleh **{second_issue['Area Perbaikan']}** dengan {second_issue['Jumlah Komentar']} komentar."
            st.info(insight_text)

            # Ranking Prioritas (Top 3)
            st.write("### 🔝 Prioritas Perbaikan")
            for i, row in area_df.sort_values("Jumlah Komentar", ascending=False).head(3).iterrows():
                st.write(f"**{i+1}. {row['Area Perbaikan']}** — {row['Jumlah Komentar']} komentar ({row['Persentase']}%)")

        else:
            st.info("Tidak terdeteksi area perbaikan yang signifikan.")

        st.markdown("---")
        st.subheader("Komentar Detail")
        st.dataframe(
            df_filtered[["source", "username", "comment_text", "rating", "sentimen_label", "sentiment_score", "created_at"]],
            height=400,
            use_container_width=True,
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
        sumber_filter = st.selectbox(
            "Pilih Sumber", 
            options=["Semua"] + sorted(df["source"].dropna().unique().tolist()), 
            index=0
        )
        df_filtered = df if sumber_filter == "Semua" else df[df["source"] == sumber_filter]

        df_filtered["sentimen_label"] = df_filtered["sentimen_label"].astype(str).str.strip().str.lower()
        sentimen_counts = df_filtered["sentimen_label"].value_counts().reset_index()
        sentimen_counts.columns = ["Sentimen", "Jumlah"]
        sentimen_counts["Sentimen"] = sentimen_counts["Sentimen"].str.capitalize()

        # -------------------------
        # Baris 1 (Bar & Pie)
        # -------------------------
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Jumlah Komentar per Sentimen")
            fig_bar = px.bar(
                sentimen_counts,
                x="Sentimen",
                y="Jumlah",
                color="Sentimen",
                color_discrete_map={"Positif": "green", "Netral": "gray", "Negatif": "red"},
                text="Jumlah",
            )
            fig_bar.update_traces(textposition="outside")
            fig_bar.update_layout(yaxis=dict(dtick=1))
            st.plotly_chart(fig_bar, use_container_width=True)

        with col2:
            st.subheader("Persentase Sentimen")
            overall = df_filtered["sentimen_label"].value_counts()
            if not overall.empty:
                fig1, ax1 = plt.subplots(figsize=(4, 4))
                ax1.pie(overall.values, labels=overall.index, autopct="%1.1f%%", startangle=90)
                ax1.axis("equal")
                st.pyplot(fig1, use_container_width=True)
            else:
                st.info("Tidak ada data untuk pie chart.")

        # -------------------------
        # Baris 2 (Trend & WordCloud)
        # -------------------------
        col3, col4 = st.columns(2)
        with col3:
            st.subheader("Tren Sentimen Mingguan")
            df_trend = df_filtered.dropna(subset=["created_at"]).copy()
            if not df_trend.empty:
                df_trend["week"] = df_trend["created_at"].dt.to_period("W").dt.to_timestamp()
                trend = df_trend.groupby(["week", "sentimen_label"]).size().reset_index(name="count")
                trend_pivot = trend.pivot(index="week", columns="sentimen_label", values="count").fillna(0)

                # Pastikan semua kolom selalu ada
                trend_pivot = trend_pivot.reindex(columns=["positif", "netral", "negatif"], fill_value=0)

                fig_area, ax_area = plt.subplots(figsize=(12, 5))
                trend_pivot.plot.area(
                    stacked=True,
                    ax=ax_area,
                    alpha=0.8,
                    color=["green", "gray", "red"]
                )

                ax_area.set_title("Sentiment Trend (Mingguan)")
                ax_area.set_xlabel("Minggu")
                ax_area.set_ylabel("Jumlah Komentar")
                ax_area.grid(alpha=0.3)
                st.pyplot(fig_area, use_container_width=True)
            else:
                st.info("Tidak ada data untuk tren mingguan.")

        with col4:
            st.subheader("WordCloud (Komentar)")
            wc = generate_wordcloud(df_filtered["comment_text"])
            if wc:
                fig2, ax2 = plt.subplots(figsize=(6, 4))
                ax2.imshow(wc, interpolation="bilinear")
                ax2.axis("off")
                st.pyplot(fig2, use_container_width=True)
            else:
                st.info("Tidak ada teks untuk WordCloud.")

# -------------------------
# Tentang
# -------------------------
elif selected == "Tentang":
    st.markdown(
        '<div style="background-color:#f0f8ff; padding:25px 40px; border-radius:10px; line-height:1.6; text-align:justify;">'
        '<h2 style="color:#008080; display:flex; align-items:center;">'
        '<span style="margin-right:8px;">ℹ️</span> Tentang</h2>'
        
        '<p>Dashboard ini dibuat untuk membantu <b>UPTB Samsat Palembang 1</b> memahami pengalaman masyarakat. '
        'Dengan menggabungkan ulasan dari <b>Google Maps</b> dan <b>Google Play Store</b>, '
        'dashboard ini menganalisis sentimen (<i>positif, netral, negatif</i>) menggunakan teknologi <b>IndoBERT</b>.</p>'
        
        '<p>Hasil analisis ditampilkan dalam bentuk grafik dan insight, sehingga memudahkan tim dalam '
        'mengidentifikasi area yang perlu ditingkatkan, seperti layanan, sistem aplikasi, maupun proses administrasi.</p>'
        
        '<p><b>Tujuan utama</b>: memberikan gambaran yang jelas dan cepat tentang suara masyarakat '
        'agar perbaikan layanan bisa lebih tepat sasaran.</p>'
        '</div>',
        unsafe_allow_html=True
    )

# -------------------------
# Footer
# -------------------------
st.markdown(f"<div class='app-footer'>© {pd.Timestamp.now().year} UPTB Samsat Palembang 1</div>", unsafe_allow_html=True)