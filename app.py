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
import base64
from zoneinfo import ZoneInfo                                

# ─────────────────────────────────────────────                                
# PERSISTANCE : SYNC AUTOMATIQUE GITHUB
# ───────────────────────────────────────────── 
def sync_to_github(file_path, data):
    """Enregistre automatiquement le JSON sur GitHub sans intervention"""
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            return
            
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["GITHUB_REPO"] # format: "pseudo/nom-du-depot"
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        res = requests.get(url, headers=headers)
        sha = res.json().get("sha") if res.status_code == 200 else None
        
        content = base64.b64encode(json.dumps(data, indent=4).encode()).decode()
        payload = {
            "message": f"Update {file_path} via Sniper Auto-Backup",
            "content": content
        }
        if sha:
            payload["sha"] = sha
        
        requests.put(url, headers=headers, json=payload)
    except Exception as e:
        pass

# ─────────────────────────────────────────────                                
# PERSISTANCE : GESTION DES FICHIERS JSON
# ─────────────────────────────────────────────                                
DB_FILE = "active_trades_db.json"
HISTORY_FILE = "trade_history_db.json"

if "sent_signals" not in st.session_state:
    st.session_state["sent_signals"] = set()

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
    sync_to_github(file, data)

# ─────────────────────────────────────────────                                
# CONFIG TELEGRAM
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
    
if st.button("📩 Test Telegram"):                                
    send_telegram_msg("✅ Test Telegram réussi depuis Sniper V17 SWING")                                
    st.success("Message de test envoyé !")                                
    
# ─────────────────────────────────────────────                                
# FILTRE HORAIRE ET JOURS
# ─────────────────────────────────────────────                                
def is_trading_session(category):
    if category == "CRYPTO":
        return True
    now = datetime.datetime.now(ZoneInfo("Europe/Paris"))                                
    weekday = now.weekday()  
    hour = now.hour                                
    if weekday >= 5: 
        return False
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
                    "currency": e["currency"],
                    "score_val": e.get("score", 0) # Conservé pour compatibilité
                })                                
        return news                                
    except:                                
        return []                                
    
def is_news_block(pair, news):                                
    now_utc = datetime.datetime.now(datetime.timezone.utc)                                
    for e in news:                                
        if e["currency"] in pair:                                
            if abs((e["time"] - now_utc).total_seconds()) < 3600: # 1h pour le swing                                
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
st.set_page_config(page_title="Sniper V17 — Swing Pro", layout="wide")                                
st_autorefresh(interval=300000, key="refresh") # 5 min pour le swing                                
    
active_trades = load_json(DB_FILE)
history_trades = load_json(HISTORY_FILE)
    
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
                                
    # Download optimisé pour SWING
    data_h1  = yf.download(tickers, period="30d", interval="1h", group_by="ticker", progress=False, threads=False)                                
    data_h4  = yf.download(tickers, period="60d", interval="4h", group_by="ticker", progress=False, threads=False)                                
    data_d1  = yf.download(tickers, period="300d", interval="1d", group_by="ticker", progress=False, threads=False)                                
                                
    for category, symbols in ASSETS.items():                                
        for ticker in symbols:                                
            try:                                
                name = ticker.replace("=X","").replace("-USD","USD")                                

                df_h1  = data_h1[ticker].dropna()                                
                df_h4  = data_h4[ticker].dropna()                                
                df_d1  = data_d1[ticker].dropna() 

                current_price = round(float(df_h1["Close"].iloc[-1]), 5)

                if name in active_trades:
                    trade = active_trades[name]
                    is_win, is_loss = False, False
                    
                    if trade["type"] == "ACHAT 🚀":
                        if current_price >= trade["tp"]: is_win = True
                        elif current_price <= trade["sl"]: is_loss = True
                    else:
                        if current_price <= trade["tp"]: is_win = True
                        elif current_price >= trade["sl"]: is_loss = True
                    
                    if is_win or is_loss:
                        gain_rr = trade["rr"] if is_win else -1.0
                        history_trades.append({
                            "Date": datetime.datetime.now().strftime("%d/%m %H:%M"),
                            "Actif": name,
                            "Type": trade["type"],
                            "Résultat": "✅ WIN" if is_win else "❌ LOSS",
                            "RR": round(gain_rr, 2),
                            "Score_Signal": trade.get("score_val", 0)
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
                news_block = False              
                session_block = False              
                                
                if category == "FOREX" and is_news_block(name, news_today):                                
                    comment = "News high impact"                                
                    news_block = True                                
                                
                if not is_trading_session(category):                                
                    comment = "Hors session" if comment == "-" else comment + " + Hors session"                                
                    session_block = True                                
                                
                close = float(df_h1["Close"].iloc[-1]) # Basé sur H1                                
                high  = float(df_h1["High"].iloc[-1])                                
                low   = float(df_h1["Low"].iloc[-1])                                
                                
                atr_h1 = AverageTrueRange(df_h1["High"], df_h1["Low"], df_h1["Close"], 14).average_true_range().iloc[-1]                                
                atr_h4 = AverageTrueRange(df_h4["High"], df_h4["Low"], df_h4["Close"], 14).average_true_range().iloc[-1]                                
                                
                highest_20d = df_d1["High"].iloc[-21:-1].max()                                
                lowest_20d = df_d1["Low"].iloc[-21:-1].min()                                
                                
                ema200_d = EMAIndicator(df_d1["Close"], 200).ema_indicator().iloc[-1]                                
                ema50_h4 = EMAIndicator(df_h4["Close"], 50).ema_indicator().iloc[-1]                                
                                
                # Box sur H1 (Breakout structure locale)
                box_high = df_h1["High"].iloc[-24:-1].max()                                
                box_low  = df_h1["Low"].iloc[-24:-1].min()                                
                
                breakout_up = close > box_high
                breakout_dn = close < box_low
                                
                adx_h4_indicator = ADXIndicator(df_h4["High"], df_h4["Low"], df_h4["Close"])                                
                adx_h4 = adx_h4_indicator.adx().iloc[-1]                                
                p_di = adx_h4_indicator.adx_pos().iloc[-1]                                
                m_di = adx_h4_indicator.adx_neg().iloc[-1]                                
              
                adx_min = 20 if category == "FOREX" else 25                                
                adx_block = adx_h4 < adx_min
                if adx_block:
                    comment = "ADX H4 Faible" if comment == "-" else comment + " + ADX H4 Faible"
                                
                blocked = adx_block or news_block or session_block                                
                                
                # Tendance de fond Daily (La boussole)
                trend_up = close > ema200_d                                
                h4_ok = close > ema50_h4 if trend_up else close < ema50_h4                                
                                
                score = 0                                
                if adx_h4 > (30 if category=="CRYPTO" else 25): score += 40                                
                if abs(p_di - m_di) > 10: score += 35                                
                score += 20 if h4_ok else 10                                
                if trend_up and close > highest_20d: score += 20                                
                if not trend_up and close < lowest_20d: score += 20                                
                                
                score = max(score, 0)                                
                score_min = 65                                
              
                reliability = "-"
                if score >= 105: reliability = "🔥 ULTIME"
                elif score >= 95: reliability = "🟥 Exceptionnelle"                                
                elif score >= 80: reliability = "🟣 Très forte"                                
                elif score >= 65: reliability = "🟢 Solide"                                
                                
                signal, sl, tp = "ATTENDRE", None, None                                
                rr_final = 0                                
                                
                # Logique d'entrée Swing (Pas de contre-tendance autorisée)
                if score >= score_min and not blocked:                                
                    if trend_up and (breakout_up or p_di > m_di):                                
                        signal = "ACHAT 🚀"                                
                        sl = round(min(df_h1["Low"].iloc[-10:].min(), lowest_20d), 5)
                        # Protection si SL trop proche
                        if (close - sl) < atr_h4: sl = close - (atr_h4 * 1.2)
                        tp = round(close + (abs(close - sl) * 1.5), 5) # TP UNIQUE 1.5
                        
                    elif not trend_up and (breakout_dn or m_di > p_di):                                
                        signal = "VENTE 🔻"                                
                        sl = round(max(df_h1["High"].iloc[-10:].max(), highest_20d), 5)
                        if (sl - close) < atr_h4: sl = close + (atr_h4 * 1.2)
                        tp = round(close - (abs(sl - close) * 1.5), 5) # TP UNIQUE 1.5
                                
                if sl and tp:                                
                    risk = abs(close - sl)                                
                    reward = abs(tp - close)                                
                    rr_final = reward / risk if risk > 0 else 0                                
                                
                if signal == "ATTENDRE" and comment == "-":                                
                    comment = "Attente Breakout H1" if score >= score_min else "Score insuffisant"                                
                                
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
                        "type": signal, "sl": round(sl, 5), "tp": round(tp, 5), 
                        "entry": round(close, 5), "rr": round(rr_final, 2), 
                        "score_val": score, "timestamp": datetime.datetime.now().isoformat()
                    }
                    save_json(DB_FILE, active_trades)
                    
                    if score >= 75:
                        send_telegram_msg(                                
                            f"🦅 SNIPER V17 SWING\n{name} | {signal}\nScore: {score}%\nRR: 1.5 (Unique)\nPrix: {close}\nSL: {sl}\nTP: {tp}"                
                        )                                
                                
            except: continue                                
                                
    return results                                
                                
# ─────────────────────────────────────────────                                
# AFFICHAGE STREAMLIT                                
# ─────────────────────────────────────────────                                
st.title("🦅 Sniper V17 — Swing Trading Master")                                

if history_trades:
    st.header("📊 Performance & Statistiques")
    df_hist = pd.DataFrame(history_trades)
    
    total_trades = len(df_hist)
    win_count = len(df_hist[df_hist["Résultat"] == "✅ WIN"])
    winrate = (win_count / total_trades * 100) if total_trades > 0 else 0
    
    # Statistiques de Score (Demande utilisateur)
    count_65 = len(df_hist[df_hist["Score_Signal"] >= 65])
    passed_65 = (len(df_hist[(df_hist["Score_Signal"] >= 65) & (df_hist["Résultat"] == "✅ WIN")]) / count_65 * 100) if count_65 > 0 else 0
    
    count_95 = len(df_hist[df_hist["Score_Signal"] >= 95])
    passed_95 = (len(df_hist[(df_hist["Score_Signal"] >= 95) & (df_hist["Résultat"] == "✅ WIN")]) / count_95 * 100) if count_95 > 0 else 0
    
    count_105 = len(df_hist[df_hist["Score_Signal"] >= 105])
    passed_105 = (len(df_hist[(df_hist["Score_Signal"] >= 105) & (df_hist["Résultat"] == "✅ WIN")]) / count_105 * 100) if count_105 > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Winrate Global", f"{round(winrate, 1)}%")
    col2.metric("Total Trades", total_trades)
    col3.metric("Gain RR", f"{round(df_hist['RR'].sum(), 2)} R")

    st.subheader("🎯 Précision par Palier de Score")
    s1, s2, s3 = st.columns(3)
    s1.metric("Score ≥ 65", f"{round(passed_65, 1)}% WR", f"{count_65} trades")
    s2.metric("Score ≥ 95", f"{round(passed_95, 1)}% WR", f"{count_95} trades")
    s3.metric("Score ≥ 105", f"{round(passed_105, 1)}% WR", f"{count_105} trades")
    
    with st.expander("Journal des trades"):
        st.table(df_hist.tail(15))

st.header("🎯 Radar de Marché (H1)")
data = run_engine()                                
if data:                                
    st.dataframe(pd.DataFrame(data), use_container_width=True)                                

with st.sidebar:
    st.info("Mode: Swing Trading (1-4 Jours)")
    if st.button("🗑 Réinitialiser Verrous"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.success("Verrous supprimés.")
    if st.button("🔴 Effacer Historique"):
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
        st.success("Historique vidé.")
