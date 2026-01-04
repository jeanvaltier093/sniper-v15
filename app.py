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
# CONFIG TELEGRAM (SECRET VIA STREAMLIT)
# ─────────────────────────────────────────────
if "TOKEN_TELEGRAM" not in st.session_state:
    st.session_state["TOKEN_TELEGRAM"] = "8150058407:AAFg44ySihFKBO1UW69QZqi07otqeB2IK5s"
if "CHAT_ID" not in st.session_state:
    st.session_state["CHAT_ID"] = "1148025596"

def send_telegram_msg(message):
    try:
        requests.get(
            f"https://api.telegram.org/bot{st.session_state['TOKEN_TELEGRAM']}/sendMessage",
            params={"chat_id": st.session_state["CHAT_ID"], "text": message},
            timeout=10
        )
    except:
        pass


# ─────────────────────────────────────────────
# TEST TELEGRAM
# ─────────────────────────────────────────────
if st.button("📩 Test Telegram"):
    send_telegram_msg("✅ Test Telegram réussi depuis Sniper V16.4")
    st.success("Message de test envoyé ! Vérifie ton Telegram.")


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
    if pair == "BTCUSD":
        return 1
    return 100 if "JPY" in pair else 10000


# ─────────────────────────────────────────────
# CONFIG APP
# ─────────────────────────────────────────────
st.set_page_config(page_title="Sniper V16.4 — Swing Forex + BTC PRO", layout="wide")
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
    ],
    "CRYPTO": [
        "BTC-USD"
    ]
}


# ─────────────────────────────────────────────
# MOTEUR PRINCIPAL
# ─────────────────────────────────────────────
@st.cache_data(ttl=170)
def run_engine():
    results = []
    news_today = get_high_impact_news()
    tickers = [t for cat in ASSETS.values() for t in cat]
    new_signals = {}

    data_m15 = yf.download(tickers, period="5d", interval="15m", group_by="ticker", progress=False)
    data_h1  = yf.download(tickers, period="21d", interval="1h", group_by="ticker", progress=False)
    data_h4  = yf.download(tickers, period="60d", interval="4h", group_by="ticker", progress=False)
    data_d1  = yf.download(tickers, period="200d", interval="1d", group_by="ticker", progress=False)

    for category, symbols in ASSETS.items():
        for ticker in symbols:
            try:
                name = ticker.replace("=X","").replace("-USD","USD")
                comment = "-"

                df_m15 = data_m15[ticker].dropna()
                df_h1  = data_h1[ticker].dropna()
                df_h4  = data_h4[ticker].dropna()
                df_d1  = data_d1[ticker].dropna()

                if category == "FOREX" and is_news_block(name, news_today):
                    comment = "News high impact"

                if category == "FOREX" and not is_trading_session():
                    comment = "Hors session" if comment == "-" else comment + " + Hors session"

                close = float(df_m15["Close"].iloc[-1])
                atr = AverageTrueRange(df_m15["High"], df_m15["Low"], df_m15["Close"], 14).average_true_range().iloc[-1]

                # --- NIVEAUX STATIQUES (S/R) ---
                highest_20d = df_d1["High"].iloc[-21:-1].max()
                lowest_20d = df_d1["Low"].iloc[-21:-1].min()

                ema200_d = EMAIndicator(df_d1["Close"], 200).ema_indicator().iloc[-1]
                ema50_h1 = EMAIndicator(df_h1["Close"], 50).ema_indicator().iloc[-1]

                # --- BREAKOUT AVEC BUFFER OPTIMISÉ (0.30 ATR) ---
                box_high = df_m15["High"].iloc[-21:-1].max()
                box_low  = df_m15["Low"].iloc[-21:-1].min()
                buffer = atr * 0.30 
                breakout_up = close > box_high + buffer
                breakout_dn = close < box_low - buffer

                if category == "FOREX":
                    box_high_h1 = df_h1["High"].iloc[-21:-1].max()
                    box_low_h1 = df_h1["Low"].iloc[-21:-1].min()
                    buffer_h1 = atr * 0.30
                    breakout_up_h1 = close > box_high_h1 + buffer_h1
                    breakout_dn_h1 = close < box_low_h1 - buffer_h1
                    breakout_up = breakout_up and breakout_up_h1
                    breakout_dn = breakout_dn and breakout_dn_h1

                adx_d = ADXIndicator(df_d1["High"], df_d1["Low"], df_d1["Close"]).adx().iloc[-1]
                adx_h4 = ADXIndicator(df_h4["High"], df_h4["Low"], df_h4["Close"]).adx().iloc[-1]
                adx_m = ADXIndicator(df_m15["High"], df_m15["Low"], df_m15["Close"])
                adx_val = adx_m.adx().iloc[-1]
                p_di = adx_m.adx_pos().iloc[-1]
                m_di = adx_m.adx_neg().iloc[-1]

                adx_min_d = 18 if category == "FOREX" else 28
                adx_min_h4 = 20 if category == "FOREX" else 25

                adx_block = False
                if adx_d < adx_min_d or adx_h4 < adx_min_h4:
                    comment = "ADX Daily/H4 trop bas" if comment == "-" else comment + " + ADX Daily/H4 trop bas"
                    adx_block = True

                trend_up = close > ema200_d
                h1_ok = close > ema50_h1 if trend_up else close < ema50_h1

                h1_block = False
                if not h1_ok:
                    comment = "Conflit structure H1" if comment == "-" else comment + " + Conflit structure H1"
                    h1_block = True

                # ───── Calcul du score amélioré ─────
                score = 0
                if adx_val > (30 if category=="CRYPTO" else 25): score += 45
                elif adx_val > (25 if category=="CRYPTO" else 20): score += 25
                if abs(p_di - m_di) > 10: score += 35
                score += 20 if h1_ok else 0
                
                # --- Bonus Score pour Breakout Zone Majeure ---
                if trend_up and close > highest_20d: score += 10
                if not trend_up and close < lowest_20d: score += 10

                if category=="CRYPTO":
                    if breakout_up or breakout_dn: score += 15
                    if atr > 0.5*close: score -= 10
                if category=="FOREX":
                    if atr < 0.0005*close or atr > 0.005*close: score -= 10
                
                score = max(score, 0)
                
                # <<< MODIFICATION ICI : score_min = 70 pour tous, y compris BTC >>>
                score_min = 70

                signal, sl, tp = "ATTENDRE", None, None
                
                # --- LOGIQUE RR DYNAMIQUE AVEC S/R STATIQUES ---
                if score >= score_min and not adx_block and not h1_block and comment == "-":
                    if trend_up and breakout_up:
                        signal = "ACHAT 🚀"
                        sl = min(lowest_20d, close - atr*2)
                        potential_tp = close + (close-sl)*2.1
                        tp = max(highest_20d, potential_tp)
                    elif not trend_up and breakout_dn:
                        signal = "VENTE 🔻"
                        sl = max(highest_20d, close + atr*2)
                        potential_tp = close - (sl-close)*2.1
                        tp = min(lowest_20d, potential_tp)

                # --- FILTRE RR FINAL ---
                if sl and tp:
                    rr = abs(tp - close) / abs(close - sl)
                    if rr < 1.2:
                        signal = "ATTENDRE"
                        comment = "RR insuffisant (S/R proche)"

                factor = pip_factor(name)
                sl_pips = abs(close-sl)*factor if sl else "-"
                tp_pips = abs(tp-close)*factor if tp else "-"

                results.append({
                    "Actif": name,
                    "Catégorie": category,
                    "Signal": signal,
                    "Score": f"{score}%",
                    "Prix": round(close,2 if category=="CRYPTO" else 5),
                    "SL Prix": round(sl,2 if category=="CRYPTO" else 5) if sl else "-",
                    "SL Pips": round(sl_pips,1) if sl else "-",
                    "TP Prix": round(tp,2 if category=="CRYPTO" else 5) if tp else "-",
                    "TP Pips": round(tp_pips,1) if tp else "-",
                    "Commentaire": comment
                })

                new_signals[name] = signal

                if signal != "ATTENDRE" and st.session_state["previous_signals"].get(name) != signal:
                    send_telegram_msg(
                        f"🦅 SIGNAL SNIPER V16.4\n{name} | {signal}\nScore: {score}%\nPrix: {close}\nSL: {sl}\nTP: {tp}"
                    )

            except:
                continue

    st.session_state["previous_signals"] = new_signals
    return results


# ─────────────────────────────────────────────
# AFFICHAGE
# ─────────────────────────────────────────────
st.title("🦅 Sniper V16.4 — Swing Forex + BTC PRO")
st.info("Version Optimisée : Buffer 0.30xATR | Détection Supports/Résistances 20j | Filtrage RR Dynamique")

data = run_engine()

if data:
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)
else:
    st.warning("⏸ Aucun signal (hors horaires ou news actives)")
