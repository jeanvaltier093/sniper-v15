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
                content = f.read()
                return json.loads(content) if content else ({} if file == DB_FILE else [])
        except: return {} if file == DB_FILE else []
    return {} if file == DB_FILE else []

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

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
    
# ─────────────────────────────────────────────                                
# TEST TELEGRAM                                
# ─────────────────────────────────────────────                                
if st.button("📩 Test Telegram"):                                
    send_telegram_msg("✅ Test Telegram réussi depuis Sniper V16.4.1")                                
    st.success("Message de test envoyé !")                                
    
# ─────────────────────────────────────────────                                
# FILTRE HORAIRE ET JOURS (PARIS)                                
# ─────────────────────────────────────────────                                
def is_trading_session(category):
    if category == "CRYPTO": return True
    now = datetime.datetime.now(ZoneInfo("Europe/Paris"))                                
    weekday = now.weekday()
    hour = now.hour                                
    if weekday >= 5: return False
    return 8 <= hour < 20                                
    
# ─────────────────────────────────────────────                                
# FILTRE NEWS                                
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
    except: return []                                
    
def is_news_block(pair, news):                                
    now_utc = datetime.datetime.now(datetime.timezone.utc)                                
    for e in news:                                
        if e["currency"] in pair:                                
            if abs((e["time"] - now_utc).total_seconds()) < 900:                                
                return True                                
    return False                                
    
def pip_factor(pair):                                
    if "BTC" in pair: return 1                                
    return 100 if "JPY" in pair else 10000                                
    
# ─────────────────────────────────────────────                                
# CONFIG APP                                
# ─────────────────────────────────────────────                                
st.set_page_config(page_title="Sniper V16.4.1 — Swing Forex + BTC PRO", layout="wide")                                
st_autorefresh(interval=180000, key="refresh")                                
    
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

                # Rechargement forcé du fichier JSON à chaque itération d'actif
                current_active = load_json(DB_FILE)

                if name in current_active:
                    trade = current_active[name]
                    df_m15 = data_m15[ticker].dropna()
                    current_price = round(float(df_m15["Close"].iloc[-1]), 5)
                    is_win = (trade["type"] == "ACHAT 🚀" and current_price >= trade["tp"]) or (trade["type"] == "VENTE 🔻" and current_price <= trade["tp"])
                    is_loss = (trade["type"] == "ACHAT 🚀" and current_price <= trade["sl"]) or (trade["type"] == "VENTE 🔻" and current_price >= trade["sl"])
                    
                    if is_win or is_loss:
                        hist = load_json(HISTORY_FILE)
                        hist.append({
                            "Date": datetime.datetime.now().strftime("%d/%m %H:%M"),
                            "Actif": name, "Type": trade["type"],
                            "Résultat": "✅ WIN" if is_win else "❌ LOSS",
                            "RR": round(trade["rr"] if is_win else -1.0, 2)
                        })
                        save_json(HISTORY_FILE, hist)
                        del current_active[name]
                        save_json(DB_FILE, current_active)
                    else:
                        results.append({
                            "Actif": name, "Catégorie": category, "Signal": "EN COURS ⏳",
                            "Fiabilité": "-", "Score": "-", "Prix": current_price,
                            "SL Prix": trade["sl"], "SL Pips": round(abs(trade["entry"]-trade["sl"])*pip_factor(name),1),
                            "TP Prix": trade["tp"], "TP Pips": round(abs(trade["tp"]-trade["entry"])*pip_factor(name),1),
                            "Commentaire": f"Trade déjà actif (Entrée: {trade['entry']})"
                        })
                        continue

                df_m15 = data_m15[ticker].dropna()
                df_h1  = data_h1[ticker].dropna()
                df_h4  = data_h4[ticker].dropna()
                df_d1  = data_d1[ticker].dropna()
                
                news_block = category == "FOREX" and is_news_block(name, news_today)
                session_block = not is_trading_session(category)
                                
                close, high, low = float(df_m15["Close"].iloc[-1]), float(df_m15["High"].iloc[-1]), float(df_m15["Low"].iloc[-1])
                atr_m15 = AverageTrueRange(df_m15["High"], df_m15["Low"], df_m15["Close"], 14).average_true_range().iloc[-1]
                atr_h4 = AverageTrueRange(df_h4["High"], df_h4["Low"], df_h4["Close"], 14).average_true_range().iloc[-1]
                highest_20d, lowest_20d = df_d1["High"].iloc[-21:-1].max(), df_d1["Low"].iloc[-21:-1].min()
                ema200_d = EMAIndicator(df_d1["Close"], 200).ema_indicator().iloc[-1]
                ema50_h1 = EMAIndicator(df_h1["Close"], 50).ema_indicator().iloc[-1]
                
                box_high, box_low = df_m15["High"].iloc[-21:-1].max(), df_m15["Low"].iloc[-21:-1].min()
                buffer = atr_m15 * 0.20
                breakout_up = (close > box_high + buffer * 0.7) or (high > box_high + buffer and (close-low)/(high-low+1e-6) > 0.55)
                breakout_dn = (close < box_low - buffer * 0.7) or (low < box_low - buffer and (high-close)/(high-low+1e-6) > 0.55)
                                
                adx_m = ADXIndicator(df_m15["High"], df_m15["Low"], df_m15["Close"])
                adx_val, p_di, m_di = adx_m.adx().iloc[-1], adx_m.adx_pos().iloc[-1], adx_m.adx_neg().iloc[-1]
                adx_h4 = ADXIndicator(df_h4["High"], df_h4["Low"], df_h4["Close"]).adx().iloc[-1]
                adx_block = adx_h4 < (12 if category == "FOREX" else 25)
                
                comment = "-"
                if news_block: comment = "News"
                if session_block: comment = "Hors session" if comment == "-" else comment + "+Session"
                if adx_block: comment = "ADX H4 Faible" if comment == "-" else comment + "+ADX"
                
                trend_up = close > ema200_d
                h1_ok = close > ema50_h1 if trend_up else close < ema50_h1
                score = (40 if adx_val > 22 else 0) + (35 if abs(p_di - m_di) > 8 else 0) + (20 if h1_ok else 0) + (10 if (trend_up and close > highest_20d) or (not trend_up and close < lowest_20d) else 0)
                
                reliability = "🟢 Solide" if score >= 65 else "🟣 Très forte" if score >= 80 else "🟥 Exceptionnelle" if score >= 90 else "-"
                signal, sl, tp, rr = "ATTENDRE", None, None, 0
                
                if score >= 65 and not (adx_block or news_block or session_block):
                    if trend_up and (breakout_up or (adx_val > 20 and p_di > m_di)):
                        signal = "ACHAT 🚀"
                        # SL au plus bas des 20j ou ATR. TP forcément au-dessus du prix.
                        sl = round(max(close - atr_h4*1.5, lowest_20d), 5)
                        tp = round(close + abs(close - sl) * 2.1, 5)
                    elif not trend_up and (breakout_dn or (adx_val > 20 and m_di > p_di)):
                        signal = "VENTE 🔻"
                        # SL au plus haut des 20j ou ATR. TP forcément au-dessous du prix.
                        sl = round(min(close + atr_h4*1.5, highest_20d), 5)
                        tp = round(close - abs(sl - close) * 2.1, 5)
                
                if sl and tp:
                    spread = 0.00012 if "JPY" not in name else 0.0016 if category=="FOREX" else close*0.0005
                    rr = (abs(tp-close)-spread)/(abs(close-sl)+spread)
                    if rr < 1.2: signal, comment = "ATTENDRE", "RR trop faible"

                results.append({
                    "Actif": name, "Catégorie": category, "Signal": signal, "Fiabilité": reliability, "Score": f"{score}%",
                    "Prix": round(close, 5), "SL Prix": sl if sl else "-", "TP Prix": tp if tp else "-", "Commentaire": comment
                })
                                
                if signal in ["ACHAT 🚀", "VENTE 🔻"]:
                    # --- SÉCURITÉ ANTI-DOUBLON ---
                    # On relit le fichier JSON juste avant d'envoyer pour être certain qu'aucun autre cycle n'a pris le trade
                    check_active = load_json(DB_FILE)
                    c1, c2 = name[:3], name[3:6]
                    is_exposed = any(c1 in k or c2 in k for k in check_active.keys())
                    
                    if name not in check_active and not is_exposed:
                        check_active[name] = {"type": signal, "sl": sl, "tp": tp, "entry": round(close, 5), "rr": round(rr, 2)}
                        save_json(DB_FILE, check_active)
                        if score >= 75:
                            send_telegram_msg(f"🦅 SIGNAL SNIPER\n{name} | {signal}\nScore: {score}%\nRR: {round(rr,2)}\nPrix: {round(close,5)}\nSL: {sl}\nTP: {tp}")
                    elif is_exposed and name not in check_active:
                        results[-1]["Commentaire"] = "Devise déjà en cours"

            except: continue
    return results                                

# ─────────────────────────────────────────────                                
# CONFIGURATION ACTIFS                                
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
    "CRYPTO": ["BTC-USD"]                                
}

# ─────────────────────────────────────────────                                
# AFFICHAGE STREAMLIT                                
# ─────────────────────────────────────────────                                
st.title("🦅 Sniper V16.4.1")                                

history_trades = load_json(HISTORY_FILE)
if history_trades:
    df_h = pd.DataFrame(history_trades)
    c1, c2, c3 = st.columns(3)
    winrate = (len(df_h[df_h["Résultat"]=="✅ WIN"])/len(df_h)*100)
    c1.metric("Winrate", f"{round(winrate,1)}%")
    c2.metric("Total", len(df_h))
    c3.metric("Profit RR", f"{round(df_h['RR'].sum(),2)}R")

st.header("🎯 Signaux")
data = run_engine()                                
if data: st.dataframe(pd.DataFrame(data), use_container_width=True)                                

with st.sidebar:
    if st.button("🗑 Reset Verrous"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE); st.rerun()
    if st.button("🔴 Reset Hist"):
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE); st.rerun()
