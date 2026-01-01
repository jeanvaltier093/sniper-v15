import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from ta.trend import EMAIndicator, ADXIndicator
from ta.volatility import AverageTrueRange
import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION TELEGRAM ---
TOKEN_TELEGRAM = "8150058407:AAFg44ySihFKBO1UW69QZqi07otqeB2IK5s"
CHAT_ID = "1148025596"

def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage?chat_id={CHAT_ID}&text={message}"
        requests.get(url, timeout=10)
    except:
        pass

# --- CONFIG INTERFACE ---
st.set_page_config(page_title="Sniper V16.2 - PRO", layout="wide")
st_autorefresh(interval=180000, key="datarefresh")

if 'previous_signals' not in st.session_state:
    st.session_state['previous_signals'] = {}

# --- ACTIFS ---
ASSETS = {
    "FOREX": [
        "EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X","USDCHF=X","NZDUSD=X",
        "EURGBP=X","EURJPY=X","GBPJPY=X","EURAUD=X","EURCAD=X","EURCHF=X","EURNZD=X",
        "GBPAUD=X","GBPCAD=X","GBPCHF=X","GBPNZD=X",
        "AUDJPY=X","AUDCAD=X","AUDCHF=X","AUDNZD=X",
        "CADJPY=X","CADCHF=X","CHFJPY=X",
        "NZDJPY=X","NZDCAD=X","NZDCHF=X"
    ],
    "MATIÈRES PREMIÈRES": ["GC=F","SI=F","CL=F","HG=F"]
}

@st.cache_data(ttl=170)
def run_confirmed_engine():
    results = []
    all_tickers = [t for cat in ASSETS.values() for t in cat]

    try:
        data_m = yf.download(all_tickers, period="5d", interval="15m", group_by='ticker', progress=False)
        data_d = yf.download(all_tickers, period="150d", interval="1d", group_by='ticker', progress=False)
        data_h4 = yf.download(all_tickers, period="60d", interval="4h", group_by='ticker', progress=False)
    except:
        return []

    current_alerts = {}

    for category, tickers in ASSETS.items():
        for ticker in tickers:
            try:
                if ticker not in data_m.columns.levels[0]:
                    continue

                df_m = data_m[ticker].dropna()
                df_d = data_d[ticker].dropna()
                df_h4 = data_h4[ticker].dropna()

                if len(df_h4) < 30:
                    continue

                # --- PRIX & INDICATEURS ---
                p_close = float(df_m['Close'].iloc[-1])
                atr_m = AverageTrueRange(df_m['High'], df_m['Low'], df_m['Close'], 14)\
                    .average_true_range().iloc[-1]
                ema_200_d = EMAIndicator(df_d['Close'], 200).ema_indicator().iloc[-1]

                # --- BOX 15M ---
                box_h = df_m['High'].iloc[-21:-1].max()
                box_l = df_m['Low'].iloc[-21:-1].min()
                buffer = atr_m * 0.15

                # --- STRUCTURE H4 (AJOUT PRO) ---
                h4_high = df_h4['High'].iloc[-20:].max()
                h4_low  = df_h4['Low'].iloc[-20:].min()

                h4_trend_up = p_close > (h4_high + atr_m * 0.2)
                h4_trend_down = p_close < (h4_low - atr_m * 0.2)

                # --- ADX ---
                adx_d = ADXIndicator(df_d['High'], df_d['Low'], df_d['Close'], 14)\
                    .adx().iloc[-1]

                ad_m_obj = ADXIndicator(df_m['High'], df_m['Low'], df_m['Close'], 14)
                ad_m = ad_m_obj.adx().iloc[-1]
                p_di = ad_m_obj.adx_pos().iloc[-1]
                m_di = ad_m_obj.adx_neg().iloc[-1]

                score, signal, sl, tp, note = 0, "ATTENDRE", 0, 0, ""

                # --- FILTRES GLOBAUX ---
                if adx_d >= 18 and (box_h - box_l) <= (atr_m * 3.5):
                    trend_up = p_close > ema_200_d

                    # --- SCORE ASYMÉTRIQUE PRO ---
                    # 1️⃣ Momentum
                    if ad_m > 25:
                        score += 45
                    elif ad_m > 20:
                        score += 25

                    # 2️⃣ Direction claire
                    if trend_up and p_di > m_di and abs(p_di - m_di) > 10:
                        score += 35
                    elif not trend_up and m_di > p_di and abs(m_di - p_di) > 10:
                        score += 35

                    # 3️⃣ Structure EMA Daily
                    if trend_up and p_close > ema_200_d:
                        score += 20
                    elif not trend_up and p_close < ema_200_d:
                        score += 20

                    # --- DÉCLENCHEMENT ---
                    if score >= 70:
                        if trend_up and h4_trend_up and p_close > (box_h + buffer):
                            signal = "ACHAT 🚀"
                            sl = p_close - (atr_m * 1.6)
                            tp = p_close + (p_close - sl) * 2.1
                        elif not trend_up and h4_trend_down and p_close < (box_l - buffer):
                            signal = "VENTE 🔻"
                            sl = p_close + (atr_m * 1.6)
                            tp = p_close - (sl - p_close) * 2.1
                        else:
                            note = "⏳ Structure HTF non validée"
                    else:
                        note = "Momentum insuffisant"

                name = ticker.replace("=X","").replace("=F","").replace("^","")
                current_alerts[name] = signal

                # --- CONFIRMATION TELEGRAM ---
                if signal != "ATTENDRE":
                    prev_signal = st.session_state['previous_signals'].get(name, "ATTENDRE")
                    if signal == prev_signal:
                        send_telegram_msg(
                            f"🦅 SIGNAL CONFIRMÉ\n"
                            f"━━━━━━━━━━━━\n"
                            f"Actif: {name}\n"
                            f"Signal: {signal}\n"
                            f"Score: {score}%\n"
                            f"Prix: {p_close:.5f}\n"
                            f"SL: {sl:.5f}\n"
                            f"TP: {tp:.5f}"
                        )

                def f(x): return round(x,5) if x < 2 else round(x,2)

                results.append({
                    "Catégorie": category,
                    "Actif": name,
                    "SIGNAL": signal,
                    "Score": f"{score}%",
                    "Prix": f(p_close),
                    "Stop Loss": f(sl) if sl else "-",
                    "Take Profit": f(tp) if tp else "-",
                    "Note": note
                })
            except:
                continue

    st.session_state['previous_signals'] = current_alerts
    return results

# --- INTERFACE ---
st.title("🦅 Sniper V16.2 — Forex Swing Pro")
st.info("Breakouts validés par structure H4 + momentum réel")

data = run_confirmed_engine()

if data:
    df = pd.DataFrame(data)
    st.dataframe(df.style.apply(
        lambda x: ['background-color:#1e8449;color:white' if 'ACHAT' in x.SIGNAL
                   else 'background-color:#942d22;color:white' if 'VENTE' in x.SIGNAL else ''
                   for _ in x],
        axis=1
    ))
else:
    st.error("Aucune donnée exploitable.")
