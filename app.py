import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from ta.trend import EMAIndicator, ADXIndicator
from ta.volatility import AverageTrueRange
from streamlit_autorefresh import st_autorefresh
import datetime
from zoneinfo import ZoneInfo

# ─────────────────────────────────────────────
# CONFIG TELEGRAM (STREAMLIT SECRETS)
# ─────────────────────────────────────────────
TOKEN_TELEGRAM = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

def send_telegram_msg(message):
    try:
        requests.get(
            f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage",
            params={"chat_id": CHAT_ID, "text": message},
            timeout=10
        )
    except:
        pass

# ─────────────────────────────────────────────
# TEST CONTRÔLÉ TELEGRAM
# ─────────────────────────────────────────────
st.sidebar.header("🔧 Tests système")
if st.sidebar.button("📨 Tester Telegram"):
    send_telegram_msg("✅ TEST TELEGRAM OK — Sniper V16.4 est connecté")
    st.sidebar.success("Message Telegram envoyé")

# ─────────────────────────────────────────────
# FILTRE HORAIRE (PARIS)
# ─────────────────────────────────────────────
def is_trading_session():
    now = datetime.datetime.now(ZoneInfo("Europe/Paris"))
    hour = now.hour
    return (8 <= hour < 12) or (14 <= hour < 17)

# ─────────────────────────────────────────────
# FILTRE NEWS HIGH IMPACT (ECONDB)
# ─────────────────────────────────────────────
def get_high_impact_news():
    try:
        r = requests.get("https://econdb.com/api/calendar", timeout=10)
        data = r.json()
        news = []
        for e in data:
            if e["impact"] == "High":
                news.append({
                    "time": datetime.datetime.fromisoformat(e["date"]).replace(tzinfo=datetime.timezone.utc),
                    "currency": e["currency"]
                })
        return news
    except:
        return []

def is_news_block(pair, news):
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    for e in news:
        if e["currency"] in pair:
            if abs((e["time"] - now_utc).total_seconds()) < 1800:
                return True
    return False

# ─────────────────────────────────────────────
# PIP FACTOR (FOREX EXACT)
# ─────────────────────────────────────────────
def pip_factor(pair):
    return 100 if "JPY" in pair else 10000

# ─────────────────────────────────────────────
# IG POINTS / DISTANCE MINIMUM + SPREAD
# ─────────────────────────────────────────────
MIN_IG_POINTS = 20  # Forex standard, ajustable par pair
SPREAD_BUFFER_PIPS = 1.2  # Ajouter buffer pour spread

def ig_points(pair, pips):
    # Conversion pips → points IG
    points = pips if "JPY" in pair else pips * 10
    # Appliquer minimum IG
    if points < MIN_IG_POINTS:
        points = MIN_IG_POINTS
    # Ajouter spread buffer
    points += SPREAD_BUFFER_PIPS
    return round(points, 1)

# ─────────────────────────────────────────────
# CONFIG APP
# ─────────────────────────────────────────────
st.set_page_config(page_title="Sniper V16.4 — Swing Forex PRO", layout="wide")
st_autorefresh(interval=180000, key="refresh")

if "previous_signals" not in st.session_state:
    st.session_state["previous_signals"] = {}

# ─────────────────────────────────────────────
# ACTIFS
# ─────────────────────────────────────────────
ASSETS = {
    "FOREX": [
        "EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X","USDCHF=X","NZDUSD=X",
        "EURGBP=X","EURJPY=X","GBPJPY=X","EURAUD=X","EURCAD=X","EURCHF=X","EURNZD=X",
        "GBPAUD=X","GBPCAD=X","GBPCHF=X","GBPNZD=X",
        "AUDJPY=X","AUDCAD=X","AUDCHF=X","AUDNZD=X",
        "CADJPY=X","CADCHF=X","CHFJPY=X",
        "NZDJPY=X","NZDCAD=X","NZDCHF=X"
    ]
}

# ─────────────────────────────────────────────
# MOTEUR PRINCIPAL
# ─────────────────────────────────────────────
@st.cache_data(ttl=170)
def run_engine():
    if not is_trading_session():
        return []

    news_today = get_high_impact_news()
    results = []
    tickers = [t for cat in ASSETS.values() for t in cat]

    data_m15 = yf.download(tickers, period="5d", interval="15m", group_by="ticker", progress=False)
    data_h1  = yf.download(tickers, period="21d", interval="1h", group_by="ticker", progress=False)
    data_h4  = yf.download(tickers, period="60d", interval="4h", group_by="ticker", progress=False)
    data_d1  = yf.download(tickers, period="200d", interval="1d", group_by="ticker", progress=False)

    new_signals = {}

    for symbols in ASSETS.values():
        for ticker in symbols:
            try:
                name = ticker.replace("=X","")

                if is_news_block(name, news_today):
                    continue

                df_m15 = data_m15[ticker].dropna()
                df_h1  = data_h1[ticker].dropna()
                df_h4  = data_h4[ticker].dropna()
                df_d1  = data_d1[ticker].dropna()

                close = float(df_m15["Close"].iloc[-1])
                atr = AverageTrueRange(
                    df_m15["High"],
                    df_m15["Low"],
                    df_m15["Close"], 14
                ).average_true_range().iloc[-1]

                ema200_d = EMAIndicator(df_d1["Close"], 200).ema_indicator().iloc[-1]
                ema50_h1 = EMAIndicator(df_h1["Close"], 50).ema_indicator().iloc[-1]

                box_high = df_m15["High"].iloc[-21:-1].max()
                box_low  = df_m15["Low"].iloc[-21:-1].min()
                buffer = atr * 0.15

                breakout_up = close > box_high + buffer
                breakout_dn = close < box_low - buffer

                adx_d = ADXIndicator(df_d1["High"], df_d1["Low"], df_d1["Close"]).adx().iloc[-1]
                adx_h4 = ADXIndicator(df_h4["High"], df_h4["Low"], df_h4["Close"]).adx().iloc[-1]

                adx_m = ADXIndicator(df_m15["High"], df_m15["Low"], df_m15["Close"])
                adx_val = adx_m.adx().iloc[-1]
                p_di = adx_m.adx_pos().iloc[-1]
                m_di = adx_m.adx_neg().iloc[-1]

                if adx_d < 18 or adx_h4 < 20:
                    continue

                trend_up = close > ema200_d
                h1_ok = close > ema50_h1 if trend_up else close < ema50_h1

                score = 0
                if adx_val > 25:
                    score += 45
                elif adx_val > 20:
                    score += 25

                if abs(p_di - m_di) > 10:
                    score += 35

                score += 20 if h1_ok else 0

                signal, sl, tp = "ATTENDRE", None, None

                if score >= 70:
                    if trend_up and breakout_up and h1_ok:
                        signal = "ACHAT 🚀"
                        sl = close - atr * 1.6
                        tp = close + (close - sl) * 2.1
                    elif not trend_up and breakout_dn and h1_ok:
                        signal = "VENTE 🔻"
                        sl = close + atr * 1.6
                        tp = close - (sl - close) * 2.1

                factor = pip_factor(name)
                sl_pips = abs(close - sl) * factor if sl else "-"
                tp_pips = abs(tp - close) * factor if tp else "-"

                # ─────────────────────────────────────────────
                # AJOUT DISTANCE IG
                # ─────────────────────────────────────────────
                sl_points = ig_points(name, sl_pips) if sl else "-"
                tp_points = ig_points(name, tp_pips) if tp else "-"

                results.append({
                    "Actif": name,
                    "Signal": signal,
                    "Score": f"{score}%",
                    "Prix": round(close, 5),
                    "SL Prix": round(sl, 5) if sl else "-",
                    "SL Pips": round(sl_pips, 1) if sl else "-",
                    "SL Distance IG": sl_points,
                    "TP Prix": round(tp, 5) if tp else "-",
                    "TP Pips": round(tp_pips, 1) if tp else "-",
                    "TP Distance IG": tp_points
                })

                new_signals[name] = signal

            except:
                continue

    st.session_state["previous_signals"] = new_signals
    return results

# ─────────────────────────────────────────────
# AFFICHAGE
# ─────────────────────────────────────────────
st.title("🦅 Sniper V16.4 — Swing Forex PRO")
st.info("Sessions Londres / NY • Filtre News • Breakout M15 • Confirmation H1 • SL/TP Prix & Pips • Distance IG")

data = run_engine()

if data:
    st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.warning("⏸ Aucun signal (hors horaires ou news actives)")
