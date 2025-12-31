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

# --- CONFIGURATION INTERFACE ---
st.set_page_config(page_title="Sniper V15.8 - Confirmed Signals", layout="wide")
st_autorefresh(interval=180000, key="datarefresh") # 3 minutes

# Initialisation de la mémoire des signaux dans la session Streamlit
if 'previous_signals' not in st.session_state:
    st.session_state['previous_signals'] = {}

ASSETS = {
    "FOREX": [
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X",
        "EURGBP=X", "EURJPY=X", "GBPJPY=X", "EURAUD=X", "EURCAD=X", "EURCHF=X", "EURNZD=X",
        "GBPAUD=X", "GBPCAD=X", "GBPCHF=X", "GBPNZD=X", "AUDJPY=X", "AUDCAD=X", "AUDCHF=X", "AUDNZD=X",
        "CADJPY=X", "CADCHF=X", "CHFJPY=X", "NZDJPY=X", "NZDCAD=X", "NZDCHF=X",
        "USDSGD=X", "USDHKD=X", "USDTRY=X", "USDZAR=X", "USDMXN=X"
    ],
    "INDICES": ["^FCHI", "^GDAXI", "YM=F", "ES=F", "NQ=F", "^FTSE", "^N225"],
    "COMMOS": ["GC=F", "SI=F", "CL=F", "HG=F"]
}

@st.cache_data(ttl=170)
def run_confirmed_engine():
    results = []
    all_tickers = [ticker for category in ASSETS.values() for ticker in category]
    
    try:
        data_m = yf.download(all_tickers, period="5d", interval="15m", group_by='ticker', progress=False)
        data_d = yf.download(all_tickers, period="150d", interval="1d", group_by='ticker', progress=False)
    except: return []

    current_alerts = {}

    for category, tickers in ASSETS.items():
        for ticker in tickers:
            try:
                if ticker not in data_m.columns.levels[0] or data_m[ticker].empty: continue
                df_m, df_d = data_m[ticker].dropna(), data_d[ticker].dropna()
                
                p_close = float(df_m['Close'].iloc[-1])
                atr_m = AverageTrueRange(df_m['High'], df_m['Low'], df_m['Close'], 14).average_true_range().iloc[-1]
                ema_200_d = EMAIndicator(df_d['Close'], 200).ema_indicator().iloc[-1]
                
                box_h, box_l = float(df_m['High'].iloc[-21:-1].max()), float(df_m['Low'].iloc[-21:-1].min())
                buffer = atr_m * 0.15
                
                adx_d = ADXIndicator(df_d['High'], df_d['Low'], df_d['Close'], 14).adx().iloc[-1]
                ad_m_obj = ADXIndicator(df_m['High'], df_m['Low'], df_m['Close'], 14)
                ad_m, p_di, m_di = ad_m_obj.adx().iloc[-1], ad_m_obj.adx_pos().iloc[-1], ad_m_obj.adx_neg().iloc[-1]
                
                multiplier = 2.0 if category == "INDICES" else 1.6
                score, signal, sl, tp, note = 0, "ATTENDRE", 0, 0, ""

                if adx_d >= 18 and (box_h - box_l) <= (atr_m * 3.5):
                    trend_up = p_close > ema_200_d
                    if (trend_up and p_di > m_di) or (not trend_up and m_di > p_di): score += 40
                    if ad_m > 25: score += 30
                    if abs(p_di - m_di) > 15: score += 30

                    if score >= 70:
                        if trend_up and p_close > (box_h + buffer):
                            signal, sl = "ACHAT 🚀", p_close - (atr_m * multiplier)
                            tp = p_close + (p_close - sl) * 2.1
                        elif not trend_up and p_close < (box_l - buffer):
                            signal, sl = "VENTE 🔻", p_close + (atr_m * multiplier)
                            tp = p_close - (sl - p_close) * 2.1
                        else: note = "⏳ Zone de Buffer"
                    else: note = "Momentum faible"

                name = ticker.replace("=X","").replace("=F","").replace("^","")
                current_alerts[name] = signal

                # LOGIQUE DE CONFIRMATION TELEGRAM
                if signal != "ATTENDRE":
                    # On vérifie si le signal était DÉJÀ là au scan précédent
                    prev_signal = st.session_state['previous_signals'].get(name, "ATTENDRE")
                    
                    if signal == prev_signal: # CONFIRMÉ (présent 2 fois de suite)
                        # Pour ne pas spammer, on peut ajouter une condition ici
                        msg = f"🦅 SIGNAL CONFIRMÉ (6min)\n━━━━━━━━━━━━\nActif: {name}\nSignal: {signal}\nScore: {score}%\n━━━━━━━━━━━━\nPrix: {p_close:.5f}\nSL: {sl:.5f}\nTP: {tp:.5f}"
                        send_telegram_msg(msg)

                def f(x): return round(x, 5) if x < 2 else round(x, 2)
                results.append({
                    "Catégorie": category, "Actif": name, "SIGNAL": signal, 
                    "Score": f"{score}%", "Prix": f(p_close),
                    "Stop Loss": f(sl) if sl != 0 else "-", "Take Profit": f(tp) if tp != 0 else "-", "Note": note
                })
            except: continue
    
    # Mise à jour de la mémoire pour le prochain scan
    st.session_state['previous_signals'] = current_alerts
    return results

# --- RENDU ---
st.title("🦅 Sniper V15.8 - Haute Précision")
st.info("Les alertes Telegram ne sont envoyées qu'après 6 minutes de confirmation pour filtrer les faux breakouts.")

data = run_confirmed_engine()
if data:
    df = pd.DataFrame(data)
    alerts = df[df['SIGNAL'].str.contains('ACHAT|VENTE')]
    if not alerts.empty:
        st.subheader("🔥 ALERTES EN COURS (Validées ou en cours de confirmation)")
        st.dataframe(alerts.style.apply(lambda x: ['background-color: #1e8449; color: white' if 'ACHAT' in x.SIGNAL else 'background-color: #942d22; color: white' for i in x], axis=1))
        st.divider()

    st.table(df.style.apply(lambda x: ['background-color: #1e8449; color: white' if 'ACHAT' in x.SIGNAL else ('background-color: #942d22; color: white' if 'VENTE' in x.SIGNAL else '') for i in x], axis=1))
