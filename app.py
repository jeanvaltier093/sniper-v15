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
    send_telegram_msg("✅ Test Telegram réussi depuis Sniper V16.4.1")                                
    st.success("Message de test envoyé ! Vérifie ton Telegram.")                                
    
# ─────────────────────────────────────────────                                
# FILTRE HORAIRE (PARIS) - OPTIMISÉ POUR 3-4 SIGN AUX/JOUR                              
# ─────────────────────────────────────────────                                
def is_trading_session():                                
    now = datetime.datetime.now(ZoneInfo("Europe/Paris"))                                
    hour = now.hour                                
    # Session élargie pour capter l'Open Londres, New York et la session US complète
    return 8 <= hour < 20                                
    
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
            # Blocage réduit à 15 minutes pour être plus opportuniste
            if abs((e["time"] - now_utc).total_seconds()) < 900:                                
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
st.set_page_config(page_title="Sniper V16.4.1 — Swing Forex + BTC PRO", layout="wide")                                
st_autorefresh(interval=180000, key="refresh")                                
    
# Initialisation du suivi des trades pour éviter les doublons avant clôture
if "active_trades" not in st.session_state:                                
    st.session_state["active_trades"] = {}                                

# Initialisation de l'historique des signaux
if "trade_history" not in st.session_state:
    st.session_state["trade_history"] = []
    
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
                                
                h1_breakout_bonus = 0                                
                if category == "FOREX":                                
                    box_high_h1 = df_h1["High"].iloc[-21:-1].max()                                
                    box_low_h1 = df_h1["Low"].iloc[-21:-1].min()                                
                    if close > box_high_h1 or close < box_low_h1:                                
                        h1_breakout_bonus = 15                                
                                
                adx_d = ADXIndicator(df_d1["High"], df_d1["Low"], df_d1["Close"]).adx().iloc[-1]                                
                adx_h4 = ADXIndicator(df_h4["High"], df_h4["Low"], df_h4["Close"]).adx().iloc[-1]                                
                adx_m = ADXIndicator(df_m15["High"], df_m15["Low"], df_m15["Close"])                                
                adx_val = adx_m.adx().iloc[-1]                                
                p_di = adx_m.adx_pos().iloc[-1]                                
                m_di = adx_m.adx_neg().iloc[-1]                                
              
                # ADX H4 assoupli à 12 pour détecter les débuts de tendances
                adx_min_d = 17 if category == "FOREX" else 28                                
                adx_min_h4 = 12 if category == "FOREX" else 25                                
                                
                adx_block = False                                
                if adx_h4 < adx_min_h4:                                
                    comment = "ADX Faible (H4)" if comment == "-" else comment + " + ADX Faible (H4)"                                
                    adx_block = True                                
                                
                blocked = adx_block or news_block or session_block                                
                                
                trend_up = close > ema200_d                                
                h1_ok = close > ema50_h1 if trend_up else close < ema50_h1                                
                                
                score = 0                                
                # Ajustement des scores pour plus de fluidité
                if adx_val > (28 if category=="CRYPTO" else 22): score += 40                                
                if abs(p_di - m_di) > 8: score += 35                                
                score += 20 if h1_ok else 0                                
                if trend_up and close > highest_20d: score += 10                                
                if not trend_up and close < lowest_20d: score += 10                                
                if category=="CRYPTO":                                
                    if breakout_up or breakout_dn: score += 15                                
                    if atr_m15 > 0.5*close: score -= 10                                
                if category=="FOREX":                                
                    if atr_m15 < 0.0005*close or atr_m15 > 0.005*close: score -= 10                                
                    box_high_h4 = df_h4["High"].iloc[-21:-1].max()                                
                    box_low_h4 = df_h4["Low"].iloc[-21:-1].min()                                
                    if box_high_h4 - box_low_h4 < 0.0005:                                
                        breakout_up = breakout_dn = False                                
                    score += h1_breakout_bonus                                
                                
                score = max(score, 0)                                
                score_min = 65                                
              
                if score >= 90:              
                    reliability = "🟥 Exceptionnelle"              
                elif score >= 80:              
                    reliability = "🟣 Très forte"              
                elif score >= 65:              
                    reliability = "🟢 Solide"              
                else:              
                    reliability = "-"              
                                
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
                    if category == "FOREX":                                
                        spread = 0.00012 if "JPY" not in name else 0.0016                                
                    else:                                
                        spread = close * 0.0005                                
                                
                    risk = abs(close - sl) + spread                                
                    reward = abs(tp - close) - spread                                
                    rr = reward / risk if risk > 0 else 0                                
                                
                    if rr < 1.2:                                
                        signal = "ATTENDRE"                                
                        comment = "RR réel IG insuffisant après spread"                                
                                
                # LOGIQUE DE BLOCAGE CRITIQUE : Vérifier si actif avant d'émettre
                if name in st.session_state["active_trades"]:
                    trade = st.session_state["active_trades"][name]
                    status = "EN COURS"
                    
                    if trade["type"] == "ACHAT 🚀":
                        if close >= trade["tp"]: status = "GAGNANT ✅"
                        elif close <= trade["sl"]: status = "PERDANT ❌"
                    elif trade["type"] == "VENTE 🔻":
                        if close <= trade["tp"]: status = "GAGNANT ✅"
                        elif close >= trade["sl"]: status = "PERDANT ❌"
                    
                    if status != "EN COURS":
                        st.session_state["trade_history"].append({
                            "Heure": datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%H:%M"),
                            "Actif": name,
                            "Direction": trade["type"],
                            "Résultat": status,
                            "Prix Entrée": trade["entry"],
                            "Prix Sortie": round(close, 5)
                        })
                        del st.session_state["active_trades"][name]
                    else:
                        # LE SIGNAL EST FORCÉ À "EN COURS" POUR BLOQUER TELEGRAM
                        signal = "EN COURS ⏳"
                        comment = f"Trade déjà actif (TP: {trade['tp']} / SL: {trade['sl']})"
                
                if signal == "ATTENDRE" and comment == "-":                                
                    if score >= score_min:                                
                        comment = "Setup valide mais breakout non confirmé"                                
                    else:                                
                        comment = "Conditions insuffisantes"                                
                                
                factor = pip_factor(name)                                
                sl_pips = abs(close-sl)*factor if sl else "-"                                
                tp_pips = abs(tp-close)*factor if tp else "-"                                
                                
                results.append({                                
                    "Actif": name,                                
                    "Catégorie": category,                                
                    "Signal": signal,                                
                    "Fiabilité": reliability,                                
                    "Score": f"{score}%",                                
                    "Prix": round(close,2 if category=="CRYPTO" else 5),                                
                    "SL Prix": round(sl,2 if category=="CRYPTO" else 5) if sl else "-",                                
                    "SL Pips": round(sl_pips,1) if sl else "-",                                
                    "TP Prix": round(tp,2 if category=="CRYPTO" else 5) if tp else "-",                                
                    "TP Pips": round(tp_pips,1) if tp else "-",                                
                    "Commentaire": comment                                
                })                                
                                
                # ENVOI TELEGRAM : Uniquement si ACHAT ou VENTE (EN COURS est ignoré)
                if signal in ["ACHAT 🚀", "VENTE 🔻"]:
                    st.session_state["active_trades"][name] = {
                        "type": signal, 
                        "sl": round(sl, 5), 
                        "tp": round(tp, 5),
                        "entry": round(close, 5)
                    }
                    send_telegram_msg(                                
                        f"🦅 SIGNAL SNIPER V16.4.1\n{name} | {signal}\nFiabilité: {reliability} | Score: {score}%\nRR: {round(rr,2)}\nPrix: {close}\nSL: {sl}\nTP: {tp}\nCommentaire: {comment}"                
                    )                                
                                
            except:                                
                continue                                
                                
    return results                                
                                
# ─────────────────────────────────────────────                                
# AFFICHAGE                                
# ─────────────────────────────────────────────                                
st.title("🦅 Sniper V16.4.1 — Swing Forex + BTC PRO")                                
st.info("Version Haute Fréquence : SL ATR 1.5x | Suivi de Position Actif | RR Min 1.2")                                
                                
data = run_engine()                                
                                
if data:                                
    df = pd.DataFrame(data)                                
    st.dataframe(df, use_container_width=True)                                
else:                                
    st.warning("⏸ Aucun signal (hors horaires ou news actives)")

# Section Historique
st.markdown("---")
st.subheader("📜 Historique des Signaux Clôturés")
if st.session_state["trade_history"]:
    hist_df = pd.DataFrame(st.session_state["trade_history"]).sort_index(ascending=False)
    st.table(hist_df)
else:
    st.write("Aucun trade clôturé pour le moment.")
