import streamlit as st                                
import pandas as pd                                
import yfinance as yf                                
import requests                                
from ta.trend import EMAIndicator, ADXIndicator                                
from ta.volatility import AverageTrueRange                                
from streamlit_autorefresh import st_autorefresh                                
import datetime                                
import json
import os
from zoneinfo import ZoneInfo                                
    
# ─────────────────────────────────────────────                                
# PERSISTANCE : GESTION DES FICHIERS JSON
# ─────────────────────────────────────────────                                
DB_FILE = "active_trades_db.json"
HISTORY_FILE = "trade_history_db.json"

def load_json(file):
    if os.path.exists(file):
        try:
            with open(file, "r") as f:
                return json.load(f)
        except: return {} if file == DB_FILE else []
    return {} if file == DB_FILE else []

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

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
    send_telegram_msg("✅ Test Telegram réussi depuis Sniper V16.4.1")                                
    st.success("Message de test envoyé ! Vérifie ton Telegram.")                                
    
# ─────────────────────────────────────────────                                
# FILTRE HORAIRE (PARIS)                                
# ─────────────────────────────────────────────                                
def is_trading_session():                                
    now = datetime.datetime.now(ZoneInfo("Europe/Paris"))                                
    hour = now.hour                                
    return 8 <= hour < 20                                
    
# ─────────────────────────────────────────────                                
# FILTRE NEWS HIGH IMPACT                                
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
            if abs((e["time"] - now_utc).total_seconds()) < 900:                                
                return True                                
    return False                                
    
# ─────────────────────────────────────────────                                
# PIP FACTOR                                
# ─────────────────────────────────────────────                                
def pip_factor(pair):                                
    if "BTC" in pair:                                
        return 1                                
    return 100 if "JPY" in pair else 10000                                
    
# ─────────────────────────────────────────────                                
# CONFIG APP                                
# ─────────────────────────────────────────────                                
st.set_page_config(page_title="Sniper V16.4.1 — Swing Forex + BTC PRO", layout="wide")                                
st_autorefresh(interval=180000, key="refresh")                                
    
# Chargement des données persistantes
active_trades = load_json(DB_FILE)
history_trades = load_json(HISTORY_FILE)
    
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
def run_engine():                                
    results = []                                
    news_today = get_high_impact_news()                                
    tickers = [t for cat in ASSETS.values() for t in cat]                                
                                
    data_m15 = yf.download(tickers, period="5d", interval="15m", group_by="ticker", progress=False)                                
    data_h1  = yf.download(tickers, period="21d", interval="1h", group_by="ticker", progress=False)                                
    data_h4  = yf.download(tickers, period="60d", interval="4h", group_by="ticker", progress=False)                                
    data_d1  = yf.download(tickers, period="200d", interval="1d", group_by="ticker", progress=False)                                
                                
    for category, symbols in ASSETS.items():                                
        for ticker in symbols:                                
            try:                                
                name = ticker.replace("=X","").replace("-USD","USD")                                

                # 🔒 GESTION DU VERROU ET DE L'HISTORIQUE
                if name in active_trades:
                    trade = active_trades[name]
                    df_m15 = data_m15[ticker].dropna()
                    current_price = round(float(df_m15["Close"].iloc[-1]), 5)
                    
                    is_win = False
                    is_loss = False
                    
                    if trade["type"] == "ACHAT 🚀":
                        if current_price >= trade["tp"]: is_win = True
                        elif current_price <= trade["sl"]: is_loss = True
                    else: # VENTE
                        if current_price <= trade["tp"]: is_win = True
                        elif current_price >= trade["sl"]: is_loss = True
                    
                    if is_win or is_loss:
                        # Calcul du Gain RR (Simplifié : on gagne le RR prévu ou on perd 1R)
                        gain_rr = trade["rr"] if is_win else -1.0
                        
                        history_trades.append({
                            "Date": datetime.datetime.now().strftime("%d/%m %H:%M"),
                            "Actif": name,
                            "Type": trade["type"],
                            "Résultat": "✅ WIN" if is_win else "❌ LOSS",
                            "RR": round(gain_rr, 2)
                        })
                        save_json(HISTORY_FILE, history_trades)
                        
                        del active_trades[name]
                        save_json(DB_FILE, active_trades)
                    else:
                        results.append({
                            "Actif": name, "Catégorie": category, "Signal": "EN COURS ⏳",
                            "Fiabilité": "-", "Score": "-", "Prix": current_price,
                            "SL Prix": trade["sl"], "SL Pips": round(abs(trade["entry"]-trade["sl"])*pip_factor(name),1),
                            "TP Prix": trade["tp"], "TP Pips": round(abs(trade["tp"]-trade["entry"])*pip_factor(name),1),
                            "Commentaire": f"Trade déjà actif (Entrée: {trade['entry']})"
                        })
                        continue

                comment = "-"                                
                                
                df_m15 = data_m15[ticker].dropna()                                
                df_h1  = data_h1[ticker].dropna()                                
                df_h4  = data_h4[ticker].dropna()                                
                df_d1  = data_d1[ticker].dropna()                                
                                
                news_block = False              
                session_block = False              
                                
                if category == "FOREX" and is_news_block(name, news_today):                                
                    comment = "News high impact"                                
                    news_block = True              
                                
                if category == "FOREX" and not is_trading_session():                                
                    comment = "Hors session" if comment == "-" else comment + " + Hors session"                                
                    session_block = True              
                                
                close = float(df_m15["Close"].iloc[-1])                                
                high  = float(df_m15["High"].iloc[-1])                                
                low   = float(df_m15["Low"].iloc[-1])                                
                                
                atr_m15 = AverageTrueRange(df_m15["High"], df_m15["Low"], df_m15["Close"], 14).average_true_range().iloc[-1]                                
                atr_h4 = AverageTrueRange(df_h4["High"], df_h4["Low"], df_h4["Close"], 14).average_true_range().iloc[-1]                                
                                
                highest_20d = df_d1["High"].iloc[-21:-1].max()                                
                lowest_20d = df_d1["Low"].iloc[-21:-1].min()                                
                                
                ema200_d = EMAIndicator(df_d1["Close"], 200).ema_indicator().iloc[-1]                                
                ema50_h1 = EMAIndicator(df_h1["Close"], 50).ema_indicator().iloc[-1]                                
                                
                box_high = df_m15["High"].iloc[-21:-1].max()                                
                box_low  = df_m15["Low"].iloc[-21:-1].min()                                
                buffer = atr_m15 * 0.20                                
                tolerance = buffer * 0.30                                
                                
                breakout_up_close = close > box_high + buffer - tolerance                                
                breakout_dn_close = close < box_low - buffer + tolerance                                
                                
                bull_power = (close - low) / (high - low + 1e-6)                                
                bear_power = (high - close) / (high - low + 1e-6)                                
                                
                breakout_up_wick = high > box_high + buffer and bull_power > 0.55                                
                breakout_dn_wick = low  < box_low  - buffer and bear_power > 0.55                                
                                
                breakout_up = breakout_up_close or breakout_up_wick                                
                breakout_dn = breakout_dn_close or breakout_dn_wick                                
                                
                adx_m = ADXIndicator(df_m15["High"], df_m15["Low"], df_m15["Close"])                                
                adx_val = adx_m.adx().iloc[-1]                                
                p_di = adx_m.adx_pos().iloc[-1]                                
                m_di = adx_m.adx_neg().iloc[-1]                                
                adx_h4 = ADXIndicator(df_h4["High"], df_h4["Low"], df_h4["Close"]).adx().iloc[-1]
              
                adx_min_h4 = 12 if category == "FOREX" else 25                                
                adx_block = adx_h4 < adx_min_h4
                if adx_block:
                    comment = "ADX Faible (H4)" if comment == "-" else comment + " + ADX Faible (H4)"
                                
                blocked = adx_block or news_block or session_block                                
                                
                trend_up = close > ema200_d                                
                h1_ok = close > ema50_h1 if trend_up else close < ema50_h1                                
                                
                score = 0                                
                if adx_val > (28 if category=="CRYPTO" else 22): score += 40                                
                if abs(p_di - m_di) > 8: score += 35                                
                score += 20 if h1_ok else 0                                
                if trend_up and close > highest_20d: score += 10                                
                if not trend_up and close < lowest_20d: score += 10                                
                                
                score = max(score, 0)                                
                score_min = 65                                
              
                reliability = "-"
                if score >= 90: reliability = "🟥 Exceptionnelle"                                
                elif score >= 80: reliability = "🟣 Très forte"                                
                elif score >= 65: reliability = "🟢 Solide"                                
                                
                signal, sl, tp = "ATTENDRE", None, None                                
                rr = 0                                
                                
                if score >= score_min and not blocked:                                
                    if trend_up and (breakout_up or (adx_val > 20 and p_di > m_di)):                                
                        signal = "ACHAT 🚀"                                
                        sl = max(close - atr_h4*1.5, lowest_20d)                                
                        tp = min(close + (close-sl)*2.1, highest_20d)                                
                    elif not trend_up and (breakout_dn or (adx_val > 20 and m_di > p_di)):                                
                        signal = "VENTE 🔻"                                
                        sl = min(close + atr_h4*1.5, highest_20d)                                
                        tp = max(close - (sl-close)*2.1, lowest_20d)                                
                                
                if sl and tp:                                
                    spread = 0.00012 if "JPY" not in name else 0.0016 if category == "FOREX" else close * 0.0005                                
                    risk = abs(close - sl) + spread                                
                    reward = abs(tp - close) - spread                                
                    rr = reward / risk if risk > 0 else 0                                
                                
                    if rr < 1.2:                                
                        signal = "ATTENDRE"                                
                        comment = "RR réel IG insuffisant après spread"                                
                
                if signal == "ATTENDRE" and comment == "-":                                
                    comment = "Setup valide mais breakout non confirmed" if score >= score_min else "Conditions insuffisantes"                                
                                
                factor = pip_factor(name)                                
                                
                results.append({                                
                    "Actif": name, "Catégorie": category, "Signal": signal,                                
                    "Fiabilité": reliability, "Score": f"{score}%",                                
                    "Prix": round(close, 2 if category=="CRYPTO" else 5),                                
                    "SL Prix": round(sl, 5) if sl else "-", "SL Pips": round(abs(close-sl)*factor,1) if sl else "-",                                
                    "TP Prix": round(tp, 5) if tp else "-", "TP Pips": round(abs(tp-close)*factor,1) if tp else "-",                                
                    "Commentaire": comment                                
                })                                
                                
                if signal in ["ACHAT 🚀", "VENTE 🔻"] and name not in active_trades:
                    active_trades[name] = {
                        "type": signal, "sl": round(sl, 5), "tp": round(tp, 5), "entry": round(close, 5), "rr": round(rr, 2)
                    }
                    save_json(DB_FILE, active_trades)
                    
                    send_telegram_msg(                                
                        f"🦅 SIGNAL SNIPER V16.4.1\n{name} | {signal}\nFiabilité: {reliability} | Score: {score}%\nRR: {round(rr,2)}\nPrix: {close}\nSL: {sl}\nTP: {tp}"                
                    )                                
            except: continue                                
    return results                                
                                
# ─────────────────────────────────────────────                                
# AFFICHAGE STREAMLIT                                
# ─────────────────────────────────────────────                                
st.title("🦅 Sniper V16.4.1 — Swing Forex + BTC PRO")                                

# Section Stats Historiques
if history_trades:
    st.header("📊 Historique de Performance")
    df_hist = pd.DataFrame(history_trades)
    
    col1, col2, col3 = st.columns(3)
    win_count = len(df_hist[df_hist["Résultat"] == "✅ WIN"])
    total_trades = len(df_hist)
    winrate = (win_count / total_trades * 100) if total_trades > 0 else 0
    total_rr = df_hist["RR"].sum()
    
    col1.metric("Winrate", f"{round(winrate, 1)}%")
    col2.metric("Trades Clôturés", total_trades)
    col3.metric("Gain Cumulé (RR)", f"{round(total_rr, 2)} R")
    
    with st.expander("Voir le détail des trades clôturés"):
        st.table(df_hist.tail(10))

# Signaux en cours
st.header("🎯 Signaux en Direct")
data = run_engine()                                
if data:                                
    st.dataframe(pd.DataFrame(data), use_container_width=True)                                

# Contrôles
with st.sidebar:
    if st.button("🗑 Réinitialiser Verrous"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.success("Verrous supprimés.")
    if st.button("🔴 Effacer Historique"):
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
        st.success("Historique vidé.")
