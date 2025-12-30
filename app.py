import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import EMAIndicator, ADXIndicator
from ta.volatility import AverageTrueRange
import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
st.set_page_config(page_title="Sniper V15.5 - Pro Alerts", layout="wide")

# --- ACTUALISATION TOUTES LES 3 MINUTES (180 000 ms) ---
st_autorefresh(interval=180000, key="datarefresh")

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
def run_final_sniper():
    results = []
    all_tickers = [ticker for category in ASSETS.values() for ticker in category]
    
    try:
        data_m = yf.download(all_tickers, period="5d", interval="15m", group_by='ticker', progress=False)
        data_d = yf.download(all_tickers, period="150d", interval="1d", group_by='ticker', progress=False)
    except: return []

    for category, tickers in ASSETS.items():
        for ticker in tickers:
            try:
                if ticker not in data_m.columns.levels[0] or data_m[ticker].empty: continue
                df_m, df_d = data_m[ticker].dropna(), data_d[ticker].dropna()
                if len(df_m) < 30 or len(df_d) < 100: continue

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

                if adx_d < 18: note = "💤 RANGE DAILY"
                elif (box_h - box_l) > (atr_m * 3.0): note = "⏳ VOLATILITÉ HAUTE"
                else:
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
                        else: note = "⏳ Attente Confirmation"
                    else: note = "Momentum insuffisant"

                def f(x): return round(x, 5) if x < 2 else round(x, 2)
                results.append({
                    "Catégorie": category, "Actif": ticker.replace("=X","").replace("=F","").replace("^",""),
                    "SIGNAL": signal, "Score": f"{score}%", "Prix": f(p_close),
                    "Stop Loss": f(sl) if sl != 0 else "-", "Take Profit": f(tp) if tp != 0 else "-", "Note": note
                })
            except: continue
    return results

# --- RENDU ---
st.title("🦅 Sniper V15.5 - Dashboard Temps Réel")

data = run_final_sniper()
if data:
    df = pd.DataFrame(data)
    
    # --- MISE EN AVANT DES SIGNAUX (TOP PANEL) ---
    alerts = df[df['SIGNAL'].str.contains('ACHAT|VENTE')]
    if not alerts.empty:
        st.subheader("🔥 ALERTES DÉTECTÉES")
        st.dataframe(alerts.style.apply(lambda x: ['background-color: #1e8449; color: white' if 'ACHAT' in x.SIGNAL else 'background-color: #942d22; color: white' for i in x], axis=1))
        st.divider()

    # --- TABLEAU COMPLET ---
    st.subheader("📊 Surveillance Globale (Toutes les 3 min)")
    def style_full(row):
        color = '#1e8449' if 'ACHAT' in row.SIGNAL else ('#942d22' if 'VENTE' in row.SIGNAL else '')
        return [f'background-color: {color}; color: white' if color else '' for _ in row]
    
    st.table(df.style.apply(style_full, axis=1))
    st.caption(f"Dernière analyse : {datetime.datetime.now().strftime('%H:%M:%S')}")

else:
    st.error("Données Yahoo Finance indisponibles.")
